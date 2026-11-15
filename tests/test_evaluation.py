# Copyright (c) 2026 Tudor Andrei Dumitrascu
"""Check evaluation contracts."""

from __future__ import annotations

import io
import json
from pathlib import Path

import pytest

from ste import evaluation

CORPUS_FILE_COUNT = 25
CORPUS_FINDING_COUNT = 73
PARTIAL_ACCURACY = 0.5
LABELED_FINDINGS = 2


def test_corpus_matches_existing_labels() -> None:
    """Check corpus matches existing labels.

    Without spaCy, the run skips the fixtures that need the analyzer. The
    other fixtures must still agree with their labels.
    """
    data = evaluation.run(Path(__file__).parents[1] / "testdata")
    assert data["files"] == CORPUS_FILE_COUNT
    assert data["totals"]["precision"] == 1
    assert data["totals"]["recall"] == 1
    if data["skipped"]:
        pytest.skip("spaCy is not installed, thus the count of findings is not complete")
    assert data["totals"]["true_positives"] == CORPUS_FINDING_COUNT


def test_counts_each_outcome_and_wildcard_label(tmp_path: Path) -> None:
    """Check counts each outcome and wildcard label."""
    (tmp_path / "sample.md").write_text("It isn't open; start the pump.")
    (tmp_path / "sample.expected.json").write_text(
        json.dumps(
            {"expect": [{"rule_id": "STE-4.2"}, {"rule_id": "STE-3.6", "text": "was closed"}]}
        )
    )
    data = evaluation.run(tmp_path)
    totals = data["totals"]
    assert (totals["true_positives"], totals["false_positives"], totals["false_negatives"]) == (
        1,
        1,
        1,
    )
    assert totals["precision"] == totals["recall"] == PARTIAL_ACCURACY
    stream = io.StringIO()
    evaluation.write_text(stream, data)
    assert "1 fixture files" in stream.getvalue()


def test_label_options(tmp_path: Path) -> None:
    """Check label options."""
    (tmp_path / "sample.md").write_text("Use the settings file. Open the fuel pump control unit.")
    (tmp_path / "sample.expected.json").write_text(
        json.dumps(
            {
                "prefer": {"config file": ["settings file"]},
                "allow_nouns": ["fuel pump control unit"],
                "max_noun_words": 3,
                "expect": [
                    {"rule_id": "STE-1.11", "text": "settings file"},
                    {"rule_id": "STE-1.9", "text": "fuel pump control unit"},
                ],
            }
        )
    )
    assert evaluation.run(tmp_path)["totals"]["true_positives"] == LABELED_FINDINGS


def test_empty_and_invalid_corpus(tmp_path: Path) -> None:
    """Check empty and invalid corpus."""
    with pytest.raises(ValueError, match="no fixture files"):
        evaluation.run(tmp_path)
    (tmp_path / "sample.md").write_text("Open the valve.")
    (tmp_path / "sample.expected.json").write_text("{")
    with pytest.raises(ValueError, match=r"sample\.expected\.json"):
        evaluation.run(tmp_path)


@pytest.mark.parametrize(
    "expected",
    [
        [],
        {"prefer": []},
        {"allow_nouns": 5},
        {"expect": 5},
        {"expect": [{"text": 5}]},
        {"max_noun_words": 0},
        {"max_noun_words": "3"},
    ],
)
def test_invalid_label_shapes_are_errors(tmp_path: Path, expected: object) -> None:
    """Check invalid label shapes are errors."""
    (tmp_path / "sample.md").write_text("Open the valve.")
    (tmp_path / "sample.expected.json").write_text(json.dumps(expected))
    with pytest.raises(ValueError, match=r"sample\.expected\.json"):
        evaluation.run(tmp_path)


def test_null_labels_and_missing_fields_follow_json_contract(tmp_path: Path) -> None:
    """Check null labels and missing fields follow json contract."""
    (tmp_path / "sample.md").write_text("Open the valve.")
    labels = tmp_path / "sample.expected.json"
    labels.write_text('{"expect": null}')
    assert evaluation.run(tmp_path)["totals"]["false_negatives"] == 0
    labels.write_text('{"expect": [{}]}')
    result = evaluation.run(tmp_path)
    assert result["rules"][0]["rule_id"] == ""
    assert result["totals"]["false_negatives"] == 1


def test_analyze_label_gives_grammar_to_the_fixture(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A fixture with "analyze": true runs with one shared analyzer."""
    from ste import analyzer  # noqa: PLC0415 - the patch needs the module object.
    from tests.grammar import StubSyntax  # noqa: PLC0415

    sentence = "Open the valve."
    grammar: dict[str, list[str]] = {}
    made: list[StubSyntax] = []

    def create() -> StubSyntax:
        made.append(StubSyntax(grammar))
        return made[-1]

    monkeypatch.setattr(analyzer, "check", lambda: {"ready": True, "problem": ""})
    monkeypatch.setattr(analyzer, "create", create)
    for name in ("a", "b"):
        (tmp_path / f"{name}.md").write_text(sentence)
        (tmp_path / f"{name}.expected.json").write_text(json.dumps({"analyze": True}))
    evaluation.run(tmp_path)
    assert len(made) == 1


def test_analyzer_fixture_is_skipped_without_the_analyzer(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Without spaCy, the run skips a fixture that needs the analyzer and names it."""
    from ste import analyzer  # noqa: PLC0415 - the patch needs the module object.

    monkeypatch.setattr(
        analyzer, "check", lambda: {"ready": False, "problem": "spaCy is not installed"}
    )
    (tmp_path / "a.md").write_text("Open the valve.")
    (tmp_path / "a.expected.json").write_text(
        json.dumps({"analyze": True, "expect": [{"rule_id": "STE-5.2"}]})
    )
    (tmp_path / "b.md").write_text("It isn't open.")
    (tmp_path / "b.expected.json").write_text(json.dumps({"expect": [{"rule_id": "STE-4.2"}]}))
    data = evaluation.run(tmp_path)
    assert data["skipped"] == ["a.md"]
    assert data["totals"]["recall"] == 1
    out = io.StringIO()
    evaluation.write_text(out, data)
    assert "1 fixture files skipped, because they need the analyzer: a.md" in out.getvalue()


def test_require_analyzer_stops_without_the_analyzer(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """With require_analyzer, a fixture that needs the analyzer stops the run."""
    from ste import analyzer  # noqa: PLC0415 - the patch needs the module object.

    monkeypatch.setattr(
        analyzer, "check", lambda: {"ready": False, "problem": "spaCy is not installed"}
    )
    (tmp_path / "a.md").write_text("Open the valve.")
    (tmp_path / "a.expected.json").write_text(json.dumps({"analyze": True}))
    with pytest.raises(ValueError, match=r"needs the analyzer\. spaCy is not installed"):
        evaluation.run(tmp_path, require_analyzer=True)
