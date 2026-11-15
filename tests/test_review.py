# Copyright (c) 2026 Tudor Andrei Dumitrascu
"""Check the instruction that the review command gives to an agent."""

from __future__ import annotations

import io
import json

from ste.cli import run


def cli(*args: str) -> tuple[int, str, str]:
    """Run a command with isolated input and output streams."""
    out, err = io.StringIO(), io.StringIO()
    code = run(list(args), io.StringIO(), out, err)
    return code, out.getvalue(), err.getvalue()


def test_text_tells_the_agent_to_lint_and_to_load_the_skill() -> None:
    """Name the lint command, the subagent, the skill, and the paths."""
    code, output, error = cli("review", "docs/", "README.md")
    assert code == 0, error
    assert "ste lint --format json --summary docs/ README.md" in output
    assert "subagent" in output
    assert "`ste-review` skill" in output
    assert "skill/ste-review" in output


def test_json_gives_the_skill_and_the_paths() -> None:
    """Give one object that an agent can read."""
    code, output, error = cli("review", "--format", "json", "docs/")
    assert code == 0, error
    data = json.loads(output)
    assert data["action"] == "review"
    assert data["skill"] == "ste-review"
    assert data["paths"] == ["docs/"]
    assert "ste-review" in data["instruction"]


def test_no_path_means_the_current_directory() -> None:
    """Review the current directory when no path is given."""
    _, output, _ = cli("review", "--format", "json")
    assert json.loads(output)["paths"] == ["."]


def test_the_command_reads_no_file() -> None:
    """Give the instruction also for a path that does not exist."""
    code, output, error = cli("review", "no/such/file.md")
    assert code == 0, error
    assert "no/such/file.md" in output
