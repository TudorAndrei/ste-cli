# Copyright (c) 2026 Tudor Andrei Dumitrascu
"""Check config contracts."""

from __future__ import annotations

from pathlib import Path

import pytest

from ste import config

OVERRIDE_WORD_LIMIT = 18
NOUN_WORD_LIMIT = 3


@pytest.mark.parametrize(
    "text",
    [
        "modes: strict",
        "mode: pedantic",
        "max_words: many",
        "just text",
        "- parser",
        "mode:",
        "max_words: 0",
        "min_confidence: 1.1",
        "rules: {STE-4.2: bad}",
        "presets: [aerospace]",
        "allow: {verb: [write]}",
        "dictionary: yesplease",
        "allow: {nouns: parser}",
        "rules: {1: off}",
        "max_noun_words: 0",
        "max_noun_words: three",
        "max_noun_words: true",
        "max_noun_words:",
    ],
)
def test_bad_config_is_an_error(text: str) -> None:
    """Check bad config is an error."""
    with pytest.raises(ValueError, match=r".+"):
        config.parse(text)


def test_unknown_rule_in_rules_is_an_error() -> None:
    """Check that an unknown rule identifier in rules names that identifier."""
    with pytest.raises(ValueError, match=r"unknown rule: STE-99\.9"):
        config.parse("rules: {STE-4.2: warning, STE-99.9: off}")


def test_unknown_rule_in_disable_rules_is_an_error() -> None:
    """Check that an unknown rule identifier in disable_rules names that identifier."""
    with pytest.raises(ValueError, match="unknown rule: nope"):
        config.parse("disable_rules: [STE-4.2, nope]")


def test_known_rule_identifiers_load() -> None:
    """Check that known rule identifiers load in rules and disable_rules."""
    cfg = config.parse("rules: {STE-4.2: info}\ndisable_rules: [STE-8.1]\n")
    assert cfg.rules == {"STE-4.2": "info"}
    assert cfg.disable_rules == ["STE-8.1"]


def test_yaml_features_and_options() -> None:
    """Check yaml features and options."""
    cfg = config.parse("""mode: strict
max_words: 18
allow:
  nouns: &shared [parser, "web#hook"]
  verbs: *shared
prefer:
  config: [configuration]
disable_rules: [STE-8.1]
rules: {STE-4.2: info}
presets: [software]
warnings_as_errors: true
""")
    options = cfg.options()
    assert options.mode == "strict"
    assert options.max_words == OVERRIDE_WORD_LIMIT
    assert options.allow_verbs == ["parser", "web#hook"]
    assert options.allow_nouns == ["parser", "web#hook"]
    assert {"file", "hook", "build"} <= set(options.preset_nouns)
    assert options.allowed("build")
    assert options.prefer[0].name == "config"
    assert options.rule_severity == {"STE-4.2": "info"}
    assert options.warnings_as_errors


def test_find_and_load(tmp_path: Path) -> None:
    """Check find and load."""
    path = tmp_path / ".ste.yml"
    path.write_text("allow: {nouns: [parser, webhook]}")
    assert config.find(tmp_path) == path
    assert config.load(path).allow_nouns == ["parser", "webhook"]
    assert config.load(None).fail_over == -1
    assert config.parse("# a comment").max_words == 0
    assert config.parse("# a comment").options().max_noun_words == 0
    assert config.parse("max_noun_words: 3").options().max_noun_words == NOUN_WORD_LIMIT
    assert config.load(Path(__file__).parents[1] / "docs/glossary.yml").mode


def test_yaml_boolean_words_and_duplicate_keys() -> None:
    """Check yaml boolean words and duplicate keys."""
    cfg = config.parse(
        "rules: {STE-8.1: off}\nallow: {nouns: [on, off, yes, "
        "no]}\nanalyzer: true\ndictionary: false\n"
    )
    assert cfg.rules == {"STE-8.1": "off"}
    assert cfg.allow_nouns == ["on", "off", "yes", "no"]
    assert cfg.analyzer is True
    assert cfg.dictionary is False
    with pytest.raises(ValueError, match="duplicate config key"):
        config.parse("mode: strict\nmode: flavored\n")
