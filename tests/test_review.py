# Copyright (c) 2026 Tudor Andrei Dumitrascu
"""Check the language-model review without a network request."""

from __future__ import annotations

import io
import json
import subprocess
import sys
from dataclasses import dataclass, field
from types import SimpleNamespace
from typing import TYPE_CHECKING, cast

import pytest

from ste import review
from ste.cli import run

if TYPE_CHECKING:
    from pathlib import Path

    from anthropic import Anthropic

EXIT_ERROR = 2
SOURCE = (
    "# Install the tool\n"
    "\n"
    "Download the archive from the release page.\n"
    "The cache keeps each answer on the disk of the\n"
    "user. Then the network sends the result.\n"
    "\n"
    "- Open the file.\n"
    "- Close the file.\n"
)


@dataclass
class FakeClient:
    """Give a fixed answer and record each request."""

    findings: list[dict[str, str]] = field(default_factory=list)
    fail: bool = False
    prompts: list[str] = field(default_factory=list)

    def ask(self, system: str, prompt: str) -> str:
        """Record the request and return the fixed answer."""
        assert system == review.system_prompt()
        self.prompts.append(prompt)
        if self.fail:
            msg = "rate limit"
            raise RuntimeError(msg)
        return json.dumps({"findings": self.findings})


GOOD = {
    "rule_id": "STE-6.5",
    "quote": "disk of the user",
    "message": "The paragraph changes its subject.",
    "suggestion": "Divide it after the second sentence.",
}


@pytest.fixture
def project(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Make a project with one Markdown file and a private cache."""
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".git").mkdir()
    (tmp_path / "guide.md").write_text(SOURCE, encoding="utf-8")
    monkeypatch.setattr(review, "cache_directory", lambda: tmp_path / "cache")
    return tmp_path


def use(monkeypatch: pytest.MonkeyPatch, client: FakeClient) -> list[str]:
    """Give the command a fake client, and record the model of each client."""
    models: list[str] = []

    def factory(model: str, _timeout: float) -> FakeClient:
        models.append(model)
        return client

    monkeypatch.setattr(review, "make_client", factory)
    return models


def cli(*args: str) -> tuple[int, str, str]:
    """Run the command with captured streams."""
    out, err = io.StringIO(), io.StringIO()
    code = run(list(args), io.StringIO(), out, err)
    return code, out.getvalue(), err.getvalue()


def test_prompts_hold_each_rule_and_the_paragraph() -> None:
    """The fixed system prompt names each rule, and the request holds the heading and text."""
    system = review.system_prompt()
    for rule_id in review.RULE_IDS:
        assert rule_id in system
    unit = review.units(SOURCE)[0]
    prompt = review.user_prompt(unit)
    assert "<heading>Install the tool</heading>" in prompt
    assert "Download the archive" in prompt


def test_schema_names_the_review_rules_and_flags() -> None:
    """The schema gives the same rule identifiers and fields as the command."""
    code, output, _ = cli("schema")
    assert code == 0
    data = json.loads(output)
    assert [r["id"] for r in data["review"]["rules"]] == list(review.RULE_IDS)
    assert data["command_flags"]["review"]["--fields"]["values"] == list(review.FIELDS)
    assert data["command_flags"]["review"]["--model"]["default"] == review.DEFAULT_MODEL


def test_units_keep_the_heading_and_join_a_list() -> None:
    """A paragraph is one unit, a list is one unit, and each start is a source offset."""
    units = review.units(SOURCE)
    assert [u.heading for u in units] == ["Install the tool", "Install the tool"]
    assert units[0].text.startswith("Download")
    assert units[0].text.endswith("result.")
    assert units[1].text == "Open the file.\n- Close the file."
    for unit in units:
        assert SOURCE[unit.start : unit.start + len(unit.text)] == unit.text


def test_anthropic_request_caches_the_system_prompt_and_asks_for_a_schema() -> None:
    """The real client marks the system prompt for the cache and gives the JSON schema."""
    calls: list[dict] = []

    def create(**kwargs: object) -> SimpleNamespace:
        calls.append(kwargs)
        return SimpleNamespace(
            stop_reason="end_turn",
            content=[SimpleNamespace(type="text", text='{"findings": []}')],
        )

    sdk = SimpleNamespace(messages=SimpleNamespace(create=create))
    client = review.AnthropicClient("claude-haiku-5-5", cast("Anthropic", sdk))
    assert client.ask("fixed", "paragraph") == '{"findings": []}'
    (call,) = calls
    assert call["model"] == "claude-haiku-5-5"
    assert call["system"] == [
        {"type": "text", "text": "fixed", "cache_control": {"type": "ephemeral"}}
    ]
    assert call["output_config"]["format"]["schema"] == review.ANSWER_SCHEMA


def test_findings_map_to_the_source_and_drop_a_bad_quote(
    project: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A quote across a line break maps to its source line, and an unknown quote goes."""
    assert project.is_dir()
    use(
        monkeypatch,
        FakeClient(
            [
                GOOD,
                {**GOOD, "quote": "words that are not in the text"},
                {**GOOD, "rule_id": "STE-3.6"},
            ]
        ),
    )
    code, output, error = cli("review", "--format", "json", "guide.md")
    assert code == 0, error
    data = json.loads(output)
    (finding,) = data["findings"]
    assert finding["rule_id"] == "STE-6.5"
    assert finding["severity"] == "info"
    assert finding["kind"] == "advice"
    assert finding["text"] == "disk of the user"
    assert finding["column"] == SOURCE.splitlines()[3].index("disk") + 1
    assert data["mode"] == "review"
    assert data["summary"]["requests"] == data["summary"]["paragraphs"] == len(review.units(SOURCE))


def test_cache_answers_and_model_is_part_of_the_key(
    project: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A second run reads the cache, and a different model sends new requests."""
    assert project.is_dir()
    client = FakeClient([GOOD])
    use(monkeypatch, client)
    assert cli("review", "guide.md")[0] == 0
    sent = len(client.prompts)
    code, output, _ = cli("review", "--format", "json", "guide.md")
    assert code == 0
    assert len(client.prompts) == sent
    summary = json.loads(output)["summary"]
    assert (summary["requests"], summary["cached"]) == (0, sent)
    assert cli("review", "--model", "claude-sonnet-5-5", "guide.md")[0] == 0
    assert len(client.prompts) == 2 * sent


def test_dry_run_gives_the_plan_and_sends_nothing(
    project: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The plan counts paragraphs, requests, and tokens, and it makes no client."""
    assert project.is_dir()
    models = use(monkeypatch, FakeClient())
    code, output, error = cli("review", "--dry-run", "--format", "json", ".")
    assert code == 0, error
    plan = json.loads(output)
    assert plan["action"] == "review"
    assert plan["dry_run"] is True
    assert plan["model"] == review.DEFAULT_MODEL
    assert plan["paragraphs"] == plan["requests"] == len(review.units(SOURCE))
    assert plan["cached"] == 0
    assert plan["approx_input_tokens"] > plan["approx_system_tokens"] > 0
    assert models == []


def test_missing_key_and_missing_extra_are_clear_errors(
    project: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Without a key or without the extra, the command exits 2 and names the cause."""
    assert project.is_dir()
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_AUTH_TOKEN", raising=False)
    code, _, error = cli("review", "guide.md")
    assert code == EXIT_ERROR
    assert "ANTHROPIC_API_KEY" in error
    monkeypatch.setitem(sys.modules, "anthropic", None)
    code, _, error = cli("review", "guide.md")
    assert code == EXIT_ERROR
    assert "llm" in error


def test_a_failed_request_is_counted(project: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A failed request is in the summary and on standard error, and it is not cached."""
    assert project.is_dir()
    use(monkeypatch, FakeClient(fail=True))
    code, output, error = cli("review", "--format", "ndjson", "guide.md")
    assert code == 0
    summary = json.loads(output.splitlines()[-1])["summary"]
    assert summary["failed"] == summary["requests"] > 0
    assert "rate limit" in error
    assert not (project / "cache").exists()


def test_limit_and_fields_select_the_output(project: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """--limit and --fields work as in the lint command, and accept the kind field."""
    assert project.is_dir()
    use(monkeypatch, FakeClient([GOOD, {**GOOD, "quote": "Open the file", "rule_id": "STE-4.5"}]))
    code, output, _ = cli(
        "review", "--format", "json", "--limit", "1", "--fields", "rule_id,kind", "guide.md"
    )
    assert code == 0
    data = json.loads(output)
    assert data["findings"] == [{"rule_id": "STE-6.5", "kind": "advice"}]
    assert data["summary"]["truncated"] is True
    assert cli("review", "--fields", "nothing", "guide.md")[0] == EXIT_ERROR


def test_review_does_not_change_lint_or_the_baseline(
    project: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Advice never reaches a lint gate, and the review writes no baseline."""
    clean = project / "clean.md"
    clean.write_text("Open the valve with the handle.\n", encoding="utf-8")
    use(monkeypatch, FakeClient([{**GOOD, "quote": "Open the valve"}]))
    before = cli("lint", "--fail-on-new", "--warnings-as-errors", "clean.md")[0]
    code, output, _ = cli("review", "--format", "json", "clean.md")
    assert code == 0
    assert json.loads(output)["summary"]["findings"] == 1
    assert cli("lint", "--fail-on-new", "--warnings-as-errors", "clean.md")[0] == before == 0
    assert not (project / ".ste-baseline.json").exists()


def test_the_base_command_does_not_import_the_sdk() -> None:
    """The base install must work without the optional llm extra."""
    code = "import sys, ste.cli; sys.exit('anthropic' in sys.modules)"
    assert subprocess.run([sys.executable, "-c", code], check=False).returncode == 0  # noqa: S603
