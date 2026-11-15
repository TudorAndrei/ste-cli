# Copyright (c) 2026 Tudor Andrei Dumitrascu
"""Suppression directives are part of the public text contract."""

from __future__ import annotations

import pytest

from ste.checker import lint
from ste.models import Diagnostic
from ste.suppress import Suppression, suppressions

EXPECTED_PROSE_FINDINGS = 3


@pytest.mark.parametrize(
    ("source", "rule", "needle", "covered"),
    [
        ("The valve isn't open.\n", "STE-4.2", "isn't", False),
        ("<!-- ste-disable-next-line -->\nThe valve isn't open.\n", "STE-4.2", "isn't", True),
        (
            "<!-- ste-disable-next-line STE-4.2 -->\nThe valve isn't open.\n",
            "STE-4.2",
            "isn't",
            True,
        ),
        (
            "<!-- ste-disable-next-line STE-8.1 -->\nThe valve isn't open.\n",
            "STE-4.2",
            "isn't",
            False,
        ),
        ("The valve isn't open. <!-- ste-disable-line -->\n", "STE-4.2", "isn't", True),
        (
            "<!-- ste-disable -->\nThe valve isn't open.\nThe pump isn't on.\n",
            "STE-4.2",
            "pump",
            True,
        ),
        (
            (
                "<!-- ste-disable STE-4.2 -->\nThe valve isn't open.\n<!-- "
                "ste-enable STE-4.2 -->\nThe pump isn't on.\n"
            ),
            "STE-4.2",
            "pump",
            False,
        ),
        ("<!-- ste-disable STE-8.1 -->\nThe valve isn't open.\n", "STE-4.2", "isn't", False),
        (
            "<!-- ste-disable STE-8.1, STE-4.2 -->\nThe valve isn't open;\n",
            "STE-4.2",
            "isn't",
            True,
        ),
        (
            "<!-- ste-disable -->\nHidden.\n<!-- ste-enable -->\nVisible.\n",
            "STE-4.2",
            "Visible",
            False,
        ),
        ("<!-- ste-disable-next-line -->", "STE-4.2", "ste-disable", False),
        (
            "```html\n<!-- ste-disable-next-line -->\n```\nThe valve isn't open.\n",
            "STE-4.2",
            "isn't",
            False,
        ),
        (
            "~~~html\n<!-- ste-disable -->\n~~~\nThe valve isn't open.\n",
            "STE-4.2",
            "isn't",
            False,
        ),
        (
            "- Use `<!-- ste-disable-next-line STE-4.2 -->` above it.\nThe valve isn't open.\n",
            "STE-4.2",
            "isn't",
            False,
        ),
        (
            (
                "```\n<!-- ste-disable -->\n```\n"
                "<!-- ste-disable-next-line -->\nThe valve isn't open.\n"
            ),
            "STE-4.2",
            "isn't",
            True,
        ),
        (
            "    ```\n<!-- ste-disable -->\nThe valve isn't open.\n",
            "STE-4.2",
            "isn't",
            True,
        ),
        (
            "```x``` is code\n<!-- ste-disable -->\nThe valve isn't open.\n",
            "STE-4.2",
            "isn't",
            True,
        ),
        (
            "> ```\n> <!-- ste-disable -->\n> ```\nThe valve isn't open.\n",
            "STE-4.2",
            "isn't",
            False,
        ),
        (
            "Text.\n\n    <!-- ste-disable -->\nThe valve isn't open.\n",
            "STE-4.2",
            "isn't",
            False,
        ),
        (
            "it`s <!-- ste-disable -->\nThe valve isn't open.\n",
            "STE-4.2",
            "isn't",
            True,
        ),
        (
            "``<!-- ste-disable -->``\nThe valve isn't open.\n",
            "STE-4.2",
            "isn't",
            False,
        ),
        (
            "`a\n<!-- ste-disable -->\nb`\nThe valve isn't open.\n",
            "STE-4.2",
            "isn't",
            True,
        ),
        (
            "The valve isn't open. <!-- ste-disable-line -->\nThe pump isn't on.\n",
            "STE-4.2",
            "pump",
            False,
        ),
        (
            "- <!-- ste-disable -->\n- The valve isn't open.\n",
            "STE-4.2",
            "isn't",
            True,
        ),
        (
            "````python\n<!-- ste-disable -->\n`````\nThe valve isn't open.\n",
            "STE-4.2",
            "isn't",
            False,
        ),
        (
            "Text <!-- ste-disable STE-4.2\n-->\nThe valve isn't open.\n",
            "STE-4.2",
            "isn't",
            True,
        ),
        (
            (
                "`<!-- ste-disable-next-line -->`\nThe valve isn't open.\n"
                "Text <!-- ste-disable-next-line -->\nThe pump isn't on.\n"
            ),
            "STE-4.2",
            "valve",
            False,
        ),
        (
            (
                "`<!-- ste-disable-next-line -->`\nThe valve isn't open.\n"
                "Text <!-- ste-disable-next-line -->\nThe pump isn't on.\n"
            ),
            "STE-4.2",
            "pump",
            True,
        ),
        (
            (
                "| A | B |\n| --- | --- |\n"
                "| It isn't ready. <!-- ste-disable-line --> | Note <!-- note --> |\n"
            ),
            "STE-4.2",
            "isn't",
            True,
        ),
    ],
)
def test_directive_scope(source: str, rule: str, needle: str, *, covered: bool) -> None:
    """Check directive scope."""
    start = source.index(needle)
    diagnostic = Diagnostic(rule, "test", "warning", 1, start, start + len(needle))
    assert any(region.covers(diagnostic) for region in suppressions(source)) is covered


def test_crlf_next_line_region_has_exact_offsets() -> None:
    """Offsets count the two characters of a CRLF line end."""
    source = "<!-- ste-disable-next-line -->\r\nThe valve isn't open.\r\n"
    start = source.index("The valve")
    assert suppressions(source) == [Suppression(start, len(source), [])]


def test_crlf_enable_ends_region_on_its_own_line() -> None:
    """A CRLF enable comment closes the region at the end of its own line."""
    source = "<!-- ste-disable -->\r\nHidden.\r\n<!-- ste-enable -->\r\nVisible.\r\n"
    enable_line = source.index("<!-- ste-enable")
    line_end = enable_line + len("<!-- ste-enable -->")
    assert suppressions(source) == [Suppression(0, line_end, [])]


def test_bare_carriage_return_line_ends() -> None:
    """A file with only carriage returns as line ends gives the region of its own line."""
    source = "a\r<!-- ste-disable-line -->\rb isn't\r"
    start = source.index("<!--")
    assert suppressions(source) == [
        Suppression(start, start + len("<!-- ste-disable-line -->"), [])
    ]


def test_fenced_example_does_not_suppress_lint_findings() -> None:
    """A directive shown as an example in a fence does not hide findings."""
    text = (
        "Use this comment:\n\n```html\n<!-- ste-disable -->\n```\n\nIt isn't done; it can't be.\n"
    )
    findings = lint(text)
    prose_start = text.index("It isn't")
    assert len(findings) == EXPECTED_PROSE_FINDINGS
    assert all(finding.start >= prose_start for finding in findings)
