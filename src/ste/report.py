# Copyright (c) 2026 Tudor Andrei Dumitrascu
"""Stable reports for people, agents, editors, and code hosts."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, TextIO

if TYPE_CHECKING:
    from ste.models import Diagnostic

FORMATS = ("text", "json", "ndjson", "sarif", "github")
FIELDS = (
    "rule_id",
    "message",
    "severity",
    "confidence",
    "start",
    "end",
    "suggestion",
    "file",
    "line",
    "column",
    "text",
)


@dataclass
class Finding:
    """A diagnostic with its report fields and editor region."""

    data: dict[str, str | int | float]
    region: dict[str, int]

    def project(self, fields: list[str]) -> dict[str, str | int | float]:
        """Select report fields and omit an empty suggestion."""
        if fields:
            return {name: self.data.get(name, "") for name in fields}
        return {name: value for name, value in self.data.items() if name != "suggestion" or value}


def position(source: str, offset: int, *, byte_column: bool = False) -> tuple[int, int]:
    """Return the source line and column for a character offset."""
    prefix = source[: max(0, min(len(source), offset))]
    tail = prefix.rsplit("\n", 1)[-1]
    return prefix.count("\n") + 1, len(tail.encode("utf-8") if byte_column else tail) + 1


def make_finding(path: str, source: str, diag: Diagnostic) -> Finding:
    """Add report positions and source text to a diagnostic."""
    line, column = position(source, diag.start, byte_column=True)
    start_line, start_column = position(source, diag.start)
    end_line, end_column = position(source, diag.end)
    text = source[diag.start : diag.end] if 0 <= diag.start < diag.end <= len(source) else ""
    return Finding(
        {
            "rule_id": diag.rule_id,
            "message": diag.message,
            "severity": diag.severity,
            "confidence": diag.confidence,
            "start": len(source[: diag.start].encode("utf-8")),
            "end": len(source[: diag.end].encode("utf-8")),
            "suggestion": diag.suggestion,
            "file": path,
            "line": line,
            "column": column,
            "text": " ".join(text.split()),
        },
        {
            "startLine": start_line,
            "startColumn": start_column,
            "endLine": end_line,
            "endColumn": end_column,
        },
    )


@dataclass
class FileResult:
    """Word count and findings for one source file."""

    path: str
    words: int
    findings: list[Finding] = field(default_factory=list)


@dataclass
class Report:
    """Results and baseline counts for one checker run."""

    mode: str
    files: list[FileResult]
    accepted: int = 0
    stale: int = 0

    def summary(self) -> dict[str, int | float | bool]:
        """Count all results before output limits apply."""
        total = sum(len(f.findings) for f in self.files)
        words = sum(f.words for f in self.files)
        out: dict[str, int | float | bool] = {
            "files": len(self.files),
            "words": words,
            "findings": total,
            "score": total * 100 / words if words else 0,
            "shown": total,
            "truncated": False,
            "errors": sum(d.data["severity"] == "error" for f in self.files for d in f.findings),
        }
        if self.accepted:
            out["accepted"] = self.accepted
        if self.stale:
            out["stale"] = self.stale
        return out

    def limited(self, limit: int) -> tuple[list[Finding], bool]:
        """Order findings and apply the requested output limit."""
        findings = sorted(
            (d for f in self.files for d in f.findings),
            key=lambda d: (str(d.data["file"]), int(d.data["start"])),
        )
        return (
            (findings[:limit], True) if limit > 0 and len(findings) > limit else (findings, False)
        )


@dataclass
class Options:
    """Settings that control checker behavior."""

    format: str = "text"
    limit: int = 0
    fields: list[str] = field(default_factory=list)
    summary_only: bool = False
    rules: list[dict[str, str]] = field(default_factory=list)
    tool_version: str = ""


def count(n: int, noun: str) -> str:
    """Write a count with the singular or plural noun."""
    return f"{n} {noun}{'' if n == 1 else 's'}"


def write_text(stream: TextIO, rep: Report, opts: Options) -> None:
    """Write the report in its text format."""
    findings, truncated = rep.limited(opts.limit)
    if not opts.summary_only:
        for item in findings:
            d = item.data
            stream.write(
                f"{d['file']}:{d['line']}:{d['column']}: "
                f"{d['severity']} [{d['rule_id']}] {d['message']}\n"
            )
            if d["suggestion"]:
                stream.write(f"    {d['suggestion']}\n")
    summary = rep.summary()
    if truncated:
        stream.write(
            f"\n{count(len(findings), 'finding')} of "
            f"{count(int(summary['findings']), 'finding')} are in this report. "
            "Give a higher --limit for more.\n"
        )
    stream.write(
        f"\n{count(int(summary['findings']), 'finding')} in "
        f"{count(int(summary['words']), 'word')} of "
        f"{count(len(rep.files), 'file')} ({summary['score']:.2f} for each 100 words)\n"
    )


def write(stream: TextIO, rep: Report, opts: Options) -> None:
    """Write the report in the requested output format."""
    findings, truncated = rep.limited(opts.limit)
    summary = rep.summary()
    summary["shown"] = 0 if opts.summary_only else len(findings)
    summary["truncated"] = truncated
    shown = [] if opts.summary_only else findings
    if opts.format == "json":
        data: dict[str, object] = {
            "version": 1,
            "tool": "ste",
            "mode": rep.mode,
            "summary": summary,
        }
        if not opts.summary_only:
            paths = list(dict.fromkeys(str(f.data["file"]) for f in shown))
            files = {f.path: f for f in rep.files}
            data["files"] = [
                {"path": path, "words": files[path].words, "count": len(files[path].findings)}
                for path in paths
            ]
            data["findings"] = [f.project(opts.fields) for f in shown]
        stream.write(json.dumps(data, indent=2, ensure_ascii=False) + "\n")
    elif opts.format == "ndjson":
        stream.writelines(
            json.dumps({**item.project(opts.fields), "type": "finding"}, ensure_ascii=False) + "\n"
            for item in shown
        )
        stream.write(
            json.dumps(
                {
                    "type": "summary",
                    "version": 1,
                    "tool": "ste",
                    "mode": rep.mode,
                    "summary": summary,
                }
            )
            + "\n"
        )
    elif opts.format == "sarif":
        _write_sarif(stream, shown, opts)
    elif opts.format == "github":
        for item in shown:
            d, r = item.data, item.region
            level = {"error": "error", "info": "notice"}.get(str(d["severity"]), "warning")
            message = str(d["message"]) + (" " + str(d["suggestion"]) if d["suggestion"] else "")
            file = _escape(str(d["file"]).replace("\\", "/"), is_property=True)
            title = _escape(str(d["rule_id"]), is_property=True)
            stream.write(
                f"::{level} file={file},line={r['startLine']},col={r['startColumn']},"
                f"endLine={r['endLine']},endColumn={r['endColumn']},"
                f"title={title}::{_escape(message)}\n"
            )
        write_text(stream, rep, Options(summary_only=True, limit=opts.limit))
    else:
        write_text(stream, rep, opts)


def _escape(value: str, *, is_property: bool = False) -> str:
    for old, new in (("%", "%25"), ("\r", "%0D"), ("\n", "%0A")):
        value = value.replace(old, new)
    if is_property:
        value = value.replace(":", "%3A").replace(",", "%2C")
    return value


def _write_sarif(stream: TextIO, findings: list[Finding], opts: Options) -> None:
    def level(severity: str) -> str:
        """Map a checker severity to its SARIF level."""
        return {"error": "error", "info": "note"}.get(severity, "warning")

    rules = [
        {
            "id": r["id"],
            "name": r["name"],
            "shortDescription": {"text": r["name"]},
            "helpUri": "https://tudorandrei.github.io/ste-cli/rules.html",
            "defaultConfiguration": {"level": level(r["default_severity"])},
        }
        for r in opts.rules
    ]
    index = {r["id"]: n for n, r in enumerate(opts.rules)}
    results = []
    for item in findings:
        d = item.data
        path = str(d["file"]).replace("\\", "/")
        uri = "file://" + path if Path(path).is_absolute() else path
        message = str(d["message"]) + (" " + str(d["suggestion"]) if d["suggestion"] else "")
        result: dict[str, object] = {
            "ruleId": d["rule_id"],
            "level": level(str(d["severity"])),
            "message": {"text": message},
            "locations": [
                {"physicalLocation": {"artifactLocation": {"uri": uri}, "region": item.region}}
            ],
            "properties": {"confidence": d["confidence"]},
        }
        if str(d["rule_id"]) in index:
            result["ruleIndex"] = index[str(d["rule_id"])]
        results.append(result)
    driver: dict[str, object] = {
        "name": "ste",
        "informationUri": "https://tudorandrei.github.io/ste-cli/",
        "rules": rules,
    }
    if opts.tool_version:
        driver["version"] = opts.tool_version
    data = {
        "$schema": "https://json.schemastore.org/sarif-2.1.0.json",
        "version": "2.1.0",
        "runs": [
            {"tool": {"driver": driver}, "columnKind": "unicodeCodePoints", "results": results}
        ],
    }
    stream.write(json.dumps(data, indent=2, ensure_ascii=False) + "\n")
