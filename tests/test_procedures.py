# Copyright (c) 2026 Tudor Andrei Dumitrascu
"""Check the grammar rules for procedures, notes, and safety instructions."""

from __future__ import annotations

import pytest

from ste.checker import lint
from ste.document import parse
from ste.grammar import annotate
from ste.models import Options, SyntaxToken
from tests.grammar import Grammar, StubSyntax

OPEN_AND_REMOVE = [
    "Open/VERB/VB/ROOT/0",
    "the/DET/DT/det/2",
    "valve/NOUN/NN/dobj/0",
    "and/CCONJ/CC/cc/0",
    "remove/VERB/VB/conj/0",
    "the/DET/DT/det/6",
    "cap/NOUN/NN/dobj/4",
    "./PUNCT/./punct/0",
]
OPEN_OR_REMOVE = [s.replace("and/CCONJ", "or/CCONJ") for s in OPEN_AND_REMOVE]
PUSH_AND_HOLD = [
    "Push/VERB/VB/ROOT/0",
    "and/CCONJ/CC/cc/0",
    "hold/VERB/VB/conj/0",
    "the/DET/DT/det/4",
    "button/NOUN/NN/dobj/2",
    "./PUNCT/./punct/0",
]
SAME_TIME = [
    "Hold/VERB/VB/ROOT/0",
    "the/DET/DT/det/2",
    "button/NOUN/NN/dobj/0",
    "and/CCONJ/CC/cc/0",
    "at/ADP/IN/prep/8",
    "the/DET/DT/det/7",
    "same/ADJ/JJ/amod/7",
    "time/NOUN/NN/pobj/4",
    "turn/VERB/VB/conj/0",
    "the/DET/DT/det/10",
    "knob/NOUN/NN/dobj/8",
    "./PUNCT/./punct/0",
]
SURE_AND = [
    "Make/VERB/VB/ROOT/0",
    "sure/ADJ/JJ/acomp/0",
    "that/SCONJ/IN/mark/5",
    "the/DET/DT/det/4",
    "pump/NOUN/NN/nsubj/5",
    "is/AUX/VBZ/ccomp/1",
    "off/ADV/RB/advmod/5",
    "and/CCONJ/CC/cc/5",
    "the/DET/DT/det/9",
    "valve/NOUN/NN/nsubj/10",
    "is/AUX/VBZ/ccomp/5",
    "open/ADJ/JJ/acomp/10",
    "./PUNCT/./punct/0",
]
DESCRIPTION_AND = [
    "The/DET/DT/det/1",
    "tool/NOUN/NN/nsubj/2",
    "reads/VERB/VBZ/ROOT/2",
    "the/DET/DT/det/4",
    "file/NOUN/NN/dobj/2",
    "and/CCONJ/CC/cc/2",
    "writes/VERB/VBZ/conj/2",
    "the/DET/DT/det/8",
    "report/NOUN/NN/dobj/6",
    "./PUNCT/./punct/2",
]


def found(text: str, grammar: Grammar, rule_id: str) -> list[str]:
    """Return the text of each finding of one rule."""
    return [
        text[d.start : d.end]
        for d in lint(text, Options(syntax=StubSyntax(grammar)))
        if d.rule_id == rule_id
    ]


@pytest.mark.parametrize(
    ("text", "grammar", "want"),
    [
        (
            "1. Open the valve and remove the cap.\n",
            {"Open the valve and remove the cap.": OPEN_AND_REMOVE},
            ["remove"],
        ),
        (
            "1. Open the valve or remove the cap.\n",
            {"Open the valve or remove the cap.": OPEN_OR_REMOVE},
            [],
        ),
        ("1. Push and hold the button.\n", {"Push and hold the button.": PUSH_AND_HOLD}, []),
        (
            "1. Hold the button and at the same time turn the knob.\n",
            {"Hold the button and at the same time turn the knob.": SAME_TIME},
            [],
        ),
        (
            "1. Make sure that the pump is off and the valve is open.\n",
            {"Make sure that the pump is off and the valve is open.": SURE_AND},
            [],
        ),
        (
            "1. The tool reads the file and writes the report.\n",
            {"The tool reads the file and writes the report.": DESCRIPTION_AND},
            [],
        ),
        (
            "- Open the valve and remove the cap.\n",
            {"Open the valve and remove the cap.": OPEN_AND_REMOVE},
            [],
        ),
        ("1. Open the valve and remove the cap.\n", {}, []),
        (
            "1. Stop the pump, drain the tank.\n",
            {
                "Stop the pump, drain the tank.": [
                    "Stop/VERB/VB/ROOT/0",
                    "the/DET/DT/det/2",
                    "pump/NOUN/NN/dobj/0",
                    ",/PUNCT/,/punct/0",
                    "drain/VERB/VBP/conj/0",
                    "the/DET/DT/det/6",
                    "tank/NOUN/NN/dobj/4",
                    "./PUNCT/./punct/0",
                ]
            },
            ["drain"],
        ),
        (
            '1. Click "Build and Deploy".\n',
            {
                'Click "Build and Deploy".': [
                    "Click/VERB/VB/ROOT/0",
                    '"/PUNCT/``/punct/2',
                    "Build/VERB/VB/dobj/0",
                    "and/CCONJ/CC/cc/2",
                    "Deploy/VERB/VB/conj/0",
                    "\"/PUNCT/''/punct/0",
                    "./PUNCT/./punct/0",
                ]
            },
            [],
        ),
        (
            "1. Freeze the ID, the checksum, and stop limits.\n",
            {
                "Freeze the ID, the checksum, and stop limits.": [
                    "Freeze/VERB/VB/ROOT/0",
                    "the/DET/DT/det/2",
                    "ID/PROPN/NNP/dobj/0",
                    ",/PUNCT/,/punct/2",
                    "the/DET/DT/det/5",
                    "checksum/NOUN/NN/conj/2",
                    ",/PUNCT/,/punct/0",
                    "and/CCONJ/CC/cc/0",
                    "stop/VERB/VB/conj/0",
                    "limits/NOUN/NNS/dobj/8",
                    "./PUNCT/./punct/0",
                ]
            },
            [],
        ),
        (
            "1. Retain the count; otherwise return the default.\n",
            {
                "Retain the count; otherwise return the default.": [
                    "Retain/VERB/VB/ROOT/0",
                    "the/DET/DT/det/2",
                    "count/NOUN/NN/dobj/0",
                    ";/PUNCT/:/punct/5",
                    "otherwise/ADV/RB/advmod/5",
                    "return/VERB/VB/conj/0",
                    "the/DET/DT/det/7",
                    "default/NOUN/NN/dobj/5",
                    "./PUNCT/./punct/5",
                ]
            },
            [],
        ),
        (
            "1. Use oxlint for linting and oxfmt for formatting.\n",
            {
                "Use oxlint for linting and oxfmt for formatting.": [
                    "Use/VERB/VB/ROOT/0",
                    "oxlint/NOUN/NN/dobj/0",
                    "for/ADP/IN/prep/1",
                    "linting/VERB/VBG/pobj/2",
                    "and/CCONJ/CC/cc/0",
                    "oxfmt/VERB/VB/conj/0/oxfmt/unknown",
                    "for/ADP/IN/prep/5",
                    "formatting/VERB/VBG/pobj/6",
                    "./PUNCT/./punct/0",
                ]
            },
            [],
        ),
        (
            "1. Use ruff for linting and run pytest for tests.\n",
            {
                "Use ruff for linting and run pytest for tests.": [
                    "Use/VERB/VB/ROOT/0",
                    "ruff/NOUN/NN/dobj/0",
                    "for/ADP/IN/prep/1",
                    "linting/VERB/VBG/pobj/2",
                    "and/CCONJ/CC/cc/0",
                    "run/VERB/VB/conj/0",
                    "pytest/NOUN/NN/dobj/5",
                    "for/ADP/IN/prep/5",
                    "tests/NOUN/NNS/pobj/7",
                    "./PUNCT/./punct/0",
                ]
            },
            ["run"],
        ),
    ],
)
def test_one_instruction_in_each_step(text: str, grammar: Grammar, want: list[str]) -> None:
    """Check that a step with two commands gives a finding, and only then."""
    assert found(text, grammar, "STE-5.2") == want


HOT = [
    "The/DET/DT/det/1",
    "surface/NOUN/NN/nsubj/2",
    "is/AUX/VBZ/ROOT/2",
    "hot/ADJ/JJ/acomp/2",
    "./PUNCT/./punct/2",
]
BURN = [
    "It/PRON/PRP/nsubj/2",
    "can/AUX/MD/aux/2",
    "burn/VERB/VB/ROOT/2",
    "your/PRON/PRP$/poss/4",
    "skin/NOUN/NN/dobj/2",
    "./PUNCT/./punct/2",
]
DO_NOT_TOUCH = [
    "Do/AUX/VB/aux/2",
    "not/PART/RB/neg/2",
    "touch/VERB/VB/ROOT/2",
    "the/DET/DT/det/4",
    "surface/NOUN/NN/dobj/2",
    "./PUNCT/./punct/2",
]
IF_THEN_COMMAND = [
    "If/SCONJ/IN/mark/3",
    "the/DET/DT/det/2",
    "pump/NOUN/NN/nsubj/3",
    "runs/VERB/VBZ/advcl/7",
    ",/PUNCT/,/punct/3",
    "do/AUX/VBP/aux/7",
    "not/PART/RB/neg/7",
    "open/VERB/VB/ROOT/7",
    "the/DET/DT/det/9",
    "valve/NOUN/NN/dobj/7",
    "./PUNCT/./punct/7",
]
YOU_MUST = [
    "You/PRON/PRP/nsubj/2",
    "must/AUX/MD/aux/2",
    "wear/VERB/VB/ROOT/2",
    "gloves/NOUN/NNS/dobj/2",
    "./PUNCT/./punct/2",
]
HIGH_VOLTAGE = ["High/ADJ/JJ/amod/1", "voltage/NOUN/NN/ROOT/1", "./PUNCT/./punct/1"]


@pytest.mark.parametrize(
    ("text", "grammar", "want"),
    [
        (
            "**WARNING:** The surface is hot. It can burn your skin.\n",
            {"The surface is hot.": HOT, "It can burn your skin.": BURN},
            ["WARNING:** The surface is hot."],
        ),
        (
            "> [!CAUTION]\n> The surface is hot.\n> It can burn your skin.\n",
            {"The surface is hot.": HOT, "It can burn your skin.": BURN},
            ["[!CAUTION]\n> The surface is hot."],
        ),
        (
            "**CAUTION:** You must wear gloves.\n",
            {"You must wear gloves.": YOU_MUST},
            ["CAUTION:** You must wear gloves."],
        ),
        (
            "**WARNING:** Do not touch the surface. It can burn your skin.\n",
            {"Do not touch the surface.": DO_NOT_TOUCH, "It can burn your skin.": BURN},
            [],
        ),
        (
            "**DANGER:** If the pump runs, do not open the valve.\n",
            {"If the pump runs, do not open the valve.": IF_THEN_COMMAND},
            [],
        ),
        ("**DANGER:** High voltage.\n", {"High voltage.": HIGH_VOLTAGE}, []),
        ("**NOTE:** The surface is hot.\n", {"The surface is hot.": HOT}, []),
        ("**WARNING:** The surface is hot.\n", {}, []),
    ],
)
def test_a_safety_instruction_starts_with_a_command(
    text: str, grammar: Grammar, want: list[str]
) -> None:
    """Check that a warning that starts with a description gives a finding."""
    assert found(text, grammar, "STE-7.2") == want


BEFORE = [
    "Close/VERB/VB/ROOT/0",
    "the/DET/DT/det/2",
    "valve/NOUN/NN/dobj/0",
    "before/SCONJ/IN/mark/5",
    "you/PRON/PRP/nsubj/5",
    "start/VERB/VBP/advcl/0",
    "the/DET/DT/det/7",
    "pump/NOUN/NN/dobj/5",
    "./PUNCT/./punct/0",
]
BEFORE_FIRST = [
    "Before/SCONJ/IN/mark/2",
    "you/PRON/PRP/nsubj/2",
    "start/VERB/VBP/advcl/6",
    "the/DET/DT/det/4",
    "pump/NOUN/NN/dobj/2",
    ",/PUNCT/,/punct/6",
    "close/VERB/VB/ROOT/6",
    "the/DET/DT/det/8",
    "valve/NOUN/NN/dobj/6",
    "./PUNCT/./punct/6",
]
AFTER_PHRASE = [
    "Close/VERB/VB/ROOT/0",
    "the/DET/DT/det/2",
    "valve/NOUN/NN/dobj/0",
    "after/ADP/IN/prep/0",
    "the/DET/DT/det/5",
    "test/NOUN/NN/pobj/3",
    "./PUNCT/./punct/0",
]
UNTIL = [
    "Wait/VERB/VB/ROOT/0",
    "until/SCONJ/IN/mark/4",
    "the/DET/DT/det/3",
    "light/NOUN/NN/nsubj/4",
    "comes/VERB/VBZ/advcl/0",
    "on/ADP/RP/prt/4",
    "./PUNCT/./punct/0",
]
BEFORE_GERUND = [
    "Read/VERB/VB/ROOT/0",
    "the/DET/DT/det/2",
    "guide/NOUN/NN/dobj/0",
    "before/ADP/IN/prep/0",
    "using/VERB/VBG/pcomp/3",
    "the/DET/DT/det/6",
    "tool/NOUN/NN/dobj/4",
    "./PUNCT/./punct/0",
]
IN_CASE = [
    "Remove/VERB/VB/ROOT/0",
    "the/DET/DT/det/2",
    "cap/NOUN/NN/dobj/0",
    "in/ADP/IN/prep/0",
    "case/NOUN/NN/pobj/3",
    "of/ADP/IN/prep/4",
    "a/DET/DT/det/7",
    "leak/NOUN/NN/pobj/5",
    "./PUNCT/./punct/0",
]


@pytest.mark.parametrize(
    ("text", "grammar", "want"),
    [
        (
            "1. Close the valve before you start the pump.\n",
            {"Close the valve before you start the pump.": BEFORE},
            ["before you start the pump"],
        ),
        (
            "1. Remove the cap in case of a leak.\n",
            {"Remove the cap in case of a leak.": IN_CASE},
            ["in case of a leak"],
        ),
        (
            "1. Before you start the pump, close the valve.\n",
            {"Before you start the pump, close the valve.": BEFORE_FIRST},
            [],
        ),
        (
            "1. Close the valve after the test.\n",
            {"Close the valve after the test.": AFTER_PHRASE},
            [],
        ),
        ("1. Wait until the light comes on.\n", {"Wait until the light comes on.": UNTIL}, []),
        (
            "1. Read the guide before using the tool.\n",
            {"Read the guide before using the tool.": BEFORE_GERUND},
            [],
        ),
        (
            "Close the valve before you start the pump.\n",
            {"Close the valve before you start the pump.": BEFORE},
            [],
        ),
    ],
)
def test_a_condition_clause_after_the_command(text: str, grammar: Grammar, want: list[str]) -> None:
    """Check that a time or case condition after a command gives a finding."""
    assert found(text, grammar, "STE-5.4") == want


DISCONNECT = [
    "Disconnect/VERB/VB/ROOT/0",
    "the/DET/DT/det/2",
    "power/NOUN/NN/dobj/0",
    "first/ADV/RB/advmod/0",
    "./PUNCT/./punct/0",
]
SEE = [
    "See/VERB/VB/ROOT/0",
    "the/DET/DT/det/2",
    "guide/NOUN/NN/dobj/0",
    "./PUNCT/./punct/0",
]
CAPACITOR = [
    "The/DET/DT/det/1",
    "capacitor/NOUN/NN/nsubj/2",
    "keeps/VERB/VBZ/ROOT/2",
    "a/DET/DT/det/4",
    "charge/NOUN/NN/dobj/2",
    "./PUNCT/./punct/2",
]


@pytest.mark.parametrize(
    ("text", "grammar", "want"),
    [
        (
            "**NOTE:** Disconnect the power first.\n",
            {"Disconnect the power first.": DISCONNECT},
            ["Disconnect"],
        ),
        (
            "> [!NOTE]\n> Disconnect the power first.\n",
            {"Disconnect the power first.": DISCONNECT},
            ["Disconnect"],
        ),
        (
            "**NOTE:** The capacitor keeps a charge. Disconnect the power first.\n",
            {"The capacitor keeps a charge.": CAPACITOR, "Disconnect the power first.": DISCONNECT},
            ["Disconnect"],
        ),
        (
            "**NOTE:** The capacitor keeps a charge.\n",
            {"The capacitor keeps a charge.": CAPACITOR},
            [],
        ),
        ("**NOTE:** See the guide.\n", {"See the guide.": SEE}, []),
        (
            "**NOTE:** Do not touch the surface.\n",
            {"Do not touch the surface.": DO_NOT_TOUCH},
            ["Do"],
        ),
        (
            "**WARNING:** Disconnect the power first.\n",
            {"Disconnect the power first.": DISCONNECT},
            [],
        ),
    ],
)
def test_a_command_in_a_note(text: str, grammar: Grammar, want: list[str]) -> None:
    """Check that a note with a plain command gives one finding for STE-5.5."""
    assert found(text, grammar, "STE-5.5") == want


class Recorder(StubSyntax):
    """A stub analyzer that keeps each text that it receives."""

    def __init__(self, grammar: Grammar) -> None:
        """Keep the grammar and an empty record."""
        super().__init__(grammar)
        self.seen: list[str] = []

    def grammar_many(self, sentences: list[str]) -> list[list[SyntaxToken]]:
        """Record the texts, then give the grammar."""
        self.seen.extend(sentences)
        return super().grammar_many(sentences)


def test_the_analyzer_does_not_read_the_label_or_the_quote_marks() -> None:
    """Check that the label and the quote marks do not go to the analyzer."""
    text = "> [!WARNING]\n> Do not touch\n> the surface.\n"
    stub = Recorder({"Do not touch\n  the surface.": DO_NOT_TOUCH})
    doc = parse(text)
    annotate(doc, stub)
    assert stub.seen == ["Do not touch\n  the surface."]
    sentence = doc.sentences[0]
    assert [(t.text, t.dep) for t in sentence.tokens] == [
        ("WARNING", ""),
        ("Do", "aux"),
        ("not", "neg"),
        ("touch", "ROOT"),
        ("the", "det"),
        ("surface", "dobj"),
    ]
