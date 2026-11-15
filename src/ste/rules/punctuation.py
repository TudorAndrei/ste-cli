# Copyright (c) 2026 Tudor Andrei Dumitrascu
"""Hyphens between the words of a compound modifier (rule 8.2)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from ste.models import Diagnostic

if TYPE_CHECKING:
    from ste.models import Document, Options, Sentence, Token

# Adjective and noun pairs that are usually one modifier before a noun.
# The parser attaches the adjective to the last noun, as in "new user
# account". Thus only a known pair can show that the two words go together.
COMPOUND_PAIRS = frozenset(
    {
        *(
            (level, noun)
            for level in ("high", "low")
            for noun in (
                "pressure",
                "temperature",
                "level",
                "speed",
                "voltage",
                "power",
                "quality",
                "frequency",
                "resolution",
                "performance",
                "priority",
                "risk",
                "density",
                "availability",
                "latency",
                "bandwidth",
                "contrast",
            )
        ),
        ("real", "time"),
        ("open", "source"),
        ("third", "party"),
        ("first", "party"),
        ("long", "term"),
        ("short", "term"),
        ("full", "text"),
        ("full", "screen"),
        ("full", "stack"),
        ("full", "time"),
        ("part", "time"),
        ("top", "level"),
        ("first", "class"),
        ("single", "page"),
        ("general", "purpose"),
        ("special", "purpose"),
        ("large", "scale"),
        ("small", "scale"),
        ("fixed", "width"),
        ("fixed", "size"),
        ("variable", "length"),
        ("fixed", "length"),
        ("hot", "air"),
        ("cold", "weather"),
        ("left", "hand"),
        ("right", "hand"),
        ("multi", "user"),
        ("single", "user"),
        ("single", "phase"),
        ("cross", "platform"),
        ("wide", "area"),
        ("local", "area"),
        ("old", "style"),
        ("new", "style"),
        ("zero", "downtime"),
    }
)
# Adjectives and participles that make a modifier with the noun before them,
# as in "user friendly" or "thread safe".
SECOND_WORDS = frozenset(
    {
        "aware",
        "based",
        "compatible",
        "dependent",
        "driven",
        "free",
        "friendly",
        "intensive",
        "oriented",
        "proof",
        "ready",
        "related",
        "resistant",
        "safe",
        "sensitive",
        "specific",
    }
)
# Adverbs that join an adjective or a participle, as in "well known".
JOINING_ADVERBS = frozenset({"well", "ill"})
MODIFIER_DEPS = frozenset({"compound", "amod", "npadvmod", "nmod"})
# The largest number that is a quantity, and not a year, before a noun.
MAX_QUANTITY = 1000
# A shorter word, such as "mm" or "kb", is the symbol of a unit.
MIN_WORD = 3


def adjacent(source: str, first: Token, second: Token) -> bool:
    """Return whether only spaces are between two words."""
    return not source[first.end : second.start].strip()


def joined(tokens: list[Token], i: int) -> bool:
    """Return whether the words at i and i + 1 make one modifier of the word at i + 2.

    The three words must be a modifier, a modifier, and a noun, in that
    order. The grammar must show that the first word belongs to the second.
    """
    a, b, c = tokens[i], tokens[i + 1], tokens[i + 2]
    if c.pos != "NOUN" or b.head != i + 2:
        return False
    if a.pos == "NOUN" and b.dep == "amod":
        # "user friendly page", "time consuming scan"
        if a.dep == "npadvmod" and a.head == i + 1:
            return b.pos in {"ADJ", "VERB"}
        # The parser can attach the noun to the last word, as in "user
        # friendly panel". Only a known second word shows the relation.
        return a.dep in MODIFIER_DEPS and a.head in {i + 1, i + 2} and b.lower in SECOND_WORDS
    if a.lower in JOINING_ADVERBS and a.dep == "advmod" and a.head == i + 1:
        # "well known problem"
        return b.dep == "amod" and (b.pos == "ADJ" or b.tag == "VBN")
    if a.pos == "NUM" and a.dep == "nummod" and a.head == i + 1:
        # "32 bit integer", "two way switch"
        number = a.lower.replace(",", "")
        # "11 word groups" counts the groups. Thus the noun must be singular.
        return (
            b.tag == "NN"
            and c.tag == "NN"
            and b.dep in MODIFIER_DEPS
            and b.lower.isalpha()
            and len(b.lower) >= MIN_WORD
            and (not number.isdigit() or int(number) < MAX_QUANTITY)
        )
    # "high pressure valve": the parser does not show the relation.
    return (
        a.pos == "ADJ"
        and a.dep == "amod"
        and a.head in {i + 1, i + 2}
        and b.tag == "NN"
        and b.dep in MODIFIER_DEPS
        and (a.lower, b.lower) in COMPOUND_PAIRS
    )


def sentence_hyphens(source: str, s: Sentence) -> list[Diagnostic]:
    """Report each compound modifier of one tagged sentence."""
    out = []
    tokens = s.tokens
    for i in range(len(tokens) - 2):
        if not (
            adjacent(source, tokens[i], tokens[i + 1])
            and adjacent(source, tokens[i + 1], tokens[i + 2])
            and joined(tokens, i)
        ):
            continue
        a, b, c = tokens[i], tokens[i + 1], tokens[i + 2]
        out.append(
            Diagnostic(
                "STE-8.2",
                f'"{a.text} {b.text}" is one modifier of "{c.text}".',
                "info",
                0.7,
                a.start,
                b.end,
                f'Write "{a.text}-{b.text} {c.text}".',
            )
        )
    return out


def compound_hyphen(doc: Document, _opts: Options) -> list[Diagnostic]:
    """Report two words that modify a noun as one unit, with no hyphen.

    The rule needs the analyzer. Without it, the rule gives no finding.
    """
    out = []
    for s in doc.sentences:
        if s.tagged:
            out.extend(sentence_hyphens(doc.source, s))
    return out
