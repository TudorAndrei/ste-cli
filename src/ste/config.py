"""Read and validate project configuration."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from ste.models import Options, Preferred


class ConfigLoader(yaml.SafeLoader):
    """Read YAML safely with YAML 1.2 boolean words and unique keys."""

    yaml_implicit_resolvers = {
        char: [
            (tag, expression) for tag, expression in resolvers if tag != "tag:yaml.org,2002:bool"
        ]
        for char, resolvers in yaml.SafeLoader.yaml_implicit_resolvers.items()
    }

    def construct_mapping(self, node, deep=False):
        seen = set()
        for key_node, _ in node.value:
            if key_node.tag == "tag:yaml.org,2002:merge":
                continue
            key = self.construct_object(key_node, deep=deep)
            try:
                if key in seen:
                    raise ValueError(f"duplicate config key: {key}")
                seen.add(key)
            except TypeError as err:
                raise ValueError("a config key must be a scalar") from err
        return super().construct_mapping(node, deep=deep)


ConfigLoader.add_implicit_resolver(
    "tag:yaml.org,2002:bool", re.compile(r"^(?:true|True|TRUE|false|False|FALSE)$"), list("tTfF")
)

DEFAULT_NAMES = (".ste.yml", ".ste.yaml", "glossary.yml", "docs/glossary.yml")
SOFTWARE_NOUNS = """backup branch changelog commit diff directory file folder merge patch path rebase repository snapshot tag version worktree binary build class compiler component constant dependency function interface library linter method module package parser plugin pointer runtime script struct variable array boolean buffer cache column database field graph hash index integer list map node payload query record row schema stack string table template transaction tree value cluster container daemon disk environment host image instance memory namespace node partition process server service socket storage thread volume address api client cookie domain endpoint gateway header packet port protocol proxy request response route router session url webhook artifact job pipeline queue release runner task workflow worker button cursor editor form icon keyboard layout menu panel prompt screen shell tab terminal widget window argument command flag input option output pipe stream subcommand account certificate credential permission profile role secret token user coverage fixture issue log metric mock review test trace config hook state link search watch run sandbox lint format parse deploy""".split()


def preset(name: str) -> list[str]:
    if name != "software":
        raise ValueError(f'the preset "{name}" is not one of: software')
    return list[str](SOFTWARE_NOUNS)


@dataclass
class Config:
    mode: str = "flavored"
    max_words: int = 0
    allow_nouns: list[str] = field(default_factory=list)
    allow_verbs: list[str] = field(default_factory=list)
    disable_rules: list[str] = field(default_factory=list)
    rules: dict[str, str] = field(default_factory=dict)
    exclude: list[str] = field(default_factory=list)
    min_confidence: float = 0
    fail_over: float = -1
    baseline: str = ""
    warnings_as_errors: bool = False
    prefer: list[Preferred] = field(default_factory=list)
    presets: list[str] = field(default_factory=list)
    analyzer: bool = False
    dictionary: bool = False

    def options(self) -> Options:
        return Options(
            mode=self.mode,
            max_words=self.max_words,
            allow_nouns=self.allow_nouns.copy(),
            allow_verbs=self.allow_verbs.copy(),
            prefer=self.prefer.copy(),
            disable_rules=self.disable_rules.copy(),
            rule_severity=self.rules.copy(),
            min_confidence=self.min_confidence,
            warnings_as_errors=self.warnings_as_errors,
        )


def find(directory: str | Path) -> Path | None:
    return next(
        (Path(directory) / name for name in DEFAULT_NAMES if (Path(directory) / name).is_file()),
        None,
    )


def _strings(value: object, key: str) -> list[str]:
    if value is None:
        return []
    if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
        raise ValueError(f"{key} must be a list of strings")
    return value.copy()


def parse(text: str) -> Config:
    try:
        raw = yaml.load(text, Loader=ConfigLoader)
    except yaml.YAMLError as err:
        raise ValueError(str(err).splitlines()[0]) from err
    if raw is None:
        raw = {}
    if not isinstance(raw, dict):
        raise ValueError("the config must be a mapping")
    if any(not isinstance(key, str) for key in raw):
        raise ValueError("a config key must be a string")
    if any(not isinstance(key, str) for key in raw):
        raise ValueError("config keys must be strings")
    known = {
        "mode",
        "max_words",
        "allow",
        "prefer",
        "disable_rules",
        "rules",
        "exclude",
        "min_confidence",
        "fail_over",
        "warnings_as_errors",
        "dictionary",
        "presets",
        "analyzer",
        "baseline",
    }
    if unknown := raw.keys() - known:
        raise ValueError(f"unknown config key: {sorted(unknown)[0]}")
    cfg = Config()
    for name in ("mode", "max_words"):
        if name in raw and raw[name] is None:
            raise ValueError(f'the key "{name}" has no value')
    if "mode" in raw:
        if raw["mode"] not in ("flavored", "strict"):
            raise ValueError(f'the mode "{raw["mode"]}" is not "flavored" or "strict"')
        cfg.mode = raw["mode"]
    if "max_words" in raw:
        if type(raw["max_words"]) is not int or raw["max_words"] <= 0:
            raise ValueError("max_words must be a positive number")
        cfg.max_words = raw["max_words"]
    allow = raw.get("allow") or {}
    if not isinstance(allow, dict) or allow.keys() - {"nouns", "verbs"}:
        raise ValueError("allow accepts only nouns and verbs")
    cfg.allow_nouns = _strings(allow.get("nouns"), "allow.nouns")
    cfg.allow_verbs = _strings(allow.get("verbs"), "allow.verbs")
    for name in ("exclude", "disable_rules", "presets"):
        setattr(cfg, name, _strings(raw.get(name), name))
    for name in cfg.presets:
        cfg.allow_nouns.extend(preset(name))
    for name in ("warnings_as_errors", "dictionary", "analyzer"):
        if raw.get(name) is not None:
            if type(raw[name]) is not bool:
                raise ValueError(f"{name} must be a boolean")
            setattr(cfg, name, raw[name])
    for name in ("min_confidence", "fail_over"):
        if raw.get(name) is not None:
            if type(raw[name]) not in (int, float):
                raise ValueError(f"{name} must be a number")
            setattr(cfg, name, raw[name])
    if not 0 <= cfg.min_confidence <= 1:
        raise ValueError("min_confidence must be between 0 and 1")
    if raw.get("baseline") is not None:
        if not isinstance(raw["baseline"], str):
            raise ValueError("baseline must be a path")
        cfg.baseline = raw["baseline"]
    rules = raw.get("rules") or {}
    if not isinstance(rules, dict):
        raise ValueError("rules must be a mapping")
    for rule, severity in rules.items():
        if severity not in ("off", "info", "warning", "error"):
            raise ValueError(
                f'the severity "{severity}" of rule "{rule}" is not "off", "info", "warning", or "error"'
            )
        cfg.rules[rule] = severity
    preferred = raw.get("prefer") or {}
    if not isinstance(preferred, dict) or any(not isinstance(k, str) for k in preferred):
        raise ValueError("prefer must be a mapping of names to lists")
    cfg.prefer = [
        Preferred(name, _strings(preferred[name], f"prefer.{name}")) for name in sorted(preferred)
    ]
    return cfg


def load(path: str | Path | None) -> Config:
    if not path:
        return Config()
    try:
        return parse(Path(path).read_text(encoding="utf-8"))
    except ValueError as err:
        raise ValueError(f"{path}: {err}") from err
