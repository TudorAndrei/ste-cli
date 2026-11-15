# Copyright (c) 2026 Tudor Andrei Dumitrascu
"""Check the verb forms of rules 3.2, 3.3, and 3.4, and the quoted word of rule 3.5."""

from __future__ import annotations

import pytest

from ste.checker import lint
from ste.models import Options
from tests.grammar import StubSyntax

WORD_CONFIDENCE = 0.8
GRAMMAR_CONFIDENCE = 0.9


def found(text: str, rule_id: str, grammar: dict[str, list[str]] | None = None) -> list[str]:
    """Return the text of each finding of one rule."""
    opts = Options(syntax=StubSyntax(grammar)) if grammar else Options()
    return [text[d.start : d.end] for d in lint(text, opts) if d.rule_id == rule_id]


@pytest.mark.parametrize(
    "text",
    [
        'The label must be "warning".',
        "The state is “loading” now.",
        "The value is 'pending'.",
    ],
)
def test_a_quoted_ing_word_after_be_is_not_progressive(text: str) -> None:
    """Check that a quoted word is a mention, and not a verb."""
    assert found(text, "STE-3.5") == []


def test_a_quoted_participle_after_be_is_not_passive() -> None:
    """Check that a quoted participle is a mention, and not a passive verb."""
    assert found("The status is “approved”.", "STE-3.6") == []


def test_a_progressive_after_a_quoted_word_is_still_found() -> None:
    """Check that a quotation elsewhere in the sentence does not hide a verb."""
    assert found('The "main" server is running.', "STE-3.5") == ["is running"]


@pytest.mark.parametrize(
    ("text", "want"),
    [
        ("You would see an error.", ["would see"]),
        ("The tool should not restart the server.", ["should not restart"]),
        ("It may fail.", ["may fail"]),
        ("The task might stop.", ["might stop"]),
        ("The operator shall remove the cover.", ["shall remove"]),
    ],
)
def test_an_unapproved_modal_and_its_verb(text: str, want: list[str]) -> None:
    """Check a modal form that is not an approved tense, without the analyzer."""
    assert found(text, "STE-3.2") == want


@pytest.mark.parametrize(
    "text",
    [
        "The pump can start. The valve will open. The pump could not start.",
        "The operator must remove the cover.",
        "Should the pump fail, stop the engine.",
        "The output would have been sent.",
    ],
)
def test_no_unapproved_modal_without_the_analyzer(text: str) -> None:
    """Check approved modals, an inversion, and a perfect that rule 3.4 reports."""
    assert found(text, "STE-3.2") == []


def test_the_word_confidence_of_a_modal() -> None:
    """Check that a word match has a lower confidence than a grammar match."""
    findings = [d for d in lint("You would see an error.") if d.rule_id == "STE-3.2"]
    assert [d.confidence for d in findings] == [WORD_CONFIDENCE]


INVERSION = {
    "Should the pump fail, stop the engine.": [
        "Should/AUX/MD/aux/3",
        "the/DET/DT/det/2",
        "pump/NOUN/NN/nsubj/3",
        "fail/VERB/VB/ROOT/3",
        ",/PUNCT/,/punct/3",
        "stop/VERB/VB/conj/3",
        "the/DET/DT/det/7",
        "engine/NOUN/NN/dobj/5",
        "./PUNCT/./punct/3",
    ]
}


def test_the_analyzer_finds_a_modal_away_from_its_verb() -> None:
    """Check that the grammar joins a modal to a verb that does not follow it."""
    text = "Should the pump fail, stop the engine."
    findings = [
        d for d in lint(text, Options(syntax=StubSyntax(INVERSION))) if d.rule_id == "STE-3.2"
    ]
    assert [text[d.start : d.end] for d in findings] == ["Should"]
    assert [d.confidence for d in findings] == [GRAMMAR_CONFIDENCE]


def test_the_analyzer_joins_a_modal_to_its_helper_verb() -> None:
    """Check that the span ends at "be" in "would be deployed"."""
    text = "The service would be deployed."
    grammar = {
        text: [
            "The/DET/DT/det/1",
            "service/NOUN/NN/nsubjpass/4",
            "would/AUX/MD/aux/4",
            "be/AUX/VB/auxpass/4",
            "deployed/VERB/VBN/ROOT/4",
            "./PUNCT/./punct/4",
        ]
    }
    assert found(text, "STE-3.2", grammar) == ["would be"]


def test_the_analyzer_vetoes_a_modal_that_is_a_name() -> None:
    """Check that "may" as a noun gives no finding when the analyzer knows it."""
    text = "The may tree grows."
    grammar = {
        text: [
            "The/DET/DT/det/2",
            "may/NOUN/NN/compound/2",
            "tree/NOUN/NN/nsubj/3",
            "grows/VERB/VBZ/ROOT/3",
            "./PUNCT/./punct/3",
        ]
    }
    assert found(text, "STE-3.2", grammar) == []


def test_a_planned_passive_is_a_complex_construction() -> None:
    """Check "is to be" and a participle, also with a participle in the adjective list."""
    assert found("The cover is to be installed before the test.", "STE-3.4") == [
        "is to be installed"
    ]


def test_a_planned_passive_gives_one_finding() -> None:
    """Check that the passive inside the construction gives no second finding."""
    text = "The file is to be sent."
    got = [(d.rule_id, text[d.start : d.end]) for d in lint(text)]
    assert got == [("STE-3.4", "is to be sent")]


def test_an_infinitive_of_purpose_is_not_a_complex_construction() -> None:
    """Check that "is to be" and an adjective gives no finding."""
    assert found("The goal is to be fast.", "STE-3.4") == []


GRAMMAR_CASES = [
    (
        "a participle after a noun, with an agent",
        "The file created by the tool is large.",
        [
            "The/DET/DT/det/1",
            "file/NOUN/NN/nsubj/6",
            "created/VERB/VBN/acl/1",
            "by/ADP/IN/agent/2",
            "the/DET/DT/det/5",
            "tool/NOUN/NN/pobj/3",
            "is/AUX/VBZ/ROOT/6",
            "large/ADJ/JJ/acomp/6",
            "./PUNCT/./punct/6",
        ],
        ["created"],
    ),
    (
        "a participle clause at the start",
        "Once installed, the tool runs.",
        [
            "Once/ADV/RB/advmod/1",
            "installed/VERB/VBN/advcl/5",
            ",/PUNCT/,/punct/5",
            "the/DET/DT/det/4",
            "tool/NOUN/NN/nsubj/5",
            "runs/VERB/VBZ/ROOT/5",
            "./PUNCT/./punct/5",
        ],
        ["installed"],
    ),
    (
        "a participle before a noun is an adjective",
        "Use the attached cable.",
        [
            "Use/VERB/VB/ROOT/0",
            "the/DET/DT/det/3",
            "attached/VERB/VBN/amod/3",
            "cable/NOUN/NN/dobj/0",
            "./PUNCT/./punct/0",
        ],
        [],
    ),
    (
        "a passive verb belongs to rule 3.6",
        "The report was approved.",
        [
            "The/DET/DT/det/1",
            "report/NOUN/NN/nsubjpass/3",
            "was/AUX/VBD/auxpass/3",
            "approved/VERB/VBN/ROOT/3",
            "./PUNCT/./punct/3",
        ],
        [],
    ),
]


@pytest.mark.parametrize(
    ("_name", "text", "spec", "want"), GRAMMAR_CASES, ids=[c[0] for c in GRAMMAR_CASES]
)
def test_a_participle_that_is_not_an_adjective(
    _name: str, text: str, spec: list[str], want: list[str]
) -> None:
    """Check rule 3.3 with the grammar of the analyzer."""
    assert found(text, "STE-3.3", {text: spec}) == want


def test_a_participle_clause_is_information() -> None:
    """Check that rule 3.3 gives the info severity, because the standard can permit the clause."""
    text = GRAMMAR_CASES[0][1]
    opts = Options(syntax=StubSyntax({text: GRAMMAR_CASES[0][2]}))
    assert [d.severity for d in lint(text, opts) if d.rule_id == "STE-3.3"] == ["info"]


def test_no_participle_finding_without_the_analyzer() -> None:
    """Check that rule 3.3 needs the analyzer."""
    assert found("The file created by the tool is large.", "STE-3.3") == []


def test_the_analyzer_does_not_read_a_quoted_word_as_a_verb() -> None:
    """Check that a quoted "-ing" word is a mention, also when the tagger gives a verb."""
    text = 'Set the severity to "warning" for this rule.'
    grammar = {
        text: [
            "Set/VERB/VB/ROOT/0",
            "the/DET/DT/det/2",
            "severity/NOUN/NN/dobj/0",
            "to/AUX/IN/aux/5",
            '"/PUNCT/``/punct/5',
            "warning/VERB/VBG/advcl/0",
            "\"/PUNCT/''/punct/5",
            "for/ADP/IN/prep/5",
            "this/DET/DT/det/9",
            "rule/NOUN/NN/pobj/7",
            "./PUNCT/./punct/0",
        ]
    }
    assert found(text, "STE-3.5", grammar) == []


def test_a_participle_must_have_the_form_of_a_participle() -> None:
    """Check that a word that the tagger gives as a participle in error gives no finding."""
    text = "Read the start page for more data."
    grammar = {
        text: [
            "Read/VERB/VB/ROOT/0",
            "the/DET/DT/det/3",
            "start/NOUN/NN/compound/3",
            "page/VERB/VBN/acl/0",
            "for/ADP/IN/prep/3",
            "more/ADJ/JJR/amod/6",
            "data/NOUN/NNS/pobj/4",
            "./PUNCT/./punct/0",
        ]
    }
    assert found(text, "STE-3.3", grammar) == []
