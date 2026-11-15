# Copyright (c) 2026 Tudor Andrei Dumitrascu
"""Shared test settings."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from pathlib import Path


@pytest.fixture(autouse=True)
def cache_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Keep the grammar cache of each test in its own directory."""
    path = tmp_path / "grammar.sqlite3"
    monkeypatch.setenv("STE_GRAMMAR_CACHE", str(path))
    return path
