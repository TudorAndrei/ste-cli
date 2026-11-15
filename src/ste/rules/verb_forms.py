# Copyright (c) 2026 Tudor Andrei Dumitrascu
"""Verb forms outside the approved tenses, and a participle used as a verb.

Rule 3.2 approves a small set of verb forms: the infinitive, the imperative,
the simple present, the simple past, the simple future, and the past
participle in its permitted uses. ``verb_tense`` reports a modal that makes
a different form, such as a conditional with "would". A perfect, a
progressive, and a passive have their own checks (STE-3.4, STE-3.5, and
STE-3.6), and this module does not report them again.

Rule 3.3 permits a past participle as an adjective, and the passive voice
permits it after "to be". ``participle_use`` reports a participle that the
analyzer reads as the verb of a reduced clause, as in "the file created by
the tool".
"""

from ste.models import Diagnostic, Document, Options, Sentence
from ste.rules.common import quoted, span
from ste.rules.data import DETERMINERS, PERFECT_AUX
from ste.rules.verbs import is_participle, joined, match_perfect, next_content

# Each modal that ASD-STE100 does not approve, and the approved replacement.
UNAPPROVED_MODALS = {
    "would": 'Write the simple present or "will".',
    "should": 'Write a command, or write "must".',
    "shall": 'Write "must", or write "will".',
    "may": 'Write "can".',
    "might": 'Write "can".',
}
SUBJECT_PRONOUNS = frozenset({"i", "you", "he", "she", "it", "we", "they", "there"})
WORD_CONFIDENCE = 0.8
GRAMMAR_CONFIDENCE = 0.9
REDUCED_CLAUSE_DEPS = frozenset({"acl", "advcl"})
VERB_HELPER_DEPS = frozenset({"aux", "auxpass"})
AGENT_CONFIDENCE = 0.8
CLAUSE_CONFIDENCE = 0.7


def tagged_modal(s: Sentence, i: int, j: int, *, near: bool) -> tuple[int, float] | None:
    """Find a modal form from the grammar of the analyzer."""
    head = s.tokens[i].head
    if s.tokens[i].tag != "MD" or head in {-1, i} or s.tokens[head].pos not in {"VERB", "AUX"}:
        return None
    # The span ends at the next word when that word is the verb, or a helper
    # of the verb, as "be" in "would be deployed".
    chain = near and (
        j == head or (s.tokens[j].head == head and s.tokens[j].dep in VERB_HELPER_DEPS)
    )
    return (j if chain else i), GRAMMAR_CONFIDENCE


def modal_verb(s: Sentence, i: int) -> tuple[int, float] | None:
    """Return the last word of a modal form, and the confidence, at one modal."""
    j = next_content(s, i + 1)
    near = j < len(s.tokens) and joined(s, i, j)
    if near and s.tokens[j].lower in PERFECT_AUX and match_perfect(s, j):
        return None
    if s.tagged and s.tokens[i].tag:
        return tagged_modal(s, i, j, near=near)
    # A capital "May" after the start of a sentence is usually a month.
    if not near or (i > 0 and s.tokens[i].text[0].isupper()):
        return None
    word = s.tokens[j].lower
    if word in DETERMINERS or word in SUBJECT_PRONOUNS or not word.isalpha():
        return None
    return j, WORD_CONFIDENCE


def verb_tense(doc: Document, opts: Options) -> list[Diagnostic]:
    """Report a modal verb form that is not one of the approved tenses."""
    out = []
    for s in doc.sentences:
        for i, t in enumerate(s.tokens):
            if t.lower not in UNAPPROVED_MODALS or opts.allowed(t.lower):
                continue
            if (found := modal_verb(s, i)) is None:
                continue
            last, confidence = found
            phrase = span(s, i, last)
            out.append(
                Diagnostic(
                    "STE-3.2",
                    f'"{phrase}" is not an approved verb form. ASD-STE100 approves the '
                    "infinitive, the imperative, and the simple present, past, and future.",
                    "warning",
                    confidence,
                    t.start,
                    s.tokens[last].end,
                    UNAPPROVED_MODALS[t.lower],
                )
            )
    return out


def participle_use(doc: Document, opts: Options) -> list[Diagnostic]:
    """Report a past participle that is the verb of a reduced clause."""
    out = []
    for s in doc.sentences:
        if not s.tagged:
            continue
        for i, t in enumerate(s.tokens):
            if t.tag != "VBN" or t.dep not in REDUCED_CLAUSE_DEPS or opts.allowed(t.lower):
                continue
            start, end = t.start - s.start, t.end - s.start
            if not is_participle(t.lower) or quoted(s.text, start, end):
                continue
            children = [c for c in s.tokens if c.head == i and c is not t]
            if any(c.dep in VERB_HELPER_DEPS for c in children):
                continue
            agent = any(c.dep == "agent" for c in children)
            out.append(
                Diagnostic(
                    "STE-3.3",
                    f'"{t.text}" is a past participle that is used as a verb. '
                    "ASD-STE100 permits a past participle as an adjective, "
                    'or after "to be".',
                    "warning",
                    AGENT_CONFIDENCE if agent else CLAUSE_CONFIDENCE,
                    t.start,
                    t.end,
                    'Write a clause with a subject and a verb, such as "that the tool creates".',
                )
            )
    return out
