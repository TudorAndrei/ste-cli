# Copyright (c) 2026 Tudor Andrei Dumitrascu
"""Read a dictionary from the user's copy of ASD-STE100.

This package contains no copy of the ASD dictionary.
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path

from platformdirs import user_data_path

from ste.models import DictionaryResult

VERSION = 1
MIN_ALTERNATIVE_LENGTH = 2
MIN_TABLE_CELLS = 2
_HEADWORD = re.compile(
    r"([A-Za-z][A-Za-z'\u2019\-]*(?:\s+[A-Za-z][A-Za-z'\u2019\-]*)*)\s*\(([a-z]+)\)"
)
_ALTERNATIVE = re.compile(r"\b([A-Z][A-Z'\u2019\-]+(?:\s+[A-Z][A-Z'\u2019\-]*)*)\b", re.ASCII)
_PART_TWO = re.compile(r"part\s*2\s*[\u2013-]\s*dictionary", re.IGNORECASE)
_BRACKETED = re.compile(r"\([^)]*\)|\[[^\]]*\]")


@dataclass
class Entry:
    """Hold one dictionary word and its permitted replacements."""

    word: str
    approved: bool
    pos: str = ""
    alternatives: list[str] = field(default_factory=list)
    technical_noun: bool = False


@dataclass
class Index:
    """Store the imported entries and provide case-insensitive lookup."""

    source: str
    words: list[Entry] = field(default_factory=list)
    version: int = VERSION
    _by_word: dict[str, list[Entry]] = field(default_factory=dict, repr=False)

    def lookup(self, word: str) -> list[Entry]:
        """Get all entries for a word without regard to letter case."""
        if not self._by_word:
            for entry in self.words:
                self._by_word.setdefault(entry.word.lower(), []).append(entry)
        return self._by_word.get(word.lower(), [])

    def unapproved(self, word: str) -> tuple[DictionaryResult, bool]:
        """Get replacement advice when no entry approves the word."""
        entries = self.lookup(word)
        if not entries or any(e.approved for e in entries):
            return DictionaryResult(), False
        return DictionaryResult(
            alternatives=list(dict.fromkeys(a for e in entries for a in e.alternatives)),
            only_verb=all(e.pos == "v" for e in entries),
            technical_noun=any(e.technical_noun for e in entries),
        ), True

    def stats(self) -> dict[str, int]:
        """Count the entries and their alternatives."""
        approved = sum(e.approved for e in self.words)
        return {
            "words": len(self.words),
            "approved": approved,
            "unapproved": len(self.words) - approved,
            "alternatives": sum(len(e.alternatives) for e in self.words),
        }

    def save(self, path: str | Path) -> None:
        """Write the private dictionary index with restricted file permissions."""
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        words = []
        for entry in self.words:
            item = asdict(entry)
            for key in ("pos", "alternatives", "technical_noun"):
                if not item[key]:
                    del item[key]
            words.append(item)
        payload = {"version": self.version, "source": self.source, "words": words}
        # The index is private data supplied by the user.
        fd = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(payload, stream, ensure_ascii=False, separators=(",", ":"))
            stream.write("\n")


def default_path() -> Path:
    """Get the user data path, with environment overrides applied."""
    if path := os.environ.get("STE_DICT"):
        return Path(path)
    if base := os.environ.get("XDG_DATA_HOME"):
        return Path(base) / "ste" / "dictionary.json"
    return user_data_path("ste", appauthor=False) / "dictionary.json"


def _alternatives(meaning: str) -> list[str]:
    words = [
        m.group(1).strip().lower() for m in _ALTERNATIVE.finditer(_BRACKETED.sub(" ", meaning))
    ]
    return list(
        dict.fromkeys(
            w
            for w in words
            if len(w) >= MIN_ALTERNATIVE_LENGTH and w not in {"tn", "tv", "ste", "asd"}
        )
    )


def _technical_noun(meaning: str) -> bool:
    return "(TN)" in meaning or "[TN]" in meaning


def _table_row(raw_line: str) -> tuple[str, str] | None:
    line = raw_line.strip()
    if not line.startswith("|") or line.startswith("|---"):
        return None
    cells = line.removeprefix("|").removesuffix("|").split("|")
    return (cells[0], cells[1]) if len(cells) >= MIN_TABLE_CELLS else None


def _row_entries(word: str, meaning: str) -> list[tuple[Entry, bool]] | None:
    matches = list(_HEADWORD.finditer(word))
    if not matches:
        return None
    entries = []
    for n, match in enumerate(matches):
        text, pos = match.group(1).strip(), match.group(2)
        if not text or text.lower() == "word":
            continue
        approved = bool(re.search("[A-Z]", text)) and not re.search("[a-z]", text)
        entry = Entry(text.lower(), approved, pos)
        continues = not approved and n == 0
        if continues:
            entry.alternatives = _alternatives(meaning)
            entry.technical_noun = _technical_noun(meaning)
        entries.append((entry, continues))
    return entries


def _merge_entry(index: Index, seen: dict[tuple[str, str], Entry], entry: Entry) -> Entry:
    key = entry.word, entry.pos
    if key in seen:
        existing = seen[key]
        existing.alternatives = list(dict.fromkeys(existing.alternatives + entry.alternatives))
        existing.approved |= entry.approved
        return existing
    seen[key] = entry
    index.words.append(entry)
    return entry


def parse(markdown: str, source: str = "") -> Index:
    """Read dictionary entries from part two of the supplied text."""
    lines = markdown.split("\n")
    start = next(
        (i for i, line in enumerate(lines) if line.startswith("#") and _PART_TWO.search(line)), None
    )
    if start is None:
        msg = "the text has no part 2, thus it is not the dictionary of ASD-STE100"
        raise ValueError(msg)
    index = Index(source=source)
    seen: dict[tuple[str, str], Entry] = {}
    last: Entry | None = None
    for line in lines[start:]:
        cells = _table_row(line)
        if cells is None:
            continue
        word, meaning = cells
        if not word.strip():
            if last is not None:
                last.alternatives = list(dict.fromkeys(last.alternatives + _alternatives(meaning)))
                last.technical_noun |= _technical_noun(meaning)
            continue
        entries = _row_entries(word, meaning)
        if entries is None:
            continue
        last = None
        for entry, continues in entries:
            existing = _merge_entry(index, seen, entry)
            if continues:
                last = existing
    return _finish(index)


def _finish(index: Index) -> Index:
    if not index.words:
        msg = "the text has no dictionary entry"
        raise ValueError(msg)
    for entry in index.words:
        entry.alternatives = [a for a in entry.alternatives if a != entry.word]
    index.words.sort(key=lambda e: (e.word, e.pos))
    return index


class _InvalidIndexError(ValueError):
    """The imported dictionary index does not meet its data schema."""


def _entry(item: object) -> Entry:
    if (
        not isinstance(item, dict)
        or not isinstance(item.get("word"), str)
        or not isinstance(item.get("approved"), bool)
        or not isinstance(item.get("pos", ""), str)
        or not isinstance(item.get("technical_noun", False), bool)
    ):
        msg = "invalid dictionary entry"
        raise _InvalidIndexError(msg)
    alternatives = item.get("alternatives", [])
    if not isinstance(alternatives, list) or not all(isinstance(a, str) for a in alternatives):
        msg = "invalid dictionary alternatives"
        raise _InvalidIndexError(msg)
    return Entry(**item)


def _contents(raw: dict[str, object]) -> Index:
    words = raw.get("words", [])
    if not isinstance(words, list):
        msg = "words must be a list"
        raise _InvalidIndexError(msg)
    entries = [_entry(item) for item in words]
    source = raw.get("source", "")
    if not isinstance(source, str):
        msg = "source must be a string"
        raise _InvalidIndexError(msg)
    return Index(source=source, words=entries)


def load(path: str | Path | None = None) -> Index | None:
    """Read an optional local index and validate its data."""
    target = Path(path) if path else default_path()
    try:
        raw = json.loads(target.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None
    except (ValueError, UnicodeError) as err:
        msg = f"{target}: {err}"
        raise ValueError(msg) from err
    if (
        not isinstance(raw, dict)
        or type(raw.get("version")) is not int
        or raw.get("version") != VERSION
    ):
        msg = f"{target}: the index has an unsupported version. Import the dictionary again"
        raise ValueError(msg)
    try:
        return _contents(raw)
    except (TypeError, ValueError) as err:
        msg = f"{target}: {err}"
        raise ValueError(msg) from err
