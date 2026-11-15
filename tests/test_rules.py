"""Observable rule results and the NLP token contract."""

import pytest
from test_rules_cases import STRUCTURE_CASES, SYNTAX_CASES, VERB_CASES

from ste.checker import lint
from ste.models import DictionaryResult, Options, Preferred, SyntaxToken


@pytest.mark.parametrize("case", VERB_CASES, ids=[str(case["name"]) for case in VERB_CASES])
def test_verb_cases(case):
    text = case["text"]
    got = [{"rule_id": d.rule_id, "text": text[d.start : d.end]} for d in lint(text)]
    assert got == case["expect"]


@pytest.mark.parametrize(
    "name,rule_id,text,want,naming", STRUCTURE_CASES, ids=[case[0] for case in STRUCTURE_CASES]
)
def test_structure_cases(name, rule_id, text, want, naming):
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


class SpecSyntax:
    """A token stream fixed independently from the checker rules."""

    def __init__(self, grammar):
        self.spec = grammar

    def passive_at(self, sentence, offset):
        return False, False

    def grammar(self, sentence):
        if sentence.strip() not in self.spec:
            return [], False
        out = []
        offset = 0
        for i, spec in enumerate(self.spec[sentence.strip()]):
            text, pos, tag, dep, head = spec.split("/")
            start = sentence.index(text, offset)
            offset = start + len(text)
            out.append(SyntaxToken(i, text, pos, tag, dep, int(head) if head else i, start))
        return out, True


@pytest.mark.parametrize(
    "name,rule_id,text,grammar,want", SYNTAX_CASES, ids=[case[0] for case in SYNTAX_CASES]
)
def test_syntax_cases(name, rule_id, text, grammar, want):
    got = [d for d in lint(text, Options(syntax=SpecSyntax(grammar))) if d.rule_id == rule_id]
    assert len(got) == want


@pytest.mark.parametrize(
    "text,rule_id,expected,suggestion",
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
def test_finding_spans_and_suggestions(text, rule_id, expected, suggestion):
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
def test_valid_word_constructions(text):
    assert lint(text) == []


def test_length_uses_sentence_type_and_override():
    text = " ".join(["one"] * 22) + "."
    assert lint(text) == []
    assert lint(text, Options(mode="strict")) == []
    step = lint("1. " + text)
    assert len(step) == 1
    assert step[0].rule_id == "STE-5.1"
    assert "limit is 20" in step[0].message
    assert lint("1. NOTE: " + text) == []
    custom = lint(text, Options(max_words=10))
    assert len(custom) == 1 and "limit is 10" in custom[0].message
    strict = lint("1. " + text, Options(mode="strict"))
    assert strict[0].severity == "error"


def test_options_control_results():
    assert len(lint("Leverage the webhook.")) == 1
    assert lint("Leverage the webhook.", Options(allow_verbs=["leverage"])) == []
    assert lint("Open the valve; then start the pump.", Options(disable_rules=["STE-8.1"])) == []
    assert lint("Use the tool, e.g. the wrench.", Options(mode="strict"))[0].severity == "info"
    assert [d.confidence for d in lint("The tool has been available.")] == []
    assert [d.confidence for d in lint("The tool has been available.", Options(mode="strict"))] == [
        0.55
    ]


class TestDictionary:
    __test__ = False

    def unapproved(self, word):
        if word == "graph":
            return DictionaryResult(only_verb=True, technical_noun=True), True
        if word == "utilize":
            return DictionaryResult(alternatives=["use"]), True
        return DictionaryResult(), False


@pytest.mark.parametrize(
    "text,want",
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
def test_dictionary_distinguishes_noun_phrases(text, want):
    got = [d for d in lint(text, Options(dictionary=TestDictionary())) if d.rule_id == "STE-1.1"]
    assert len(got) == want


def test_dictionary_alternative_has_priority():
    findings = lint("The utilize option is wrong.", Options(dictionary=TestDictionary()))
    assert len(findings) == 1
    assert findings[0].confidence == 0.95
    assert findings[0].suggestion == 'Write "use".'


def test_passive_syntax_veto_and_confidence():
    class PassiveSyntax:
        def __init__(self, passive):
            self.passive = passive

        def grammar(self, sentence):
            return [], False

        def passive_at(self, sentence, offset):
            return self.passive, True

    text = "There is measured user demand."
    assert lint(text, Options(syntax=PassiveSyntax(False))) == []
    got = lint("The report was approved.", Options(syntax=PassiveSyntax(True)))
    assert got[0].confidence == 0.9


def test_paragraph_sentence_limit():
    assert lint("One. Two. Three. Four. Five. Six.\n") == []
    findings = lint("One. Two. Three. Four. Five. Six. Seven.\n")
    assert len(findings) == 1 and findings[0].rule_id == "STE-6.6"
    assert lint("- One.\n- Two.\n- Three.\n- Four.\n- Five.\n- Six.\n- Seven.\n") == []
    assert lint("One. Two. Three. Four.\n\nFive. Six. Seven. Eight.\n") == []


def test_simple_commands_after_sentence_boundaries():
    assert lint("Open the settings file. Then read the configuration file.\n") == []


@pytest.mark.parametrize(
    "command,spec,extra",
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
def test_command_forms_in_mixed_procedures(command, spec, extra):
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
        d for d in lint(text, Options(syntax=SpecSyntax(grammar))) if d.rule_id == "STE-5.3"
    ]
    assert [text[d.start : d.end] for d in findings] == ["Installation"]


def test_noun_cluster_allowance_and_character_spans():
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
    opts = Options(syntax=SpecSyntax(grammar))
    findings = [d for d in lint(text, opts) if d.rule_id == "STE-2.1"]
    assert [text[d.start : d.end] for d in findings] == ["Élan: engine fuel pump control unit"]
    # A project can name a technical noun explicitly.
    opts.allow_nouns = ["Élan engine fuel pump control unit"]
    assert not [d for d in lint(text, opts) if d.rule_id == "STE-2.1"]
