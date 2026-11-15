# Copyright (c) 2026 Tudor Andrei Dumitrascu
"""Run the checks, apply settings, and return ordered findings."""

from __future__ import annotations

from dataclasses import replace

from ste.document import parse
from ste.grammar import annotate
from ste.models import Diagnostic, Document, Options
from ste.rules import all_rules
from ste.suppress import suppressions


def lint(text: str, options: Options | None = None) -> list[Diagnostic]:
    """Find violations in Markdown or plain text."""
    return lint_document(parse(text), options)


def lint_document(doc: Document, options: Options | None = None) -> list[Diagnostic]:
    """Run all rules and apply settings and suppressions."""
    opts = options or Options()
    if opts.syntax is not None and not doc.analyzed:
        annotate(doc, opts.syntax)
    disabled = set(opts.disable_rules)
    hidden = suppressions(doc.source)
    out: list[Diagnostic] = []
    for rule in all_rules():
        for finding in rule(doc, opts):
            if finding.rule_id in disabled or finding.confidence < opts.confidence():
                continue
            severity = opts.severity(finding.rule_id, finding.severity)
            if severity == "off" or any(region.covers(finding) for region in hidden):
                continue
            out.append(replace(finding, severity=severity))
    return sorted(out, key=lambda d: (d.start, d.end, d.rule_id))
