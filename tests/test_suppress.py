# Copyright (c) 2026 Tudor Andrei Dumitrascu
"""Suppression directives are part of the public text contract."""

from __future__ import annotations

import pytest

from ste.models import Diagnostic
from ste.suppress import suppressions


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
    ],
)
def test_directive_scope(source: str, rule: str, needle: str, *, covered: bool) -> None:
    """Check directive scope."""
    start = source.index(needle)
    diagnostic = Diagnostic(rule, "test", "warning", 1, start, start + len(needle))
    assert any(region.covers(diagnostic) for region in suppressions(source)) is covered
