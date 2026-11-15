# Copyright (c) 2026 Tudor Andrei Dumitrascu
"""Dictionary contracts use invented words, not the ASD dictionary."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from ste.dictionary import default_path, load, parse

PRIVATE_FILE_MODE = 0o600

FIXTURE = Path(__file__).parent / "fixtures" / "dictionary.md"


def test_dictionary_import_and_persistence(tmp_path: Path) -> None:
    """Check dictionary import and persistence."""
    index = parse(FIXTURE.read_text(), "fixture")
    assert index.stats() == {
        "words": 9,
        "approved": 4,
        "unapproved": 5,
        "alternatives": 4,
        "forms": 4,
    }
    path = tmp_path / "sub" / "dictionary.json"
    index.save(path)
    restored = load(path)
    assert restored is not None
    assert restored.source == "fixture"
    assert restored.stats() == index.stats()
    if os.name != "nt":
        assert path.stat().st_mode & 0o777 == PRIVATE_FILE_MODE
    result, found = restored.unapproved("wibble")
    assert found
    assert result.alternatives == ["gribble", "frammis"]
    assert not result.only_verb
    verb = next(e for e in restored.lookup("gribble") if e.pos == "v")
    assert verb.forms == ["gribbles", "gribbled"]
    assert [e.word for e in restored.by_form("wibbliest")] == ["wibbly"]


@pytest.mark.parametrize(
    ("word", "found", "verb", "alternatives", "technical"),
    [
        ("frammis", False, False, [], False),
        ("gribble", False, False, [], False),
        ("snarf", True, True, ["make a list"], False),
        ("zorble", True, False, [], False),
        ("blep", True, True, [], True),
        ("frob", True, True, ["gribble"], True),
        ("unknown-word", False, False, [], False),
    ],
)
def test_word_meanings(
    word: str, alternatives: list[str], *, found: bool, verb: bool, technical: bool
) -> None:
    """Check word meanings."""
    index = parse(FIXTURE.read_text())
    result, actual = index.unapproved(word)
    assert actual == found
    assert result.only_verb == verb
    assert result.alternatives == alternatives
    assert result.technical_noun == technical


def test_dictionary_paths(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Check dictionary paths."""
    monkeypatch.delenv("STE_DICT", raising=False)
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path))
    assert default_path() == tmp_path / "ste" / "dictionary.json"
    monkeypatch.setenv("STE_DICT", str(tmp_path / "own.json"))
    assert default_path() == tmp_path / "own.json"
    assert load(tmp_path / "missing") is None


def test_dictionary_rejects_invalid_input(tmp_path: Path) -> None:
    """Check dictionary rejects invalid input."""
    with pytest.raises(ValueError, match="no part 2"):
        parse("# Other document\nNo dictionary")
    with pytest.raises(ValueError, match="no dictionary entry"):
        parse("# Part 2 - Dictionary\nNo entries")
    path = tmp_path / "index.json"
    path.write_text(json.dumps({"version": 3}))
    with pytest.raises(ValueError, match="version"):
        load(path)
    path.write_text(json.dumps({"version": 1, "words": [{"word": 1, "approved": False}]}))
    with pytest.raises(ValueError, match="entry"):
        load(path)


def test_forms_follow_their_headword() -> None:
    """Check that each form belongs to the headword before it in the cell."""
    text = (
        "## Part 2 - Dictionary\n"
        "|Word|Meaning|\n"
        "|---|---|\n"
        "|GLORP (v), GLORPS, GLORPED, GLORPED|To join|\n"
        "|SNOOT (n)|A tube|\n"
    )
    index = parse(text)
    assert [(e.word, e.pos, e.forms) for e in index.words] == [
        ("glorp", "v", ["glorps", "glorped"]),
        ("snoot", "n", []),
    ]


def test_an_index_of_version_one_still_loads(tmp_path: Path) -> None:
    """Check that an index from an earlier import loads without forms."""
    path = tmp_path / "index.json"
    path.write_text(
        json.dumps({"version": 1, "source": "old", "words": [{"word": "glorp", "approved": True}]})
    )
    index = load(path)
    assert index is not None
    assert index.lookup("glorp")[0].forms == []
    path.write_text(
        json.dumps({"version": 2, "words": [{"word": "glorp", "approved": True, "forms": [1]}]})
    )
    with pytest.raises(ValueError, match="forms"):
        load(path)
