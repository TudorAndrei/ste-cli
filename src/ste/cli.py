"""Command interface for the ASD-STE100 checker."""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from collections.abc import Mapping
from contextlib import redirect_stderr, redirect_stdout
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import Annotated, TextIO

import typer
from typer._click.core import Context, ParameterSource
from typer.core import TyperCommand, TyperGroup, TyperOption

from ste import __version__, analyzer, baseline, config, dictionary, evaluation, report
from ste.checker import lint_document
from ste.document import parse
from ste.models import Options

STDIN_NAME = "(standard input)"
STARTER_CONFIG = """# The config of ste. Each key is optional. Run "ste schema" for all keys.

mode: flavored          # or strict: also report the low-confidence findings

rules: {}               # a severity for each rule: off, info, warning, or error
#  STE-3.6: info        # advice today, and a rule later

exclude: []             # path patterns from this directory
#  - "**/fixtures/**"

allow:                  # the technical words of this project (rule 1.6)
  nouns: []
  verbs: []

prefer: {}              # rule STE-1.11: one name for each item
#  "config file": ["settings file", "configuration file"]

presets: []             # software: the technical nouns of software

# min_confidence: 0.7   # remove each finding below this value
# fail_over: 2.5        # exit 1 when the score for each 100 words is higher
# warnings_as_errors: false
# baseline: .ste-baseline.json
"""
SKIPPED_DIRS = {
    "node_modules",
    "vendor",
    "dist",
    "build",
    "target",
    "bin",
    "obj",
    "out",
    "coverage",
    "__pycache__",
}
GENERATED_FILES = {
    "changelog",
    "change_log",
    "changes",
    "history",
    "news",
    "release-notes",
    "releasenotes",
    "release_notes",
}


def _boolean_args(params, ctx: Context, args: list[str], group: bool = False):
    """Keep explicit boolean values while Typer reads all other arguments."""
    options = {
        name: param for param in params if isinstance(param, TyperOption) for name in param.opts
    }
    converted: list[str] = []
    values: dict[str, bool] = {}
    at = 0
    while at < len(args):
        arg = args[at]
        if arg == "--" or (group and not arg.startswith("-")):
            converted.extend(args[at:])
            break
        name, sep, value = arg.partition("=")
        option = options.get(name)
        if option is not None and option.is_bool_flag and not option.is_eager:
            if option.name is not None:
                if sep and value.lower() not in {"true", "false", "1", "0", "t", "f"}:
                    raise typer.BadParameter(f"invalid boolean: {value}", ctx=ctx, param=option)
                values[option.name] = not sep or value.lower() in {"true", "1", "t"}
        else:
            converted.append(arg)
            # An option value can look like a flag. Leave it for Typer to read.
            if option is not None and not option.is_flag and not sep and at + 1 < len(args):
                at += 1
                converted.append(args[at])
        at += 1
    return converted, values


def _set_booleans(ctx: Context, values: dict[str, bool]) -> None:
    for name, value in values.items():
        ctx.params[name] = value
        ctx.set_parameter_source(name, ParameterSource.COMMANDLINE)


class SteCommand(TyperCommand):
    """Accept the existing --flag=true and --flag=false forms."""

    def parse_args(self, ctx: Context, args: list[str]) -> list[str]:
        converted, values = _boolean_args(self.params, ctx, args)
        rest = super().parse_args(ctx, converted)
        _set_booleans(ctx, values)
        return rest

    def invoke(self, ctx: Context):
        try:
            return super().invoke(ctx)
        except (OSError, ValueError) as err:
            raise typer.BadParameter(str(err), ctx=ctx) from err


class SteGroup(TyperGroup):
    """Apply the same boolean syntax to options before a subcommand."""

    def parse_args(self, ctx: Context, args: list[str]) -> list[str]:
        converted, values = _boolean_args(self.params, ctx, args, group=True)
        rest = super().parse_args(ctx, converted)
        _set_booleans(ctx, values)
        return rest


class OutputFormat(StrEnum):
    text = "text"
    json = "json"
    ndjson = "ndjson"
    sarif = "sarif"
    github = "github"


class SimpleFormat(StrEnum):
    text = "text"
    json = "json"


@dataclass
class Streams:
    stdin: TextIO
    stdout: TextIO
    stderr: TextIO


def streams(ctx: typer.Context) -> Streams:
    if isinstance(ctx.obj, Streams):
        return ctx.obj
    return Streams(sys.stdin, sys.stdout, sys.stderr)


@dataclass
class LintOptions:
    paths: list[str] = field(default_factory=list)
    format: str = "text"
    mode: str = ""
    fields: str = ""
    config: str = ""
    baseline: str = ""
    dict: str = ""
    preset: str = ""
    analyzer: str = ""
    summary: bool = False
    no_config: bool = False
    all: bool = False
    no_baseline: bool = False
    fail_on_new: bool = False
    warnings_as_errors: bool = False
    use_dict: bool = False
    analyze: bool = False
    dry_run: bool = False
    limit: int = 0
    max_words: int = 0
    fail_over: float = -1


@dataclass
class DictOptions:
    format: str = "text"
    out: str = ""
    dry_run: bool = False


@dataclass
class Project:
    directory: Path
    config_path: Path | None = None

    def resolve(self, path: str) -> str:
        return str(self.directory / path) if path else ""


def find_project(config_path: str = "", no_config: bool = False) -> Project:
    cwd = Path.cwd()
    if config_path and not no_config:
        path = Path(os.path.abspath(config_path))
        return Project(path.parent, path)
    for directory in (cwd, *cwd.parents):
        if not no_config and (found := config.find(directory)):
            return Project(directory, found)
        if (directory / ".git").exists():
            return Project(directory)
    return Project(cwd)


def repo_root(directory: Path) -> Path:
    return next((p for p in (directory, *directory.parents) if (p / ".git").exists()), directory)


def relative_to(directory: str | Path, path: str | Path) -> str:
    return os.path.relpath(os.path.abspath(path), os.path.abspath(directory)).replace("\\", "/")


def display_path(path: str) -> str:
    if not path or not os.path.isabs(path):
        return path
    relative = relative_to(Path.cwd(), path)
    return path if relative.startswith("..") else relative


def match_pattern(pattern: str, path: str) -> bool:
    if not pattern:
        return False
    if "**" in pattern:
        position = 0
        for n, part in enumerate(pattern.split("**")):
            part = part.strip("/")
            if not part:
                continue
            match = re.search(
                ("^" if n == 0 else r"(?:^|/)") + re.escape(part) + r"(?=/|$)", path[position:]
            )
            if not match:
                return False
            position += match.end()
        return True
    # A single star cannot cross a directory boundary.
    import fnmatch

    if len(pattern.split("/")) != len(path.split("/")):
        return False
    return all(
        fnmatch.fnmatchcase(s, p) for p, s in zip(pattern.split("/"), path.split("/"), strict=True)
    )


def matches_any(path: str | Path, root: str | Path, patterns: list[str]) -> bool:
    relative = relative_to(root, path)
    return any(
        match_pattern(p.removeprefix("./").replace("\\", "/"), relative)
        or match_pattern(p.removeprefix("./").replace("\\", "/"), Path(relative).name)
        for p in patterns
    )


def git_visible(directory: str) -> set[str] | None:
    try:
        process = subprocess.run(
            [
                "git",
                "-C",
                directory,
                "ls-files",
                "--cached",
                "--others",
                "--exclude-standard",
                "-z",
            ],
            capture_output=True,
            check=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return None
    return {
        os.path.abspath(os.path.join(directory, p))
        for p in os.fsdecode(process.stdout).split("\0")
        if p
    }


def text_files(path: str, all_files: bool, project_dir: Path, exclude: list[str]) -> list[str]:
    target = Path(path)
    target.stat()
    if not target.is_dir():
        return [] if matches_any(path, project_dir, exclude) else [path]
    visible = None if all_files else git_visible(path)
    files = []

    def raise_error(error: OSError) -> None:
        raise error

    for directory, dirs, names in os.walk(path, onerror=raise_error):
        if not all_files:
            dirs[:] = [d for d in dirs if not d.startswith(".") and d not in SKIPPED_DIRS]
        for name in names:
            file = os.path.normpath(os.path.join(directory, name))
            if Path(name).suffix not in (".md", ".markdown", ".txt"):
                continue
            if visible is not None and os.path.abspath(file) not in visible:
                continue
            if not all_files and Path(name).stem.lower() in GENERATED_FILES:
                continue
            if not matches_any(file, project_dir, exclude):
                files.append(file)
    if not files:
        raise ValueError(f"{path}: the directory has no Markdown or text files")
    return sorted(files)


def _write_plan(stream: TextIO, format: str, data: Mapping[str, object], text: str) -> None:
    stream.write(
        json.dumps(data, indent=2 if format == "json" else None, ensure_ascii=False) + "\n"
        if format in ("json", "ndjson")
        else text
    )


def _lint_one(path: str, source: str, options: Options) -> report.FileResult:
    doc = parse(source)
    return report.FileResult(
        path,
        doc.word_count(),
        [report.make_finding(path, source, d) for d in lint_document(doc, options)],
    )


def _baseline_key(path: str, file: str) -> str:
    return file if file == STDIN_NAME else relative_to(Path(path).parent, file)


def _run_lint(ns: LintOptions, stdin: TextIO, stdout: TextIO, stderr: TextIO, write: bool) -> int:
    fields = [f.strip() for f in ns.fields.split(",")] if ns.fields else []
    if unknown := set(fields) - set(report.FIELDS):
        raise ValueError(
            f"no field is named {', '.join(sorted(unknown))}. The fields are: {', '.join(report.FIELDS)}"
        )
    if ns.limit < 0:
        raise ValueError("--limit must not be less than 0")
    if ns.dry_run and not write:
        raise ValueError(
            "--dry-run applies only to the baseline command. The lint command writes no file."
        )
    if not ns.paths:
        if stdin.isatty():
            raise ValueError('give a file or a directory. Give "-" to read standard input.')
        ns.paths = ["-"]
    proj = find_project(ns.config, ns.no_config)
    cfg = config.load(proj.config_path)
    opts = cfg.options()
    if ns.mode:
        if ns.mode not in ("flavored", "strict"):
            raise ValueError(f'the mode "{ns.mode}" is not "flavored" or "strict"')
        opts.mode = ns.mode
    if ns.max_words:
        if ns.max_words < 0:
            raise ValueError("--max-words must not be less than 0")
        opts.max_words = ns.max_words
    if ns.warnings_as_errors:
        opts.warnings_as_errors = True
    if ns.preset:
        opts.allow_nouns.extend(config.preset(ns.preset))
    if ns.use_dict or cfg.dictionary:
        opts.dictionary = dictionary.load(ns.dict or None)
        if opts.dictionary is None:
            raise ValueError('there is no dictionary index. Run "ste dict import <file>" first.')
    client = None
    if ns.analyze or ns.analyzer or cfg.analyzer:
        try:
            client = analyzer.create(ns.analyzer or None)
        except (ValueError, RuntimeError, OSError) as err:
            raise ValueError(
                f'the analyzer did not start.\n{err}\nRun "ste analyzer" to see what it needs.'
            ) from err
        opts.syntax = client
    try:
        results = []
        for path in ns.paths:
            if path == "-":
                results.append(_lint_one(STDIN_NAME, stdin.read(), opts))
            else:
                for file in text_files(path, ns.all, proj.directory, cfg.exclude):
                    with open(file, encoding="utf-8", newline="") as stream:
                        results.append(_lint_one(file, stream.read(), opts))
    finally:
        if client is not None:
            client.close()
    base_path = ns.baseline or proj.resolve(cfg.baseline)
    if not base_path:
        default = proj.resolve(baseline.DEFAULT_NAME)
        if Path(default).is_file() or write:
            base_path = default
    shown = display_path(base_path)
    if write:
        entries = [
            baseline.Result(
                _baseline_key(base_path, r.path),
                [(str(f.data["rule_id"]), str(f.data["text"])) for f in r.findings],
            )
            for r in results
        ]
        merge = baseline.plan(base_path, entries)
        total = sum(len(r.findings) for r in results)
        plan: dict[str, object] = {
            "action": "baseline",
            "dry_run": ns.dry_run,
            "path": shown,
            "findings": total,
            "files": len(results),
            "kept": merge.kept,
            "removed": merge.removed,
        }
        extra = (
            f"It keeps {merge.kept} accepted findings of the files that this run did not read.\n"
            if merge.kept
            else ""
        ) + (
            f"It removes {merge.removed} accepted findings of the files that do not exist now.\n"
            if merge.removed
            else ""
        )
        if ns.dry_run:
            plan["exists"] = Path(base_path).is_file()
            text = (
                f"A real run writes {shown} with {total} findings of {len(results)} files.\n{extra}"
            )
        else:
            baseline.save(
                base_path,
                entries,
                datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z"),
            )
            text = f"{shown} holds {total} findings of {len(results)} files.\n{extra}The tool now reports only a new finding. Remove the file to report all.\n"
        _write_plan(stdout, ns.format, plan, text)
        return 0
    accepted = stale = 0
    if base_path and not ns.no_baseline:
        accepted_set = baseline.load(base_path)
        read = set()
        for result in results:
            file = _baseline_key(base_path, result.path)
            read.add(file)
            kept = []
            for f in result.findings:
                if accepted_set.take(file, str(f.data["rule_id"]), str(f.data["text"])):
                    accepted += 1
                else:
                    kept.append(f)
            result.findings = kept
        stale = accepted_set.stale(read)
    schema = _schema()
    if ns.format in ("sarif", "github"):
        root = repo_root(proj.directory)
        for result in results:
            if result.path == STDIN_NAME:
                continue
            relative = relative_to(root, result.path)
            if relative.startswith("../"):
                continue
            result.path = relative
            for f in result.findings:
                f.data["file"] = relative
    rep = report.Report(opts.mode, results, accepted, stale)
    report.write(
        stdout,
        rep,
        report.Options(
            format=ns.format,
            limit=ns.limit,
            fields=fields,
            summary_only=ns.summary,
            rules=schema["rules"],
            tool_version=__version__,
        ),
    )
    if ns.format == "text":
        if accepted:
            stdout.write(
                f"{accepted} findings are in the baseline {shown}, thus this report does not show them.\n"
            )
        if stale:
            stdout.write(
                f'{stale} accepted findings are not in the text now. Run "ste baseline" to record the lower number.\n'
            )
    summary = rep.summary()
    if opts.warnings_as_errors and summary["errors"]:
        stderr.write(f"ste: {summary['errors']} findings have the error severity\n")
        return 1
    if ns.fail_on_new and summary["findings"]:
        stderr.write(f"ste: {summary['findings']} findings are not in the baseline\n")
        return 1
    fail_over = cfg.fail_over if ns.fail_over < 0 else ns.fail_over
    if fail_over >= 0 and summary["score"] > fail_over:
        stderr.write(
            f"ste: the score {summary['score']:.2f} is more than the limit {fail_over:.2f}\n"
        )
        return 1
    return 0


def _schema() -> dict:
    data = json.loads(Path(__file__).with_name("schema.json").read_text(encoding="utf-8"))
    data["version"] = __version__
    return data


def _run_init(format: str, dry_run: bool, force: bool, stdout: TextIO) -> int:
    path = Path(config.DEFAULT_NAMES[0])
    if (existing := config.find(".")) and not force:
        raise ValueError(f"{existing} exists. Give --force to write {path} all the same.")
    plan = {"action": "init", "dry_run": dry_run, "path": str(path), "exists": path.is_file()}
    if dry_run:
        text = f"A real run writes {path}.\n"
    else:
        path.write_text(STARTER_CONFIG, encoding="utf-8")
        text = f'{path} holds the start config. Run "ste lint --summary ." to see the size of the problem.\n'
    _write_plan(stdout, format, plan, text)
    return 0


def _run_dict(command: str, source: str, ns: DictOptions, stdout: TextIO) -> int:
    path = Path(ns.out or dictionary.default_path())
    if command == "path":
        _write_plan(stdout, ns.format, {"path": str(path)}, f"{path}\n")
    elif command == "remove":
        exists = path.is_file()
        plan: dict[str, object] = {
            "action": "dict remove",
            "dry_run": ns.dry_run,
            "path": str(path),
        }
        if ns.dry_run:
            plan["exists"] = exists
            text = f"A real run deletes {path}.\n"
        else:
            path.unlink(missing_ok=True)
            plan["removed"] = exists
            text = "The index is removed. The term rule now uses only its hand-written list.\n"
        _write_plan(stdout, ns.format, plan, text)
    elif command == "info":
        index = dictionary.load(path)
        plan = {"path": str(path), "present": index is not None}
        if index is None:
            text = f'There is no index at {path}.\nRule STE-1.1 uses its hand-written list of 27 words and 11 word groups.\nRun "ste dict import <file>" to make the index.\n'
        else:
            stats = index.stats()
            plan.update({"source": index.source, **stats})
            text = f"index:        {path}\nsource:       {index.source}\nwords:        {stats['words']}\napproved:     {stats['approved']}\nnot approved: {stats['unapproved']}\nalternatives: {stats['alternatives']}\n"
        _write_plan(stdout, ns.format, plan, text)
    else:
        if Path(source).suffix.lower() == ".pdf":
            raise ValueError(
                f"{source} is a PDF. This tool reads text, thus make the Markdown first:\n  npx -y @firecrawl/anydoc@0.2.4 {source} -o ste100.md\n  ste dict import ste100.md"
            )
        index = dictionary.parse(Path(source).read_text(encoding="utf-8"), Path(source).name)
        stats = index.stats()
        plan = {
            "action": "dict import",
            "dry_run": ns.dry_run,
            "source": source,
            "path": str(path),
            **stats,
        }
        if ns.dry_run:
            plan["exists"] = path.is_file()
            text = f"A real run writes {path} with {stats['words']} words.\n"
        else:
            index.save(path)
            text = f'{path} holds {stats["words"]} words: {stats["approved"]} approved and {stats["unapproved"]} not approved, with {stats["alternatives"]} alternatives.\n\nThe index is for you only: do not commit it.\nThe dictionary is off by default. Give --use-dict, or put "dictionary: true"\nin your config, to make rule STE-1.1 use it.\n'
        _write_plan(stdout, ns.format, plan, text)
    return 0


def _run_analyzer(format: str, stdout: TextIO) -> int:
    status = analyzer.check()
    if status["ready"]:
        text = f'The analyzer is ready.\n  python: {status["python"]}\n  script: {status["script"]}\n\nRun "ste lint --analyze docs/" to use it.\nIt makes rule STE-3.6 more exact, and it is never necessary.\n'
    else:
        text = f"The analyzer cannot run: {status['problem']}\n"
        if status["fix"]:
            text += "\nTo make it work:\n" + "".join(f"  {fix}\n" for fix in status["fix"])
        text += "\nThe analyzer is optional. Each rule works without it.\n"
    _write_plan(stdout, format, status, text)
    return 0


def _run_eval(
    directory: str, format: str, fail_under: float, stdout: TextIO, stderr: TextIO
) -> int:
    data = evaluation.run(directory)
    if format == "json":
        stdout.write(json.dumps(data, indent=2) + "\n")
    else:
        evaluation.write_text(stdout, data)
    totals = data["totals"]
    if fail_under >= 0 and (totals["precision"] < fail_under or totals["recall"] < fail_under):
        stderr.write(
            f"ste: precision {totals['precision']:.2f} and recall {totals['recall']:.2f}, and the limit is {fail_under:.2f}\n"
        )
        return 1
    return 0


app = typer.Typer(
    name="ste",
    help="Find ASD-STE100 violations in Markdown and plain text.",
    add_completion=False,
    no_args_is_help=True,
    pretty_exceptions_enable=False,
    context_settings={"help_option_names": ["-h", "--help"]},
)
dict_app = typer.Typer(
    cls=SteGroup,
    help="Manage a local dictionary index.",
    no_args_is_help=True,
    pretty_exceptions_enable=False,
)
app.add_typer(dict_app, name="dict")


def _version_option(value: bool) -> None:
    if value:
        typer.echo(f"ste {__version__}")
        raise typer.Exit()


@app.callback()
def root(
    version: Annotated[
        bool,
        typer.Option(
            "--version", "-v", callback=_version_option, is_eager=True, help="Print the version."
        ),
    ] = False,
) -> None:
    """Findings alone do not change the exit code. Give a gate to fail a run."""


@app.command("lint", cls=SteCommand, help="Check files, directories, or standard input.")
@app.command("baseline", cls=SteCommand, help="Accept the findings of today.")
def lint_command(
    ctx: typer.Context,
    paths: Annotated[
        list[str] | None, typer.Argument(help="Files, directories, or - for standard input.")
    ] = None,
    format: Annotated[
        OutputFormat, typer.Option("--format", help="Output format.")
    ] = OutputFormat.text,
    mode: Annotated[str, typer.Option("--mode", help="flavored or strict.")] = "",
    fields: Annotated[
        str, typer.Option("--fields", help="Finding fields separated by a comma.")
    ] = "",
    config: Annotated[str, typer.Option("--config", help="Path of the configuration file.")] = "",
    baseline: Annotated[
        str, typer.Option("--baseline", help="Path of the accepted findings.")
    ] = "",
    dictionary: Annotated[str, typer.Option("--dict", help="Path of the dictionary index.")] = "",
    preset: Annotated[
        str, typer.Option("--preset", help="Technical nouns of a subject field.")
    ] = "",
    analyzer: Annotated[
        str, typer.Option("--analyzer", help="Command of a different analyzer.")
    ] = "",
    summary: Annotated[bool, typer.Option("--summary", help="Give only the summary.")] = False,
    no_config: Annotated[
        bool, typer.Option("--no-config", help="Do not read a configuration file.")
    ] = False,
    all: Annotated[bool, typer.Option("--all", help="Read files that git ignores.")] = False,
    no_baseline: Annotated[
        bool, typer.Option("--no-baseline", help="Report all findings.")
    ] = False,
    fail_on_new: Annotated[
        bool, typer.Option("--fail-on-new", help="Exit 1 for a new finding.")
    ] = False,
    warnings_as_errors: Annotated[
        bool, typer.Option("--warnings-as-errors", help="Make warnings errors.")
    ] = False,
    use_dict: Annotated[
        bool, typer.Option("--use-dict", help="Use the imported dictionary.")
    ] = False,
    analyze: Annotated[bool, typer.Option("--analyze", help="Use the grammar analyzer.")] = False,
    dry_run: Annotated[
        bool, typer.Option("--dry-run", help="Show the baseline plan without writing.")
    ] = False,
    limit: Annotated[
        int, typer.Option("--limit", min=0, help="Maximum findings to show. 0 gives all.")
    ] = 0,
    max_words: Annotated[
        int, typer.Option("--max-words", min=0, help="Replace the sentence word limit.")
    ] = 0,
    fail_over: Annotated[
        float, typer.Option("--fail-over", help="Maximum findings for each 100 words.")
    ] = -1,
) -> None:
    io = streams(ctx)
    opts = LintOptions(
        paths=paths or [],
        format=format.value,
        mode=mode,
        fields=fields,
        config=config,
        baseline=baseline,
        dict=dictionary,
        preset=preset,
        analyzer=analyzer,
        summary=summary,
        no_config=no_config,
        all=all,
        no_baseline=no_baseline,
        fail_on_new=fail_on_new,
        warnings_as_errors=warnings_as_errors,
        use_dict=use_dict,
        analyze=analyze,
        dry_run=dry_run,
        limit=limit,
        max_words=max_words,
        fail_over=fail_over,
    )
    raise typer.Exit(_run_lint(opts, io.stdin, io.stdout, io.stderr, ctx.info_name == "baseline"))


@app.command("init", cls=SteCommand)
def init_command(
    ctx: typer.Context,
    format: Annotated[
        SimpleFormat, typer.Option("--format", help="Output format.")
    ] = SimpleFormat.text,
    dry_run: Annotated[
        bool, typer.Option("--dry-run", help="Show the plan without writing.")
    ] = False,
    force: Annotated[
        bool, typer.Option("--force", help="Replace an existing configuration.")
    ] = False,
) -> None:
    """Write a start configuration in .ste.yml."""
    raise typer.Exit(_run_init(format.value, dry_run, force, streams(ctx).stdout))


@app.command("analyzer", cls=SteCommand)
def analyzer_command(
    ctx: typer.Context,
    format: Annotated[
        SimpleFormat, typer.Option("--format", help="Output format.")
    ] = SimpleFormat.text,
) -> None:
    """Show the grammar analyzer and what it needs."""
    raise typer.Exit(_run_analyzer(format.value, streams(ctx).stdout))


@app.command("eval", cls=SteCommand)
def eval_command(
    ctx: typer.Context,
    directory: Annotated[str, typer.Argument(help="Directory of the labeled corpus.")] = "testdata",
    format: Annotated[
        SimpleFormat, typer.Option("--format", help="Output format.")
    ] = SimpleFormat.text,
    fail_under: Annotated[
        float, typer.Option("--fail-under", help="Minimum precision and recall.")
    ] = -1,
) -> None:
    """Measure rules against a labeled corpus."""
    io = streams(ctx)
    raise typer.Exit(_run_eval(directory, format.value, fail_under, io.stdout, io.stderr))


@app.command("schema", cls=SteCommand)
def schema_command(ctx: typer.Context) -> None:
    """Print the command interface as JSON."""
    streams(ctx).stdout.write(json.dumps(_schema(), indent=2) + "\n")


@app.command("version", cls=SteCommand)
def version_command(ctx: typer.Context) -> None:
    """Print the version."""
    streams(ctx).stdout.write(f"ste {__version__}\n")


@app.command("help", hidden=True)
def help_command(ctx: typer.Context) -> None:
    """Show the command help."""
    assert ctx.parent is not None
    streams(ctx).stdout.write(ctx.parent.get_help() + "\n")


@dict_app.callback()
def dictionary_group(
    ctx: typer.Context,
    format: Annotated[
        SimpleFormat, typer.Option("--format", help="Output format.")
    ] = SimpleFormat.text,
    out: Annotated[str, typer.Option("--out", help="Path of the dictionary index.")] = "",
    dry_run: Annotated[
        bool, typer.Option("--dry-run", help="Show the plan without a change.")
    ] = False,
) -> None:
    ctx.meta["dictionary_options"] = DictOptions(format.value, out, dry_run)


def _dict_options(ctx: typer.Context, format: SimpleFormat, out: str, dry_run: bool) -> DictOptions:
    options = ctx.meta.get("dictionary_options", DictOptions())
    changes: dict[str, object] = {}
    for name, value in (("format", format.value), ("out", out), ("dry_run", dry_run)):
        if ctx.get_parameter_source(name) == ParameterSource.COMMANDLINE:
            changes[name] = value
    return replace(options, **changes)


@dict_app.command("import", cls=SteCommand)
def dict_import(
    ctx: typer.Context,
    source: Annotated[str, typer.Argument(help="The user's dictionary in Markdown or plain text.")],
    format: Annotated[
        SimpleFormat, typer.Option("--format", help="Output format.")
    ] = SimpleFormat.text,
    out: Annotated[str, typer.Option("--out", help="Path of the dictionary index.")] = "",
    dry_run: Annotated[
        bool, typer.Option("--dry-run", help="Show the plan without writing.")
    ] = False,
) -> None:
    """Read the user's dictionary and write an index."""
    raise typer.Exit(
        _run_dict("import", source, _dict_options(ctx, format, out, dry_run), streams(ctx).stdout)
    )


@dict_app.command("path", cls=SteCommand, help="Print the path of the index.")
@dict_app.command("info", cls=SteCommand, help="Show the index of this user.")
@dict_app.command("remove", cls=SteCommand, help="Delete the index.")
def dict_status(
    ctx: typer.Context,
    format: Annotated[
        SimpleFormat, typer.Option("--format", help="Output format.")
    ] = SimpleFormat.text,
    out: Annotated[str, typer.Option("--out", help="Path of the dictionary index.")] = "",
    dry_run: Annotated[
        bool, typer.Option("--dry-run", help="Show the plan without a change.")
    ] = False,
) -> None:
    assert ctx.info_name is not None
    raise typer.Exit(
        _run_dict(ctx.info_name, "", _dict_options(ctx, format, out, dry_run), streams(ctx).stdout)
    )


def run(args: list[str], stdin: TextIO, stdout: TextIO, stderr: TextIO) -> int:
    try:
        with redirect_stdout(stdout), redirect_stderr(stderr):
            result = app(
                args=args,
                prog_name="ste",
                standalone_mode=False,
                obj=Streams(stdin, stdout, stderr),
            )
        return int(result or 0)
    except typer.TyperException as err:
        stderr.write(f"ste: {err.format_message()}\n")
        return err.exit_code
    except (OSError, ValueError) as err:
        stderr.write(f"ste: {err}\n")
        return 2
    except typer.Exit as err:
        return err.exit_code


def main() -> int:
    try:
        return run(sys.argv[1:], sys.stdin, sys.stdout, sys.stderr)
    except BrokenPipeError:
        return 0
