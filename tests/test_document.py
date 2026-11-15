# Copyright (c) 2026 Tudor Andrei Dumitrascu
"""Source positions, prose boundaries, and standard word counts."""

from __future__ import annotations

import pytest

from ste.document import parse

PARAGRAPH_COUNT = 2
PROCEDURE_WORD_LIMIT = 20


@pytest.mark.parametrize(
    ("src", "want"),
    [
        ("# Installation\n\nStart the pump.\n", ["Installation", "Start the pump."]),
        ("- Open the valve\n- Start the pump\n", ["Open the valve", "Start the pump"]),
        ("1. Open the valve.\n2. Start the pump.\n", ["Open the valve.", "Start the pump."]),
        (
            "The tool checks the text. `ste` gives a report of the findings.\n",
            ["The tool checks the text.", "gives a report of the findings."],
        ),
        (
            "The tool obeys Issue 9. The rules agree with it.\n",
            ["The tool obeys Issue 9.", "The rules agree with it."],
        ),
        ("The author is J. Smith of the group.\n", ["The author is J. Smith of the group."]),
        ("**Open the valve.** Then start the pump.\n", ["Open the valve.", "Then start the pump."]),
        (
            "Use the correct tool, e.g. the torque wrench, for this task.\n",
            ["Use the correct tool, e.g. the torque wrench, for this task."],
        ),
        (
            "The pump gives pressure to the system\nand the valve controls the flow.\n",
            ["The pump gives pressure to the system\nand the valve controls the flow."],
        ),
        ("- Open the valve\n  - Start the pump\n", ["Open the valve", "Start the pump"]),
        ("The valve isn't open\n====================\n", ["The valve isn't open"]),
        ("> The valve isn't open.\n", ["The valve isn't open."]),
        ("| A | B |\n|---|---|\n| Foo | Bar |\n", ["A", "B", "Foo", "Bar"]),
        ("Text.\r\n\r\nSecond paragraph.\r\n", ["Text.", "Second paragraph."]),
        ("The valve is open.\rThe pump is on.", ["The valve is open.", "The pump is on."]),
    ],
)
def test_prose_boundaries(src: str, want: list[str]) -> None:
    """Check prose boundaries."""
    doc = parse(src)
    assert [s.text for s in doc.sentences] == want
    for sentence in doc.sentences:
        assert src[sentence.start : sentence.end] == sentence.text
        assert (
            sentence.first
            or sentence.block == doc.sentences[doc.sentences.index(sentence) - 1].block
        )


@pytest.mark.parametrize(
    "src",
    [
        "```\nThe file has been sent to the server.\n```\n",
        "~~~\nThe file has been sent to the server.\n~~~\n",
        '```go\nx := "it isn\'t code prose"\n```\n',
        "    docs/   # Additional documentation\n    tools/  # It isn't ready\n",
        '<div class="note">The report isn\'t ready.</div>\n',
        "![the report isn't ready](a.png)\n",
        "<https://example.com/a;b>\n",
    ],
)
def test_non_prose_blocks(src: str) -> None:
    """Check non prose blocks."""
    doc = parse(src)
    assert doc.sentences == []
    assert doc.word_count() == 0


@pytest.mark.parametrize(
    ("src", "visible", "hidden"),
    [
        ("Text `code` and [link](http://example.com/a;b).\n", "link", "http://example.com/a;b"),
        (
            "See [the report isn't ready][ref] here.\n\n[ref]: http://example.com/a;b\n",
            "isn't",
            "http://example.com/a;b",
        ),
        ("The valve <b>isn't</b> open.\n", "isn't", "<b>"),
        ('Run `git commit -m "it\'s done"; make` and then stop.\n', "Run", "it's done"),
        ("Éléments `code` and [link](url).\n", "Éléments", "code"),
    ],
)
def test_inline_prose_mask(src: str, visible: str, hidden: str) -> None:
    """Check inline prose mask."""
    doc = parse(src)
    assert len(doc.masked) == len(src)
    assert doc.masked.index(visible) == src.index(visible)
    start = src.index(hidden)
    assert doc.masked[start : start + len(hidden)].isspace()


@pytest.mark.parametrize(
    ("text", "want"),
    [
        ("Set the pressure of the pump.", 6),
        ("Set the pressure to 30 psi.", 5),
        ("Set the pressure to 30 psi before you start the test.", 10),
        ('Push the "EMER PWR" switch.', 4),
        ("Push the “EMER PWR” switch.", 4),
        ("Start the pump (the second pump on the left).", 4),
        ("Start the pump (the second (spare) pump).", 4),
        ("Install the quick-release fastener.", 4),
        ("Remove the 4 bolts.", 4),
        ("Open the valve. Start the pump.\n", 6),
        ("The pressure is 3.5 bar.", 4),
        ("Use the (damaged pump.", 4),
    ],
)
def test_word_count(text: str, want: int) -> None:
    """Check word count."""
    assert parse(text).word_count() == want


def test_sentence_types_and_limits() -> None:
    """Check sentence types and limits."""
    src = (
        "Start the pump.\n\n1. Open the valve.\n2. NOTE: The pump needs "
        "pressure.\n\n- Open the valve.\n"
    )
    doc = parse(src)
    assert [(s.procedural, s.note, s.limit()) for s in doc.sentences] == [
        (False, False, 25),
        (True, False, 20),
        (True, True, 25),
        (False, False, 25),
    ]
    assert [s.kind for s in doc.sentences] == ["paragraph", "list-item", "list-item", "list-item"]


@pytest.mark.parametrize(
    ("src", "want"),
    [
        ("- The flag: it starts the pump.\n", 2),
        ("The flag: it starts the pump.\n", 1),
        ("- The run starts at 12:30 each day.\n", 1),
        ("- **NOTE:** The pump needs pressure.\n", 1),
        ("- The flag does this:\n", 1),
    ],
)
def test_colon_sentence_boundary(src: str, want: int) -> None:
    """Check colon sentence boundary."""
    assert len(parse(src).sentences) == want


@pytest.mark.parametrize("fence", ["---", "+++"])
def test_front_matter(fence: str) -> None:
    """Check front matter."""
    src = f"{fence}\nid: ADR-0035\nstatus: it isn't ready\n{fence}\n\nThe report isn't ready.\n"
    doc = parse(src)
    assert [s.text for s in doc.sentences] == ["The report isn't ready."]
    assert doc.sentences[0].start == src.index("The report")


def test_horizontal_rule_keeps_prose() -> None:
    """Check horizontal rule keeps prose."""
    src = "The report isn't ready.\n\n---\n\nThe valve isn't open.\n"
    assert len(parse(src).sentences) == PARAGRAPH_COUNT


def test_wrapped_list_step_stays_one_sentence() -> None:
    """Check wrapped list step stays one sentence."""
    src = (
        "1. Open the valve one two three four five six seven eight "
        "nine ten and\n   then start the pump one two three four five "
        "six seven.\n"
    )
    doc = parse(src)
    assert len(doc.sentences) == 1
    assert doc.sentences[0].procedural
    assert doc.sentences[0].words > PROCEDURE_WORD_LIMIT
    assert "pump" in doc.sentences[0].text


def test_word_tokens_keep_apostrophes_and_positions() -> None:
    """Check word tokens keep apostrophes and positions."""
    src = "Élodie isn\u2019t ready for a quick-release test."
    tokens = parse(src).sentences[0].tokens
    assert [t.lower for t in tokens] == [
        "élodie",
        "isn't",
        "ready",
        "for",
        "a",
        "quick-release",
        "test",
    ]
    assert all(src[t.start : t.end] == t.text for t in tokens)
