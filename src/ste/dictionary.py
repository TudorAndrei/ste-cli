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
_HEADWORD = re.compile(r"([A-Za-z][A-Za-z'’\-]*(?:\s+[A-Za-z][A-Za-z'’\-]*)*)\s*\(([a-z]+)\)")
_ALTERNATIVE = re.compile(r"\b([A-Z][A-Z'’\-]+(?:\s+[A-Z][A-Z'’\-]*)*)\b", re.ASCII)
_PART_TWO = re.compile(r"part\s*2\s*[–-]\s*dictionary", re.IGNORECASE)
_BRACKETED = re.compile(r"\([^)]*\)|\[[^\]]*\]")


@dataclass
class Entry:
    word: str
    approved: bool
    pos: str = ""
    alternatives: list[str] = field(default_factory=list)
    technical_noun: bool = False


@dataclass
class Index:
    source: str
    words: list[Entry] = field(default_factory=list)
    version: int = VERSION
    _by_word: dict[str, list[Entry]] = field(default_factory=dict, repr=False)

    def lookup(self, word: str) -> list[Entry]:
        if not self._by_word:
            for entry in self.words:
                self._by_word.setdefault(entry.word.lower(), []).append(entry)
        return self._by_word.get(word.lower(), [])

    def unapproved(self, word: str) -> tuple[DictionaryResult, bool]:
        entries = self.lookup(word)
        if not entries or any(e.approved for e in entries):
            return DictionaryResult(), False
        return DictionaryResult(
            alternatives=list(dict.fromkeys(a for e in entries for a in e.alternatives)),
            only_verb=all(e.pos == "v" for e in entries),
            technical_noun=any(e.technical_noun for e in entries),
        ), True

    def stats(self) -> dict[str, int]:
        approved = sum(e.approved for e in self.words)
        return {
            "words": len(self.words),
            "approved": approved,
            "unapproved": len(self.words) - approved,
            "alternatives": sum(len(e.alternatives) for e in self.words),
        }

    def save(self, path: str | Path) -> None:
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
        dict.fromkeys(w for w in words if len(w) >= 2 and w not in {"tn", "tv", "ste", "asd"})
    )


def _technical_noun(meaning: str) -> bool:
    return "(TN)" in meaning or "[TN]" in meaning


def parse(markdown: str, source: str = "") -> Index:
    lines = markdown.split("\n")
    start = next(
        (i for i, line in enumerate(lines) if line.startswith("#") and _PART_TWO.search(line)), None
    )
    if start is None:
        raise ValueError("the text has no part 2, thus it is not the dictionary of ASD-STE100")
    index = Index(source=source)
    seen: dict[tuple[str, str], Entry] = {}
    last: Entry | None = None
    for line in lines[start:]:
        line = line.strip()
        if not line.startswith("|") or line.startswith("|---"):
            continue
        cells = line.removeprefix("|").removesuffix("|").split("|")
        if len(cells) < 2:
            continue
        word, meaning = cells[:2]
        if not word.strip():
            if last is not None:
                last.alternatives = list(dict.fromkeys(last.alternatives + _alternatives(meaning)))
                last.technical_noun |= _technical_noun(meaning)
            continue
        matches = list(_HEADWORD.finditer(word))
        if not matches:
            continue
        last = None
        for n, match in enumerate(matches):
            text, pos = match.group(1).strip(), match.group(2)
            if not text or text.lower() == "word":
                continue
            approved = bool(re.search("[A-Z]", text)) and not re.search("[a-z]", text)
            entry = Entry(text.lower(), approved, pos)
            if not approved and n == 0:
                entry.alternatives = _alternatives(meaning)
                entry.technical_noun = _technical_noun(meaning)
            key = entry.word, entry.pos
            if key in seen:
                existing = seen[key]
                existing.alternatives = list(
                    dict.fromkeys(existing.alternatives + entry.alternatives)
                )
                existing.approved |= entry.approved
                if not approved and n == 0:
                    last = existing
            else:
                seen[key] = entry
                index.words.append(entry)
                if not approved and n == 0:
                    last = entry
    if not index.words:
        raise ValueError("the text has no dictionary entry")
    for entry in index.words:
        entry.alternatives = [a for a in entry.alternatives if a != entry.word]
    index.words.sort(key=lambda e: (e.word, e.pos))
    return index


def load(path: str | Path | None = None) -> Index | None:
    target = Path(path) if path else default_path()
    try:
        raw = json.loads(target.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None
    except (ValueError, UnicodeError) as err:
        raise ValueError(f"{target}: {err}") from err
    if (
        not isinstance(raw, dict)
        or type(raw.get("version")) is not int
        or raw.get("version") != VERSION
    ):
        raise ValueError(
            f"{target}: the index has an unsupported version. Import the dictionary again"
        )
    try:
        words = raw.get("words", [])
        if not isinstance(words, list):
            raise ValueError("words must be a list")
        entries = []
        for item in words:
            if (
                not isinstance(item, dict)
                or not isinstance(item.get("word"), str)
                or not isinstance(item.get("approved"), bool)
            ):
                raise ValueError("invalid dictionary entry")
            if not isinstance(item.get("pos", ""), str) or not isinstance(
                item.get("technical_noun", False), bool
            ):
                raise ValueError("invalid dictionary entry")
            alternatives = item.get("alternatives", [])
            if not isinstance(alternatives, list) or not all(
                isinstance(a, str) for a in alternatives
            ):
                raise ValueError("invalid dictionary alternatives")
            entries.append(Entry(**item))
        source = raw.get("source", "")
        if not isinstance(source, str):
            raise ValueError("source must be a string")
        return Index(source=source, words=entries)
    except (TypeError, ValueError) as err:
        raise ValueError(f"{target}: {err}") from err
