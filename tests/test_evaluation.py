# Copyright (c) 2026 Tudor Andrei Dumitrascu
"""Check evaluation contracts."""

from __future__ import annotations

import io
import json
from pathlib import Path

import pytest

from ste import evaluation

CORPUS_FILE_COUNT = 12
CORPUS_FINDING_COUNT = 33
PARTIAL_ACCURACY = 0.5
LABELED_FINDINGS = 2


def test_corpus_matches_existing_labels() -> None:
    """Check corpus matches existing labels."""
    data = evaluation.run(Path(__file__).parents[1] / "testdata")
    assert data["files"] == CORPUS_FILE_COUNT
    assert data["totals"]["precision"] == 1
    assert data["totals"]["recall"] == 1
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
