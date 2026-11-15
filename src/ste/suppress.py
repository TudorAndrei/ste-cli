# Copyright (c) 2026 Tudor Andrei Dumitrascu
"""Read rule suppression comments from the source document."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from markdown_it import MarkdownIt

if TYPE_CHECKING:
    from ste.models import Diagnostic

_MARKDOWN = MarkdownIt("commonmark").enable("table")
_COMMENT = re.compile(r"<!--.*?-->")
_LINE_END = re.compile(r"\r\n|\r|\n")


@dataclass
class Suppression:
    """A source region in which selected rules do not report findings."""

    start: int
    end: int
    rules: list[str]

    def covers(self, diagnostic: Diagnostic) -> bool:
        """Check whether a finding starts in this region."""
        return self.start <= diagnostic.start < self.end and (
            not self.rules or diagnostic.rule_id in self.rules
        )


def _parse_directive(line: str) -> tuple[str, list[str]]:
    if "<!--" not in line:
        return "", []
    rest = line.split("<!--", 1)[1]
    body = rest.split("-->", 1)[0].split()
    if body and body[0] in {
        "ste-disable-next-line",
        "ste-disable-line",
        "ste-enable",
        "ste-disable",
    }:
        return body[0], [word.removesuffix(",") for word in body[1:]]
    return "", []


@dataclass
class _SuppressionState:
    opened: dict[str, int] = field(default_factory=dict)
    open_all: int = -1
    regions: list[Suppression] = field(default_factory=list)

    def disable(self, ids: list[str], start: int) -> None:
        """Start suppressions that are not already open."""
        if ids:
            for rule_id in ids:
                self.opened.setdefault(rule_id, start)
        elif self.open_all < 0:
            self.open_all = start

    def enable(self, ids: list[str], end: int) -> None:
        """Close the requested rules, or all rules when no ID is given."""
        if ids:
            self.regions.extend(
                Suppression(self.opened.pop(rule_id), end, [rule_id])
                for rule_id in ids
                if rule_id in self.opened
            )
            return
        self.finish(end)
        self.opened.clear()
        self.open_all = -1

    def finish(self, end: int) -> None:
        """Record each suppression that is still open at this position."""
        if self.open_all >= 0:
            self.regions.append(Suppression(self.open_all, end, []))
        self.regions.extend(
            Suppression(start, end, [rule_id]) for rule_id, start in self.opened.items()
        )


def _line_spans(source: str) -> list[tuple[int, int, int]]:
    """Give the start, the end, and the next start of each line, as CommonMark counts lines."""
    spans = []
    start = 0
    for match in _LINE_END.finditer(source):
        spans.append((start, match.start(), match.end()))
        start = match.end()
    spans.append((start, len(source), len(source)))
    return spans


def _directive_text(source: str, spans: list[tuple[int, int, int]]) -> dict[int, str]:
    """Map each 0-based line to the HTML comment that CommonMark reads as raw HTML.

    A line that is inside a code block or a code span is not in the map.
    """
    lines = [source[start:end] for start, end, _ in spans]
    found: dict[int, str] = {}
    for token in _MARKDOWN.parse(source):
        if token.map is None:
            continue
        first, last = token.map[0], min(token.map[1], len(lines))
        if token.type == "html_block":
            for index in range(first, last):
                found[index] = lines[index]
        elif token.type == "inline":
            comments = {
                child.content for child in token.children or () if child.type == "html_inline"
            }
            for index in range(first, last):
                for match in _COMMENT.finditer(lines[index]):
                    if match.group(0) in comments:
                        found[index] = match.group(0)
                        break
    return found


def suppressions(source: str) -> list[Suppression]:
    """Read all rule suppression regions from HTML comments outside code."""
    if "ste-disable" not in source:
        return []
    spans = _line_spans(source)
    directives = _directive_text(source, spans)
    state = _SuppressionState()
    for index, (line_start, line_end, next_start) in enumerate(spans):
        directive, ids = _parse_directive(directives.get(index, ""))
        if directive == "ste-disable-next-line":
            # A directive on the last line has no next line.
            following = spans[index + 1][2] if index + 1 < len(spans) else len(source)
            state.regions.append(Suppression(next_start, following, ids))
        elif directive == "ste-disable-line":
            state.regions.append(Suppression(line_start, line_end, ids))
        elif directive == "ste-disable":
            state.disable(ids, line_start)
        elif directive == "ste-enable":
            state.enable(ids, line_end)
    state.finish(len(source))
    return state.regions
