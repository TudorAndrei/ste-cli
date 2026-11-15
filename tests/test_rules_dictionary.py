# Copyright (c) 2026 Tudor Andrei Dumitrascu
"""Dictionary rules that need the grammar. The dictionary has invented words only."""

from __future__ import annotations

import pytest

from ste.checker import lint, lint_document
from ste.dictionary import parse
from ste.models import Diagnostic, Options
from tests.grammar import Grammar, tagged

DICTIONARY = """## Part 2 - Dictionary
|Word (part of speech)|Approved meaning/ ALTERNATIVES|
|---|---|
|FRAMMIS (n)|A part of the machine|
|frammis (v)|GRIBBLE (v)|
|GRIBBLE (v), GRIBBLES, GRIBBLED|To make a hole|
|WIBBLY (adj), WIBBLIER, WIBBLIEST|Not stable|
|blep (v)|BLEP (TN)|
|ZORP (v), ZORPS, ZORPED|To close|
|ZORP (adj)|Not open|
|PLONK (n)|A plate|
|SKREE (v)|To cut|
|AFTER (prep)|Later than|
"""

GRAMMAR: Grammar = {
    # A noun that the dictionary approves only as a noun, used as a verb.
    "The man plonks the frammis.": [
        "The/DET/DT/det/1",
        "man/NOUN/NN/nsubj/2",
        "plonks/VERB/VBZ/ROOT//plonk",
        "the/DET/DT/det/4",
        "frammis/NOUN/NN/dobj/2/frammis",
        "./PUNCT/./punct/2",
    ],
    # An approved noun with an unapproved verb entry, used as a verb.
    "The man frammises the plonk.": [
        "The/DET/DT/det/1",
        "man/NOUN/NN/nsubj/2",
        "frammises/VERB/VBZ/ROOT//frammis",
        "the/DET/DT/det/4",
        "plonk/NOUN/NN/dobj/2/plonk",
        "./PUNCT/./punct/2",
    ],
    # A verb form that the dictionary does not give.
    "The man has gribbelt the plonk.": [
        "The/DET/DT/det/1",
        "man/NOUN/NN/nsubj/3",
        "has/AUX/VBZ/aux/3/have",
        "gribbelt/VERB/VBN/ROOT//gribble",
        "the/DET/DT/det/5",
        "plonk/NOUN/NN/dobj/3/plonk",
        "./PUNCT/./punct/3",
    ],
    # Approved forms.
    "The man gribbled the plonk after the zorped frammis.": [
        "The/DET/DT/det/1",
        "man/NOUN/NN/nsubj/2",
        "gribbled/VERB/VBD/ROOT//gribble",
        "the/DET/DT/det/4",
        "plonk/NOUN/NN/dobj/2/plonk",
        "after/ADP/IN/prep/2/after",
        "the/DET/DT/det/9",
        "zorped/ADJ/JJ/amod/9/zorped",
        "frammis/NOUN/NN/pobj/5/frammis",
        "./PUNCT/./punct/2",
    ],
    # An adjective form that the dictionary does not give.
    "The plonk is wibblyest.": [
        "The/DET/DT/det/1",
        "plonk/NOUN/NN/nsubj/2/plonk",
        "is/AUX/VBZ/ROOT//be",
        "wibblyest/ADJ/JJS/acomp/2/wibbly",
        "./PUNCT/./punct/2",
    ],
    # The unapproved verb "blep" as a noun and as a verb.
    "Blep marks are on the plonk.": [
        "Blep/NOUN/NN/compound/1/blep",
        "marks/NOUN/NNS/nsubj/2/mark",
        "are/AUX/VBP/ROOT//be",
        "on/ADP/IN/prep/2/on",
        "the/DET/DT/det/5",
        "plonk/NOUN/NN/pobj/3/plonk",
        "./PUNCT/./punct/2",
    ],
    "The man can blep the plonk.": [
        "The/DET/DT/det/1",
        "man/NOUN/NN/nsubj/3",
        "can/AUX/MD/aux/3/can",
        "blep/VERB/VB/ROOT//blep",
        "the/DET/DT/det/5",
        "plonk/NOUN/NN/dobj/3/plonk",
        "./PUNCT/./punct/3",
    ],
    # A word that the dictionary approves for a closed class only.
    "The after is wibbly.": [
        "The/DET/DT/det/1",
        "after/NOUN/NN/nsubj/2/after",
        "is/AUX/VBZ/ROOT//be",
        "wibbly/ADJ/JJ/acomp/2/wibbly",
        "./PUNCT/./punct/2",
    ],
    # A word that the dictionary approves only as a verb, used as a noun.
    "The man put the skree code in.": [
        "The/DET/DT/det/1",
        "man/NOUN/NN/nsubj/2",
        "put/VERB/VBD/ROOT//put",
        "the/DET/DT/det/5",
        "skree/NOUN/NN/compound/5/skree",
        "code/NOUN/NN/dobj/2/code",
        "in/ADP/RP/prt/2/in",
        "./PUNCT/./punct/2",
    ],
    # A capital letter in the sentence shows a name.
    "The man put the Skree code in.": [
        "The/DET/DT/det/1",
        "man/NOUN/NN/nsubj/2",
        "put/VERB/VBD/ROOT//put",
        "the/DET/DT/det/5",
        "Skree/NOUN/NN/compound/5/skree",
        "code/NOUN/NN/dobj/2/code",
        "in/ADP/RP/prt/2/in",
        "./PUNCT/./punct/2",
    ],
    # The tagger often gives a noun before a noun as an adjective.
    "The plonk edge is wibbly.": [
        "The/DET/DT/det/2",
        "plonk/ADJ/JJ/amod/2/plonk",
        "edge/NOUN/NN/nsubj/3/edge",
        "is/AUX/VBZ/ROOT//be",
        "wibbly/ADJ/JJ/acomp/3/wibbly",
        "./PUNCT/./punct/3",
    ],
    # A heading has no context for the tagger.
    "The man plonks the frammis": [
        "The/DET/DT/det/1",
        "man/NOUN/NN/nsubj/2",
        "plonks/VERB/VBZ/ROOT//plonk",
        "the/DET/DT/det/4",
        "frammis/NOUN/NN/dobj/2/frammis",
    ],
    # The tagger can give the first word of an instruction as a noun.
    "Skree the plonk edge.": [
        "Skree/NOUN/NN/ROOT//skree",
        "the/DET/DT/det/3",
        "plonk/NOUN/NN/compound/3/plonk",
        "edge/NOUN/NN/appos/0/edge",
        "./PUNCT/./punct/0",
    ],
    # A sentence of two words is usually a label.
    "Man plonks.": [
        "Man/NOUN/NN/nsubj/1/man",
        "plonks/VERB/VBZ/ROOT//plonk",
        "./PUNCT/./punct/1",
    ],
    # A word with a hyphen is often a compound or a name.
    "The man has re-gribbelt the plonk.": [
        "The/DET/DT/det/1",
        "man/NOUN/NN/nsubj/3",
        "has/AUX/VBZ/aux/3/have",
        "re-gribbelt/VERB/VBN/ROOT//gribble",
        "the/DET/DT/det/5",
        "plonk/NOUN/NN/dobj/3/plonk",
        "./PUNCT/./punct/3",
    ],
}
INDEX = parse(DICTIONARY)


def _found(text: str, rules: tuple[str, ...]) -> list[Diagnostic]:
    findings = lint_document(tagged(text, GRAMMAR), Options(dictionary=INDEX))
    return [d for d in findings if d.rule_id in rules]


def _texts(text: str, found: list[Diagnostic]) -> list[tuple[str, str]]:
    return [(d.rule_id, text[d.start : d.end]) for d in found]


@pytest.mark.parametrize(
    ("text", "want"),
    [
        ("The man plonks the frammis.", [("STE-1.2", "plonks")]),
        ("The man frammises the plonk.", [("STE-1.2", "frammises")]),
        ("The man gribbled the plonk after the zorped frammis.", []),
        ("The after is wibbly.", []),
        ("The man put the skree code in.", [("STE-1.2", "skree")]),
        ("The man put the Skree code in.", []),
        ("The plonk edge is wibbly.", []),
        ("## The man plonks the frammis\n", []),
        ("Skree the plonk edge.", []),
        ("Man plonks.", []),
    ],
)
def test_part_of_speech(text: str, want: list[tuple[str, str]]) -> None:
    """Check that a word must have a part of speech that the dictionary approves."""
    assert _texts(text, _found(text, ("STE-1.2",))) == want


def test_part_of_speech_is_information() -> None:
    """Check that rule 1.2 gives the info severity, because the tagger can be wrong."""
    assert [d.severity for d in _found("The man plonks the frammis.", ("STE-1.2",))] == ["info"]


def test_part_of_speech_gives_the_alternatives() -> None:
    """Check that the suggestion uses the unapproved entry of the same part of speech."""
    (finding,) = _found("The man frammises the plonk.", ("STE-1.2",))
    assert finding.suggestion == 'Write "gribble".'
    (finding,) = _found("The man plonks the frammis.", ("STE-1.2",))
    assert "noun" in finding.message


@pytest.mark.parametrize(
    ("text", "want"),
    [
        ("The man has gribbelt the plonk.", [("STE-3.1", "gribbelt")]),
        ("The plonk is wibblyest.", [("STE-1.4", "wibblyest")]),
        ("The man has re-gribbelt the plonk.", []),
        ("The man gribbled the plonk after the zorped frammis.", []),
    ],
)
def test_forms(text: str, want: list[tuple[str, str]]) -> None:
    """Check that a verb or an adjective must have a form that the dictionary gives."""
    found = _found(text, ("STE-1.4", "STE-3.1"))
    assert _texts(text, found) == want


def test_forms_suggest_the_listed_forms() -> None:
    """Check that the suggestion names the forms of the dictionary."""
    (finding,) = _found("The man has gribbelt the plonk.", ("STE-3.1",))
    assert finding.suggestion == 'Write "gribble", "gribbles", or "gribbled".'


@pytest.mark.parametrize(
    ("text", "want"),
    [
        ("Blep marks are on the plonk.", []),
        ("The man can blep the plonk.", [0.95]),
    ],
)
def test_grammar_decides_a_verb_only_entry(text: str, want: list[float]) -> None:
    """Check that the grammar removes a noun and confirms a verb for an entry of a verb."""
    assert [d.confidence for d in _found(text, ("STE-1.1",))] == want


def test_rules_need_the_grammar_and_the_dictionary() -> None:
    """Check that the rules give no finding without the grammar or without the dictionary."""
    rules = ("STE-1.2", "STE-1.4", "STE-3.1")
    for text in ("The man plonks the frammis.", "The man has gribbelt the plonk."):
        assert [d for d in lint(text, Options(dictionary=INDEX)) if d.rule_id in rules] == []
        assert [
            d for d in lint_document(tagged(text, GRAMMAR), Options()) if d.rule_id in rules
        ] == []


def test_allowed_words_are_not_reported() -> None:
    """Check that a word of the glossary is not reported."""
    opts = Options(dictionary=INDEX, allow_verbs=["plonk", "gribbelt"])
    for text in ("The man plonks the frammis.", "The man has gribbelt the plonk."):
        found = lint_document(tagged(text, GRAMMAR), opts)
        assert [d for d in found if d.rule_id in ("STE-1.2", "STE-3.1")] == []
