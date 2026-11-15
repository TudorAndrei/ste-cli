"""Dictionary contracts use invented words, not the ASD dictionary."""

import json
import os
from pathlib import Path

import pytest

from ste.dictionary import default_path, load, parse

FIXTURE = Path(__file__).parent / "fixtures" / "dictionary.md"


def test_dictionary_import_and_persistence(tmp_path):
    index = parse(FIXTURE.read_text(), "fixture")
    assert index.stats() == {"words": 8, "approved": 3, "unapproved": 5, "alternatives": 4}
    path = tmp_path / "sub" / "dictionary.json"
    index.save(path)
    restored = load(path)
    assert restored is not None
    assert restored.source == "fixture"
    assert restored.stats() == index.stats()
    if os.name != "nt":
        assert path.stat().st_mode & 0o777 == 0o600
    result, found = restored.unapproved("wibble")
    assert found
    assert result.alternatives == ["gribble", "frammis"]
    assert not result.only_verb


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
def test_word_meanings(word, found, verb, alternatives, technical):
    index = parse(FIXTURE.read_text())
    result, actual = index.unapproved(word)
    assert actual == found
    assert result.only_verb == verb
    assert result.alternatives == alternatives
    assert result.technical_noun == technical


def test_dictionary_paths(monkeypatch, tmp_path):
    monkeypatch.delenv("STE_DICT", raising=False)
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path))
    assert default_path() == tmp_path / "ste" / "dictionary.json"
    monkeypatch.setenv("STE_DICT", str(tmp_path / "own.json"))
    assert default_path() == tmp_path / "own.json"
    assert load(tmp_path / "missing") is None


def test_dictionary_rejects_invalid_input(tmp_path):
    with pytest.raises(ValueError, match="no part 2"):
        parse("# Other document\nNo dictionary")
    with pytest.raises(ValueError, match="no dictionary entry"):
        parse("# Part 2 - Dictionary\nNo entries")
    path = tmp_path / "index.json"
    path.write_text(json.dumps({"version": 2}))
    with pytest.raises(ValueError, match="version"):
        load(path)
    path.write_text(json.dumps({"version": 1, "words": [{"word": 1, "approved": False}]}))
    with pytest.raises(ValueError, match="entry"):
        load(path)
