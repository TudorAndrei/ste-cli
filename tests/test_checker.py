"""Checks at the public checker boundary."""

from dataclasses import asdict

import pytest

from ste.checker import lint
from ste.models import Options


@pytest.mark.parametrize(
    "text,want",
    [
        ("Start the pump. Then open the valve.", []),
        ("The file has been sent to the server.\n", ["STE-3.4"]),
        ("See [the report isn't ready](http://example.com/a;b) for the data.\n", ["STE-4.2"]),
        ("Some `code` here. The valve isn't open.\n", ["STE-4.2"]),
        ("- The first step:\n\n    The valve isn't open.\n", ["STE-4.2"]),
        ("<!-- ste-disable-next-line STE-4.2 -->\nThe valve isn't open.\n", []),
    ],
)
def test_lint_prose(text, want):
    found = lint(text)
    assert [d.rule_id for d in found] == want
    for diagnostic in found:
        assert text[diagnostic.start : diagnostic.end]


def test_positions_and_sort_order():
    text = "Some `code` here. The pump isn't full; the valve is running."
    found = lint(text)
    assert len(found) >= 3
    assert found == sorted(found, key=lambda d: (d.start, d.end, d.rule_id))
    contraction = next(d for d in found if d.rule_id == "STE-4.2")
    assert text[contraction.start : contraction.end] == "isn't"
    assert set(asdict(contraction)) == {
        "rule_id",
        "message",
        "severity",
        "confidence",
        "start",
        "end",
        "suggestion",
    }


def test_per_rule_settings():
    text = "Open the valve; the report isn't ready.\n"
    found = lint(text, Options(rule_severity={"STE-8.1": "error", "STE-4.2": "off"}))
    assert [(d.rule_id, d.severity) for d in found] == [("STE-8.1", "error")]


def test_confidence_filter():
    text = "The report was approved.\n"
    assert len(lint(text)) == 1
    assert lint(text, Options(min_confidence=0.8)) == []
