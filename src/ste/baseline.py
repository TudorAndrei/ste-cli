# Copyright (c) 2026 Tudor Andrei Dumitrascu
"""Record and consume accepted findings without line-number fingerprints."""

from __future__ import annotations

import json
import posixpath
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

DEFAULT_NAME = ".ste-baseline.json"
Key = tuple[str, str, str]


class _InvalidBaselineError(ValueError):
    def __init__(self, path: str | Path, *, entry: bool = False) -> None:
        """Name the baseline file whose stored data is invalid."""
        detail = "invalid baseline entry" if entry else "invalid baseline"
        super().__init__(f"{path}: {detail}")


def clean(path: str) -> str:
    """Normalize a baseline path to forward slashes."""
    return posixpath.normpath(path.replace("\\", "/"))


def key(file: str, rule_id: str, text: str) -> Key:
    """Make a stable fingerprint independent of line numbers."""
    return file, rule_id, " ".join(text.split())


@dataclass
class Entry:
    """One accepted finding and its occurrence count."""

    file: str
    rule_id: str
    text: str
    count: int = 1


@dataclass
class Result:
    """Findings of one file to record in a baseline."""

    path: str
    findings: list[tuple[str, str]]


@dataclass
class Set:
    """A multiset of findings that a project already accepts."""

    counts: Counter[Key] = field(default_factory=Counter)

    def add(self, file: str, rule_id: str, text: str) -> None:
        """Record one occurrence of a finding."""
        self.counts[key(file, rule_id, text)] += 1

    def take(self, file: str, rule_id: str, text: str) -> bool:
        """Consume one accepted occurrence, if present."""
        fingerprint = key(file, rule_id, text)
        if self.counts[fingerprint] <= 0:
            return False
        self.counts[fingerprint] -= 1
        return True

    def stale(self, files: set[str]) -> int:
        """Count unused accepted findings in the files that a run read."""
        return sum(count for (file, _, _), count in self.counts.items() if file in files)


def read(path: str | Path) -> list[Entry]:
    """Read and validate accepted findings from a baseline file."""
    try:
        raw = json.loads(Path(path).read_text(encoding="utf-8"))
    except FileNotFoundError:
        return []
    except json.JSONDecodeError as err:
        msg = f"{path}: {err}"
        raise ValueError(msg) from err
    if not isinstance(raw, dict) or not isinstance(raw.get("entries", []), list):
        raise _InvalidBaselineError(path)
    entries = []
    for entry in raw.get("entries", []):
        if (
            not isinstance(entry, dict)
            or any(not isinstance(entry.get(k, ""), str) for k in ("file", "rule_id", "text"))
            or type(entry.get("count", 1)) is not int
        ):
            raise _InvalidBaselineError(path, entry=True)
        entries.append(
            Entry(
                clean(entry.get("file", "")),
                entry.get("rule_id", ""),
                entry.get("text", ""),
                max(1, entry.get("count", 1)),
            )
        )
    return entries


def load(path: str | Path) -> Set:
    """Load the accepted findings as a consumable multiset."""
    accepted = Set()
    for entry in read(path):
        accepted.counts[key(entry.file, entry.rule_id, entry.text)] += entry.count
    return accepted


@dataclass
class Merge:
    """Accepted findings to keep or remove during a partial update."""

    kept: int = 0
    removed: int = 0
    entries: list[Entry] = field(default_factory=list)


def plan(path: str | Path, results: list[Result]) -> Merge:
    """Plan a baseline update without changing a file."""
    run = {clean(r.path) for r in results}
    merge = Merge()
    for entry in read(path):
        if entry.file in run:
            continue
        if not (Path(path).parent / entry.file).exists():
            merge.removed += entry.count
        else:
            merge.kept += entry.count
            merge.entries.append(entry)
    return merge


def save(path: str | Path, results: list[Result], created: str) -> None:
    """Write a baseline while retaining accepted findings of other files."""
    merge = plan(path, results)
    accepted = Set()
    for result in results:
        for rule_id, text in result.findings:
            accepted.add(clean(result.path), rule_id, text)
    for entry in merge.entries:
        accepted.counts[key(entry.file, entry.rule_id, entry.text)] += entry.count
    entries = [
        {"file": f, "rule_id": r, "text": t, "count": c}
        for (f, r, t), c in sorted(accepted.counts.items())
    ]
    Path(path).write_text(
        json.dumps(
            {"version": 1, "created": created, "entries": entries}, indent=2, ensure_ascii=False
        )
        + "\n",
        encoding="utf-8",
    )
