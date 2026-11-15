"""Command interface for the ASD-STE100 checker."""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Never, TextIO

from ste import __version__, analyzer, baseline, config, dictionary, evaluation, report
from ste.checker import lint_document
from ste.document import parse
from ste.models import Options

STDIN_NAME = "(standard input)"
USAGE = """ste finds ASD-STE100 violations in Markdown and plain text.

Usage:
  ste lint [flags] [path ...]   Check files, directories, or standard input
  ste baseline [flags] [path]   Accept the findings of today
  ste init [--dry-run]          Write a start config, .ste.yml
  ste analyzer                 Show the grammar analyzer and what it needs
  ste dict <command>           Manage a local dictionary index
  ste eval [flags] <dir>       Measure rules against a labeled corpus
  ste schema                   Print the command interface as JSON
  ste version                  Print the version

Findings alone do not change the exit code. Give --fail-on-new,
--warnings-as-errors, or --fail-over to use a gate.
Run ste lint --help for all flags.
"""
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


class Parser(argparse.ArgumentParser):
    output: TextIO

    def print_help(self, file=None) -> None:
        super().print_help(file or self.output)

    def error(self, message: str) -> Never:
        raise ValueError(message)


def _bool(text: str) -> bool:
    if text.lower() in ("true", "1", "t"):
        return True
    if text.lower() in ("false", "0", "f"):
        return False
    raise ValueError(f"invalid boolean: {text}")


def _parse(parser: Parser, args: list[str], stdout: TextIO) -> argparse.Namespace:
    parser.output = stdout
    # pflag accepts --flag=false while a bare boolean flag consumes no word.
    converted = []
    bools: dict[str, bool] = {}
    options_done = False
    for arg in args:
        if arg == "--":
            options_done = True
        name, sep, value = arg.partition("=")
        action = parser._option_string_actions.get(name)
        if not options_done and isinstance(action, argparse._StoreTrueAction):
            bools[action.dest] = _bool(value) if sep else True
        else:
            converted.append(arg)
    result = parser.parse_intermixed_args(converted)
    for name, value in bools.items():
        setattr(result, name, value)
    return result


def _parser(command: str, formats: tuple[str, ...] = ("text", "json")) -> Parser:
    parser = Parser(prog=f"ste {command}", allow_abbrev=False)
    parser.add_argument("--format", default="text", choices=formats)
    return parser


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


def _run_lint(args: list[str], stdin: TextIO, stdout: TextIO, stderr: TextIO, write: bool) -> int:
    parser = _parser("baseline" if write else "lint", report.FORMATS)
    for name in ("mode", "fields", "config", "baseline", "dict", "preset", "analyzer"):
        parser.add_argument("--" + name, default="")
    for name in (
        "summary",
        "no-config",
        "all",
        "no-baseline",
        "fail-on-new",
        "warnings-as-errors",
        "use-dict",
        "analyze",
        "dry-run",
    ):
        parser.add_argument("--" + name, action="store_true")
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--max-words", type=int, default=0)
    parser.add_argument("--fail-over", type=float, default=-1)
    parser.add_argument("paths", nargs="*")
    ns = _parse(parser, args, stdout)
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


def _no_args(command: str, args: list[str]) -> None:
    if args:
        raise ValueError(f'the {command} command takes no argument, and it got "{args[0]}"')


def _run_init(args: list[str], stdout: TextIO) -> int:
    parser = _parser("init")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--force", action="store_true")
    parser.add_argument("args", nargs="*")
    ns = _parse(parser, args, stdout)
    _no_args("init", ns.args)
    path = Path(config.DEFAULT_NAMES[0])
    if (existing := config.find(".")) and not ns.force:
        raise ValueError(f"{existing} exists. Give --force to write {path} all the same.")
    plan = {"action": "init", "dry_run": ns.dry_run, "path": str(path), "exists": path.is_file()}
    if ns.dry_run:
        text = f"A real run writes {path}.\n"
    else:
        path.write_text(STARTER_CONFIG, encoding="utf-8")
        text = f'{path} holds the start config. Run "ste lint --summary ." to see the size of the problem.\n'
    _write_plan(stdout, ns.format, plan, text)
    return 0


def _run_dict(args: list[str], stdout: TextIO) -> int:
    parser = _parser("dict")
    parser.add_argument("--out", default="")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("args", nargs="*")
    ns = _parse(parser, args, stdout)
    path = Path(ns.out or dictionary.default_path())
    if not ns.args or ns.args[0] not in ("import", "info", "path", "remove"):
        raise ValueError(
            'give "ste dict import <file>", "ste dict info", "ste dict path", or "ste dict remove"'
        )
    command = ns.args[0]
    expected = 2 if command == "import" else 1
    if len(ns.args) > expected:
        raise ValueError(f'"ste dict {command}" got an extra argument "{ns.args[expected]}"')
    if len(ns.args) < expected:
        raise ValueError('give "ste dict import <file>"')
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
        source = ns.args[1]
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


def _run_analyzer(args: list[str], stdout: TextIO) -> int:
    parser = _parser("analyzer")
    parser.add_argument("args", nargs="*")
    ns = _parse(parser, args, stdout)
    _no_args("analyzer", ns.args)
    status = analyzer.check()
    if status["ready"]:
        text = f'The analyzer is ready.\n  python: {status["python"]}\n  script: {status["script"]}\n\nRun "ste lint --analyze docs/" to use it.\nIt makes rule STE-3.6 more exact, and it is never necessary.\n'
    else:
        text = f"The analyzer cannot run: {status['problem']}\n"
        if status["fix"]:
            text += "\nTo make it work:\n" + "".join(f"  {fix}\n" for fix in status["fix"])
        text += "\nThe analyzer is optional. Each rule works without it.\n"
    _write_plan(stdout, ns.format, status, text)
    return 0


def _run_eval(args: list[str], stdout: TextIO, stderr: TextIO) -> int:
    parser = _parser("eval")
    parser.add_argument("--fail-under", type=float, default=-1)
    parser.add_argument("args", nargs="*")
    ns = _parse(parser, args, stdout)
    if len(ns.args) > 1:
        raise ValueError(f"the eval command takes one directory, and it got {len(ns.args)}")
    data = evaluation.run(ns.args[0] if ns.args else "testdata")
    if ns.format == "json":
        stdout.write(json.dumps(data, indent=2) + "\n")
    else:
        evaluation.write_text(stdout, data)
    totals = data["totals"]
    if ns.fail_under >= 0 and (
        totals["precision"] < ns.fail_under or totals["recall"] < ns.fail_under
    ):
        stderr.write(
            f"ste: precision {totals['precision']:.2f} and recall {totals['recall']:.2f}, and the limit is {ns.fail_under:.2f}\n"
        )
        return 1
    return 0


def run(args: list[str], stdin: TextIO, stdout: TextIO, stderr: TextIO) -> int:
    if not args:
        stderr.write(USAGE)
        return 2
    command, rest = args[0], args[1:]
    try:
        if command in ("help", "--help", "-h"):
            stdout.write(USAGE)
            return 0
        if command in ("version", "--version", "-v"):
            _no_args("version", rest)
            stdout.write(f"ste {__version__}\n")
            return 0
        if command == "schema":
            _no_args("schema", rest)
            stdout.write(json.dumps(_schema(), indent=2) + "\n")
            return 0
        if command in ("lint", "baseline"):
            return _run_lint(rest, stdin, stdout, stderr, command == "baseline")
        if command == "init":
            return _run_init(rest, stdout)
        if command == "dict":
            return _run_dict(rest, stdout)
        if command == "analyzer":
            return _run_analyzer(rest, stdout)
        if command == "eval":
            return _run_eval(rest, stdout, stderr)
        raise ValueError(f'"{command}" is not a command\n\n{USAGE}')
    except (OSError, ValueError, UnicodeError) as err:
        stderr.write(f"ste: {err}\n")
        return 2
    except SystemExit as err:
        return int(err.code or 0)


def main() -> int:
    try:
        return run(sys.argv[1:], sys.stdin, sys.stdout, sys.stderr)
    except BrokenPipeError:
        return 0
