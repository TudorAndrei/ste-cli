# Copyright (c) 2026 Tudor Andrei Dumitrascu
"""Command interface for the ASD-STE100 checker."""

from __future__ import annotations

import fnmatch
import json
import os
import re
import shutil
import subprocess
import sys
from contextlib import redirect_stderr, redirect_stdout
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import TYPE_CHECKING, Annotated, TextIO

import typer
from typer._click.core import Context, ParameterSource
from typer.core import TyperCommand, TyperGroup, TyperOption

from ste import __version__, analyzer, baseline, config, dictionary, evaluation, report
from ste.checker import lint_document
from ste.document import parse

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

    from typer._click.core import Parameter

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


def _boolean_args(
    params: Sequence[Parameter],
    ctx: Context,
    args: list[str],
    *,
    group: bool = False,
) -> tuple[list[str], dict[str, bool]]:
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
                    msg = f"invalid boolean: {value}"
                    raise typer.BadParameter(msg, ctx=ctx, param=option)
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
        """Read Typer arguments and preserve explicit boolean flag values."""
        converted, values = _boolean_args(self.params, ctx, args)
        rest = super().parse_args(ctx, converted)
        _set_booleans(ctx, values)
        return rest

    def invoke(self, ctx: Context) -> object:
        """Run the command and convert input failures to usage errors."""
        try:
            return super().invoke(ctx)
        except (OSError, ValueError) as err:
            raise typer.BadParameter(str(err), ctx=ctx) from err


class SteGroup(TyperGroup):
    """Apply the same boolean syntax to options before a subcommand."""

    def parse_args(self, ctx: Context, args: list[str]) -> list[str]:
        """Read Typer arguments and preserve explicit boolean flag values."""
        converted, values = _boolean_args(self.params, ctx, args, group=True)
        rest = super().parse_args(ctx, converted)
        _set_booleans(ctx, values)
        return rest


class OutputFormat(StrEnum):
    """List the report formats accepted by the lint commands."""

    text = "text"
    json = "json"
    ndjson = "ndjson"
    sarif = "sarif"
    github = "github"


class SimpleFormat(StrEnum):
    """List formats accepted by status and data commands."""

    text = "text"
    json = "json"


@dataclass
class Streams:
    """Hold the input and output streams for one command."""

    stdin: TextIO
    stdout: TextIO
    stderr: TextIO


def streams(ctx: typer.Context) -> Streams:
    """Get the streams bound to the current invocation."""
    if isinstance(ctx.obj, Streams):
        return ctx.obj
    return Streams(sys.stdin, sys.stdout, sys.stderr)


@dataclass
class LintOptions:
    """Hold the parsed lint command options."""

    paths: list[str] = field(default_factory=list)
    output_format: str = "text"
    mode: str = ""
    fields: str = ""
    config: str = ""
    baseline: str = ""
    dict: str = ""
    preset: str = ""
    analyzer: str = ""
    summary: bool = False
    no_config: bool = False
    read_all: bool = False
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
    """Hold dictionary options shared with the subcommands."""

    output_format: str = "text"
    out: str = ""
    dry_run: bool = False


@dataclass
class Project:
    """Resolve configuration paths from the project directory."""

    directory: Path
    config_path: Path | None = None

    def resolve(self, path: str) -> str:
        """Resolve a nonempty path from the project directory."""
        return str(self.directory / path) if path else ""


def _absolute(path: str | Path) -> Path:
    return Path(os.path.normpath(path)).absolute()


def find_project(config_path: str = "", *, no_config: bool = False) -> Project:
    """Find the project directory and its optional configuration."""
    cwd = Path.cwd()
    if config_path and not no_config:
        path = Path(_absolute(config_path))
        return Project(path.parent, path)
    for directory in (cwd, *cwd.parents):
        if not no_config and (found := config.find(directory)):
            return Project(directory, found)
        if (directory / ".git").exists():
            return Project(directory)
    return Project(cwd)


def repo_root(directory: Path) -> Path:
    """Find the Git root containing the given directory."""
    return next((p for p in (directory, *directory.parents) if (p / ".git").exists()), directory)


def relative_to(directory: str | Path, path: str | Path) -> str:
    """Get a portable relative path without changing file identity."""
    return os.path.relpath(_absolute(path), _absolute(directory)).replace("\\", "/")


def display_path(path: str) -> str:
    """Shorten an absolute path when it is inside the current directory."""
    if not path or not Path(path).is_absolute():
        return path
    relative = relative_to(Path.cwd(), path)
    return path if relative.startswith("..") else relative


def match_pattern(pattern: str, path: str) -> bool:
    """Match a project exclusion pattern against a path."""
    if not pattern:
        return False
    if "**" in pattern:
        position = 0
        for n, segment in enumerate(pattern.split("**")):
            part = segment.strip("/")
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
    if len(pattern.split("/")) != len(path.split("/")):
        return False
    return all(
        fnmatch.fnmatchcase(s, p) for p, s in zip(pattern.split("/"), path.split("/"), strict=True)
    )


def matches_any(path: str | Path, root: str | Path, patterns: list[str]) -> bool:
    """Check a file against all project exclusion patterns."""
    relative = relative_to(root, path)
    return any(
        match_pattern(p.removeprefix("./").replace("\\", "/"), relative)
        or match_pattern(p.removeprefix("./").replace("\\", "/"), Path(relative).name)
        for p in patterns
    )


def git_visible(directory: str) -> set[str] | None:
    """Get the files visible to Git, or defer when Git is unavailable."""
    git = shutil.which("git")
    if git is None:
        return None
    try:
        process = subprocess.run(  # noqa: S603 - Fixed git executable; paths are separate arguments.
            [
                git,
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
    except OSError, subprocess.CalledProcessError:
        return None
    return {
        str(_absolute(Path(directory) / p)) for p in os.fsdecode(process.stdout).split("\0") if p
    }


def _include_file(file: str, visible: set[str] | None, *, all_files: bool) -> bool:
    path = Path(file)
    if path.suffix not in (".md", ".markdown", ".txt"):
        return False
    if visible is not None and str(_absolute(file)) not in visible:
        return False
    return all_files or path.stem.lower() not in GENERATED_FILES


def text_files(path: str, project_dir: Path, exclude: list[str], *, all_files: bool) -> list[str]:
    """Collect permitted Markdown and text files in path order."""
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
            file = os.path.normpath(Path(directory) / name)
            if _include_file(file, visible, all_files=all_files) and not matches_any(
                file, project_dir, exclude
            ):
                files.append(file)
    if not files:
        msg = f"{path}: the directory has no Markdown or text files"
        raise ValueError(msg)
    return sorted(files)


def _write_plan(stream: TextIO, output_format: str, data: Mapping[str, object], text: str) -> None:
    stream.write(
        json.dumps(data, indent=2 if output_format == "json" else None, ensure_ascii=False) + "\n"
        if output_format in ("json", "ndjson")
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


def _validate_lint(ns: LintOptions, stdin: TextIO, *, write: bool) -> list[str]:
    fields = [f.strip() for f in ns.fields.split(",")] if ns.fields else []
    if unknown := set(fields) - set(report.FIELDS):
        msg = (
            "no field is named "
            f"{', '.join(sorted(unknown))}"
            ". The fields are: "
            f"{', '.join(report.FIELDS)}"
        )
        raise ValueError(msg)
    if ns.limit < 0:
        msg = "--limit must not be less than 0"
        raise ValueError(msg)
    if ns.dry_run and not write:
        msg = "--dry-run applies only to the baseline command. The lint command writes no file."
        raise ValueError(msg)
    if not ns.paths:
        if stdin.isatty():
            msg = 'give a file or a directory. Give "-" to read standard input.'
            raise ValueError(msg)
        ns.paths = ["-"]
    return fields


def _lint_options(ns: LintOptions, cfg: config.Config) -> Options:
    opts = cfg.options()
    if ns.mode:
        if ns.mode not in ("flavored", "strict"):
            msg = f'the mode "{ns.mode}" is not "flavored" or "strict"'
            raise ValueError(msg)
        opts.mode = ns.mode
    if ns.max_words:
        if ns.max_words < 0:
            msg = "--max-words must not be less than 0"
            raise ValueError(msg)
        opts.max_words = ns.max_words
    if ns.warnings_as_errors:
        opts.warnings_as_errors = True
    if ns.preset:
        opts.allow_nouns.extend(config.preset(ns.preset))
    if ns.use_dict or cfg.dictionary:
        opts.dictionary = dictionary.load(ns.dict or None)
        if opts.dictionary is None:
            msg = 'there is no dictionary index. Run "ste dict import <file>" first.'
            raise ValueError(msg)
    return opts


def _read_lint(
    ns: LintOptions, proj: Project, cfg: config.Config, opts: Options, stdin: TextIO
) -> list[report.FileResult]:
    client = None
    if ns.analyze or ns.analyzer or cfg.analyzer:
        try:
            client = analyzer.create(ns.analyzer or None)
        except (ValueError, RuntimeError, OSError) as err:
            msg = f'the analyzer did not start.\n{err}\nRun "ste analyzer" to see what it needs.'
            raise ValueError(msg) from err
        opts.syntax = client
    try:
        results = []
        for path in ns.paths:
            if path == "-":
                results.append(_lint_one(STDIN_NAME, stdin.read(), opts))
            else:
                for file in text_files(path, proj.directory, cfg.exclude, all_files=ns.read_all):
                    with Path(file).open(encoding="utf-8", newline="") as stream:
                        results.append(_lint_one(file, stream.read(), opts))
    finally:
        if client is not None:
            client.close()
    return results


def _write_baseline(
    ns: LintOptions, base_path: str, results: list[report.FileResult], stdout: TextIO
) -> int:
    shown = display_path(base_path)
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
        text = f"A real run writes {shown} with {total} findings of {len(results)} files.\n{extra}"
    else:
        baseline.save(
            base_path,
            entries,
            datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z"),
        )
        text = (
            f"{shown}"
            " holds "
            f"{total}"
            " findings of "
            f"{len(results)}"
            " files.\n"
            f"{extra}"
            "The tool now reports only a new finding. Remove the file to report "
            "all.\n"
        )
    _write_plan(stdout, ns.output_format, plan, text)
    return 0


def _apply_baseline(base_path: str, results: list[report.FileResult]) -> tuple[int, int]:
    accepted = 0
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
    return accepted, stale


def _host_paths(project_dir: Path, results: list[report.FileResult]) -> None:
    root = repo_root(project_dir)
    for result in results:
        if result.path == STDIN_NAME:
            continue
        relative = relative_to(root, result.path)
        if relative.startswith("../"):
            continue
        result.path = relative
        for f in result.findings:
            f.data["file"] = relative


def _lint_report(
    ns: LintOptions, rep: report.Report, base_path: str, stdout: TextIO, fields: list[str]
) -> None:
    shown = display_path(base_path)
    accepted, stale = rep.accepted, rep.stale
    report.write(
        stdout,
        rep,
        report.Options(
            format=ns.output_format,
            limit=ns.limit,
            fields=fields,
            summary_only=ns.summary,
            rules=_schema()["rules"],
            tool_version=__version__,
        ),
    )
    if ns.output_format == "text":
        if accepted:
            stdout.write(
                f"{accepted}"
                " findings are in the baseline "
                f"{shown}"
                ", thus this report does not show them.\n"
            )
        if stale:
            stdout.write(
                f"{stale}"
                ' accepted findings are not in the text now. Run "ste baseline" to '
                "record the lower number.\n"
            )


def _lint_gate(
    ns: LintOptions, cfg: config.Config, rep: report.Report, opts: Options, stderr: TextIO
) -> int:
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


def _run_lint(ns: LintOptions, io: Streams, *, write: bool) -> int:
    fields = _validate_lint(ns, io.stdin, write=write)
    proj = find_project(ns.config, no_config=ns.no_config)
    cfg = config.load(proj.config_path)
    opts = _lint_options(ns, cfg)
    results = _read_lint(ns, proj, cfg, opts, io.stdin)
    base_path = ns.baseline or proj.resolve(cfg.baseline)
    if not base_path:
        default = proj.resolve(baseline.DEFAULT_NAME)
        if Path(default).is_file() or write:
            base_path = default
    if write:
        return _write_baseline(ns, base_path, results, io.stdout)
    accepted, stale = (
        _apply_baseline(base_path, results) if base_path and not ns.no_baseline else (0, 0)
    )
    if ns.output_format in ("sarif", "github"):
        _host_paths(proj.directory, results)
    rep = report.Report(opts.mode, results, accepted, stale)
    _lint_report(ns, rep, base_path, io.stdout, fields)
    return _lint_gate(ns, cfg, rep, opts, io.stderr)


def _schema() -> dict:
    data = json.loads(Path(__file__).with_name("schema.json").read_text(encoding="utf-8"))
    data["version"] = __version__
    return data


def _run_init(output_format: str, stdout: TextIO, *, dry_run: bool, force: bool) -> int:
    path = Path(config.DEFAULT_NAMES[0])
    if (existing := config.find(".")) and not force:
        msg = f"{existing} exists. Give --force to write {path} all the same."
        raise ValueError(msg)
    plan = {"action": "init", "dry_run": dry_run, "path": str(path), "exists": path.is_file()}
    if dry_run:
        text = f"A real run writes {path}.\n"
    else:
        path.write_text(STARTER_CONFIG, encoding="utf-8")
        text = (
            f"{path}"
            ' holds the start config. Run "ste lint --summary ." to see the size '
            "of the problem.\n"
        )
    _write_plan(stdout, output_format, plan, text)
    return 0


def _run_dict(command: str, source: str, ns: DictOptions, stdout: TextIO) -> int:
    path = Path(ns.out or dictionary.default_path())
    if command == "path":
        _write_plan(stdout, ns.output_format, {"path": str(path)}, f"{path}\n")
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
        _write_plan(stdout, ns.output_format, plan, text)
    elif command == "info":
        index = dictionary.load(path)
        plan = {"path": str(path), "present": index is not None}
        if index is None:
            text = (
                "There is no index at "
                f"{path}"
                ".\nRule STE-1.1 uses its hand-written list of 27 words and 11 word "
                'groups.\nRun "ste dict import <file>" to make the index.\n'
            )
        else:
            stats = index.stats()
            plan.update({"source": index.source, **stats})
            text = (
                "index:        "
                f"{path}"
                "\nsource:       "
                f"{index.source}"
                "\nwords:        "
                f"{stats['words']}"
                "\napproved:     "
                f"{stats['approved']}"
                "\nnot approved: "
                f"{stats['unapproved']}"
                "\nalternatives: "
                f"{stats['alternatives']}"
                "\n"
            )
        _write_plan(stdout, ns.output_format, plan, text)
    else:
        if Path(source).suffix.lower() == ".pdf":
            msg = (
                f"{source}"
                " is a PDF. This tool reads text, thus make the Markdown first:\n  npx"
                " -y @firecrawl/anydoc@0.2.4 "
                f"{source}"
                " -o ste100.md\n  ste dict import ste100.md"
            )
            raise ValueError(msg)
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
            text = (
                f"{path}"
                " holds "
                f"{stats['words']}"
                " words: "
                f"{stats['approved']}"
                " approved and "
                f"{stats['unapproved']}"
                " not approved, with "
                f"{stats['alternatives']}"
                " alternatives.\n\nThe index is for you only: do not commit it.\nThe "
                'dictionary is off by default. Give --use-dict, or put "dictionary: '
                'true"\nin your config, to make rule STE-1.1 use it.\n'
            )
        _write_plan(stdout, ns.output_format, plan, text)
    return 0


def _run_analyzer(output_format: str, stdout: TextIO) -> int:
    status = analyzer.check()
    if status["ready"]:
        text = (
            "The analyzer is ready.\n  python: "
            f"{status['python']}"
            "\n  script: "
            f"{status['script']}"
            '\n\nRun "ste lint --analyze docs/" to use it.\nIt makes rule STE-3.6 '
            "more exact, and it is never necessary.\n"
        )
    else:
        text = f"The analyzer cannot run: {status['problem']}\n"
        if status["fix"]:
            text += "\nTo make it work:\n" + "".join(f"  {fix}\n" for fix in status["fix"])
        text += "\nThe analyzer is optional. Each rule works without it.\n"
    _write_plan(stdout, output_format, status, text)
    return 0


def _run_eval(
    directory: str, output_format: str, fail_under: float, stdout: TextIO, stderr: TextIO
) -> int:
    data = evaluation.run(directory)
    if output_format == "json":
        stdout.write(json.dumps(data, indent=2) + "\n")
    else:
        evaluation.write_text(stdout, data)
    totals = data["totals"]
    if fail_under >= 0 and (totals["precision"] < fail_under or totals["recall"] < fail_under):
        stderr.write(
            f"ste: precision {totals['precision']:.2f} and recall {totals['recall']:.2f}, "
            f"and the limit is {fail_under:.2f}\n"
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


def _version_option(*, value: bool) -> None:
    if value:
        typer.echo(f"ste {__version__}")
        raise typer.Exit


@app.callback()
def root(
    *,
    version: Annotated[
        bool,
        typer.Option(
            "--version", "-v", callback=_version_option, is_eager=True, help="Print the version."
        ),
    ] = False,
) -> None:
    """Select a command or print the version before it runs."""


@app.command("lint", cls=SteCommand, help="Check files, directories, or standard input.")
@app.command("baseline", cls=SteCommand, help="Accept the findings of today.")
def lint_command(  # noqa: PLR0913 - Typer needs one typed parameter per CLI option.
    ctx: typer.Context,
    *,
    paths: Annotated[
        list[str] | None, typer.Argument(help="Files, directories, or - for standard input.")
    ] = None,
    output_format: Annotated[
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
    read_all: Annotated[bool, typer.Option("--all", help="Read files that git ignores.")] = False,
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
    """Check prose or record its accepted findings."""
    io = streams(ctx)
    opts = LintOptions(
        paths=paths or [],
        output_format=output_format.value,
        mode=mode,
        fields=fields,
        config=config,
        baseline=baseline,
        dict=dictionary,
        preset=preset,
        analyzer=analyzer,
        summary=summary,
        no_config=no_config,
        read_all=read_all,
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
    raise typer.Exit(_run_lint(opts, io, write=ctx.info_name == "baseline"))


@app.command("init", cls=SteCommand)
def init_command(
    ctx: typer.Context,
    *,
    output_format: Annotated[
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
    raise typer.Exit(
        _run_init(output_format.value, streams(ctx).stdout, dry_run=dry_run, force=force)
    )


@app.command("analyzer", cls=SteCommand)
def analyzer_command(
    ctx: typer.Context,
    *,
    output_format: Annotated[
        SimpleFormat, typer.Option("--format", help="Output format.")
    ] = SimpleFormat.text,
) -> None:
    """Show the grammar analyzer and what it needs."""
    raise typer.Exit(_run_analyzer(output_format.value, streams(ctx).stdout))


@app.command("eval", cls=SteCommand)
def eval_command(
    ctx: typer.Context,
    *,
    directory: Annotated[str, typer.Argument(help="Directory of the labeled corpus.")] = "testdata",
    output_format: Annotated[
        SimpleFormat, typer.Option("--format", help="Output format.")
    ] = SimpleFormat.text,
    fail_under: Annotated[
        float, typer.Option("--fail-under", help="Minimum precision and recall.")
    ] = -1,
) -> None:
    """Measure rules against a labeled corpus."""
    io = streams(ctx)
    raise typer.Exit(_run_eval(directory, output_format.value, fail_under, io.stdout, io.stderr))


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
    if ctx.parent is None:
        raise typer.Exit(2)
    streams(ctx).stdout.write(ctx.parent.get_help() + "\n")


@dict_app.callback()
def dictionary_group(
    ctx: typer.Context,
    *,
    output_format: Annotated[
        SimpleFormat, typer.Option("--format", help="Output format.")
    ] = SimpleFormat.text,
    out: Annotated[str, typer.Option("--out", help="Path of the dictionary index.")] = "",
    dry_run: Annotated[
        bool, typer.Option("--dry-run", help="Show the plan without a change.")
    ] = False,
) -> None:
    """Set defaults for the dictionary subcommands."""
    ctx.meta["dictionary_options"] = DictOptions(output_format.value, out, dry_run)


def _dict_options(
    ctx: typer.Context, output_format: SimpleFormat, out: str, *, dry_run: bool
) -> DictOptions:
    options = ctx.meta.get("dictionary_options", DictOptions())
    changes = {
        name: value
        for name, value in (
            ("output_format", output_format.value),
            ("out", out),
            ("dry_run", dry_run),
        )
        if ctx.get_parameter_source(name) == ParameterSource.COMMANDLINE
    }
    return replace(options, **changes)


@dict_app.command("import", cls=SteCommand)
def dict_import(
    ctx: typer.Context,
    *,
    source: Annotated[str, typer.Argument(help="The user's dictionary in Markdown or plain text.")],
    output_format: Annotated[
        SimpleFormat, typer.Option("--format", help="Output format.")
    ] = SimpleFormat.text,
    out: Annotated[str, typer.Option("--out", help="Path of the dictionary index.")] = "",
    dry_run: Annotated[
        bool, typer.Option("--dry-run", help="Show the plan without writing.")
    ] = False,
) -> None:
    """Read the user's dictionary and write an index."""
    raise typer.Exit(
        _run_dict(
            "import",
            source,
            _dict_options(ctx, output_format, out, dry_run=dry_run),
            streams(ctx).stdout,
        )
    )


@dict_app.command("path", cls=SteCommand, help="Print the path of the index.")
@dict_app.command("info", cls=SteCommand, help="Show the index of this user.")
@dict_app.command("remove", cls=SteCommand, help="Delete the index.")
def dict_status(
    ctx: typer.Context,
    *,
    output_format: Annotated[
        SimpleFormat, typer.Option("--format", help="Output format.")
    ] = SimpleFormat.text,
    out: Annotated[str, typer.Option("--out", help="Path of the dictionary index.")] = "",
    dry_run: Annotated[
        bool, typer.Option("--dry-run", help="Show the plan without a change.")
    ] = False,
) -> None:
    """Run a dictionary status or removal command."""
    if ctx.info_name is None:
        raise typer.Exit(2)
    raise typer.Exit(
        _run_dict(
            ctx.info_name,
            "",
            _dict_options(ctx, output_format, out, dry_run=dry_run),
            streams(ctx).stdout,
        )
    )


def run(args: list[str], stdin: TextIO, stdout: TextIO, stderr: TextIO) -> int:
    """Run the Typer application with the given streams and return its exit code."""
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
    """Run the command with the process arguments and standard streams."""
    try:
        return run(sys.argv[1:], sys.stdin, sys.stdout, sys.stderr)
    except BrokenPipeError:
        return 0
