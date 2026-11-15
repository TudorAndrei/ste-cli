# Copyright (c) 2026 Tudor Andrei Dumitrascu
"""Sentence length, punctuation, and contractions."""

import re

from ste.document import count_words
from ste.models import Diagnostic, Document, Options, Sentence
from ste.rules.data import CONTRACTION_EXPANSIONS, S_CONTRACTIONS


def parenthesized(masked: str, s: Sentence) -> list[tuple[int, int]]:
    """Return the outer parenthesis groups of a sentence, with their marks."""
    groups = []
    depth = 0
    start = 0
    for i in range(s.start, s.end):
        if masked[i] == "(":
            if depth == 0:
                start = i
            depth += 1
        elif masked[i] == ")" and depth:
            depth -= 1
            if depth == 0:
                groups.append((start, i + 1))
    return groups


def sentence_length(doc: Document, opts: Options) -> list[Diagnostic]:
    """Report sentences, and text in parentheses, that exceed their word limit."""
    out = []
    for s in doc.sentences:
        limit = opts.max_words if opts.max_words > 0 else s.limit()
        kind = "instruction" if s.procedural and not s.note else "sentence"
        # Rule 8.5: the text in parentheses is also a sentence of its own.
        for start, end in parenthesized(doc.masked, s):
            words = count_words(doc.masked, start + 1, end - 1)
            if words > limit:
                out.append(
                    Diagnostic(
                        "STE-5.1",
                        f"The text in parentheses has {words} words. The limit is {limit} words.",
                        "warning",
                        0.9,
                        start,
                        end,
                        "Write the text in parentheses as a different sentence.",
                    )
                )
        if s.words > limit:
            out.append(
                Diagnostic(
                    "STE-5.1",
                    f"The {kind} has {s.words} words. The limit is {limit} words.",
                    "warning",
                    0.9,
                    s.start,
                    s.end,
                    "Divide the sentence into two or more sentences.",
                )
            )
    return out


def semicolons(doc: Document, _opts: Options) -> list[Diagnostic]:
    """Report prose semicolons that are not part of an HTML entity."""
    out = []
    for s in doc.sentences:
        for i in range(s.start, s.end):
            if doc.masked[i] != ";":
                continue
            # An entity can have at most ten characters between & and ;.
            if re.search(r"&[A-Za-z0-9#]{1,10}$", doc.masked[max(s.start, i - 11) : i]):
                continue
            out.append(
                Diagnostic(
                    "STE-8.1",
                    "The semicolon is the one punctuation mark that ASD-STE100 does not approve.",
                    "warning",
                    1.0,
                    i,
                    i + 1,
                    "Write two sentences, or use a list.",
                )
            )
    return out


def contractions(doc: Document, _opts: Options) -> list[Diagnostic]:
    """Report contracted verb forms."""
    out = []
    suffixes = ("n't", "'re", "'ve", "'ll", "'m", "'d")
    for s in doc.sentences:
        for t in s.tokens:
            if t.lower not in S_CONTRACTIONS and not any(
                t.lower.endswith(end) and len(t.lower) > len(end) for end in suffixes
            ):
                continue
            full = CONTRACTION_EXPANSIONS.get(t.lower)
            suggestion = f'Write "{full}".' if full else "Write the full form."
            out.append(
                Diagnostic(
                    "STE-4.2",
                    f'The contraction "{t.text}" is not approved.',
                    "warning",
                    0.98,
                    t.start,
                    t.end,
                    suggestion,
                )
            )
    return out
