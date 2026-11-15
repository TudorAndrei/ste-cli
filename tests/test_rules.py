# Copyright (c) 2026 Tudor Andrei Dumitrascu
"""Observable rule results and the NLP token contract."""

from __future__ import annotations

import pytest

from ste.checker import lint
from ste.models import DictionaryResult, Options, Preferred
from tests.grammar import StubSyntax
from tests.test_rules_cases import STRUCTURE_CASES, SYNTAX_CASES, VERB_CASES, VerbCase

DICTIONARY_CONFIDENCE = 0.95
ANALYZER_CONFIDENCE = 0.9


@pytest.mark.parametrize("case", VERB_CASES, ids=[str(case["name"]) for case in VERB_CASES])
def test_verb_cases(case: VerbCase) -> None:
    """Check verb cases."""
    text = case["text"]
    got = [{"rule_id": d.rule_id, "text": text[d.start : d.end]} for d in lint(text)]
    assert got == case["expect"]


@pytest.mark.parametrize(
    ("_name", "rule_id", "text", "want", "naming"),
    STRUCTURE_CASES,
    ids=[case[0] for case in STRUCTURE_CASES],
)
def test_structure_cases(
    _name: str, rule_id: str, text: str, want: str | int, *, naming: bool
) -> None:
    """Check structure cases."""
    opts = Options()
    if naming:
        opts.prefer = [
            Preferred("config file", ["settings file", "configuration file"]),
            Preferred("pump", ["frammis"]),
        ]
    got = [d for d in lint(text, opts) if d.rule_id == rule_id]
    if isinstance(want, str):
        assert [text[d.start : d.end] for d in got] == ([want] if want else [])
    else:
        assert len(got) == want


@pytest.mark.parametrize(
    ("_name", "rule_id", "text", "grammar", "want"),
    SYNTAX_CASES,
    ids=[case[0] for case in SYNTAX_CASES],
)
def test_syntax_cases(
    _name: str, rule_id: str, text: str, grammar: dict[str, list[str]], want: str | int
) -> None:
    """Check syntax cases."""
    got = [d for d in lint(text, Options(syntax=StubSyntax(grammar))) if d.rule_id == rule_id]
    assert len(got) == want


@pytest.mark.parametrize(
    ("text", "rule_id", "expected", "suggestion"),
    [
        (
            "Open the valve; then start the pump.",
            "STE-8.1",
            ";",
            "Write two sentences, or use a list.",
        ),
        ("Do not use the pump if it isn't full.", "STE-4.2", "isn't", 'Write "is not".'),
        ("The colour of the centre indicator changed.", "STE-1.14", "colour", 'Write "color".'),
        ("Do a check of the pressure.", "STE-3.7", "Do a check of", 'Write "check".'),
        (
            "Use the correct tool, e.g. the torque wrench.",
            "STE-GR-6",
            "e.g",
            'Write "for example".',
        ),
        ("Utilize the tool in order to start the pump.", "STE-1.1", "Utilize", 'Write "use".'),
    ],
)
def test_finding_spans_and_suggestions(
    text: str, rule_id: str, expected: str, suggestion: str
) -> None:
    """Check finding spans and suggestions."""
    got = [d for d in lint(text) if d.rule_id == rule_id]
    assert text[got[0].start : got[0].end] == expected
    assert got[0].suggestion == suggestion


@pytest.mark.parametrize(
    "text",
    [
        "The gap is 10&nbsp;mm.",
        "The parser's output is correct.",
        "The color of the center indicator is correct.",
        "Open the Colour Manager.",
        "The AeroSpace and Defence Industries Association makes the standard.",
        "Check the pressure.",
        "Install the VS Code extension.",
        "Compare the vs value of the two files.",
    ],
)
def test_valid_word_constructions(text: str) -> None:
    """Check valid word constructions."""
    assert lint(text) == []


def test_length_uses_sentence_type_and_override() -> None:
    """Check length uses sentence type and override."""
    text = " ".join(["one"] * 22) + "."
    assert lint(text) == []
    assert lint(text, Options(mode="strict")) == []
    step = lint("1. " + text)
    assert len(step) == 1
    assert step[0].rule_id == "STE-5.1"
    assert "limit is 20" in step[0].message
    assert lint("1. NOTE: " + text) == []
    custom = lint(text, Options(max_words=10))
    assert len(custom) == 1
    assert "limit is 10" in custom[0].message
    strict = lint("1. " + text, Options(mode="strict"))
    assert strict[0].severity == "error"


def test_options_control_results() -> None:
    """Check options control results."""
    assert len(lint("Leverage the webhook.")) == 1
    assert lint("Leverage the webhook.", Options(allow_verbs=["leverage"])) == []
    assert lint("Open the valve; then start the pump.", Options(disable_rules=["STE-8.1"])) == []
    assert lint("Use the tool, e.g. the wrench.", Options(mode="strict"))[0].severity == "info"
    assert [d.confidence for d in lint("The tool has been available.")] == []
    assert [d.confidence for d in lint("The tool has been available.", Options(mode="strict"))] == [
        0.55
    ]


class TestDictionary:
    """An independent dictionary with selected test meanings."""

    __test__ = False

    def unapproved(self, word: str) -> tuple[DictionaryResult, bool]:
        """Return the independent dictionary entry."""
        if word == "graph":
            return DictionaryResult(only_verb=True, technical_noun=True), True
        if word == "utilize":
            return DictionaryResult(alternatives=["use"]), True
        return DictionaryResult(), False


@pytest.mark.parametrize(
    ("text", "want"),
    [
        ("Graph the test results.", 1),
        ("The dependency graph is large.", 0),
        ("The graph is large.", 0),
        ("Look at its graph of the data.", 0),
        ("The tool can graph the results.", 1),
        ("Do not graph the results.", 1),
        ("The parser's graph is large.", 0),
    ],
)
def test_dictionary_distinguishes_noun_phrases(text: str, want: str | int) -> None:
    """Check dictionary distinguishes noun phrases."""
    got = [d for d in lint(text, Options(dictionary=TestDictionary())) if d.rule_id == "STE-1.1"]
    assert len(got) == want


def test_dictionary_alternative_has_priority() -> None:
    """Check dictionary alternative has priority."""
    findings = lint("The utilize option is wrong.", Options(dictionary=TestDictionary()))
    assert len(findings) == 1
    assert findings[0].confidence == DICTIONARY_CONFIDENCE
    assert findings[0].suggestion == 'Write "use".'


def test_passive_syntax_veto_and_confidence() -> None:
    """Check passive syntax veto and confidence."""
    text = "There is measured user demand."
    adjective = [
        "There/PRON/EX/expl/1",
        "is/VERB/VBZ/ROOT/1",
        "measured/ADJ/JJ/amod/4",
        "user/NOUN/NN/compound/4",
        "demand/NOUN/NN/attr/1",
    ]
    assert lint(text, Options(syntax=StubSyntax({text: adjective}))) == []
    passive = [
        "The/DET/DT/det/1",
        "report/NOUN/NN/nsubjpass/3",
        "was/AUX/VBD/auxpass/3",
        "approved/VERB/VBN/ROOT/3",
    ]
    text = "The report was approved."
    got = lint(text, Options(syntax=StubSyntax({text: passive})))
    assert got[0].confidence == ANALYZER_CONFIDENCE


def test_paragraph_sentence_limit() -> None:
    """Check paragraph sentence limit."""
    assert lint("One. Two. Three. Four. Five. Six.\n") == []
    findings = lint("One. Two. Three. Four. Five. Six. Seven.\n")
    assert len(findings) == 1
    assert findings[0].rule_id == "STE-6.6"
    assert lint("- One.\n- Two.\n- Three.\n- Four.\n- Five.\n- Six.\n- Seven.\n") == []
    assert lint("One. Two. Three. Four.\n\nFive. Six. Seven. Eight.\n") == []


def test_simple_commands_after_sentence_boundaries() -> None:
    """Check simple commands after sentence boundaries."""
    assert lint("Open the settings file. Then read the configuration file.\n") == []


@pytest.mark.parametrize(
    ("command", "spec", "extra"),
    [
        (
            "Atomically replace the file.",
            [
                "Atomically/ADV/RB/advmod/1",
                "replace/VERB/VB/ROOT/1",
                "the/DET/DT/det/3",
                "file/NOUN/NN/dobj/1",
            ],
            {},
        ),
        (
            "Do not touch the surface.",
            [
                "Do/AUX/VBP/aux/2",
                "not/PART/RB/neg/2",
                "touch/VERB/VB/ROOT/2",
                "the/DET/DT/det/4",
                "surface/NOUN/NN/dobj/2",
            ],
            {},
        ),
        (
            "Delete quarantined files.",
            ["Delete/ADJ/JJ/amod/2", "quarantined/ADJ/JJ/amod/2", "files/NOUN/NNS/ROOT/2"],
            {
                "please delete quarantined files.": [
                    "please/INTJ/UH/intj/1",
                    "delete/VERB/VB/ROOT/1",
                    "quarantined/ADJ/JJ/amod/3",
                    "files/NOUN/NNS/dobj/1",
                ]
            },
        ),
    ],
)
def test_command_forms_in_mixed_procedures(
    command: str, spec: list[str], extra: dict[str, list[str]]
) -> None:
    """Check command forms in mixed procedures."""
    text = f"1. Open the valve.\n2. {command}\n3. Installation is necessary.\n"
    grammar = {
        "Open the valve.": ["Open/VERB/VB/ROOT/0", "the/DET/DT/det/2", "valve/NOUN/NN/dobj/0"],
        command: spec,
        "Installation is necessary.": [
            "Installation/NOUN/NN/nsubj/1",
            "is/AUX/VBZ/ROOT/1",
            "necessary/ADJ/JJ/acomp/1",
        ],
        **extra,
    }
    findings = [
        d for d in lint(text, Options(syntax=StubSyntax(grammar))) if d.rule_id == "STE-5.3"
    ]
    assert [text[d.start : d.end] for d in findings] == ["Installation"]


def test_noun_cluster_allowance_and_character_spans() -> None:
    """Check noun cluster allowance and character spans."""
    text = "Élan: engine fuel pump control unit."
    grammar = {
        text: [
            "Élan/PROPN/NNP/ROOT/0",
            "engine/NOUN/NN/compound/5",
            "fuel/NOUN/NN/compound/5",
            "pump/NOUN/NN/compound/5",
            "control/NOUN/NN/compound/5",
            "unit/NOUN/NN/appos/0",
        ]
    }
    opts = Options(syntax=StubSyntax(grammar))
    findings = [d for d in lint(text, opts) if d.rule_id == "STE-2.1"]
    assert [text[d.start : d.end] for d in findings] == ["Élan: engine fuel pump control unit"]
    # A project can name a technical noun explicitly.
    opts.allow_nouns = ["Élan engine fuel pump control unit"]
    assert not [d for d in lint(text, opts) if d.rule_id == "STE-2.1"]


@pytest.mark.parametrize(
    ("text", "nouns", "prefer", "limit", "want"),
    [
        ("Open the fuel pump control unit.", ["fuel pump control unit"], [], 0, []),
        (
            "Open the fuel pump control unit.",
            ["fuel pump control unit"],
            [],
            3,
            ["fuel pump control unit"],
        ),
        ("Open the fuel pump control unit.", ["fuel pump control unit"], [], 4, []),
        (
            "Open the Fuel Pump Control Unit.",
            ["fuel pump control unit"],
            [],
            3,
            ["Fuel Pump Control Unit"],
        ),
        ("Open the fuel pump.", ["fuel pump"], [], 1, ["fuel pump"]),
        ("Open the air-conditioning system.", ["air-conditioning system"], [], 2, []),
        ("Open the parser.", ["fuel pump control unit"], [], 3, []),
        (
            "Open the config file. Then close the config file.",
            [],
            [Preferred("config file", ["settings file"])],
            1,
            ["config file"],
        ),
    ],
)
def test_short_technical_noun(
    text: str, nouns: list[str], prefer: list[Preferred], limit: int, want: list[str]
) -> None:
    """Check that a configured technical noun obeys the configured word limit."""
    opts = Options(allow_nouns=nouns, prefer=prefer, max_noun_words=limit)
    got = [d for d in lint(text, opts) if d.rule_id == "STE-1.9"]
    assert [text[d.start : d.end] for d in got] == want


@pytest.mark.parametrize(
    ("text", "want"),
    [
        ("> [!CAUTION]\n> Do not touch the blade. The blade can cause injury.\n", ["injury"]),
        ("> [!CAUTION]\n> Do not drop the unit. A fall can cause damage.\n", []),
        ("> [!WARNING]\n> Do not touch the blade. The blade can cause injury.\n", []),
        ("> [!CAUTION]\n> Keep away. Death or injuries can occur.\n", ["Death"]),
    ],
)
def test_caution_that_tells_of_injury(text: str, want: list[str]) -> None:
    """Check that a caution with a risk of injury or death needs a warning label."""
    got = [d for d in lint(text) if d.rule_id == "STE-7.1"]
    assert [text[d.start : d.end] for d in got] == want


def test_text_in_parentheses_is_a_sentence_with_its_own_limit() -> None:
    """Check that the text in parentheses has the limit of its sentence."""
    inner = " ".join(["word"] * 26)
    text = f"Open the valve ({inner}).\n"
    got = [d for d in lint(text) if d.rule_id == "STE-5.1"]
    assert [text[d.start : d.end] for d in got] == [f"({inner})"]
    assert "parentheses" in got[0].message
    short = " ".join(["word"] * 25)
    assert not [d for d in lint(f"Open the valve ({short}).\n") if d.rule_id == "STE-5.1"]
    step = " ".join(["word"] * 21)
    assert [d.rule_id for d in lint(f"1. Open the valve ({step}).\n")] == ["STE-5.1"]
