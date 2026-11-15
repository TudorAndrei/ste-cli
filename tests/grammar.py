# Copyright (c) 2026 Tudor Andrei Dumitrascu
"""Build tagged documents for rule tests, without spaCy.

A test gives the grammar of each sentence as a list of tokens. A token is a
string ``"text/POS/TAG/dep/head"`` or ``"text/POS/TAG/dep/head/lemma"``, or a
tuple with the same fields. ``head`` is the index of the head token in the
same list, and an empty head makes the token its own head (the root). The
helper finds the offset of each token in the sentence, in order.

Two forms give the same grammar to the rules:

    from ste.checker import lint, lint_document
    from ste.models import Options
    from tests.grammar import StubSyntax, tagged

    grammar = {
        "Open the valve.": ["Open/VERB/VB/ROOT/0", "the/DET/DT/det/2",
                            "valve/NOUN/NN/dobj/0", "./PUNCT/./punct/0"],
    }
    doc = tagged("Open the valve.", grammar)
    assert doc.sentences[0].tagged
    assert doc.sentences[0].tokens[2].dep == "dobj"
    findings = lint_document(doc, Options())

    # Or let the checker ask the stub, as it asks a real analyzer:
    findings = lint("Open the valve.", Options(syntax=StubSyntax(grammar)))

A sentence that is not in the dictionary stays untagged, as when the
analyzer fails. The key is the sentence text without spaces at its ends.
Use the second form when a rule asks the analyzer for a text that is not a
sentence of the document, such as rule STE-5.3.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from ste.document import parse
from ste.grammar import annotate
from ste.models import Document, SyntaxToken

type Spec = str | tuple[str, ...]
type Grammar = Mapping[str, Sequence[Spec]]

_FIELDS = 5


def syntax_tokens(sentence: str, spec: Sequence[Spec]) -> list[SyntaxToken]:
    """Convert a token specification to analyzer tokens of a sentence."""
    out = []
    offset = 0
    for i, item in enumerate(spec):
        # A tuple can hold a token that contains a slash.
        fields = item.split("/") if isinstance(item, str) else list(item)
        text, pos, tag, dep, head = fields[:_FIELDS]
        lemma = fields[_FIELDS] if len(fields) > _FIELDS else ""
        start = sentence.index(text, offset)
        offset = start + len(text)
        out.append(SyntaxToken(i, text, pos, tag, dep, int(head) if head else i, start, lemma))
    return out


class StubSyntax:
    """An analyzer that gives a fixed grammar for each known sentence."""

    def __init__(self, grammar: Grammar) -> None:
        """Keep the grammar of each sentence, by its text."""
        self.spec = grammar

    def grammar(self, sentence: str) -> tuple[list[SyntaxToken], bool]:
        """Return the specified grammar for one sentence."""
        if sentence.strip() not in self.spec:
            return [], False
        return syntax_tokens(sentence, self.spec[sentence.strip()]), True

    def grammar_many(self, sentences: list[str]) -> list[list[SyntaxToken]]:
        """Return the specified grammar for each sentence."""
        return [self.grammar(sentence)[0] for sentence in sentences]


def tagged(text: str, grammar: Grammar) -> Document:
    """Parse Markdown and fill each sentence of the grammar."""
    doc = parse(text)
    annotate(doc, StubSyntax(grammar))
    return doc
