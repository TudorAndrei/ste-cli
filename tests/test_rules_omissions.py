# Copyright (c) 2026 Tudor Andrei Dumitrascu
"""Check the rules for an omitted word (4.2), a hyphen (8.2), and a name (8.6)."""

from __future__ import annotations

from ste.checker import lint, lint_document
from ste.models import Options
from tests.grammar import StubSyntax, tagged

# The omitted article has a low confidence. Only this setting shows it.
ALL = Options(min_confidence=0.01)


def found(text: str, grammar: dict[str, list[str]], rule_id: str) -> list[str]:
    """Return the text of each finding of one rule."""
    doc = tagged(text, grammar)
    return [text[d.start : d.end] for d in lint_document(doc, ALL) if d.rule_id == rule_id]


COVER = {
    "Remove cover from the unit.": [
        "Remove/VERB/VB/ROOT/0",
        "cover/NOUN/NN/dobj/0",
        "from/ADP/IN/prep/0",
        "the/DET/DT/det/4",
        "unit/NOUN/NN/pobj/2",
        "./PUNCT/./punct/0",
    ],
}


def test_a_count_noun_object_with_no_article_is_reported() -> None:
    """Check that an object with no article gives an info finding."""
    text = "Remove cover from the unit."
    got = [d for d in lint_document(tagged(text, COVER), ALL) if d.rule_id == "STE-4.2"]
    assert [(text[d.start : d.end], d.severity) for d in got] == [("cover", "info")]
    assert [
        d for d in lint_document(tagged(text, COVER), Options()) if d.rule_id == "STE-4.2"
    ] == []


def test_an_omitted_article_needs_the_grammar() -> None:
    """Check that the rule gives no finding without the analyzer."""
    assert [d for d in lint("Remove cover from the unit.", ALL) if d.rule_id == "STE-4.2"] == []


def test_a_subject_with_no_article_is_reported() -> None:
    """Check that a singular subject with no article gives a finding."""
    text = "If file is missing, the tool makes it."
    grammar = {
        text: [
            "If/SCONJ/IN/mark/2",
            "file/NOUN/NN/nsubj/2",
            "is/AUX/VBZ/advcl/7",
            "missing/VERB/VBG/acomp/2",
            ",/PUNCT/,/punct/7",
            "the/DET/DT/det/6",
            "tool/NOUN/NN/nsubj/7",
            "makes/VERB/VBZ/ROOT/7",
            "it/PRON/PRP/dobj/7",
            "./PUNCT/./punct/7",
        ]
    }
    assert found(text, grammar, "STE-4.2") == ["file"]


def test_a_noun_with_a_determiner_or_a_number_is_not_reported() -> None:
    """Check the words that take the place of an article."""
    text = "Remove each cover and its seal."
    grammar = {
        text: [
            "Remove/VERB/VB/ROOT/0",
            "each/DET/DT/det/2",
            "cover/NOUN/NN/dobj/0",
            "and/CCONJ/CC/cc/2",
            "its/PRON/PRP$/poss/5",
            "seal/NOUN/NN/conj/2",
            "./PUNCT/./punct/0",
        ]
    }
    assert found(text, grammar, "STE-4.2") == []


def test_a_mass_noun_or_a_plural_is_not_reported() -> None:
    """Check that a noun with no plural, and a plural, need no article."""
    text = "Send data and files."
    grammar = {
        text: [
            "Send/VERB/VB/ROOT/0",
            "data/NOUN/NN/dobj/0",
            "and/CCONJ/CC/cc/1",
            "files/NOUN/NNS/conj/1",
            "./PUNCT/./punct/0",
        ]
    }
    assert found(text, grammar, "STE-4.2") == []


def test_a_heading_and_a_fragment_are_not_reported() -> None:
    """Check that a heading, and a list label with no verb, give no finding."""
    heading = "# Remove cover from the unit\n"
    grammar = {"Remove cover from the unit": COVER["Remove cover from the unit."][:-1]}
    assert found(heading, grammar, "STE-4.2") == []
    label = "- Main valve.\n"
    grammar = {
        "Main valve.": ["Main/ADJ/JJ/amod/1", "valve/NOUN/NN/ROOT/1", "./PUNCT/./punct/1"],
    }
    assert found(label, grammar, "STE-4.2") == []


def test_a_noun_before_code_is_not_reported() -> None:
    """Check that a noun that names the next code element gives no finding."""
    text = "Set option `color` to the value."
    grammar = {
        text: [
            "Set/VERB/VB/ROOT/0",
            "option/NOUN/NN/dobj/0",
            "`color`/NOUN/NN/appos/1",
            "to/ADP/IN/prep/0",
            "the/DET/DT/det/5",
            "value/NOUN/NN/pobj/3",
            "./PUNCT/./punct/0",
        ]
    }
    assert found(text, grammar, "STE-4.2") == []


VALVE = [
    "The/DET/DT/det/3",
    "high/ADJ/JJ/amod/3",
    "pressure/NOUN/NN/compound/3",
    "valve/NOUN/NN/nsubj/4",
    "opens/VERB/VBZ/ROOT/4",
    "./PUNCT/./punct/4",
]


def test_a_known_compound_modifier_needs_a_hyphen() -> None:
    """Check that "high pressure valve" gives an info finding."""
    text = "The high pressure valve opens."
    doc = tagged(text, {text: VALVE})
    got = [d for d in lint_document(doc, Options()) if d.rule_id == "STE-8.2"]
    assert [(text[d.start : d.end], d.severity) for d in got] == [("high pressure", "info")]
    assert "high-pressure" in got[0].suggestion


def test_a_hyphenated_modifier_is_not_reported() -> None:
    """Check that "high-pressure valve" gives no finding."""
    text = "The high-pressure valve opens."
    grammar = {
        text: [
            "The/DET/DT/det/4",
            "high/ADJ/JJ/amod/2",
            "-/PUNCT/HYPH/punct/2",
            "pressure/NOUN/NN/compound/4",
            "valve/NOUN/NN/nsubj/5",
            "opens/VERB/VBZ/ROOT/5",
            "./PUNCT/./punct/5",
        ]
    }
    assert found(text, grammar, "STE-8.2") == []


def test_a_noun_and_an_adjective_that_modify_a_noun_need_a_hyphen() -> None:
    """Check that a noun that modifies an adjective, as in "user friendly", is reported."""
    text = "Make a user friendly page."
    grammar = {
        text: [
            "Make/VERB/VB/ROOT/0",
            "a/DET/DT/det/4",
            "user/NOUN/NN/npadvmod/3",
            "friendly/ADJ/JJ/amod/4",
            "page/NOUN/NN/dobj/0",
            "./PUNCT/./punct/0",
        ]
    }
    assert found(text, grammar, "STE-8.2") == ["user friendly"]


def test_a_number_and_a_unit_that_modify_a_noun_need_a_hyphen() -> None:
    """Check that "32 bit integer" is reported."""
    text = "Use a 32 bit integer."
    grammar = {
        text: [
            "Use/VERB/VB/ROOT/0",
            "a/DET/DT/det/4",
            "32/NUM/CD/nummod/3",
            "bit/NOUN/NN/npadvmod/4",
            "integer/NOUN/NN/dobj/0",
            "./PUNCT/./punct/0",
        ]
    }
    assert found(text, grammar, "STE-8.2") == ["32 bit"]


def test_an_adjective_before_a_noun_cluster_is_not_reported() -> None:
    """Check that "new user account" is not a compound modifier."""
    text = "The new user account opens."
    grammar = {
        text: [
            "The/DET/DT/det/3",
            "new/ADJ/JJ/amod/3",
            "user/NOUN/NN/compound/3",
            "account/NOUN/NN/nsubj/4",
            "opens/VERB/VBZ/ROOT/4",
            "./PUNCT/./punct/4",
        ]
    }
    assert found(text, grammar, "STE-8.2") == []


def test_a_compound_modifier_needs_the_grammar() -> None:
    """Check that the rule gives no finding without the analyzer."""
    assert [d for d in lint("The high pressure valve opens.") if d.rule_id == "STE-8.2"] == []


LONG = (
    "The team at Amazon Web Services wrote the Lambda Runtime Interface Client "
    "for the developers who need a custom image of the function to run on the server today."
)


def test_a_known_second_word_shows_a_modifier_that_the_parser_attached_flat() -> None:
    """Check that "user friendly panel" is reported when "user" modifies "panel"."""
    text = "The pump has a user friendly panel."
    grammar = {
        text: [
            "The/DET/DT/det/1",
            "pump/NOUN/NN/nsubj/2",
            "has/VERB/VBZ/ROOT/2",
            "a/DET/DT/det/6",
            "user/NOUN/NN/nmod/6",
            "friendly/ADJ/JJ/amod/6",
            "panel/NOUN/NN/dobj/2",
            "./PUNCT/./punct/2",
        ]
    }
    assert found(text, grammar, "STE-8.2") == ["user friendly"]


def test_a_number_before_a_plural_noun_counts_the_noun() -> None:
    """Check that "11 word groups" is not reported."""
    text = "It has 11 word groups."
    grammar = {
        text: [
            "It/PRON/PRP/nsubj/1",
            "has/VERB/VBZ/ROOT/1",
            "11/NUM/CD/nummod/3",
            "word/NOUN/NN/compound/4",
            "groups/NOUN/NNS/dobj/1",
            "./PUNCT/./punct/1",
        ]
    }
    assert found(text, grammar, "STE-8.2") == []


def name_grammar() -> dict[str, list[str]]:
    """Return a grammar that marks two names of many words."""
    names = {"Amazon", "Web", "Services", "Lambda", "Runtime", "Interface", "Client"}
    spec = []
    for i, word in enumerate(LONG.rstrip(".").split()):
        pos = "PROPN" if word in names else "NOUN"
        spec.append(f"{word}/{pos}/NN/dep/{0 if i else ''}")
    spec.append("./PUNCT/./punct/0")
    return {LONG: spec}


def test_a_name_of_many_words_counts_as_one_word() -> None:
    """Check that rule 8.6 lowers the count only for a run of names."""
    plain = [d.message for d in lint(LONG) if d.rule_id == "STE-5.1"]
    assert plain == ["The sentence has 29 words. The limit is 25 words."]
    opts = Options(syntax=StubSyntax(name_grammar()))
    assert [d for d in lint(LONG, opts) if d.rule_id == "STE-5.1"] == []


def test_names_separated_by_punctuation_are_different_words() -> None:
    """Check that a comma between two names keeps two words."""
    text = "Open Alpha, Beta."
    grammar = {
        text: [
            "Open/VERB/VB/ROOT/0",
            "Alpha/PROPN/NNP/dobj/0",
            ",/PUNCT/,/punct/1",
            "Beta/PROPN/NNP/conj/1",
            "./PUNCT/./punct/0",
        ]
    }
    opts = Options(max_words=2, syntax=StubSyntax(grammar))
    assert [d.message for d in lint(text, opts) if d.rule_id == "STE-5.1"] == [
        "The sentence has 3 words. The limit is 2 words."
    ]
