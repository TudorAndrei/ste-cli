# Copyright (c) 2026 Tudor Andrei Dumitrascu
"""Check the grammar layer: alignment, batch requests, and the disk cache."""

from __future__ import annotations

import importlib.util
import io
import json
import re
import sys
from typing import TYPE_CHECKING

import pytest

from ste import grammar_cache
from ste.analyzer import Analyzer, ExternalAnalyzer, SpacyAnalyzer
from ste.checker import lint, lint_document
from ste.cli import run
from ste.document import parse
from ste.grammar import align, analyzer_text, annotate
from ste.grammar_cache import GrammarCache
from ste.models import Options, SyntaxToken
from tests.grammar import StubSyntax, syntax_tokens, tagged

if TYPE_CHECKING:
    from pathlib import Path


def words(text: str, spec: list[str]) -> list[tuple[str, str, str, int]]:
    """Return (word, tag, dep, head word) for each word of one tagged sentence."""
    sentence = tagged(text, {text: spec}).sentences[0]
    return [(t.text, t.tag, t.dep, t.head) for t in sentence.tokens]


def test_a_contraction_takes_the_grammar_of_its_head() -> None:
    """Check that "isn't" takes the grammar of "is", and not of "n't"."""
    spec = [
        "The/DET/DT/det/1",
        "pump/NOUN/NN/nsubj/2",
        "is/AUX/VBZ/ROOT/2",
        "n't/PART/RB/neg/2",
        "full/ADJ/JJ/acomp/2",
        "./PUNCT/./punct/2",
    ]
    assert words("The pump isn't full.", spec) == [
        ("The", "DT", "det", 1),
        ("pump", "NN", "nsubj", 2),
        ("isn't", "VBZ", "ROOT", 2),
        ("full", "JJ", "acomp", 2),
    ]


def test_a_possessive_word_keeps_its_head_outside_the_word() -> None:
    """Check that "parser's" takes the grammar of "parser", and not of "'s"."""
    spec = [
        "The/DET/DT/det/1",
        "parser/NOUN/NN/poss/3",
        "'s/PART/POS/case/1",
        "output/NOUN/NN/nsubj/4",
        "is/AUX/VBZ/ROOT/4",
        "correct/ADJ/JJ/acomp/4",
    ]
    assert words("The parser's output is correct.", spec)[:3] == [
        ("The", "DT", "det", 1),
        ("parser's", "NN", "poss", 2),
        ("output", "NN", "nsubj", 3),
    ]


def test_a_head_that_is_punctuation_goes_to_the_next_word() -> None:
    """Check that a punctuation head gives its own head to the word."""
    spec = [
        "Open/VERB/VB/ROOT/0",
        "it/PRON/PRP/dobj/0",
        "(/PUNCT/-LRB-/punct/0",
        "now/ADV/RB/advmod/2",
        ")/PUNCT/-RRB-/punct/0",
    ]
    assert [w[3] for w in words("Open it (now).", spec)] == [0, 0, 0]


def test_one_analyzer_token_gives_its_grammar_to_each_word() -> None:
    """Check that an analyzer token over two words tags the two words."""
    spec = ["Visit/VERB/VB/ROOT/0", "New York/PROPN/NNP/dobj/0"]
    assert words("Visit New York", spec) == [
        ("Visit", "VB", "ROOT", 0),
        ("New", "NNP", "dobj", 0),
        ("York", "NNP", "dobj", 0),
    ]


def test_a_masked_word_and_an_unknown_sentence_stay_untagged() -> None:
    """Check that code and an unknown sentence get no grammar."""
    text = "Run `ls` now. Stop."
    _, read = analyzer_text(parse(text).sentences[0])
    code = read.split()[1]
    doc = tagged(
        text,
        {read: ["Run/VERB/VB/ROOT/0", f"{code}/NOUN/NN/dobj/0", "now/ADV/RB/advmod/0"]},
    )
    first, second = doc.sentences
    assert first.tagged
    assert [(t.pos, t.dep) for t in first.syntax] == [
        ("VERB", "ROOT"),
        ("X", "dobj"),
        ("ADV", "advmod"),
    ]
    assert [(t.text, t.dep, t.head) for t in first.tokens] == [
        ("Run", "ROOT", 0),
        ("now", "advmod", 0),
    ]
    assert not second.tagged
    assert (second.tokens[0].pos, second.tokens[0].head) == ("", -1)


class NounTagger(Analyzer):
    """An analyzer that gives the noun tag to each part of a text between spaces."""

    def __init__(self) -> None:
        """Start with no text."""
        super().__init__()
        self.seen: list[str] = []

    def analyze(self, text: str) -> list[SyntaxToken]:
        """Give a noun token for each part of the text between spaces."""
        self.seen.append(text)
        return [
            SyntaxToken(i, m[0], "NOUN", "NN", "dep", 0, m.start())
            for i, m in enumerate(re.finditer(r"\S+", text))
        ]


@pytest.mark.parametrize(
    "text",
    [
        "Run `ste lint --format json` now.\n",
        "1. Run `ste lint --format json` now.\n",
        "- Run `ste lint --format json` now.\n",
        "> Run `ste lint --format json` now.\n",
        "# Run `ste lint --format json` now\n",
        "| Step |\n|---|\n| Run `ste lint --format json` now. |\n",
    ],
)
def test_the_analyzer_never_reads_inline_code(text: str) -> None:
    """Check that the text of inline code does not reach the analyzer or a rule."""
    analyzer = NounTagger()
    findings = lint(text, Options(syntax=analyzer))
    assert analyzer.seen
    assert not any("lint" in seen or "json" in seen for seen in analyzer.seen)
    assert [d for d in findings if d.rule_id == "STE-2.1"] == []
    sentence = next(s for s in parse(text).sentences if "Run" in s.text)
    offset, read = analyzer_text(sentence)
    assert len(read) == len(sentence.text) - offset


def test_a_token_without_an_offset_tags_no_word() -> None:
    """Check that a negative analyzer offset agrees with no word."""
    sentence = parse("Read it.").sentences[0]
    align(sentence, [SyntaxToken(0, "Read", "VERB", "VB", "ROOT", 0, -1)])
    assert sentence.tagged
    assert sentence.tokens[0].pos == ""


def test_lemma_and_tuple_specifications() -> None:
    """Check the lemma field and a tuple token of the test helper."""
    text = "The valve closed and/or opened."
    spec = [
        ("The", "DET", "DT", "det", "1"),
        ("valve", "NOUN", "NN", "nsubj", "2", "valve"),
        ("closed", "VERB", "VBD", "ROOT", "", "close"),
        ("and/or", "CCONJ", "CC", "cc", "2"),
        ("opened", "VERB", "VBD", "conj", "2", "open"),
    ]
    tokens = tagged(text, {text: spec}).sentences[0].tokens
    assert [t.lemma for t in tokens] == ["", "valve", "close", "", "", "open"]
    assert [t.head for t in tokens] == [1, 2, 2, 2, 2, 2]
    assert syntax_tokens(text, spec)[3].text == "and/or"


def test_a_tagged_document_needs_no_analyzer() -> None:
    """Check that the rules read a tagged document without an analyzer."""
    text = "The engine fuel pump control unit is clean."
    spec = [
        "The/DET/DT/det/5",
        "engine/NOUN/NN/compound/5",
        "fuel/NOUN/NN/compound/5",
        "pump/NOUN/NN/compound/5",
        "control/NOUN/NN/compound/5",
        "unit/NOUN/NN/nsubj/6",
        "is/AUX/VBZ/ROOT/6",
        "clean/ADJ/JJ/acomp/6",
    ]
    findings = lint_document(tagged(text, {text: spec}), Options())
    assert [d.rule_id for d in findings] == ["STE-2.1"]
    assert lint(text, Options(syntax=StubSyntax({text: spec}))) == findings


class CountingAnalyzer(Analyzer):
    """An analyzer that counts the sentences that reach its model."""

    identity = "counting\x001\x00tagger"

    def __init__(self) -> None:
        """Start the count at zero."""
        super().__init__()
        self.seen: list[str] = []

    def analyze(self, text: str) -> list[SyntaxToken]:
        """Give one noun token for each sentence."""
        self.seen.append(text)
        return [SyntaxToken(0, text, "NOUN", "NN", "ROOT", 0, 0)]


def test_disk_cache_serves_a_second_run() -> None:
    """Check that the second run reads the disk cache and not the model."""
    first = CountingAnalyzer()
    first.grammar_many(["One.", "Two.", "One."])
    first.close()
    assert first.seen == ["One.", "Two."]
    second = CountingAnalyzer()
    assert second.grammar_many(["Two.", "Three."])[0][0].text == "Two."
    second.close()
    assert second.seen == ["Three."]


def test_disk_cache_separates_analyzers(cache_file: Path) -> None:
    """Check that a different model identity does not read an entry."""
    tokens = [
        SyntaxToken(0, "Go", "VERB", "VB", "ROOT", 0, 0, "go"),
        SyntaxToken(1, "oxfmt", "VERB", "VB", "conj", 0, 3, "oxfmt", in_lexicon=False),
    ]
    cache = GrammarCache("a", cache_file)
    cache.put_many({"Go.": tokens})
    assert cache.get_many(["Go."]) == {"Go.": tokens}
    cache.close()
    assert GrammarCache("b", cache_file).get_many(["Go."]) == {}


def test_disk_cache_keeps_the_newest_entries(
    cache_file: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Check that the cache removes the oldest entries above its limit."""
    monkeypatch.setattr("ste.grammar_cache.MAX_ENTRIES", 2)
    cache = GrammarCache("a", cache_file)
    for text in ("One.", "Two.", "Three."):
        cache.put_many({text: [SyntaxToken(0, text, "X", "X", "ROOT", 0, 0)]})
    cache.close()
    assert set(GrammarCache("a", cache_file).get_many(["One.", "Two.", "Three."])) == {
        "Two.",
        "Three.",
    }


def test_disk_cache_can_be_off(monkeypatch: pytest.MonkeyPatch, cache_file: Path) -> None:
    """Check that STE_GRAMMAR_CACHE=off writes no file."""
    monkeypatch.setenv("STE_GRAMMAR_CACHE", "off")
    analyzer = CountingAnalyzer()
    analyzer.grammar_many(["One."])
    analyzer.close()
    assert not cache_file.exists()
    assert grammar_cache.default_path() is None


def test_a_damaged_cache_file_only_disables_the_cache(cache_file: Path) -> None:
    """Check that a file that is not SQLite does not stop the analyzer."""
    cache_file.write_bytes(b"this is not a database" * 100)
    analyzer = CountingAnalyzer()
    assert analyzer.grammar_many(["One."])[0][0].text == "One."
    analyzer.close()


def test_clear_cache_command(cache_file: Path) -> None:
    """Check that "ste analyzer --clear-cache" removes the file."""
    analyzer = CountingAnalyzer()
    analyzer.grammar_many(["One."])
    analyzer.close()
    assert cache_file.exists()
    stdout = io.StringIO()
    status = run(
        ["analyzer", "--clear-cache", "--format=json"], io.StringIO(), stdout, io.StringIO()
    )
    assert status == 0
    assert json.loads(stdout.getvalue())["removed"] is True
    assert not cache_file.exists()


BATCH_SCRIPT = """
import json, sys
print(json.dumps({"ready": True, "model": "batch", "batch": True}), flush=True)
for line in sys.stdin:
    request = json.loads(line)
    if request.get("stop"):
        break
    if "texts" not in request:
        print(json.dumps({"id": request["id"], "error": "only batches"}), flush=True)
        continue
    results = []
    for text in request["texts"]:
        if text.startswith("Bad"):
            results.append({"error": "bad sentence"})
            continue
        first = text.split(" ")[0]
        results.append([{"i": 0, "text": first, "pos": "VERB", "tag": "VB",
                         "dep": "ROOT", "head": 0, "start": 0, "lemma": first.lower()}])
    print(json.dumps({"id": request["id"], "results": results}), flush=True)
"""


def test_external_batch_request(tmp_path: Path) -> None:
    """Check that a batch analyzer gets all sentences of a document in one request."""
    script = tmp_path / "batch.py"
    script.write_text(BATCH_SCRIPT)
    client = ExternalAnalyzer([sys.executable, str(script)])
    try:
        doc = parse("Open the valve. Bad sentence here. Close the valve.")
        annotate(doc, client)
        assert [s.tagged for s in doc.sentences] == [True, False, True]
        assert doc.sentences[2].tokens[0].lemma == "close"
    finally:
        client.close()


@pytest.mark.skipif(
    importlib.util.find_spec("en_core_web_sm") is None,
    reason="optional spaCy model is not installed",
)
def test_spacy_aligns_and_can_load_only_the_tagger() -> None:
    """Check the real model, with the full pipeline and with the tagger alone."""
    text = "The pump isn't full, and the parser's output is correct."
    full = SpacyAnalyzer()
    doc = parse(text)
    annotate(doc, full)
    tokens = {t.text: t for t in doc.sentences[0].tokens}
    assert tokens["isn't"].lemma == "be"
    assert tokens["pump"].head == doc.sentences[0].tokens.index(tokens["isn't"])
    assert tokens["parser's"].dep == "poss"
    tagger = SpacyAnalyzer(frozenset())
    assert "parser" not in tagger.nlp.pipe_names
    assert tagger.identity != full.identity
    grammar, known = tagger.grammar(text)
    assert known
    assert {t.dep for t in grammar} <= {""}
