"""Record and consume accepted findings without line-number fingerprints."""

from __future__ import annotations

import json
import posixpath
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

DEFAULT_NAME = ".ste-baseline.json"
Key = tuple[str, str, str]


def clean(path: str) -> str:
    return posixpath.normpath(path.replace("\\", "/"))


def key(file: str, rule_id: str, text: str) -> Key:
    return file, rule_id, " ".join(text.split())


@dataclass
class Entry:
    file: str
    rule_id: str
    text: str
    count: int = 1


@dataclass
class Result:
    path: str
    findings: list[tuple[str, str]]


@dataclass
class Set:
    counts: Counter[Key] = field(default_factory=Counter)

    def add(self, file: str, rule_id: str, text: str) -> None:
        self.counts[key(file, rule_id, text)] += 1

    def take(self, file: str, rule_id: str, text: str) -> bool:
        fingerprint = key(file, rule_id, text)
        if self.counts[fingerprint] <= 0:
            return False
        self.counts[fingerprint] -= 1
        return True

    def stale(self, files: set[str]) -> int:
        return sum(count for (file, _, _), count in self.counts.items() if file in files)


def read(path: str | Path) -> list[Entry]:
    try:
        raw = json.loads(Path(path).read_text(encoding="utf-8"))
    except FileNotFoundError:
        return []
    except json.JSONDecodeError as err:
        raise ValueError(f"{path}: {err}") from err
    if not isinstance(raw, dict) or not isinstance(raw.get("entries", []), list):
        raise ValueError(f"{path}: invalid baseline")
    entries = []
    for entry in raw.get("entries", []):
        if (
            not isinstance(entry, dict)
            or any(not isinstance(entry.get(k, ""), str) for k in ("file", "rule_id", "text"))
            or type(entry.get("count", 1)) is not int
        ):
            raise ValueError(f"{path}: invalid baseline entry")
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
    accepted = Set()
    for entry in read(path):
        accepted.counts[key(entry.file, entry.rule_id, entry.text)] += entry.count
    return accepted


@dataclass
class Merge:
    kept: int = 0
    removed: int = 0
    entries: list[Entry] = field(default_factory=list)


def plan(path: str | Path, results: list[Result]) -> Merge:
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
