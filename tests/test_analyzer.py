# Copyright (c) 2026 Tudor Andrei Dumitrascu
"""Check analyzer protocol transport and model integration."""

from __future__ import annotations

import importlib.util
import io
import json
import shlex
import sys
from pathlib import Path

import pytest

from ste.analyzer import ExternalAnalyzer, SpacyAnalyzer
from ste.checker import lint
from ste.cli import run
from ste.models import Options

SIGNED_CHARACTER_START = 15

STUB = Path(__file__).parent / "fixtures" / "stub_analyzer.py"


def test_external_analyzer_protocol() -> None:
    """Check external analyzer protocol."""
    client = ExternalAnalyzer([sys.executable, str(STUB)])
    try:
        assert client.model == "stub"
        sentence = "The report was signed by the team."
        assert client.passive_at(sentence, 15) == (True, True)
        assert client.passive_at(sentence, 4) == (False, True)
        assert client.passive_at(sentence, 999) == (False, False)
        grammar, known = client.grammar(sentence)
        assert known
        assert grammar[3].text == "signed"
        assert grammar[3].start == SIGNED_CHARACTER_START
        # The analyzer must retain usable results after a repeat request.
        assert client.grammar(sentence) == (grammar, True)
    finally:
        client.close()


@pytest.mark.parametrize("response", [[], {"ready": False}, "invalid JSON"])
def test_invalid_startup_is_an_error(tmp_path: Path, response: object) -> None:
    """Check invalid startup is an error."""
    script = tmp_path / "bad.py"
    payload = json.dumps(response) if response != "invalid JSON" else response
    script.write_text(f"print({payload!r}, flush=True)\n")
    with pytest.raises(ValueError, match="analyzer"):
        ExternalAnalyzer([sys.executable, str(script)])


def test_sentence_error_does_not_become_grammar(tmp_path: Path) -> None:
    """Check sentence error does not become grammar."""
    script = tmp_path / "error.py"
    script.write_text(
        "import json, sys\nprint('{\"ready\": true}', flush=True)\nfor "
        'line in sys.stdin:\n r=json.loads(line)\n if r.get("stop"): '
        'break\n print(json.dumps({"id":r["id"],"error":"bad '
        'sentence"}), flush=True)\n'
    )
    client = ExternalAnalyzer([sys.executable, str(script)])
    try:
        assert client.grammar("Read this.") == ([], False)
    finally:
        client.close()


@pytest.mark.skipif(
    importlib.util.find_spec("en_core_web_sm") is None,
    reason="optional spaCy model is not installed",
)
def test_local_spacy_grammar() -> None:
    """Check local spacy grammar."""
    client = SpacyAnalyzer()
    sentence = "The report was signed by the team."
    assert client.passive_at(sentence, 15) == (True, True)
    grammar, known = client.grammar(sentence)
    assert known
    assert any(t.text == "signed" and t.pos == "VERB" for t in grammar)


@pytest.mark.parametrize("token", [None, {"start": "bad"}, {"i": True}, {"text": []}])
def test_invalid_tokens_keep_basic_checks(tmp_path: Path, token: object) -> None:
    """Check invalid tokens keep basic checks."""
    script = tmp_path / "tokens.py"
    script.write_text(
        "import json, sys\nprint('{\"ready\": true}', flush=True)\n"
        'for line in sys.stdin:\n r=json.loads(line)\n if r.get("stop"): break\n'
        f' print(json.dumps({{"id":r["id"],"tokens":[{token!r}]}}), flush=True)\n'
    )
    client = ExternalAnalyzer([sys.executable, str(script)])
    try:
        findings = lint(
            "The engine fuel pump unit isn't clean; inspect it.", Options(syntax=client)
        )
        assert {d.rule_id for d in findings} >= {"STE-4.2", "STE-8.1"}
        assert client.grammar("engine fuel pump unit") == ([], False)
    finally:
        client.close()


def test_analyzer_exit_does_not_break_close(tmp_path: Path) -> None:
    """Check analyzer exit does not break close."""
    script = tmp_path / "exit.py"
    script.write_text("import sys\nprint('{\"ready\": true}', flush=True)\nsys.stdin.readline()\n")
    client = ExternalAnalyzer([sys.executable, str(script)])
    try:
        assert client.grammar("First sentence.") == ([], False)
        assert client.grammar("Next sentence.") == ([], False)
    finally:
        client.close()


def test_cli_external_analyzer_with_space_in_path(tmp_path: Path) -> None:
    """Check cli external analyzer with space in path."""
    script = tmp_path / "analyzer with spaces.py"
    script.write_text(STUB.read_text())
    stdout, stderr = io.StringIO(), io.StringIO()
    status = run(
        [
            "lint",
            "--no-config",
            "--no-baseline",
            "--format=json",
            "--analyzer",
            shlex.join([sys.executable, str(script)]),
            "-",
        ],
        io.StringIO("The report was signed by the team."),
        stdout,
        stderr,
    )
    assert status == 0, stderr.getvalue()
    findings = json.loads(stdout.getvalue())["findings"]
    assert [f["rule_id"] for f in findings] == ["STE-3.6"]
    assert findings[0]["text"] == "was signed"
