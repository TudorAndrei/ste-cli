import io
import json
import subprocess
from pathlib import Path

import pytest

from ste.cli import run


def cli(*args, text=""):
    stdout, stderr = io.StringIO(), io.StringIO()
    code = run(list(args), io.StringIO(text), stdout, stderr)
    return code, stdout.getvalue(), stderr.getvalue()


def report(*args, text=""):
    code, output, error = cli("lint", "--format", "json", *args, text=text)
    assert code == 0, error
    return json.loads(output)


def test_json_and_gates(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    text = "The file has been sent; it isn't ready.\n"
    data = report("--no-config", "-", text=text)
    assert data["summary"]["findings"] == 3
    assert data["summary"]["words"] > 0
    assert all(f["file"] == "(standard input)" for f in data["findings"])
    for flags in (("--fail-over", "2.5"), ("--fail-on-new",), ("--warnings-as-errors",)):
        assert cli("lint", "--no-config", *flags, "-", text=text)[0] == 1
    assert cli("lint", "--no-config", "--fail-over", "100", "-", text=text)[0] == 0
    assert report("--no-config", "-", text="Open the valve.")["findings"] == []


def test_interspersed_flags_and_output_controls(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    path = tmp_path / "draft.md"
    path.write_text("It isn't open; it isn't ready.")
    data = report(str(path), "--no-config", "--limit=1", "--fields", "rule_id,text")
    assert data["summary"]["findings"] == 3
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
    assert report(str(path), "--no-config=true")["summary"]["findings"] == 3


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
def test_invalid_arguments_exit_two(args):
    code, _, error = cli(*args)
    assert code == 2
    assert error


def test_schema_and_help():
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
        "schema",
        "version",
    }
    assert data["exit_codes"]["2"]
    assert cli("version")[1].startswith("ste ")
    assert "Usage:" in cli("help")[1]
    assert cli()[0] == 2


def test_init_dry_run_and_force(tmp_path, monkeypatch):
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
    assert cli("init")[0] == 2
    assert cli("init", "--force")[0] == 0
    assert report("-", text="Open the valve.")["findings"] == []


def test_baseline_workflow_and_stale(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    file = tmp_path / "draft.md"
    file.write_text("It isn't ready; start the pump.")
    args = ("--no-config", "--format=json", str(file))
    code, output, error = cli("baseline", "--dry-run", *args)
    assert code == 0, error
    assert json.loads(output)["findings"] == 2
    assert not (tmp_path / ".ste-baseline.json").exists()
    assert cli("baseline", *args)[0] == 0
    data = report("--no-config", "--fail-on-new", str(file))
    assert data["summary"]["findings"] == 0
    assert data["summary"]["accepted"] == 2
    assert report("--no-config", "--no-baseline", str(file))["summary"]["findings"] == 2
    file.write_text("It is not ready; start the pump.")
    data = report("--no-config", str(file))
    assert data["summary"]["accepted"] == 1
    assert data["summary"]["stale"] == 1


def test_baseline_merge_and_path_spelling(tmp_path, monkeypatch):
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


def test_config_search_exclude_and_flags(tmp_path, monkeypatch):
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


def test_git_walk_and_explicit_paths(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    (tmp_path / ".gitignore").write_text("generated.md\nprivate/\n")
    for name in ("guide.md", "generated.md", "CHANGELOG.md"):
        (tmp_path / name).write_text("It isn't ready.")
    for name in ("private", "dist", ".cache"):
        (tmp_path / name).mkdir()
        (tmp_path / name / "draft.md").write_text("It isn't ready.")
    assert report("--no-config", ".")["summary"]["files"] == 1
    assert report("--no-config", "--all", ".")["summary"]["files"] == 6
    assert report("--no-config", "generated.md")["summary"]["files"] == 1
    assert report("--no-config", "dist")["summary"]["files"] == 1
    assert report("--no-config", "CHANGELOG.md")["summary"]["files"] == 1


@pytest.mark.parametrize("format", ["github", "sarif"])
def test_code_host_paths_are_relative_to_repository(tmp_path, monkeypatch, format):
    (tmp_path / ".git").mkdir()
    docs = tmp_path / "docs"
    docs.mkdir()
    file = docs / "guide.md"
    file.write_text("It isn't ready.")
    monkeypatch.chdir(docs)
    code, output, error = cli("lint", "--no-config", "--format", format, str(file))
    assert code == 0, error
    if format == "github":
        assert "file=docs/guide.md" in output
    else:
        assert (
            json.loads(output)["runs"][0]["results"][0]["locations"][0]["physicalLocation"][
                "artifactLocation"
            ]["uri"]
            == "docs/guide.md"
        )


def test_dict_mutation_plans_and_load(tmp_path, monkeypatch):
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
        == 2
    )
    assert cli("dict", "import", "input.PDF")[0] == 2


def test_eval_and_analyzer_status():
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
        == 2
    )


@pytest.mark.parametrize(
    "flags, expected",
    [
        (["--warnings-as-errors=false", "--warnings-as-errors"], 1),
        (["--warnings-as-errors", "--warnings-as-errors=false"], 0),
        (["--warnings-as-errors=true", "--warnings-as-errors=false"], 0),
        (["--summary=bad"], 2),
    ],
)
def test_boolean_flags_use_last_value_and_reject_bad_values(flags, expected):
    code, _, error = cli("lint", "--no-config", *flags, "-", text="The valve isn't open.")
    assert code == expected
    if expected == 2:
        assert "invalid boolean" in error


@pytest.mark.parametrize("command", ["lint", "baseline", "init", "dict", "analyzer", "eval"])
def test_command_help_uses_output_stream(command):
    code, output, error = cli(command, "--help")
    assert code == 0
    assert f"usage: ste {command}" in output
    assert not error
