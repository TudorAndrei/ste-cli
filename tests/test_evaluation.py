import io
import json
from pathlib import Path

import pytest

from ste import evaluation


def test_corpus_matches_existing_labels():
    data = evaluation.run(Path(__file__).parents[1] / "testdata")
    assert data["files"] == 10
    assert data["totals"]["precision"] == 1
    assert data["totals"]["recall"] == 1
    assert data["totals"]["true_positives"] == 30


def test_counts_each_outcome_and_wildcard_label(tmp_path):
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
    assert totals["precision"] == totals["recall"] == 0.5
    stream = io.StringIO()
    evaluation.write_text(stream, data)
    assert "1 fixture files" in stream.getvalue()


def test_label_options(tmp_path):
    (tmp_path / "sample.md").write_text("Use the settings file.")
    (tmp_path / "sample.expected.json").write_text(
        json.dumps(
            {
                "prefer": {"config file": ["settings file"]},
                "expect": [{"rule_id": "STE-1.11", "text": "settings file"}],
            }
        )
    )
    assert evaluation.run(tmp_path)["totals"]["true_positives"] == 1


def test_empty_and_invalid_corpus(tmp_path):
    with pytest.raises(ValueError, match="no fixture files"):
        evaluation.run(tmp_path)
    (tmp_path / "sample.md").write_text("Open the valve.")
    (tmp_path / "sample.expected.json").write_text("{")
    with pytest.raises(ValueError):
        evaluation.run(tmp_path)


@pytest.mark.parametrize(
    "expected", [[], {"prefer": []}, {"allow_nouns": 5}, {"expect": 5}, {"expect": [{"text": 5}]}]
)
def test_invalid_label_shapes_are_errors(tmp_path, expected):
    (tmp_path / "sample.md").write_text("Open the valve.")
    (tmp_path / "sample.expected.json").write_text(json.dumps(expected))
    with pytest.raises(ValueError):
        evaluation.run(tmp_path)


def test_null_labels_and_missing_fields_follow_json_contract(tmp_path):
    (tmp_path / "sample.md").write_text("Open the valve.")
    labels = tmp_path / "sample.expected.json"
    labels.write_text('{"expect": null}')
    assert evaluation.run(tmp_path)["totals"]["false_negatives"] == 0
    labels.write_text('{"expect": [{}]}')
    result = evaluation.run(tmp_path)
    assert result["rules"][0]["rule_id"] == ""
    assert result["totals"]["false_negatives"] == 1
