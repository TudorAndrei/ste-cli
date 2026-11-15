"""Read rule suppression comments from the source document."""

from __future__ import annotations

from dataclasses import dataclass

from ste.models import Diagnostic


@dataclass
class Suppression:
    start: int
    end: int
    rules: list[str]

    def covers(self, diagnostic: Diagnostic) -> bool:
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


def suppressions(source: str) -> list[Suppression]:
    if "ste-disable" not in source:
        return []
    out: list[Suppression] = []
    opened: dict[str, int] = {}
    open_all = -1
    line_start = 0
    for line in source.split("\n"):
        line_end = line_start + len(line)
        next_start = line_end + 1
        directive, ids = _parse_directive(line)
        if directive == "ste-disable-next-line":
            next_end = source.find("\n", next_start)
            out.append(Suppression(next_start, next_end + 1 if next_end >= 0 else len(source), ids))
        elif directive == "ste-disable-line":
            out.append(Suppression(line_start, line_end, ids))
        elif directive == "ste-disable":
            if ids:
                for rule_id in ids:
                    opened.setdefault(rule_id, line_start)
            elif open_all < 0:
                open_all = line_start
        elif directive == "ste-enable":
            if not ids:
                if open_all >= 0:
                    out.append(Suppression(open_all, line_end, []))
                    open_all = -1
                for rule_id, start in opened.items():
                    out.append(Suppression(start, line_end, [rule_id]))
                opened.clear()
            else:
                for rule_id in ids:
                    if rule_id in opened:
                        out.append(Suppression(opened.pop(rule_id), line_end, [rule_id]))
        line_start = next_start
    if open_all >= 0:
        out.append(Suppression(open_all, len(source), []))
    out.extend(Suppression(start, len(source), [rule_id]) for rule_id, start in opened.items())
    return out
