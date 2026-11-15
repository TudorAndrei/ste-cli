# Copyright (c) 2026 Tudor Andrei Dumitrascu
"""Checks that use syntax from an NLP analyzer."""

from ste.grammar import analyzer_text
from ste.models import Diagnostic, Document, Options, Sentence, SyntaxToken
from ste.rules.common import quoted
from ste.rules.data import ADJECTIVAL_ING, BE_FORMS, CONDITION_WORDS, GERUND_DEPS

MIN_PROCEDURE_ITEMS = 2
MAX_NOUN_WORDS = 3


def syntax_span(s: Sentence, t: SyntaxToken) -> tuple[int, int]:
    """Convert a sentence token position to a document span."""
    start = s.start + t.start
    end = start + len(t.text)
    return (s.start, s.end) if start < s.start or end > s.end else (start, end)


def procedures(doc: Document) -> list[list[Sentence]]:
    """Group first sentences of consecutive numbered steps."""
    groups: list[list[Sentence]] = []
    previous = -2
    for s in doc.sentences:
        if not s.procedural or s.note or not s.first or s.kind != "list-item" or not s.tokens:
            continue
        if not groups or s.block != previous + 1:
            groups.append([])
        groups[-1].append(s)
        previous = s.block
    return groups


def command_start(s: Sentence, grammar: list[SyntaxToken]) -> int:
    """Find the command after an initial condition or location phrase."""
    if not grammar:
        return -1
    first = grammar[0]
    if first.text.lower() not in CONDITION_WORDS and first.pos not in {"ADP", "SCONJ"}:
        return 0
    comma = s.text.find(",")
    if comma < 0:
        return -1
    return next((i for i, t in enumerate(grammar) if t.start > comma), -1)


def reads_as_command_with_please(s: Sentence, opts: Options, index: int) -> bool:
    """Use explicit command context to resolve an ambiguous first word."""
    if opts.syntax is None:
        return False
    _, text = analyzer_text(s)
    if text and "A" <= text[0] <= "Z":
        text = text[0].lower() + text[1:]
    grammar, ok = opts.syntax.grammar("please " + text)
    return ok and index + 1 < len(grammar) and grammar[index + 1].tag == "VB"


def not_imperative(s: Sentence, grammar: list[SyntaxToken], opts: Options) -> Diagnostic | None:
    """Report a first command word that is not an imperative verb."""
    first = command_start(s, grammar)
    if first < 0 or first >= len(grammar):
        return None
    while first < len(grammar) and grammar[first].pos == "ADV":
        first += 1
    if first >= len(grammar):
        return None
    t = grammar[first]
    if t.tag == "VB" or (t.pos == "VERB" and t.dep == "ROOT"):
        return None
    if (
        t.pos == "AUX"
        and t.dep == "aux"
        and 0 <= t.head < len(grammar)
        and grammar[t.head].tag == "VB"
    ):
        return None
    if t.pos in {"ADJ", "NOUN", "PROPN"} and reads_as_command_with_please(s, opts, first):
        return None
    start, end = syntax_span(s, t)
    return Diagnostic(
        "STE-5.3",
        f'The instruction starts with "{t.text}", which is not a command verb.',
        "warning",
        0.75,
        start,
        end,
        "Start the instruction with the command form of the verb.",
    )


def imperative(doc: Document, opts: Options) -> list[Diagnostic]:
    """Report a descriptive item in a sequence of commands."""
    out = []
    for group in procedures(doc):
        items = []
        commands = 0
        for s in group:
            grammar = s.syntax
            if not grammar:
                continue
            d = not_imperative(s, grammar, opts)
            items.append((s, grammar, d is None))
            commands += d is None
        if len(items) < MIN_PROCEDURE_ITEMS or commands * 2 <= len(items):
            continue
        for s, grammar, command in items:
            if not command and (d := not_imperative(s, grammar, opts)):
                out.append(d)
    return out


def noun_cluster(doc: Document, opts: Options) -> list[Diagnostic]:
    """Report a noun cluster that exceeds its word limit."""
    out = []
    for s in doc.sentences:
        grammar = s.syntax
        i = 0
        while i < len(grammar):
            if grammar[i].pos not in {"NOUN", "PROPN"}:
                i += 1
                continue
            j = i
            while j + 1 < len(grammar) and grammar[j + 1].pos in {"NOUN", "PROPN"}:
                j += 1
            tokens = grammar[i : j + 1]
            phrase = " ".join(t.text for t in tokens)
            if (
                len(tokens) > MAX_NOUN_WORDS
                and not all(t.pos == "PROPN" for t in tokens)
                and not opts.allowed(phrase)
            ):
                start, _ = syntax_span(s, grammar[i])
                _, end = syntax_span(s, grammar[j])
                out.append(
                    Diagnostic(
                        "STE-2.1",
                        f'The noun "{phrase}" has {len(tokens)} words. The limit is 3 words.',
                        "warning",
                        0.8,
                        start,
                        end,
                        "Divide the noun, or write it with a preposition.",
                    )
                )
            i = j + 1
    return out


_DETERMINER_TAGS = frozenset({"DT", "PDT", "PRP$", "WP$", "POS"})


def _has_determiner(t: SyntaxToken, grammar: list[SyntaxToken]) -> bool:
    """Return whether a determiner or a possessive comes before an -ing word.

    "each" in "Make each warning an error" and "its" in "before its cleaning"
    show that the -ing word is a noun, also when the tagger gives a verb.
    """
    return any(
        other.head == t.index
        and other.index < t.index
        and (other.dep in {"det", "poss"} or other.tag in _DETERMINER_TAGS)
        for other in grammar
    )


def gerund(doc: Document, opts: Options) -> list[Diagnostic]:
    """Report an ing-form verb outside a permitted noun or modifier."""
    out = []
    for s in doc.sentences:
        grammar = s.syntax
        for t in grammar:
            if t.tag != "VBG" or t.pos != "VERB" or t.dep not in GERUND_DEPS:
                continue
            word = t.text.lower()
            if (
                opts.allowed(word)
                or word in ADJECTIVAL_ING
                or quoted(s.text, t.start, t.start + len(t.text))
            ):
                continue
            if any(
                other.head == t.index
                and other.dep in {"aux", "auxpass"}
                and other.text.lower() in BE_FORMS
                for other in grammar
            ):
                continue
            if _has_determiner(t, grammar):
                continue
            start, end = syntax_span(s, t)
            out.append(
                Diagnostic(
                    "STE-3.5",
                    f'"{t.text}" is an "-ing" form of a verb.',
                    "warning",
                    0.8,
                    start,
                    end,
                    "Write a sentence with a verb in the simple present or the simple past.",
                )
            )
    return out
