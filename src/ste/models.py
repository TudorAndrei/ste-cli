# Copyright (c) 2026 Tudor Andrei Dumitrascu
"""Shared checker data. Internal offsets count Python characters.

Report writers convert offsets and columns to UTF-8 bytes for CLI compatibility.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from collections.abc import Sequence


@dataclass
class Diagnostic:
    """One finding with its source span and suggested correction."""

    rule_id: str
    message: str
    severity: str
    confidence: float
    start: int
    end: int
    suggestion: str = ""


@dataclass
class SyntaxToken:
    """One analyzer token with its grammar and its offset in the sentence text.

    ``index`` and ``head`` count analyzer tokens, and the analyzer can split
    a word or give a token for a punctuation mark.
    """

    index: int
    text: str
    pos: str
    tag: str
    dep: str
    head: int
    start: int
    lemma: str = ""
    # False when the analyzer has a word list and the word is not in it, as
    # for the name of a tool such as "oxfmt". The tagger can give such a
    # word any part of speech.
    in_lexicon: bool = True


@dataclass
class Token:
    """One prose word with its source span and, when known, its grammar.

    The grammar fields stay empty until an analyzer fills the document. A rule
    must read ``Sentence.tagged`` before it reads them. ``ste.grammar.align``
    gives the rule that joins the analyzer tokens to these tokens.

    The grammar fields are not arguments of the constructor. Thus a token
    without grammar keeps only its four source fields in memory.
    """

    text: str
    lower: str
    start: int
    end: int
    # The universal part of speech, such as "VERB", "NOUN", or "ADJ".
    pos: str = field(default="", init=False)
    # The Penn Treebank tag, such as "VB", "VBN", or "NNS".
    tag: str = field(default="", init=False)
    # The dependency relation to the head, such as "nsubj" or "ROOT".
    dep: str = field(default="", init=False)
    # The index of the head in ``Sentence.tokens``. The root is its own head.
    # The value is -1 when the head is not a word of the sentence.
    head: int = field(default=-1, init=False)
    # The base form, such as "close" for "closed". It is empty when the
    # analyzer has no lemmatizer.
    lemma: str = field(default="", init=False)


@dataclass
class Sentence:
    """One sentence and its Markdown block information."""

    text: str
    start: int
    end: int
    tokens: list[Token] = field(default_factory=list)
    words: int = 0
    procedural: bool = False
    note: bool = False
    block: int = 0
    kind: str = "paragraph"
    admonition: str = ""
    first: bool = False
    last: bool = False
    # All analyzer tokens of the sentence, punctuation included, with offsets
    # from the start of ``text``. It is empty when the grammar is not known.
    syntax: list[SyntaxToken] = field(default_factory=list)
    # The inline code spans of the sentence, with offsets from the start of
    # ``text``. The analyzer does not read their text.
    code: list[tuple[int, int]] = field(default_factory=list)

    @property
    def tagged(self) -> bool:
        """Return whether an analyzer gave the grammar of this sentence."""
        return bool(self.syntax)

    def limit(self) -> int:
        """Return the word limit for this sentence type."""
        return 20 if self.procedural and not self.note else 25


@dataclass
class Document:
    """Source text, masked prose, and parsed sentences."""

    source: str
    masked: str
    sentences: list[Sentence] = field(default_factory=list)
    # True after ``ste.grammar.annotate`` ran on this document.
    analyzed: bool = False

    def word_count(self) -> int:
        """Return the total word count of the prose."""
        return sum(s.words for s in self.sentences)


@dataclass
class Preferred:
    """The project name for an item and its other names."""

    name: str
    instead: list[str] = field(default_factory=list)


@dataclass
class DictionaryResult:
    """The dictionary result for one unapproved word."""

    alternatives: list[str] = field(default_factory=list)
    only_verb: bool = False
    technical_noun: bool = False


class WordEntry(Protocol):
    """One entry of an imported dictionary: a word, as one part of speech."""

    @property
    def word(self) -> str:
        """The headword, in lower case."""
        ...

    @property
    def approved(self) -> bool:
        """Whether the dictionary approves the word as this part of speech."""
        ...

    @property
    def pos(self) -> str:
        """The part of speech of the dictionary, such as "n", "v", or "adj"."""
        ...

    @property
    def alternatives(self) -> list[str]:
        """The approved words to use instead."""
        ...

    @property
    def forms(self) -> list[str]:
        """The other forms that the dictionary gives, in lower case."""
        ...


class Dictionary(Protocol):
    """The word lookup contract for an imported dictionary."""

    def unapproved(self, word: str) -> tuple[DictionaryResult, bool]:
        """Look up an unapproved word and its permitted alternatives."""
        ...

    def lookup(self, word: str, /) -> Sequence[WordEntry]:
        """Get each entry of a headword."""
        ...

    def by_form(self, form: str, /) -> Sequence[WordEntry]:
        """Get each entry that gives this word as one of its other forms."""
        ...


class Syntax(Protocol):
    """The sentence grammar contract for an NLP analyzer."""

    def grammar(self, sentence: str) -> tuple[list[SyntaxToken], bool]:
        """Return sentence tokens and whether the grammar is known."""
        ...

    def grammar_many(self, sentences: list[str]) -> list[list[SyntaxToken]]:
        """Return the tokens of each sentence, in order. An empty list is not known."""
        ...


@dataclass
class Options:
    """Settings that control checker behavior."""

    mode: str = "flavored"
    max_words: int = 0
    max_noun_words: int = 0
    allow_nouns: list[str] = field(default_factory=list)
    allow_verbs: list[str] = field(default_factory=list)
    # The nouns of a preset, such as "software". They permit a word as the
    # nouns of the user do, but rule STE-1.7 reads only the nouns of the user.
    preset_nouns: list[str] = field(default_factory=list)
    prefer: list[Preferred] = field(default_factory=list)
    disable_rules: list[str] = field(default_factory=list)
    rule_severity: dict[str, str] = field(default_factory=dict)
    min_confidence: float = 0
    warnings_as_errors: bool = False
    dictionary: Dictionary | None = None
    syntax: Syntax | None = None
    _allowed_key: tuple[tuple[str, ...], ...] | None = field(
        default=None, init=False, repr=False, compare=False
    )
    _allowed_words: frozenset[str] = field(
        default=frozenset(), init=False, repr=False, compare=False
    )

    def confidence(self) -> float:
        """Return the minimum confidence for the current mode."""
        return self.min_confidence or (0 if self.mode == "strict" else 0.6)

    def severity(self, rule_id: str, given: str) -> str:
        """Apply rule severity settings and warning promotion."""
        severity = self.rule_severity.get(rule_id, given)
        if (
            rule_id not in self.rule_severity
            and self.mode == "strict"
            and not rule_id.startswith("STE-GR-")
        ):
            severity = "warning" if given == "info" else "error"
        if self.warnings_as_errors and severity == "warning":
            severity = "error"
        return severity

    def allowed(self, word: str) -> bool:
        """Return whether the glossary permits this word."""
        key = (tuple(self.allow_nouns), tuple(self.allow_verbs), tuple(self.preset_nouns))
        if key != self._allowed_key:
            self._allowed_words = frozenset(w.lower() for words in key for w in words)
            self._allowed_key = key
        return word.lower() in self._allowed_words
