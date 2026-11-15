# Copyright (c) 2026 Tudor Andrei Dumitrascu
"""Measure rule results against a labeled text corpus."""

from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path
from typing import TextIO, TypedDict

from ste import analyzer
from ste.checker import lint
from ste.models import Options, Preferred


class RuleScore(TypedDict):
    """Precision and recall counts for one rule."""

    rule_id: str
    true_positives: int
    false_positives: int
    false_negatives: int
    precision: float
    recall: float


class EvaluationReport(TypedDict):
    """Results of a run against the labeled corpus."""

    files: int
    rules: list[RuleScore]
    totals: RuleScore


def _score(rule: str, counts: list[int]) -> RuleScore:
    tp, fp, fn = counts
    return {
        "rule_id": rule,
        "true_positives": tp,
        "false_positives": fp,
        "false_negatives": fn,
        "precision": tp / (tp + fp) if tp + fp else 1,
        "recall": tp / (tp + fn) if tp + fn else 1,
    }


def _invalid(path: Path, reason: str) -> ValueError:
    return ValueError(f"{path}: {reason}")


def _string_list(path: Path, value: object, label: str) -> list[str]:
    if value is None:
        return []
    if not isinstance(value, list) or any(not isinstance(word, str) for word in value):
        raise _invalid(path, f"{label} must be a list of strings")
    return [str(word) for word in value]


def _preferences(path: Path, value: object) -> list[Preferred]:
    if value is None:
        return []
    if not isinstance(value, dict):
        raise _invalid(path, "prefer must be a mapping")
    return [
        Preferred(name, _string_list(path, alternatives, "prefer alternatives"))
        for name, alternatives in sorted(value.items())
    ]


def _expectations(path: Path, value: object) -> list[dict[str, str]]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise _invalid(path, "expect must be a list")
    expectations = []
    for item in value:
        entry = {} if item is None else item
        if not isinstance(entry, dict) or any(
            entry.get(key) is not None and not isinstance(entry.get(key), str)
            for key in ("rule_id", "text")
        ):
            raise _invalid(path, "each expectation must have string rule_id and text fields")
        expectations.append(
            {"rule_id": entry.get("rule_id") or "", "text": entry.get("text") or ""}
        )
    return expectations


def _expected(path: Path) -> tuple[Options, bool, list[dict[str, str]]]:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raw = {}
    except json.JSONDecodeError as err:
        raise _invalid(path, str(err)) from err
    if raw is None:
        raw = {}
    if not isinstance(raw, dict):
        raise _invalid(path, "expected a JSON object")
    mode = raw.get("mode")
    if mode is not None and not isinstance(mode, str):
        raise _invalid(path, "mode must be a string")
    analyze = raw.get("analyze", False)
    if not isinstance(analyze, bool):
        raise _invalid(path, "analyze must be true or false")
    limit = raw.get("max_noun_words")
    if limit is not None and (type(limit) is not int or limit <= 0):
        raise _invalid(path, "max_noun_words must be a positive number")
    opts = Options(
        mode=mode or "flavored",
        max_noun_words=limit or 0,
        allow_nouns=_string_list(path, raw.get("allow_nouns"), "allow_nouns"),
        allow_verbs=_string_list(path, raw.get("allow_verbs"), "allow_verbs"),
        prefer=_preferences(path, raw.get("prefer")),
    )
    return opts, analyze, _expectations(path, raw.get("expect"))


def run(directory: str | Path) -> EvaluationReport:
    """Measure all fixtures in a labeled corpus."""
    root = Path(directory)
    if not root.is_dir():
        msg = f"{root}: the corpus directory does not exist"
        raise ValueError(msg)
    files = sorted(
        p for p in root.rglob("*") if p.is_file() and p.suffix in (".md", ".markdown", ".txt")
    )
    if not files:
        msg = f"{root}: the corpus has no fixture files"
        raise ValueError(msg)
    counts: defaultdict[str, list[int]] = defaultdict(lambda: [0, 0, 0])
    client: analyzer.Analyzer | None = None
    try:
        for path in files:
            client = _measure(path, counts, client)
    finally:
        if client is not None:
            client.close()
    totals = [sum(v[n] for v in counts.values()) for n in range(3)]
    return {
        "files": len(files),
        "rules": [_score(k, counts[k]) for k in sorted(counts)],
        "totals": _score("all", totals),
    }


def _measure(
    path: Path, counts: defaultdict[str, list[int]], client: analyzer.Analyzer | None
) -> analyzer.Analyzer | None:
    """Add the results of one fixture, and return the analyzer for the next fixture.

    A fixture with ``"analyze": true`` uses the grammar analyzer. The analyzer
    starts at the first such fixture, and the next fixtures use it again.
    """
    source = path.read_text(encoding="utf-8")
    expected_path = path.with_suffix(".expected.json")
    opts, analyze, want = _expected(expected_path)
    if analyze:
        if client is None:
            status = analyzer.check()
            if not status["ready"]:
                msg = f"{path}: the fixture needs the analyzer. {status['problem']}"
                raise ValueError(msg)
            client = analyzer.create()
        opts.syntax = client
    used: set[int] = set()
    for diag in lint(source, opts):
        text = " ".join(source[diag.start : diag.end].split())
        match = next(
            (
                n
                for n, w in enumerate(want)
                if n not in used
                and w["rule_id"] == diag.rule_id
                and (not w.get("text") or w["text"] == text)
            ),
            None,
        )
        if match is None:
            counts[diag.rule_id][1] += 1
        else:
            used.add(match)
            counts[diag.rule_id][0] += 1
    for n, expectation in enumerate(want):
        if n not in used:
            counts[expectation["rule_id"]][2] += 1
    return client


def write_text(stream: TextIO, data: EvaluationReport) -> None:
    """Write the report in its text format."""
    stream.write(f"{'rule':<10} {'tp':>5} {'fp':>5} {'fn':>5} {'precision':>10} {'recall':>8}\n")
    rows = data["rules"]
    stream.writelines(
        f"{row['rule_id']:<10} {row['true_positives']:>5} {row['false_positives']:>5} "
        f"{row['false_negatives']:>5} {row['precision']:>10.2f} {row['recall']:>8.2f}\n"
        for row in [*rows, data["totals"]]
    )
    stream.write(f"\n{data['files']} fixture files\n")
