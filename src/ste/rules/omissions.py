# Copyright (c) 2026 Tudor Andrei Dumitrascu
"""An article that the writer omitted (rule 4.2)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from ste.models import Diagnostic

if TYPE_CHECKING:
    from ste.models import Document, Options, Sentence, Token

# A hand check of real text gave a precision of less than 0.9. Thus the
# finding shows only in strict mode, or with a lower --min-confidence.
CONFIDENCE = 0.5
# Nouns that usually have no plural, thus they need no article. The list
# also holds nouns of fixed expressions, such as "take place".
MASS_NOUNS = frozenset(
    {
        "access",
        "accuracy",
        "action",
        "advantage",
        "advice",
        "air",
        "attention",
        "authentication",
        "authorization",
        "automation",
        "bandwidth",
        "behavior",
        "behaviour",
        "boilerplate",
        "care",
        "chaos",
        "code",
        "coercion",
        "color",
        "colour",
        "comparison",
        "compliance",
        "compression",
        "concurrency",
        "config",
        "configuration",
        "consent",
        "content",
        "context",
        "control",
        "coverage",
        "credit",
        "damage",
        "data",
        "debt",
        "deployment",
        "development",
        "disablement",
        "documentation",
        "effect",
        "enablement",
        "encryption",
        "energy",
        "enforcement",
        "english",
        "equipment",
        "evidence",
        "execution",
        "fallback",
        "feedback",
        "fuel",
        "fun",
        "functionality",
        "grammar",
        "guidance",
        "hardware",
        "harm",
        "health",
        "heat",
        "help",
        "history",
        "inference",
        "information",
        "inheritance",
        "input",
        "insight",
        "integration",
        "interest",
        "knowledge",
        "latency",
        "light",
        "logic",
        "lookup",
        "love",
        "luck",
        "maintenance",
        "management",
        "markup",
        "memory",
        "metadata",
        "money",
        "news",
        "noise",
        "note",
        "oil",
        "output",
        "overhead",
        "ownership",
        "parallelism",
        "part",
        "percentage",
        "performance",
        "permission",
        "place",
        "power",
        "precedence",
        "precision",
        "pressure",
        "priority",
        "privacy",
        "progress",
        "prose",
        "punctuation",
        "quality",
        "recall",
        "removal",
        "research",
        "responsibility",
        "reuse",
        "revenue",
        "risk",
        "room",
        "safety",
        "scope",
        "security",
        "sense",
        "software",
        "space",
        "speed",
        "spelling",
        "storage",
        "stuff",
        "style",
        "support",
        "syntax",
        "temperature",
        "text",
        "throughput",
        "time",
        "track",
        "traffic",
        "traversal",
        "trouble",
        "usage",
        "validation",
        "water",
        "weather",
        "weight",
        "work",
    }
)
# Suffixes of abstract nouns that usually have no plural.
MASS_SUFFIXES = (
    "ing",
    "ness",
    "ity",
    "ism",
    "ics",
    "ware",
    "tion",
    "sion",
    "sis",
    "ency",
    "ance",
)
# Nouns with an abstract suffix that are usually countable.
COUNT_NOUNS = frozenset(
    {
        "application",
        "collection",
        "condition",
        "connection",
        "definition",
        "dependency",
        "description",
        "exception",
        "expression",
        "extension",
        "function",
        "instance",
        "instruction",
        "notification",
        "option",
        "partition",
        "position",
        "question",
        "section",
        "session",
        "solution",
        "string",
        "thing",
        "transaction",
        "version",
    }
)
# Nouns that act as pronouns, such as "none", or as part of a fixed expression.
PRONOUN_NOUNS = frozenset(
    {"none", "nothing", "something", "everything", "anything", "nobody", "matter", "rest"}
)
# A shorter word is often the name of a tool, such as "git" or "uv".
MIN_LENGTH = 4
# Words that take the place of an article.
DETERMINER_DEPS = frozenset({"det", "poss", "nummod", "predet"})
# Parts of speech of the words between a determiner and its noun.
MODIFIER_POS = frozenset({"ADJ", "ADV", "NOUN", "PROPN", "VERB"})
# The tags of a verb that can be the root of a full clause.
FINITE_TAGS = frozenset({"VB", "VBZ", "VBP", "VBD", "MD"})
CHECKED_DEPS = frozenset({"nsubj", "nsubjpass", "dobj"})
# A noun before one of these characters names the next element, as in
# "set option `color`".
NAMING_MARKS = "`\"'\u201c\u2018:#0123456789<([{"
# A noun after one of these characters belongs to code, a link, or a quotation.
PREVIOUS_MARKS = "`\"'\u201d\u2019)]"
# A word next to one of these characters is part of a path or an address.
JOINING_MARKS = "/\\:@#_=-"
# Words that tell a quantity, and thus take the place of an article.
QUANTITY_WORDS = frozenset(
    {"more", "less", "much", "enough", "little", "plenty", "most", "few", "many", "several"}
)


def is_clause(s: Sentence) -> bool:
    """Return whether the sentence has a finite verb at its root, and is not a label.

    A list item such as "Concise approach to model definition, using
    composition" has a participle at its root. It is a label.
    """
    return any(t.dep == "ROOT" and t.tag in FINITE_TAGS for t in s.tokens)


def listed(s: Sentence, i: int) -> bool:
    """Return whether the noun starts a list of three or more items."""
    return sum(u.dep == "conj" and u.head == i for u in s.tokens) > 1


def misparsed(s: Sentence, i: int) -> bool:
    """Return whether the next word shows that the noun is not a subject or an object.

    In "Improved error messaging", the noun modifies the next word. In
    "render markdown import the class", the noun is a verb.
    """
    if i + 1 >= len(s.tokens):
        return False
    after = s.tokens[i + 1]
    return after.pos == "NOUN" or after.tag == "VBG" or after.lower in {"the", "a", "an"}


def plain_word(t: Token) -> bool:
    """Return whether the word is a common singular word, and not a name.

    A word with a capital letter can be a name, as in "Vulture finds unused
    code". Thus the rule does not examine it, also at the start of a sentence.
    A word that ends in "s" can be a plural that the tagger did not find.
    """
    text = t.text
    if text.endswith("s") and not text.endswith(("ss", "us", "is")):
        return False
    return text.isalpha() and text.islower() and len(text) >= MIN_LENGTH


def determiner(t: Token) -> bool:
    """Return whether a word takes the place of an article."""
    return (
        t.dep in DETERMINER_DEPS
        or t.pos in {"DET", "NUM"}
        or t.tag == "PRP$"
        or t.lower in QUANTITY_WORDS
    )


def mass(word: str) -> bool:
    """Return whether a noun usually has no article."""
    if word in COUNT_NOUNS:
        return False
    return word in MASS_NOUNS or word in PRONOUN_NOUNS or word.endswith(MASS_SUFFIXES)


def left_words(s: Sentence, i: int) -> list[int]:
    """Return the words before word i that depend on it, directly or not."""
    out = []
    for k in range(i - 1, -1, -1):
        node, seen = k, set()
        while node not in seen and 0 <= node < len(s.tokens) and node != i:
            seen.add(node)
            node = s.tokens[node].head
        if node == i:
            out.append(k)
    return out


def next_mark(source: str, end: int) -> str:
    """Return the first character after a position that is not a space."""
    rest = source[end : end + 40].lstrip(" \t")
    return rest[:1]


def attached(source: str, t: Token) -> bool:
    """Return whether the word is part of a path, an address, or an identifier."""
    before = source[t.start - 1 : t.start] if t.start else ""
    after = source[t.end : t.end + 2]
    if before and before in JOINING_MARKS:
        return True
    return bool(after) and (
        after[0] in JOINING_MARKS or (after[0] == "." and after[1:].strip() != "")
    )


def named(source: str, s: Sentence, i: int, left: list[int]) -> bool:
    """Return whether code, a link, a quotation, or a possessive comes with the noun."""
    t = s.tokens[i]
    if next_mark(source, t.end) in NAMING_MARKS:
        return True
    start = s.tokens[min(left, default=i)].start
    before = source[max(0, start - 40) : start].rstrip(" \t")
    return before.endswith(("'s", "\u2019s")) or before[-1:] in PREVIOUS_MARKS


def candidate(source: str, s: Sentence, i: int) -> bool:
    """Return whether the word at i is a common singular noun, as a subject or an object."""
    t = s.tokens[i]
    if t.pos != "NOUN" or t.tag != "NN" or t.dep not in CHECKED_DEPS:
        return False
    if not plain_word(t) or mass(t.lower) or attached(source, t):
        return False
    # The object of an "-ing" form, as in "running ruff", is often a name.
    head = s.tokens[t.head] if 0 <= t.head < len(s.tokens) else None
    if head is None or head.pos not in {"VERB", "AUX"} or head.tag == "VBG":
        return False
    # "line by line" is a fixed expression.
    fixed = [u.lower for u in s.tokens[i + 1 : i + 3]] == ["by", t.lower]
    return not (fixed or listed(s, i) or misparsed(s, i))


def needs_article(source: str, s: Sentence, i: int) -> bool:
    """Return whether the word at i is a singular count noun with no article."""
    if not candidate(source, s, i):
        return False
    left = left_words(s, i)
    # The parser can attach a determiner to a different word, as in "at
    # least one labeled example". Thus also read the word before the
    # modifiers of the noun.
    k = i - 1
    while k >= 0 and s.tokens[k].pos in MODIFIER_POS and s.tokens[k].lower not in QUANTITY_WORDS:
        k -= 1
    if any(determiner(s.tokens[j]) for j in [*left, k] if j >= 0):
        return False
    return not named(source, s, i, left)


def omitted_article(doc: Document, _opts: Options) -> list[Diagnostic]:
    """Report a singular count noun, as a subject or an object, with no article.

    The rule needs the analyzer. Without it, the rule gives no finding. A
    heading, a table cell, and a list item with no verb are labels, and the
    rule does not examine them.
    """
    out = []
    for s in doc.sentences:
        if not s.tagged or s.kind in {"heading", "table-cell"} or not is_clause(s):
            continue
        for i, t in enumerate(s.tokens):
            if needs_article(doc.source, s, i):
                out.append(
                    Diagnostic(
                        "STE-4.2",
                        f'The noun "{t.text}" has no article.',
                        "info",
                        CONFIDENCE,
                        t.start,
                        t.end,
                        f'Write "the {t.lower}" or "a {t.lower}", if the noun is not a name.',
                    )
                )
    return out
