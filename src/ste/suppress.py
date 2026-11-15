# Copyright (c) 2026 Tudor Andrei Dumitrascu
"""Read rule suppression comments from the source document."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ste.models import Diagnostic


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
    body = line.split("<!--", 1)[1].split("-->", 1)[0].split()
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


def suppressions(source: str) -> list[Suppression]:
    """Read all rule suppression regions from HTML comments."""
    if "ste-disable" not in source:
        return []
    state = _SuppressionState()
    line_start = 0
    for line in source.split("\n"):
        line_end = line_start + len(line)
        next_start = line_end + 1
        directive, ids = _parse_directive(line)
        if directive == "ste-disable-next-line":
            next_end = source.find("\n", next_start)
            state.regions.append(
                Suppression(next_start, next_end + 1 if next_end >= 0 else len(source), ids)
            )
        elif directive == "ste-disable-line":
            state.regions.append(Suppression(line_start, line_end, ids))
        elif directive == "ste-disable":
            state.disable(ids, line_start)
        elif directive == "ste-enable":
            state.enable(ids, line_end)
        line_start = next_start
    state.finish(len(source))
    return state.regions
