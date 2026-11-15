# Copyright (c) 2026 Tudor Andrei Dumitrascu
"""Check report contracts."""

from __future__ import annotations

import io
import json
from typing import TypedDict, Unpack

from ste import report
from ste.models import Diagnostic

SEMICOLON_BYTE_START = 20
SEMICOLON_BYTE_END = 21
SEMICOLON_BYTE_COLUMN = 6
REPORT_FINDING_COUNT = 2
SEMICOLON_CHARACTER_COLUMN = 5


class ReportOptions(TypedDict, total=False):
    """Report output options accepted by the test renderer."""

    format: str
    limit: int
    fields: list[str]
    summary_only: bool
    rules: list[dict[str, str]]
    tool_version: str


def sample() -> report.Report:
    """Build a report with independent findings and source positions."""
    source = "It isn't open.\nÉtat; now.\n"
    diags = [
        Diagnostic("STE-4.2", "A contraction.", "warning", 0.98, 3, 8, 'Write "is not".'),
        Diagnostic("STE-8.1", "A semicolon, 100%: no.", "info", 1, 19, 20),
    ]
    return report.Report(
        "flavored",
        [
            report.FileResult(
                "docs/a.md", 5, [report.make_finding("docs/a.md", source, d) for d in diags]
            )
        ],
    )


def render(rep: report.Report, **kwargs: Unpack[ReportOptions]) -> str:
    """Write a report in the requested output format."""
    stream = io.StringIO()
    report.write(stream, rep, report.Options(**kwargs))
    return stream.getvalue()


def reference_position(source: str, offset: int, *, byte_column: bool) -> tuple[int, int]:
    """Compute a line and column from the whole prefix, as the slow original did."""
    prefix = source[: max(0, min(len(source), offset))]
    tail = prefix.rsplit("\n", 1)[-1]
    column_text = tail.encode("utf-8") if byte_column else tail
    return prefix.count("\n") + 1, len(column_text) + 1


def test_positions_match_reference_at_every_offset() -> None:
    """Check line index positions and byte offsets against a straightforward reference."""
    source = "Café ☕ isn't.\r\nÉtat 😀; now.\n\nLast 🚀 line"
    for offset in range(len(source) + 1):
        for byte_column in (False, True):
            assert report.position(source, offset, byte_column=byte_column) == reference_position(
                source, offset, byte_column=byte_column
            )
        end = min(len(source), offset + 3)
        finding = report.make_finding(
            "a.md", source, Diagnostic("STE-4.2", "A test.", "warning", 1, offset, end)
        )
        line, column = reference_position(source, offset, byte_column=True)
        start_line, start_column = reference_position(source, offset, byte_column=False)
        end_line, end_column = reference_position(source, end, byte_column=False)
        assert finding.data["start"] == len(source[:offset].encode("utf-8"))
        assert finding.data["end"] == len(source[:end].encode("utf-8"))
        assert (finding.data["line"], finding.data["column"]) == (line, column)
        assert finding.region == {
            "startLine": start_line,
            "startColumn": start_column,
            "endLine": end_line,
            "endColumn": end_column,
        }


def test_byte_offsets_and_unicode_region() -> None:
    """Check byte offsets and unicode region."""
    finding = sample().files[0].findings[1]
    assert finding.data["start"] == SEMICOLON_BYTE_START
    assert finding.data["end"] == SEMICOLON_BYTE_END
    assert finding.data["column"] == SEMICOLON_BYTE_COLUMN
    assert finding.region == {"startLine": 2, "startColumn": 5, "endLine": 2, "endColumn": 6}


def test_json_controls_preserve_real_totals() -> None:
    """Check json controls preserve real totals."""
    rep = sample()
    data = json.loads(render(rep, format="json", limit=1, fields=["rule_id", "text"]))
    assert data["findings"] == [{"rule_id": "STE-4.2", "text": "isn't"}]
    assert data["summary"]["findings"] == REPORT_FINDING_COUNT
    assert data["summary"]["shown"] == 1
    assert data["summary"]["truncated"]
    assert data["files"] == [{"path": "docs/a.md", "words": 5, "count": 2}]
    summary = json.loads(render(rep, format="json", summary_only=True))
    assert summary["summary"]["shown"] == 0
    assert set(summary) == {"version", "tool", "mode", "summary"}


def test_ndjson_has_last_summary() -> None:
    """Check ndjson has last summary."""
    data = [json.loads(line) for line in render(sample(), format="ndjson").splitlines()]
    assert [row["type"] for row in data] == ["finding", "finding", "summary"]
    assert data[-1]["summary"]["findings"] == REPORT_FINDING_COUNT


def test_sarif_and_github_contracts() -> None:
    """Check sarif and github contracts."""
    rules = [{"id": "STE-4.2", "name": "Contraction", "default_severity": "warning"}]
    data = json.loads(render(sample(), format="sarif", rules=rules, tool_version="1.2.3"))
    run = data["runs"][0]
    assert data["version"] == "2.1.0"
    assert run["columnKind"] == "unicodeCodePoints"
    assert run["tool"]["driver"]["version"] == "1.2.3"
    assert run["results"][0]["ruleIndex"] == 0
    assert run["results"][1]["level"] == "note"
    assert (
        run["results"][1]["locations"][0]["physicalLocation"]["region"]["startColumn"]
        == SEMICOLON_CHARACTER_COLUMN
    )
    assert len(json.loads(render(sample(), format="sarif", limit=1))["runs"][0]["results"]) == 1
    lines = render(sample(), format="github").splitlines()
    assert lines[0] == (
        "::warning file=docs/a.md,line=1,col=4,endLine=1,endColumn=9,"
        'title=STE-4.2::A contraction. Write "is not".'
    )
    assert lines[1] == (
        "::notice file=docs/a.md,line=2,col=5,endLine=2,endColumn=6,t"
        "itle=STE-8.1::A semicolon, 100%25: no."
    )
    assert "2 findings in 5 words of 1 file" in lines[-1]
