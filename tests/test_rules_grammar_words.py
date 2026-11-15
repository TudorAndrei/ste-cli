# Copyright (c) 2026 Tudor Andrei Dumitrascu
"""Word checks that read the part of speech and the dependencies."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from ste.checker import lint, lint_document
from ste.models import Diagnostic, Options
from ste.rules.grammar_words import PHRASAL_LIST_CONFIDENCE, PHRASAL_OTHER_CONFIDENCE
from tests.grammar import Spec, tagged

if TYPE_CHECKING:
    from collections.abc import Sequence

TURN_OFF = "Turn the pump off."
TURN_OFF_SPEC = [
    "Turn/VERB/VB/ROOT//turn",
    "the/DET/DT/det/2/the",
    "pump/NOUN/NN/dobj/0/pump",
    "off/ADP/RP/prt/0/off",
    "./PUNCT/./punct/0/.",
]
LOG_IN = "Log in to the server."
LOG_IN_SPEC = [
    "Log/VERB/VB/ROOT//log",
    "in/ADP/RP/prt/0/in",
    "to/ADP/IN/prep/0/to",
    "the/DET/DT/det/4/the",
    "server/NOUN/NN/pobj/2/server",
    "./PUNCT/./punct/0/.",
]
INSTALLATION = "Do an installation of the software."
INSTALLATION_SPEC = [
    "Do/VERB/VB/ROOT//do",
    "an/DET/DT/det/2/an",
    "installation/NOUN/NN/dobj/0/installation",
    "of/ADP/IN/prep/2/of",
    "the/DET/DT/det/5/the",
    "software/NOUN/NN/pobj/3/software",
    "./PUNCT/./punct/0/.",
]


def found(
    text: str, spec: Sequence[Spec], rule_id: str, opts: Options | None = None
) -> list[Diagnostic]:
    """Lint one tagged sentence and keep the findings of one rule."""
    doc = tagged(text, {text: spec})
    return [d for d in lint_document(doc, opts or Options()) if d.rule_id == rule_id]


def texts(text: str, findings: list[Diagnostic]) -> list[str]:
    """Return the source text of each finding."""
    return [text[d.start : d.end] for d in findings]


def test_a_particle_after_the_object_is_a_phrasal_verb() -> None:
    """Check that the parser joins a verb to a particle after its object."""
    findings = found(TURN_OFF, TURN_OFF_SPEC, "STE-9.3")
    assert texts(TURN_OFF, findings) == ["Turn the pump off"]
    assert findings[0].suggestion == 'Write "stop" or "de-energize".'
    assert findings[0].confidence == PHRASAL_LIST_CONFIDENCE


def test_a_phrasal_verb_outside_the_list() -> None:
    """Check that a verb with a particle is a phrasal verb with lower confidence."""
    findings = found(LOG_IN, LOG_IN_SPEC, "STE-9.3")
    assert texts(LOG_IN, findings) == ["Log in"]
    assert findings[0].confidence == PHRASAL_OTHER_CONFIDENCE


def test_a_listed_phrasal_verb_gives_one_finding() -> None:
    """Check that the word list and the parser do not report the same words."""
    text = "Shut down the engine."
    spec = [
        "Shut/VERB/VB/ROOT//shut",
        "down/ADP/RP/prt/0/down",
        "the/DET/DT/det/3/the",
        "engine/NOUN/NN/dobj/0/engine",
        "./PUNCT/./punct/0/.",
    ]
    assert texts(text, found(text, spec, "STE-9.3")) == ["Shut down"]


def test_a_preposition_is_not_a_particle() -> None:
    """Check that a verb with a prepositional phrase gives no finding."""
    text = "Look at the gauge."
    spec = [
        "Look/VERB/VB/ROOT//look",
        "at/ADP/IN/prep/0/at",
        "the/DET/DT/det/3/the",
        "gauge/NOUN/NN/pobj/1/gauge",
        "./PUNCT/./punct/0/.",
    ]
    assert found(text, spec, "STE-9.3") == []


def test_a_particle_that_the_parser_joins_to_the_object() -> None:
    """Check a listed verb when the parser gives its particle to the object."""
    text = "Look the API key up in the settings page."
    spec = [
        "Look/VERB/VB/ROOT//look",
        "the/DET/DT/det/2/the",
        "API/NOUN/NN/nsubj/3/api",
        "key/NOUN/NN/ccomp/0/key",
        "up/ADP/RP/prt/3/up",
        "in/ADP/IN/prep/3/in",
        "the/DET/DT/det/7/the",
        "settings/NOUN/NNS/pobj/5/setting",
        "page/NOUN/NN/advmod/0/page",
        "./PUNCT/./punct/0/.",
    ]
    findings = found(text, spec, "STE-9.3")
    assert texts(text, findings) == ["Look the API key up"]
    assert findings[0].suggestion == 'Write "find".'


def test_an_adverb_particle_of_a_listed_verb() -> None:
    """Check that "away" after the object of "throw" is a particle."""
    text = "Throw the old logs away."
    spec = [
        "Throw/VERB/VB/ROOT//throw",
        "the/DET/DT/det/3/the",
        "old/ADJ/JJ/amod/3/old",
        "logs/NOUN/NNS/dobj/0/log",
        "away/ADV/RB/advmod/0/away",
        "./PUNCT/./punct/0/.",
    ]
    assert texts(text, found(text, spec, "STE-9.3")) == ["Throw the old logs away"]


def test_an_adverb_for_a_state_is_not_a_particle() -> None:
    """Check that "on" for a state, and a verb outside the list, give no finding."""
    keep = "Keep the light on."
    keep_spec = [
        "Keep/VERB/VB/ROOT//keep",
        "the/DET/DT/det/2/the",
        "light/NOUN/NN/dobj/0/light",
        "on/ADV/RB/advmod/0/on",
        "./PUNCT/./punct/0/.",
    ]
    move = "Move the API key up in the list."
    move_spec = [
        "Move/VERB/VB/ROOT//move",
        "the/DET/DT/det/2/the",
        "API/NOUN/NN/compound/3/api",
        "key/NOUN/NN/dobj/0/key",
        "up/ADP/RP/prt/3/up",
        "in/ADP/IN/prep/3/in",
        "the/DET/DT/det/7/the",
        "list/NOUN/NN/pobj/5/list",
        "./PUNCT/./punct/0/.",
    ]
    keep_prt = [item.replace("on/ADV/RB/advmod", "on/ADP/RP/prt") for item in keep_spec]
    assert found(keep, keep_spec, "STE-9.3") == []
    assert found(keep, keep_prt, "STE-9.3") == []
    assert found(move, move_spec, "STE-9.3") == []


def test_up_to_an_amount_is_not_a_particle() -> None:
    """Check that "up to five" gives a limit, also when the parser reads a particle."""
    text = "Give up to five seconds."
    spec = [
        "Give/VERB/VB/ROOT//give",
        "up/ADP/RP/prt/0/up",
        "to/PART/TO/quantmod/3/to",
        "five/NUM/CD/nummod/4/five",
        "seconds/NOUN/NNS/dobj/0/second",
        "./PUNCT/./punct/0/.",
    ]
    assert found(text, spec, "STE-9.3") == []


def test_a_separated_phrasal_verb_needs_the_grammar() -> None:
    """Check that the word list alone does not report a separated form."""
    assert [d for d in lint(TURN_OFF, Options()) if d.rule_id == "STE-9.3"] == []


def test_an_empty_verb_with_an_action_noun() -> None:
    """Check that the parser finds a noun for an action outside the word list."""
    findings = found(INSTALLATION, INSTALLATION_SPEC, "STE-3.7")
    assert texts(INSTALLATION, findings) == ["Do an installation"]
    assert findings[0].suggestion == 'Write the verb "install".'


def test_a_passive_action_noun() -> None:
    """Check that the subject of a passive empty verb is an action noun."""
    text = "The inspection was performed by the team."
    spec = [
        "The/DET/DT/det/1/the",
        "inspection/NOUN/NN/nsubjpass/3/inspection",
        "was/AUX/VBD/auxpass/3/be",
        "performed/VERB/VBN/ROOT//perform",
        "by/ADP/IN/agent/3/by",
        "the/DET/DT/det/6/the",
        "team/NOUN/NN/pobj/4/team",
        "./PUNCT/./punct/3/.",
    ]
    findings = found(text, spec, "STE-3.7")
    assert texts(text, findings) == ["inspection was performed"]


def test_carry_out_an_action_noun() -> None:
    """Check that "carry out" is an empty verb only with its particle."""
    text = "Carry out an inspection of the valve."
    spec = [
        "Carry/VERB/VB/ROOT//carry",
        "out/ADP/RP/prt/0/out",
        "an/DET/DT/det/3/an",
        "inspection/NOUN/NN/dobj/0/inspection",
        "of/ADP/IN/prep/3/of",
        "the/DET/DT/det/6/the",
        "valve/NOUN/NN/pobj/4/valve",
        "./PUNCT/./punct/0/.",
    ]
    assert texts(text, found(text, spec, "STE-3.7")) == ["Carry out an inspection"]


def test_an_action_noun_with_a_full_verb() -> None:
    """Check that a verb with its own meaning keeps an action noun."""
    text = "Read the description of the pump."
    spec = [
        "Read/VERB/VB/ROOT//read",
        "the/DET/DT/det/2/the",
        "description/NOUN/NN/dobj/0/description",
        "of/ADP/IN/prep/2/of",
        "the/DET/DT/det/5/the",
        "pump/NOUN/NN/pobj/3/pump",
        "./PUNCT/./punct/0/.",
    ]
    assert found(text, spec, "STE-3.7") == []


def test_make_takes_only_its_own_nouns() -> None:
    """Check that "make a preparation" can make an item, thus no finding."""
    text = "Make a preparation of the mixture."
    spec = [
        "Make/VERB/VB/ROOT//make",
        "a/DET/DT/det/2/a",
        "preparation/NOUN/NN/dobj/0/preparation",
        "of/ADP/IN/prep/2/of",
        "the/DET/DT/det/5/the",
        "mixture/NOUN/NN/pobj/3/mixture",
        "./PUNCT/./punct/0/.",
    ]
    assert found(text, spec, "STE-3.7") == []


def test_a_listed_action_noun_gives_one_finding() -> None:
    """Check that the word list and the parser do not report the same words."""
    text = "Perform an installation of the software."
    spec = ["Perform/VERB/VB/ROOT//perform", *INSTALLATION_SPEC[1:]]
    assert texts(text, found(text, spec, "STE-3.7")) == ["Perform an installation of"]


def test_an_action_noun_needs_the_grammar() -> None:
    """Check that the word list alone does not report an unlisted noun."""
    assert [d for d in lint(INSTALLATION, Options()) if d.rule_id == "STE-3.7"] == []


def test_a_technical_noun_as_a_verb() -> None:
    """Check that a glossary noun with a verb tag gives rule 1.7, as information."""
    text = "Shim the bracket."
    spec = [
        "Shim/VERB/VB/ROOT//shim",
        "the/DET/DT/det/2/the",
        "bracket/NOUN/NN/dobj/0/bracket",
        "./PUNCT/./punct/0/.",
    ]
    opts = Options(allow_nouns=["shim"])
    findings = found(text, spec, "STE-1.7", opts)
    assert texts(text, findings) == ["Shim"]
    assert findings[0].severity == "info"
    assert found(text, spec, "STE-1.7", Options(allow_nouns=["shim"], allow_verbs=["shim"])) == []
    assert found(text, spec, "STE-1.7") == []


def test_a_software_preset_noun_is_also_a_verb() -> None:
    """Check that only a noun that the user lists, and not a preset noun, is rule 1.7."""
    text = "Cache the result."
    spec = [
        "Cache/VERB/VB/ROOT//cache",
        "the/DET/DT/det/2/the",
        "result/NOUN/NN/dobj/0/result",
        "./PUNCT/./punct/0/.",
    ]
    preset = Options(preset_nouns=["cache"])
    listed = Options(allow_nouns=["cache"], preset_nouns=["cache"])
    assert found(text, spec, "STE-1.7", preset) == []
    assert texts(text, found(text, spec, "STE-1.7", listed)) == ["Cache"]


@pytest.mark.parametrize(
    ("text", "spec"),
    [
        (
            "Use the built-in parser.",
            [
                "Use/VERB/VB/ROOT//use",
                "the/DET/DT/det/5/the",
                "built/VERB/VBN/amod/5/build",
                "-/PUNCT/HYPH/punct/2/-",
                "in/ADP/RP/prt/2/in",
                "parser/NOUN/NN/dobj/0/parser",
                "./PUNCT/./punct/0/.",
            ],
        ),
        ("Build:", ["Build/VERB/VB/ROOT//build", ":/PUNCT/:/punct/0/:"]),
        (
            "Keep the build output.",
            [
                "Keep/VERB/VB/ROOT//keep",
                "the/DET/DT/det/3/the",
                "build/VERB/VB/amod/3/build",
                "output/NOUN/NN/dobj/0/output",
                "./PUNCT/./punct/0/.",
            ],
        ),
        (
            "Record the owner, the time, and the build.",
            [
                "Record/VERB/VB/ROOT//record",
                "the/DET/DT/det/2/the",
                "owner/NOUN/NN/dobj/0/owner",
                ",/PUNCT/,/punct/2/,",
                "the/DET/DT/det/5/the",
                "time/NOUN/NN/conj/2/time",
                ",/PUNCT/,/punct/5/,",
                "and/CCONJ/CC/cc/5/and",
                "the/DET/DT/det/9/the",
                "build/VERB/VB/conj/5/build",
                "./PUNCT/./punct/0/.",
            ],
        ),
    ],
)
def test_a_compound_word_or_a_label_is_not_a_verb(text: str, spec: list[Spec]) -> None:
    """Check that a compound, a label, a modifier, and a noun list give no finding."""
    assert found(text, spec, "STE-1.7", Options(allow_nouns=["build"])) == []


def test_a_technical_noun_as_a_noun() -> None:
    """Check that a glossary noun with a noun tag gives no finding."""
    text = "The caches hold the result."
    spec = [
        "The/DET/DT/det/1/the",
        "caches/NOUN/NNS/nsubj/2/cache",
        "hold/VERB/VBP/ROOT//hold",
        "the/DET/DT/det/4/the",
        "result/NOUN/NN/dobj/2/result",
        "./PUNCT/./punct/2/.",
    ]
    assert found(text, spec, "STE-1.7", Options(allow_nouns=["cache"])) == []


def test_a_technical_verb_as_a_noun() -> None:
    """Check that a glossary verb with a noun tag gives rule 1.13."""
    text = "Do the install again."
    spec = [
        "Do/VERB/VB/ROOT//do",
        "the/DET/DT/det/2/the",
        "install/NOUN/NN/dobj/0/install",
        "again/ADV/RB/advmod/0/again",
        "./PUNCT/./punct/0/.",
    ]
    findings = found(text, spec, "STE-1.13", Options(allow_verbs=["install"]))
    assert texts(text, findings) == ["install"]
    assert findings[0].suggestion == 'Write a sentence with "install" as its verb.'


def test_a_technical_word_needs_the_grammar() -> None:
    """Check that the glossary alone gives no part-of-speech finding."""
    findings = lint("Cache the result.", Options(allow_nouns=["cache"]))
    assert not [d for d in findings if d.rule_id in {"STE-1.7", "STE-1.13"}]


def test_a_british_noun_spelling() -> None:
    """Check that the British noun "licence" gives rule 1.14."""
    text = "Buy a licence."
    spec = [
        "Buy/VERB/VB/ROOT//buy",
        "a/DET/DT/det/2/a",
        "licence/NOUN/NN/dobj/0/licence",
        "./PUNCT/./punct/0/.",
    ]
    findings = found(text, spec, "STE-1.14")
    assert texts(text, findings) == ["licence"]
    assert findings[0].message == (
        '"licence" is the British spelling of the noun. American English writes "license".'
    )


def test_a_british_verb_spelling() -> None:
    """Check that the British verb "practise" gives rule 1.14."""
    text = "Practise the steps."
    spec = [
        "Practise/VERB/VB/ROOT//practise",
        "the/DET/DT/det/2/the",
        "steps/NOUN/NNS/dobj/0/step",
        "./PUNCT/./punct/0/.",
    ]
    findings = found(text, spec, "STE-1.14")
    assert texts(text, findings) == ["Practise"]
    assert findings[0].suggestion == 'Write "practice".'


def test_a_british_form_with_the_wrong_part_of_speech() -> None:
    """Check that "dependant" as an adjective is a wrong spelling in both forms."""
    text = "The pump is dependant on the valve."
    spec = [
        "The/DET/DT/det/1/the",
        "pump/NOUN/NN/nsubj/2/pump",
        "is/AUX/VBZ/ROOT//be",
        "dependant/ADJ/JJ/acomp/2/dependant",
        "on/ADP/IN/prep/3/on",
        "the/DET/DT/det/6/the",
        "valve/NOUN/NN/pobj/4/valve",
        "./PUNCT/./punct/2/.",
    ]
    findings = found(text, spec, "STE-1.14")
    assert findings[0].message == '"dependant" is not a correct spelling of the adjective.'
    assert findings[0].suggestion == 'Write "dependent".'


def test_a_part_of_speech_spelling_needs_the_grammar() -> None:
    """Check that the word list alone keeps out a pair that needs a part of speech."""
    assert [d for d in lint("Buy a licence.", Options()) if d.rule_id == "STE-1.14"] == []


def test_a_quoted_spelling_is_a_mention() -> None:
    """Check that a word in quotation marks names the word, and it is not a use."""
    text = 'Do not write "licence" in a document.'
    spec = [
        "Do/AUX/VB/aux/2/do",
        "not/PART/RB/neg/2/not",
        "write/VERB/VB/ROOT//write",
        '"/PUNCT/``/punct/2/"',
        "licence/NOUN/NN/dobj/2/licence",
        "\"/PUNCT/''/punct/2/\"",
        "in/ADP/IN/prep/2/in",
        "a/DET/DT/det/8/a",
        "document/NOUN/NN/pobj/6/document",
        "./PUNCT/./punct/2/.",
    ]
    assert found(text, spec, "STE-1.14") == []


def test_a_capitalized_command_with_an_object_is_a_verb() -> None:
    """Check that a first word with a direct object is a verb, with a name tag too."""
    text = "Shim the bracket."
    spec = [
        "Shim/PROPN/NNP/ROOT//Shim",
        "the/DET/DT/det/2/the",
        "bracket/NOUN/NN/dobj/0/bracket",
        "./PUNCT/./punct/0/.",
    ]
    opts = Options(allow_nouns=["shim"])
    assert texts(text, found(text, spec, "STE-1.7", opts)) == ["Shim"]
    name = ["Shim/PROPN/NNP/ROOT//Shim", "./PUNCT/./punct/0/."]
    assert found("Shim.", name, "STE-1.7", opts) == []
