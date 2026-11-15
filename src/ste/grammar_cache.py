# Copyright (c) 2026 Tudor Andrei Dumitrascu
"""A disk cache of sentence grammar, shared by all runs of the analyzer.

The key is a hash of the sentence text and of the analyzer identity: the
model name, the model version, the pipeline components, and the format of
this cache. A new model or a different pipeline thus never reads an old
result.

The cache is one SQLite file. A transaction makes each write atomic, and
SQLite locks the file, thus two runs at the same time are safe. Each error of
the cache only disables the cache for the run: the analyzer then computes
the grammar again.

``$STE_GRAMMAR_CACHE`` controls the file. The value ``off`` disables the
cache, and a different value is the path of the file.
"""

from __future__ import annotations

import hashlib
import json
import os
import sqlite3
from contextlib import closing, suppress
from pathlib import Path
from typing import TYPE_CHECKING

from platformdirs import user_cache_path

from ste.models import SyntaxToken

if TYPE_CHECKING:
    from collections.abc import Iterable

# Increment this number when the stored token format changes.
FORMAT = 2
# The cache keeps the newest entries up to this number. One entry is about
# 600 bytes, thus the file stays below about 60 MB.
MAX_ENTRIES = 100_000
_DISABLED = {"off", "0", "false", "no"}
_BUSY_SECONDS = 5.0


def default_path() -> Path | None:
    """Return the cache file, or None when the user disabled the cache."""
    value = os.environ.get("STE_GRAMMAR_CACHE")
    if value is not None:
        return None if value.strip().lower() in _DISABLED or not value.strip() else Path(value)
    if base := os.environ.get("XDG_CACHE_HOME"):
        return Path(base) / "ste" / "grammar.sqlite3"
    return user_cache_path("ste", appauthor=False) / "grammar.sqlite3"


def clear(path: Path | None = None) -> bool:
    """Remove the cache file. Return whether a file was there."""
    path = path or default_path()
    if path is None:
        return False
    found = False
    for name in (path, Path(f"{path}-wal"), Path(f"{path}-shm"), Path(f"{path}-journal")):
        with suppress(FileNotFoundError):
            name.unlink()
            found = True
    return found


def _encode(tokens: list[SyntaxToken]) -> str:
    return json.dumps(
        [
            [t.index, t.text, t.pos, t.tag, t.dep, t.head, t.start, t.lemma, t.in_lexicon]
            for t in tokens
        ],
        ensure_ascii=False,
        separators=(",", ":"),
    )


def _decode(value: str) -> list[SyntaxToken]:
    return [SyntaxToken(*row) for row in json.loads(value)]


class GrammarCache:
    """Read and write the grammar of sentences for one analyzer identity."""

    def __init__(self, identity: str, path: Path | None = None) -> None:
        """Open the cache file. A failure leaves the cache disabled."""
        self._identity = f"{FORMAT}\x00{identity}\x00"
        self._db: sqlite3.Connection | None = None
        path = path or default_path()
        if path is None:
            return
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            db = sqlite3.connect(path, timeout=_BUSY_SECONDS, isolation_level=None)
            db.execute("PRAGMA journal_mode=WAL")
            db.execute("CREATE TABLE IF NOT EXISTS grammar (key BLOB PRIMARY KEY, tokens TEXT)")
            self._db = db
        except sqlite3.Error, OSError:
            self._db = None

    def _key(self, text: str) -> bytes:
        return hashlib.blake2b((self._identity + text).encode(), digest_size=16).digest()

    def get_many(self, texts: Iterable[str]) -> dict[str, list[SyntaxToken]]:
        """Return the cached tokens of each text that the cache holds."""
        if self._db is None:
            return {}
        keys = {self._key(text): text for text in texts}
        found: dict[str, list[SyntaxToken]] = {}
        items = list(keys)
        try:
            for i in range(0, len(items), 500):
                chunk = items[i : i + 500]
                marks = ",".join("?" * len(chunk))
                query = f"SELECT key, tokens FROM grammar WHERE key IN ({marks})"  # noqa: S608
                for key, value in self._db.execute(query, chunk):
                    found[keys[key]] = _decode(value)
        except sqlite3.Error, ValueError, TypeError:
            self._disable()
            return {}
        return found

    def put_many(self, results: dict[str, list[SyntaxToken]]) -> None:
        """Write the tokens of each text in one transaction."""
        if self._db is None or not results:
            return
        rows = [(self._key(text), _encode(tokens)) for text, tokens in results.items() if tokens]
        try:
            with self._db:
                self._db.execute("BEGIN IMMEDIATE")
                self._db.executemany("INSERT OR REPLACE INTO grammar VALUES (?, ?)", rows)
        except sqlite3.Error:
            self._disable()

    def close(self) -> None:
        """Remove the oldest entries above the limit and close the file."""
        if self._db is None:
            return
        with suppress(sqlite3.Error), closing(self._db) as db:
            (last,) = db.execute("SELECT COALESCE(MAX(rowid), 0) FROM grammar").fetchone()
            if last > MAX_ENTRIES:
                db.execute("DELETE FROM grammar WHERE rowid <= ?", (last - MAX_ENTRIES,))
        self._db = None

    def _disable(self) -> None:
        if self._db is not None:
            with suppress(sqlite3.Error):
                self._db.close()
        self._db = None
