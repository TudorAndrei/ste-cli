# Copyright (c) 2026 Tudor Andrei Dumitrascu
"""Shared checker data. Internal offsets count Python characters.

Report writers convert offsets and columns to UTF-8 bytes for CLI compatibility.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol


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
class Token:
    """One prose word with its source span."""

    text: str
    lower: str
    start: int
    end: int


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

    def limit(self) -> int:
        """Return the word limit for this sentence type."""
        return 20 if self.procedural and not self.note else 25


@dataclass
class Document:
    """Source text, masked prose, and parsed sentences."""

    source: str
    masked: str
    sentences: list[Sentence] = field(default_factory=list)

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


class Dictionary(Protocol):
    """The word lookup contract for an imported dictionary."""

    def unapproved(self, word: str) -> tuple[DictionaryResult, bool]:
        """Look up an unapproved word and its permitted alternatives."""
        ...


@dataclass
class SyntaxToken:
    """One word with its grammar and position in a sentence."""

    index: int
    text: str
    pos: str
    tag: str
    dep: str
    head: int
    start: int


class Syntax(Protocol):
    """The sentence grammar contract for an NLP analyzer."""

    def grammar(self, sentence: str) -> tuple[list[SyntaxToken], bool]:
        """Return sentence tokens and whether the grammar is known."""
        ...

    def passive_at(self, sentence: str, offset: int) -> tuple[bool, bool]:
        """Return whether a word is passive and whether the answer is known."""
        ...


@dataclass
class Options:
    """Settings that control checker behavior."""

    mode: str = "flavored"
    max_words: int = 0
    allow_nouns: list[str] = field(default_factory=list)
    allow_verbs: list[str] = field(default_factory=list)
    prefer: list[Preferred] = field(default_factory=list)
    disable_rules: list[str] = field(default_factory=list)
    rule_severity: dict[str, str] = field(default_factory=dict)
    min_confidence: float = 0
    warnings_as_errors: bool = False
    dictionary: Dictionary | None = None
    syntax: Syntax | None = None
    _allowed_key: tuple[tuple[str, ...], tuple[str, ...]] | None = field(
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
        key = (tuple(self.allow_nouns), tuple(self.allow_verbs))
        if key != self._allowed_key:
            self._allowed_words = frozenset(w.lower() for w in key[0] + key[1])
            self._allowed_key = key
        return word.lower() in self._allowed_words
