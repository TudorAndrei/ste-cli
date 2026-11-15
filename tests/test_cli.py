# Copyright (c) 2026 Tudor Andrei Dumitrascu
"""Check cli contracts."""

from __future__ import annotations

import errno
import io
import json
import shutil
import subprocess
import sys
from pathlib import Path
from typing import TypedDict

import pytest
from rich.text import Text
from typer.testing import CliRunner

from ste.cli import app, find_project, main, match_pattern, matches_any, run

SAMPLE_FINDING_COUNT = 3
EXIT_ERROR = 2
BASELINE_FINDING_COUNT = 2
WALK_FILE_COUNT = 6
MIXED_FILE_COUNT = 2


class BrokenStream(io.StringIO):
    """Fail every write as a reader that closed the pipe would."""

    def write(self, _text: str, /) -> int:
        """Raise the error of a closed pipe, with its operating system code."""
        raise BrokenPipeError(errno.EPIPE, "Broken pipe")


class LintReport(TypedDict):
    """The JSON fields read by the command tests."""

    summary: dict[str, int | float | bool]
    findings: list[dict[str, str | int | float]]
    mode: str


def cli(*args: str, text: str = "") -> tuple[int, str, str]:
    """Run a command with isolated input and output streams."""
    stdout, stderr = io.StringIO(), io.StringIO()
    code = run(list(args), io.StringIO(text), stdout, stderr)
    return code, stdout.getvalue(), stderr.getvalue()


def report(*args: str, text: str = "") -> LintReport:
    """Read the JSON report of a successful lint command."""
    code, output, error = cli("lint", "--format", "json", *args, text=text)
    assert code == 0, error
    return json.loads(output)


def test_json_and_gates(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Check json and gates."""
    monkeypatch.chdir(tmp_path)
    text = "The file has been sent; it isn't ready.\n"
    data = report("--no-config", "-", text=text)
    assert data["summary"]["findings"] == SAMPLE_FINDING_COUNT
    assert data["summary"]["words"] > 0
    assert all(f["file"] == "(standard input)" for f in data["findings"])
    for flags in (("--fail-over", "2.5"), ("--fail-on-new",), ("--warnings-as-errors",)):
        assert cli("lint", "--no-config", *flags, "-", text=text)[0] == 1
    assert cli("lint", "--no-config", "--fail-over", "100", "-", text=text)[0] == 0
    assert report("--no-config", "-", text="Open the valve.")["findings"] == []


def test_interspersed_flags_and_output_controls(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Check interspersed flags and output controls."""
    monkeypatch.chdir(tmp_path)
    path = tmp_path / "draft.md"
    path.write_text("It isn't open; it isn't ready.")
    data = report(str(path), "--no-config", "--limit=1", "--fields", "rule_id,text")
    assert data["summary"]["findings"] == SAMPLE_FINDING_COUNT
    assert data["summary"]["shown"] == 1
    assert data["summary"]["truncated"]
    assert set(data["findings"][0]) == {"rule_id", "text"}
    assert report(str(path), "--no-config", "--summary")["summary"]["shown"] == 0
    code, output, error = cli("lint", str(path), "--no-config", "--format=ndjson")
    assert code == 0, error
    assert [json.loads(s)["type"] for s in output.splitlines()] == [
        "finding",
        "finding",
        "finding",
        "summary",
    ]
    assert report(str(path), "--no-config=true")["summary"]["findings"] == SAMPLE_FINDING_COUNT


@pytest.mark.parametrize(
    "args",
    [
        ("lint", "--mode", "pedantic"),
        ("lint", "--format", "yaml"),
        ("lint", "--limit", "-1"),
        ("lint", "--fields", "missing"),
        ("lint", "--unknown"),
        ("lint", "--dry-run"),
        ("version", "extra"),
        ("schema", "extra"),
        ("eval", "a", "b"),
        ("init", "--unknown"),
        ("dict", "path", "extra"),
        ("analyzer", "extra"),
        ("nonesuch",),
    ],
)
def test_invalid_arguments_exit_two(args: tuple[str, ...]) -> None:
    """Check invalid arguments exit two."""
    code, _, error = cli(*args)
    assert code == EXIT_ERROR
    assert error


def test_schema_and_help() -> None:
    """Check schema and help."""
    code, output, error = cli("schema")
    assert code == 0, error
    data = json.loads(output)
    assert set(data["commands"]) == {
        "lint",
        "baseline",
        "dict",
        "init",
        "analyzer",
        "eval",
        "review",
        "schema",
        "version",
    }
    assert data["exit_codes"]["2"]
    assert cli("version")[1].startswith("ste ")
    assert "Usage:" in cli("help")[1]
    assert cli()[0] == EXIT_ERROR


def test_init_dry_run_and_force(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Check init dry run and force."""
    monkeypatch.chdir(tmp_path)
    code, output, error = cli("init", "--dry-run", "--format=json")
    assert code == 0, error
    assert json.loads(output) == {
        "action": "init",
        "dry_run": True,
        "path": ".ste.yml",
        "exists": False,
    }
    assert not (tmp_path / ".ste.yml").exists()
    assert cli("init")[0] == 0
    assert cli("init")[0] == EXIT_ERROR
    assert cli("init", "--force")[0] == 0
    assert report("-", text="Open the valve.")["findings"] == []


def test_baseline_workflow_and_stale(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Check baseline workflow and stale."""
    monkeypatch.chdir(tmp_path)
    file = tmp_path / "draft.md"
    file.write_text("It isn't ready; start the pump.")
    args = ("--no-config", "--format=json", str(file))
    code, output, error = cli("baseline", "--dry-run", *args)
    assert code == 0, error
    assert json.loads(output)["findings"] == BASELINE_FINDING_COUNT
    assert not (tmp_path / ".ste-baseline.json").exists()
    assert cli("baseline", *args)[0] == 0
    data = report("--no-config", "--fail-on-new", str(file))
    assert data["summary"]["findings"] == 0
    assert data["summary"]["accepted"] == BASELINE_FINDING_COUNT
    assert (
        report("--no-config", "--no-baseline", str(file))["summary"]["findings"]
        == BASELINE_FINDING_COUNT
    )
    file.write_text("It is not ready; start the pump.")
    data = report("--no-config", str(file))
    assert data["summary"]["accepted"] == 1
    assert data["summary"]["stale"] == 1


def test_baseline_merge_and_path_spelling(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Check baseline merge and path spelling."""
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".git").mkdir()
    (tmp_path / ".ste.yml").write_text("mode: flavored")
    for name in ("a", "b"):
        (tmp_path / name).mkdir()
        (tmp_path / name / "draft.md").write_text("It isn't ready.")
    assert cli("baseline", ".")[0] == 0
    (tmp_path / "a/draft.md").write_text("It is ready.")
    assert cli("baseline", "a")[0] == 0
    assert report("b")["summary"]["accepted"] == 1
    monkeypatch.chdir(tmp_path / "b")
    assert report("draft.md")["summary"]["accepted"] == 1
    assert report(str(tmp_path / "b/draft.md"))["summary"]["accepted"] == 1


def test_config_search_exclude_and_flags(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Check config search exclude and flags."""
    (tmp_path / ".git").mkdir()
    (tmp_path / ".ste.yml").write_text(
        'mode: strict\nexclude: ["docs/legacy/**"]\nrules: {STE-4.2: info}\nfail_over: 0\n'
    )
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "guide.md").write_text("It isn't ready.")
    (docs / "legacy").mkdir()
    (docs / "legacy/old.md").write_text("It isn't ready.")
    monkeypatch.chdir(docs)
    data = report("--fail-over=100", "--mode=flavored", ".")
    assert data["mode"] == "flavored"
    assert data["summary"]["files"] == 1
    assert data["findings"][0]["severity"] == "info"
    assert report("--fail-over=100", str(docs / "legacy/old.md"))["summary"]["files"] == 0
    assert cli("lint", "guide.md")[0] == 1
    assert cli("lint", "--warnings-as-errors", "--fail-over=100", "guide.md")[0] == 0
    assert report("--no-config", "guide.md")["findings"][0]["severity"] == "warning"


def test_git_walk_and_explicit_paths(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Check git walk and explicit paths."""
    monkeypatch.chdir(tmp_path)
    git = shutil.which("git")
    assert git is not None
    subprocess.run([git, "init", "-q", str(tmp_path)], check=True)  # noqa: S603 -- fixed arguments in a pytest temporary directory
    (tmp_path / ".gitignore").write_text("generated.md\nprivate/\n")
    for name in ("guide.md", "generated.md", "CHANGELOG.md"):
        (tmp_path / name).write_text("It isn't ready.")
    for name in ("private", "dist", ".cache"):
        (tmp_path / name).mkdir()
        (tmp_path / name / "draft.md").write_text("It isn't ready.")
    assert report("--no-config", ".")["summary"]["files"] == 1
    assert report("--no-config", "--all", ".")["summary"]["files"] == WALK_FILE_COUNT
    assert report("--no-config", "generated.md")["summary"]["files"] == 1
    assert report("--no-config", "dist")["summary"]["files"] == 1
    assert report("--no-config", "CHANGELOG.md")["summary"]["files"] == 1


@pytest.mark.parametrize("output_format", ["github", "sarif"])
def test_code_host_paths_are_relative_to_repository(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, output_format: str
) -> None:
    """Check code host paths are relative to repository."""
    (tmp_path / ".git").mkdir()
    docs = tmp_path / "docs"
    docs.mkdir()
    file = docs / "guide.md"
    file.write_text("It isn't ready.")
    monkeypatch.chdir(docs)
    code, output, error = cli("lint", "--no-config", "--format", output_format, str(file))
    assert code == 0, error
    if output_format == "github":
        assert "file=docs/guide.md" in output
    else:
        assert (
            json.loads(output)["runs"][0]["results"][0]["locations"][0]["physicalLocation"][
                "artifactLocation"
            ]["uri"]
            == "docs/guide.md"
        )


def test_dict_mutation_plans_and_load(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Check dict mutation plans and load."""
    monkeypatch.chdir(tmp_path)
    source = tmp_path / "sample.txt"
    source.write_text("""## Part 2 - Dictionary
| Keyword | Meaning | Alternatives |
|---|---|---|
| **ABORT** (v) | | CANCEL |
""")
    index = tmp_path / "dictionary.json"
    # The exact source parser contract has separate dictionary tests.
    index.write_text('{"version":1,"source":"sample","entries":{}}')
    code, output, error = cli("dict", "remove", "--out", str(index), "--dry-run", "--format=json")
    assert code == 0, error
    assert json.loads(output)["exists"]
    assert index.exists()
    assert cli("dict", "remove", "--out", str(index))[0] == 0
    assert not index.exists()
    code, output, error = cli("dict", "info", "--out", str(index), "--format=json")
    assert code == 0, error
    assert not json.loads(output)["present"]
    assert (
        cli("lint", "--no-config", "--use-dict", "--dict", str(index), "-", text="Open the valve.")[
            0
        ]
        == EXIT_ERROR
    )
    assert cli("dict", "import", "input.PDF")[0] == EXIT_ERROR


def test_eval_and_analyzer_status() -> None:
    """Check eval and analyzer status."""
    directory = str(Path(__file__).parents[1] / "testdata")
    code, output, error = cli("eval", "--format=json", "--fail-under=1", directory)
    assert code == 0, error
    assert json.loads(output)["totals"]["precision"] == 1
    code, output, error = cli("analyzer", "--format=json")
    assert code == 0, error
    assert {"ready", "python", "script", "spacy", "problem", "fix"} <= json.loads(output).keys()
    assert (
        cli(
            "lint",
            "--no-config",
            "--analyzer",
            "a-program-that-does-not-exist",
            "-",
            text="Open the valve.",
        )[0]
        == EXIT_ERROR
    )


@pytest.mark.parametrize(
    ("flags", "expected"),
    [
        (["--warnings-as-errors=false", "--warnings-as-errors"], 1),
        (["--warnings-as-errors", "--warnings-as-errors=false"], 0),
        (["--warnings-as-errors=true", "--warnings-as-errors=false"], 0),
        (["--summary=bad"], 2),
    ],
)
def test_boolean_flags_use_last_value_and_reject_bad_values(
    flags: list[str], expected: int
) -> None:
    """Check boolean flags use last value and reject bad values."""
    code, _, error = cli("lint", "--no-config", *flags, "-", text="The valve isn't open.")
    assert code == expected
    if expected == EXIT_ERROR:
        assert "invalid boolean" in error


@pytest.mark.parametrize("command", ["lint", "baseline", "init", "dict", "analyzer", "eval"])
@pytest.mark.parametrize("force_color", [False, True])
def test_command_help_uses_output_stream(
    command: str, monkeypatch: pytest.MonkeyPatch, *, force_color: bool
) -> None:
    """Check the help stream with and without terminal color."""
    if force_color:
        monkeypatch.setenv("FORCE_COLOR", "1")
        monkeypatch.delenv("NO_COLOR", raising=False)
    else:
        monkeypatch.delenv("FORCE_COLOR", raising=False)
        monkeypatch.setenv("NO_COLOR", "1")
    code, output, error = cli(command, "--help")
    assert code == 0
    visible_text = Text.from_ansi(output).plain
    assert f"usage: ste {command}" in visible_text.lower()
    assert not error


@pytest.mark.parametrize(
    ("args", "dry_run"),
    [
        (["--dry-run=true", "--format=json", "remove"], True),
        (["--dry-run", "remove", "--dry-run=false", "--format=json"], False),
        (["--format=json", "path"], None),
    ],
)
def test_dictionary_options_before_and_after_subcommand(
    tmp_path: Path, args: tuple[str, ...], *, dry_run: bool
) -> None:
    """Check dictionary options before and after subcommand."""
    path = tmp_path / "dictionary.json"
    path.write_text('{"version":1,"source":"fixture","words":[]}')
    result = CliRunner().invoke(app, ["dict", "--out", str(path), *args])
    assert result.exit_code == 0, result.output
    data = json.loads(result.output)
    assert data["path"] == str(path)
    if dry_run is not None:
        assert data["dry_run"] is dry_run
        assert path.exists() is dry_run


def test_broken_pipe_propagates_to_the_caller() -> None:
    """Check that a closed output pipe is not turned into a usage error."""
    with pytest.raises(BrokenPipeError):
        run(
            ["lint", "--no-config", "--format", "ndjson", "-"],
            io.StringIO("The valve isn't open.\n"),
            BrokenStream(),
            io.StringIO(),
        )


def test_closed_stdout_pipe_exits_zero(tmp_path: Path) -> None:
    """Check that a small report to a closed pipe does not fail at interpreter exit."""
    small = tmp_path / "small.md"
    small.write_text("It isn't done.\n", encoding="utf-8")
    process = subprocess.Popen(  # noqa: S603 -- fixed arguments and a temporary file
        [sys.executable, "-m", "ste", "lint", "--format", "json", str(small)],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    assert process.stdout is not None
    assert process.stderr is not None
    process.stdout.close()
    code = process.wait(timeout=60)
    stderr = process.stderr.read()
    process.stderr.close()
    assert code == 0
    assert stderr == b""


def test_closed_stdout_descriptor_keeps_exit_code(tmp_path: Path) -> None:
    """Check that a closed standard output descriptor gives the usual exit code."""
    shell = shutil.which("sh")
    if shell is None:
        pytest.skip("this test needs a POSIX shell")
    small = tmp_path / "small.md"
    small.write_text("It isn't done.\n", encoding="utf-8")
    command = [shell, "-c", 'exec "$@" >&-', "sh", sys.executable, "-m", "ste", "lint"]
    for arguments, expected in (([str(small)], 0), ([str(tmp_path / "absent.md")], 2)):
        done = subprocess.run(  # noqa: S603 -- fixed arguments and a temporary file
            [*command, *arguments], capture_output=True, timeout=60, check=False
        )
        assert done.returncode == expected
        assert b"Traceback" not in done.stderr


@pytest.mark.parametrize(
    ("pattern", "path", "expected"),
    [
        ("**/*.md", "a/b.md", True),
        ("docs/**/*.gen.md", "docs/x/y.gen.md", True),
        ("**/fixtures/**", "a/fixtures/b.md", True),
        ("docs/*.md", "docs/a.md", True),
        ("*.md", "a/b.md", False),
        ("docs", "docs/a.md", True),
        ("docs/", "docs/a.md", True),
        ("docs/*.md", "other/a.md", False),
        ("", "a.md", False),
    ],
)
def test_match_pattern_by_directory_segment(pattern: str, path: str, *, expected: bool) -> None:
    """Check that exclusion patterns match whole directory segments."""
    assert match_pattern(pattern, path) is expected


@pytest.mark.parametrize(
    ("pattern", "path", "expected"),
    [
        ("docs", "a/docs/b.md", True),
        ("docs/", "a/docs/b.md", True),
        ("/docs", "docs/b.md", True),
        ("/docs", "a/docs/b.md", False),
        ("*.md", "a/b.md", True),
        ("docs/*.md", "x/docs/a.md", False),
    ],
)
def test_matches_any_follows_gitignore_depth(
    tmp_path: Path, pattern: str, path: str, *, expected: bool
) -> None:
    """Check that a bare name matches at any depth and a leading slash anchors the pattern."""
    assert matches_any(tmp_path / path, tmp_path, [pattern]) is expected


def test_non_utf8_file_is_named_in_error(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Check that a file that is not UTF-8 is named in the error."""
    monkeypatch.chdir(tmp_path)
    file = tmp_path / "latin.md"
    file.write_bytes("Caf\xe9 is open.\n".encode("latin-1"))
    code, _, error = cli("lint", "--no-config", str(file))
    assert code == EXIT_ERROR
    assert f"{file}: the file is not UTF-8 text" in error


def test_duplicate_paths_are_read_once(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Check that a file and standard input are each read once per run."""
    monkeypatch.chdir(tmp_path)
    file = tmp_path / "draft.md"
    file.write_text("It isn't ready.")
    single = report("--no-config", str(file))
    doubled = report("--no-config", str(file), str(file))
    assert doubled["summary"]["files"] == 1
    assert doubled["summary"]["findings"] == single["summary"]["findings"]
    mixed = report("--no-config", str(file), ".", "-", "-", text="Open the valve.")
    assert mixed["summary"]["files"] == MIXED_FILE_COUNT


def test_config_in_docs_directory_sets_project_root(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Check that an explicit docs/glossary.yml gives the same project as discovery."""
    monkeypatch.chdir(tmp_path)
    docs = tmp_path / "docs"
    docs.mkdir()
    config_file = docs / "glossary.yml"
    config_file.write_text("mode: flavored\n")
    discovered = find_project()
    explicit = find_project(str(config_file))
    assert discovered.directory == tmp_path
    assert explicit.directory == tmp_path
    assert explicit.config_path == config_file


def test_explicit_config_from_subdirectory_matches_discovery(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Check that an explicit config gives the project directory that discovery gives."""
    (tmp_path / ".git").mkdir()
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "glossary.yml").write_text('exclude: ["/draft.md"]\n')
    (docs / "draft.md").write_text("It isn't ready.")
    (docs / "guide.md").write_text("It isn't ready.")
    monkeypatch.chdir(docs)
    assert find_project().directory == docs
    assert find_project("glossary.yml").directory == docs
    assert report(".")["summary"]["files"] == 1
    assert report("--config", "glossary.yml", ".")["summary"]["files"] == 1


def test_symlink_parent_is_a_different_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Check that link/../draft.md is read when the link goes to another directory."""
    project, other = tmp_path / "project", tmp_path / "other"
    (other / "subdir").mkdir(parents=True)
    project.mkdir()
    (project / "draft.md").write_text("It isn't ready.")
    (other / "draft.md").write_text("It isn't ready; it isn't open.")
    (project / "link").symlink_to(other / "subdir", target_is_directory=True)
    monkeypatch.chdir(project)
    data = report("--no-config", "draft.md", "link/../draft.md")
    assert data["summary"]["files"] == MIXED_FILE_COUNT


def test_closed_stdin_reads_as_empty(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Check that a closed standard input gives empty text and not an error."""
    monkeypatch.setattr(sys, "stdin", None)
    monkeypatch.setattr(sys, "argv", ["ste", "lint", "--no-config", "--format", "json", "-"])
    assert main() == 0
    assert json.loads(capsys.readouterr().out)["summary"]["findings"] == 0


def test_dict_path_turns_dictionary_on(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Check that a dictionary path alone reads the dictionary index."""
    monkeypatch.chdir(tmp_path)
    index = tmp_path / "missing.json"
    code, _, error = cli("lint", "--no-config", "--dict", str(index), "-", text="Open the valve.")
    assert code == EXIT_ERROR
    assert "there is no dictionary index" in error
