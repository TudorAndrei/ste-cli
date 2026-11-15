"""Measure rule results against a labeled text corpus."""

from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path
from typing import TextIO, TypedDict

from ste.checker import lint
from ste.models import Options, Preferred


class RuleScore(TypedDict):
    rule_id: str
    true_positives: int
    false_positives: int
    false_negatives: int
    precision: float
    recall: float


class EvaluationReport(TypedDict):
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


def _expected(path: Path) -> tuple[Options, list[dict[str, str]]]:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raw = {}
    except json.JSONDecodeError as err:
        raise ValueError(f"{path}: {err}") from err
    if raw is None:
        raw = {}
    if not isinstance(raw, dict):
        raise ValueError(f"{path}: expected a JSON object")
    mode = raw.get("mode")
    nouns = raw.get("allow_nouns")
    prefer = raw.get("prefer")
    expect = raw.get("expect")
    if mode is not None and not isinstance(mode, str):
        raise ValueError(f"{path}: mode must be a string")
    if nouns is not None and (
        not isinstance(nouns, list) or any(not isinstance(w, str) for w in nouns)
    ):
        raise ValueError(f"{path}: allow_nouns must be a list of strings")
    if prefer is not None and not isinstance(prefer, dict):
        raise ValueError(f"{path}: prefer must be a mapping")
    preferences = []
    for name, alternatives in sorted((prefer or {}).items()):
        if alternatives is not None and (
            not isinstance(alternatives, list) or any(not isinstance(w, str) for w in alternatives)
        ):
            raise ValueError(f"{path}: prefer alternatives must be a list of strings")
        preferences.append(Preferred(name, alternatives or []))
    if expect is not None and not isinstance(expect, list):
        raise ValueError(f"{path}: expect must be a list")
    expectations = []
    for item in expect or []:
        if item is None:
            item = {}
        if not isinstance(item, dict) or any(
            item.get(k) is not None and not isinstance(item.get(k), str)
            for k in ("rule_id", "text")
        ):
            raise ValueError(f"{path}: each expectation must have string rule_id and text fields")
        expectations.append({"rule_id": item.get("rule_id") or "", "text": item.get("text") or ""})
    return Options(
        mode=mode or "flavored", allow_nouns=nouns or [], prefer=preferences
    ), expectations


def run(directory: str | Path) -> EvaluationReport:
    root = Path(directory)
    if not root.is_dir():
        raise ValueError(f"{root}: the corpus directory does not exist")
    files = sorted(
        p for p in root.rglob("*") if p.is_file() and p.suffix in (".md", ".markdown", ".txt")
    )
    if not files:
        raise ValueError(f"{root}: the corpus has no fixture files")
    counts: defaultdict[str, list[int]] = defaultdict(lambda: [0, 0, 0])
    for path in files:
        source = path.read_text(encoding="utf-8")
        expected_path = path.with_suffix(".expected.json")
        opts, want = _expected(expected_path)
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
    totals = [sum(v[n] for v in counts.values()) for n in range(3)]
    return {
        "files": len(files),
        "rules": [_score(k, counts[k]) for k in sorted(counts)],
        "totals": _score("all", totals),
    }


def write_text(stream: TextIO, data: EvaluationReport) -> None:
    stream.write(f"{'rule':<10} {'tp':>5} {'fp':>5} {'fn':>5} {'precision':>10} {'recall':>8}\n")
    rows = data["rules"]
    assert isinstance(rows, list)
    for row in [*rows, data["totals"]]:
        stream.write(
            f"{row['rule_id']:<10} {row['true_positives']:>5} {row['false_positives']:>5} {row['false_negatives']:>5} {row['precision']:>10.2f} {row['recall']:>8.2f}\n"
        )
    stream.write(f"\n{data['files']} fixture files\n")
