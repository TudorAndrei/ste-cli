# Copyright (c) 2026 Tudor Andrei Dumitrascu
"""The grammar layer: analyzer tokens joined to the words of the checker.

The checker and the analyzer divide a sentence in different ways. The
checker keeps only words, and it keeps "isn't" and "parser's" as one word.
spaCy gives a token for each punctuation mark, and it divides "isn't" into
"is" and "n't". ``align`` joins the two lists by their character offsets.

A rule reads the grammar of a sentence in one of two forms:

- ``Sentence.syntax`` holds each analyzer token, punctuation included.
- ``Token.pos``, ``tag``, ``dep``, ``head``, and ``lemma`` hold the grammar
  of each word of ``Sentence.tokens``.

``Sentence.tagged`` is true only when the analyzer gave the grammar.
"""

from __future__ import annotations

import re
from dataclasses import replace
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ste.models import Document, Sentence, Syntax, SyntaxToken


def _group_head(group: list[int], syntax: list[SyntaxToken]) -> int:
    """Return the analyzer token that governs the other tokens of a word.

    This is the first token whose head is outside the word, or the root.
    "is" governs "n't" in "isn't", and "parser" governs "'s" in "parser's".
    """
    members = {syntax[k].index for k in group}
    for k in group:
        token = syntax[k]
        if token.head == token.index or token.head not in members:
            return k
    return group[0]


def align(sentence: Sentence, syntax: list[SyntaxToken]) -> None:
    """Fill the grammar of each word of a sentence from analyzer tokens.

    The alignment rule:

    1. A word overlaps an analyzer token when their character spans share
       one character or more. An analyzer token with a negative offset has
       no span, and it agrees with no word.
    2. A word that overlaps no analyzer token keeps empty grammar.
    3. A word that overlaps more than one token, such as "isn't", takes the
       grammar of the token that governs the others (``_group_head``).
    4. An analyzer token that covers more than one word gives its grammar to
       each of them.
    5. ``Token.head`` is the index of the nearest ancestor that is a different
       word of the sentence. An ancestor that is a punctuation mark or a
       masked word does not count. The root is its own head, and a word with
       no such ancestor gets -1.
    """
    sentence.syntax = syntax
    words = sentence.tokens
    if not syntax or not words:
        return
    by_index = {t.index: k for k, t in enumerate(syntax)}
    spans = sorted(
        (t.start, t.start + len(t.text), k) for k, t in enumerate(syntax) if t.start >= 0
    )
    groups: list[list[int]] = []
    word_of: dict[int, int] = {}
    first = 0
    for w, word in enumerate(words):
        start, end = word.start - sentence.start, word.end - sentence.start
        while first < len(spans) and spans[first][1] <= start:
            first += 1
        group = []
        k = first
        while k < len(spans) and spans[k][0] < end:
            if spans[k][1] > start:
                group.append(spans[k][2])
                word_of.setdefault(syntax[spans[k][2]].index, w)
            k += 1
        groups.append(group)
    for w, (word, group) in enumerate(zip(words, groups, strict=True)):
        if not group:
            continue
        token = syntax[_group_head(group, syntax)]
        word.pos, word.tag, word.dep, word.lemma = token.pos, token.tag, token.dep, token.lemma
        word.head = _head_word(token, w, syntax, by_index, word_of)


def _head_word(
    token: SyntaxToken,
    w: int,
    syntax: list[SyntaxToken],
    by_index: dict[int, int],
    word_of: dict[int, int],
) -> int:
    seen = set()
    while token.index not in seen:
        seen.add(token.index)
        if token.head == token.index:
            return w if word_of.get(token.index) == w else -1
        parent = by_index.get(token.head)
        if parent is None:
            return -1
        token = syntax[parent]
        if (head := word_of.get(token.index, w)) != w:
            return head
    return -1


_QUOTE_MARKS = re.compile(r"(?<=\n)[ \t]*>[ \t>]*")


def analyzer_text(sentence: Sentence) -> tuple[int, str]:
    """Return the offset and the text that the analyzer reads for a sentence.

    A label such as "**NOTE:**" or "[!WARNING]" is not a part of the sentence,
    and the analyzer reads it as the subject or the root. The text starts after
    the label. Spaces replace the quote marks of each line of a block quote, and
    thus each offset stays the same.
    """
    text = sentence.text
    offset = 0
    if sentence.first and sentence.admonition:
        label = re.match(
            rf"[\s*_>:!\-\[]*{re.escape(sentence.admonition)}(?![a-z])[\s*_\]:!>]*",
            text,
            re.IGNORECASE,
        )
        if label is not None and label.end() < len(text):
            offset = label.end()
    body = _QUOTE_MARKS.sub(lambda m: " " * len(m[0]), text[offset:])
    return offset, body


def annotate(doc: Document, syntax: Syntax) -> None:
    """Fill the grammar of each sentence with one batch request."""
    doc.analyzed = True
    if not doc.sentences:
        return
    texts = [analyzer_text(s) for s in doc.sentences]
    results = syntax.grammar_many([text for _, text in texts])
    for sentence, (offset, _), tokens in zip(doc.sentences, texts, results, strict=True):
        shifted = tokens
        if offset:
            shifted = [replace(t, start=t.start + offset) if t.start >= 0 else t for t in tokens]
        align(sentence, shifted)


_PASSIVE_DEPS = frozenset({"auxpass", "nsubjpass", "csubjpass"})


def passive_at(sentence: Sentence, offset: int) -> bool | None:
    """Return whether the analyzer token at a sentence offset is a passive verb.

    The result is None when the grammar is not known, or when no analyzer
    token starts at the offset.
    """
    verb = next((t.index for t in sentence.syntax if t.start == offset), None)
    if verb is None:
        return None
    return any(t.head == verb and t.dep in _PASSIVE_DEPS for t in sentence.syntax)
