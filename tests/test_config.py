from pathlib import Path

import pytest

from ste import config


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
    ],
)
def test_bad_config_is_an_error(text):
    with pytest.raises(ValueError):
        config.parse(text)


def test_yaml_features_and_options():
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
    assert options.max_words == 18
    assert options.allow_verbs == ["parser", "web#hook"]
    assert {"file", "hook", "build", "web#hook"} <= set(options.allow_nouns)
    assert options.prefer[0].name == "config"
    assert options.rule_severity == {"STE-4.2": "info"}
    assert options.warnings_as_errors


def test_find_and_load(tmp_path):
    path = tmp_path / ".ste.yml"
    path.write_text("allow: {nouns: [parser, webhook]}")
    assert config.find(tmp_path) == path
    assert config.load(path).allow_nouns == ["parser", "webhook"]
    assert config.load(None).fail_over == -1
    assert config.parse("# a comment").max_words == 0
    assert config.load(Path(__file__).parents[1] / "docs/glossary.yml").mode


def test_yaml_boolean_words_and_duplicate_keys():
    cfg = config.parse(
        "rules: {STE-8.1: off}\nallow: {nouns: [on, off, yes, no]}\nanalyzer: true\ndictionary: false\n"
    )
    assert cfg.rules == {"STE-8.1": "off"}
    assert cfg.allow_nouns == ["on", "off", "yes", "no"]
    assert cfg.analyzer is True
    assert cfg.dictionary is False
    with pytest.raises(ValueError, match="duplicate config key"):
        config.parse("mode: strict\nmode: flavored\n")
