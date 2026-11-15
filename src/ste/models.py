"""Shared checker data. Internal offsets count Python characters.

Report writers convert offsets and columns to UTF-8 bytes for CLI compatibility.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol


@dataclass
class Diagnostic:
    rule_id: str
    message: str
    severity: str
    confidence: float
    start: int
    end: int
    suggestion: str = ""


@dataclass
class Token:
    text: str
    lower: str
    start: int
    end: int


@dataclass
class Sentence:
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
        return 20 if self.procedural and not self.note else 25


@dataclass
class Document:
    source: str
    masked: str
    sentences: list[Sentence] = field(default_factory=list)

    def word_count(self) -> int:
        return sum(s.words for s in self.sentences)


@dataclass
class Preferred:
    name: str
    instead: list[str] = field(default_factory=list)


@dataclass
class DictionaryResult:
    alternatives: list[str] = field(default_factory=list)
    only_verb: bool = False
    technical_noun: bool = False


class Dictionary(Protocol):
    def unapproved(self, word: str) -> tuple[DictionaryResult, bool]: ...


@dataclass
class SyntaxToken:
    index: int
    text: str
    pos: str
    tag: str
    dep: str
    head: int
    start: int


class Syntax(Protocol):
    def grammar(self, sentence: str) -> tuple[list[SyntaxToken], bool]: ...
    def passive_at(self, sentence: str, offset: int) -> tuple[bool, bool]: ...


@dataclass
class Options:
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

    def confidence(self) -> float:
        return self.min_confidence or (0 if self.mode == "strict" else 0.6)

    def severity(self, rule_id: str, given: str) -> str:
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
        return word.lower() in {w.lower() for w in self.allow_nouns + self.allow_verbs}
