# Copyright (c) 2026 Tudor Andrei Dumitrascu
"""Verb construction checks."""

from ste.grammar import passive_at
from ste.models import Diagnostic, Document, Options, Sentence
from ste.rules.common import span
from ste.rules.data import (
    ADJECTIVAL_ING,
    ADJECTIVAL_PARTICIPLES,
    BE_FORMS,
    INTERRUPTERS,
    IRREGULAR_PARTICIPLES,
    PERFECT_AUX,
    PHRASAL_VERBS,
    VERB_FORMS,
)

MIN_PARTICIPLE_LENGTH = 3
MIN_ING_LENGTH = 4
MIN_ADVERB_LENGTH = 3
SYNTAX_CONFIDENCE = 0.9
PHRASAL_INDEX: dict[str, list[tuple[list[str], str]]] = {}
for _base, _particles, _suggestion in PHRASAL_VERBS:
    for _form in VERB_FORMS[_base]:
        PHRASAL_INDEX.setdefault(_form, []).append((_particles, _suggestion))


def is_participle(word: str) -> bool:
    """Check for a past participle that is not a compound word."""
    return "-" not in word and (
        word in IRREGULAR_PARTICIPLES or (len(word) > MIN_PARTICIPLE_LENGTH and word.endswith("ed"))
    )


def is_ing_form(word: str) -> bool:
    """Check for an ing-form word that is not a compound."""
    return "-" not in word and len(word) > MIN_ING_LENGTH and word.endswith("ing")


def next_content(s: Sentence, i: int) -> int:
    """Find the next token after adverbs and other interrupters."""
    while i < len(s.tokens) and (
        s.tokens[i].lower in INTERRUPTERS
        or (len(s.tokens[i].lower) > MIN_ADVERB_LENGTH and s.tokens[i].lower.endswith("ly"))
    ):
        i += 1
    return i


def joined(s: Sentence, first: int, last: int) -> bool:
    """Check that adjacent tokens form one unmasked construction."""
    if last <= first:
        return False
    for k in range(first, last):
        start, end = s.tokens[k].end - s.start, s.tokens[k + 1].start - s.start
        if start < 0 or end > len(s.text) or start > end:
            return False
        if any(c.isascii() and c.isalnum() for c in s.text[start:end]):
            return False
    return True


def perfect_diag(s: Sentence, first: int, last: int, confidence: float) -> Diagnostic:
    """Make a finding for a perfect-tense construction."""
    return Diagnostic(
        "STE-3.4",
        f'"{span(s, first, last)}" is a perfect tense. '
        "ASD-STE100 approves only the simple present, the simple past, and the simple future.",
        "warning",
        confidence,
        s.tokens[first].start,
        s.tokens[last].end,
        "Write the simple past or the simple present.",
    )


def match_perfect(s: Sentence, i: int) -> Diagnostic | None:
    """Find a perfect-tense construction at one token."""
    j = next_content(s, i + 1)
    if j >= len(s.tokens) or not joined(s, i, j) or s.tokens[j].lower == "to":
        return None
    if s.tokens[j].lower == "been":
        k = next_content(s, j + 1)
        if k < len(s.tokens) and (
            is_participle(s.tokens[k].lower) or is_ing_form(s.tokens[k].lower)
        ):
            return perfect_diag(s, i, k, 0.9)
        return perfect_diag(s, i, j, 0.55)
    if is_participle(s.tokens[j].lower):
        return perfect_diag(s, i, j, 0.9)
    return None


def match_progressive(s: Sentence, i: int, opts: Options) -> Diagnostic | None:
    """Find a progressive verb construction at one token."""
    j = next_content(s, i + 1)
    if j >= len(s.tokens) or not joined(s, i, j):
        return None
    w = s.tokens[j].lower
    if not is_ing_form(w) or w in ADJECTIVAL_ING or opts.allowed(w) or w == "being":
        return None
    return Diagnostic(
        "STE-3.5",
        f'"{span(s, i, j)}" is a progressive form. '
        'ASD-STE100 does not approve the "-ing" verb forms.',
        "warning",
        0.9,
        s.tokens[i].start,
        s.tokens[j].end,
        "Write the simple present or the simple past.",
    )


def match_passive(s: Sentence, i: int, opts: Options) -> tuple[Diagnostic, bool] | None:
    """Find a passive construction and whether it has a by-agent."""
    j = next_content(s, i + 1)
    if j >= len(s.tokens) or not joined(s, i, j):
        return None
    w = s.tokens[j].lower
    if not is_participle(w) or opts.allowed(w):
        return None
    agent = j + 1 < len(s.tokens) and s.tokens[j + 1].lower == "by"
    if w in ADJECTIVAL_PARTICIPLES and not agent:
        return None
    confidence = 0.95 if agent else 0.85 if w in IRREGULAR_PARTICIPLES else 0.7
    passive = passive_at(s, s.tokens[j].start - s.start)
    if passive is False:
        return None
    if passive and confidence < SYNTAX_CONFIDENCE:
        confidence = SYNTAX_CONFIDENCE
    return Diagnostic(
        "STE-3.6",
        f'"{span(s, i, j)}" is the passive voice.',
        "warning",
        confidence,
        s.tokens[i].start,
        s.tokens[j].end,
        "Write the active voice. Name the person or the part that does the task.",
    ), agent


def match_phrasal(s: Sentence, i: int, opts: Options) -> Diagnostic | None:
    """Find a phrasal verb that starts at one token."""
    for particles, suggestion in PHRASAL_INDEX.get(s.tokens[i].lower, []):
        if [t.lower for t in s.tokens[i + 1 : i + 1 + len(particles)]] != particles:
            continue
        last = i + len(particles)
        phrase = span(s, i, last)
        if opts.allowed(phrase) or opts.allowed(s.tokens[i].lower):
            continue
        return Diagnostic(
            "STE-9.3",
            f'"{phrase}" is a phrasal verb. ASD-STE100 does not approve phrasal verbs.',
            "warning",
            0.85,
            s.tokens[i].start,
            s.tokens[last].end,
            suggestion,
        )
    return None


def verbs(doc: Document, opts: Options) -> list[Diagnostic]:
    """Find perfect, passive, progressive, and phrasal verb forms."""
    out = []
    for s in doc.sentences:
        perfect = []
        passive = []
        other = []
        for i, t in enumerate(s.tokens):
            if opts.allowed(t.lower):
                continue
            if t.lower in PERFECT_AUX and (d := match_perfect(s, i)):
                perfect.append(d)
            if t.lower in BE_FORMS:
                if d := match_progressive(s, i, opts):
                    other.append(d)
                if p := match_passive(s, i, opts):
                    passive.append(p)
            if d := match_phrasal(s, i, opts):
                other.append(d)
        out.extend(perfect)
        out.extend(
            d
            for d, agent in passive
            if agent or not any(d.start >= outer.start and d.end <= outer.end for outer in perfect)
        )
        out.extend(other)
    return out
