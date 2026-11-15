# Copyright (c) 2026 Tudor Andrei Dumitrascu
"""Read and validate project configuration."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from ste.models import Options, Preferred


class ConfigLoader(yaml.SafeLoader):
    """Read YAML safely with YAML 1.2 boolean words and unique keys."""

    # PyYAML calls this override with a positional deep argument.
    def construct_mapping(
        self,
        node: yaml.MappingNode,
        deep: bool = False,  # noqa: FBT001, FBT002
    ) -> dict[object, object]:
        """Read a mapping and reject duplicate configuration keys."""
        seen = set()
        for key_node, _ in node.value:
            if key_node.tag == "tag:yaml.org,2002:merge":
                continue
            key = self.construct_object(key_node, deep=deep)
            try:
                if key in seen:
                    msg = f"duplicate config key: {key}"
                    raise ValueError(msg)
                seen.add(key)
            except TypeError as err:
                msg = "a config key must be a scalar"
                raise ValueError(msg) from err
        return super().construct_mapping(node, deep=deep)


ConfigLoader.yaml_implicit_resolvers = {
    char: [(tag, expression) for tag, expression in resolvers if tag != "tag:yaml.org,2002:bool"]
    for char, resolvers in yaml.SafeLoader.yaml_implicit_resolvers.items()
}


ConfigLoader.add_implicit_resolver(
    "tag:yaml.org,2002:bool", re.compile(r"^(?:true|True|TRUE|false|False|FALSE)$"), list("tTfF")
)

DEFAULT_NAMES = (".ste.yml", ".ste.yaml", "glossary.yml", "docs/glossary.yml")
SOFTWARE_NOUNS = [
    "backup",
    "branch",
    "changelog",
    "commit",
    "diff",
    "directory",
    "file",
    "folder",
    "merge",
    "patch",
    "path",
    "rebase",
    "repository",
    "snapshot",
    "tag",
    "version",
    "worktree",
    "binary",
    "build",
    "class",
    "compiler",
    "component",
    "constant",
    "dependency",
    "function",
    "interface",
    "library",
    "linter",
    "method",
    "module",
    "package",
    "parser",
    "plugin",
    "pointer",
    "runtime",
    "script",
    "struct",
    "variable",
    "array",
    "boolean",
    "buffer",
    "cache",
    "column",
    "database",
    "field",
    "graph",
    "hash",
    "index",
    "integer",
    "list",
    "map",
    "node",
    "payload",
    "query",
    "record",
    "row",
    "schema",
    "stack",
    "string",
    "table",
    "template",
    "transaction",
    "tree",
    "value",
    "cluster",
    "container",
    "daemon",
    "disk",
    "environment",
    "host",
    "image",
    "instance",
    "memory",
    "namespace",
    "node",
    "partition",
    "process",
    "server",
    "service",
    "socket",
    "storage",
    "thread",
    "volume",
    "address",
    "api",
    "client",
    "cookie",
    "domain",
    "endpoint",
    "gateway",
    "header",
    "packet",
    "port",
    "protocol",
    "proxy",
    "request",
    "response",
    "route",
    "router",
    "session",
    "url",
    "webhook",
    "artifact",
    "job",
    "pipeline",
    "queue",
    "release",
    "runner",
    "task",
    "workflow",
    "worker",
    "button",
    "cursor",
    "editor",
    "form",
    "icon",
    "keyboard",
    "layout",
    "menu",
    "panel",
    "prompt",
    "screen",
    "shell",
    "tab",
    "terminal",
    "widget",
    "window",
    "argument",
    "command",
    "flag",
    "input",
    "option",
    "output",
    "pipe",
    "stream",
    "subcommand",
    "account",
    "certificate",
    "credential",
    "permission",
    "profile",
    "role",
    "secret",
    "token",
    "user",
    "coverage",
    "fixture",
    "issue",
    "log",
    "metric",
    "mock",
    "review",
    "test",
    "trace",
    "config",
    "hook",
    "state",
    "link",
    "search",
    "watch",
    "run",
    "sandbox",
    "lint",
    "format",
    "parse",
    "deploy",
]


def preset(name: str) -> list[str]:
    """Get the technical nouns of a named preset."""
    if name != "software":
        msg = f'the preset "{name}" is not one of: software'
        raise ValueError(msg)
    return list[str](SOFTWARE_NOUNS)


@dataclass
class Config:
    """Hold validated project settings and glossary terms."""

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
        """Build checker options without sharing mutable lists."""
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
    """Find the first recognized configuration file in a directory."""
    return next(
        (Path(directory) / name for name in DEFAULT_NAMES if (Path(directory) / name).is_file()),
        None,
    )


def _strings(value: object, key: str) -> list[str]:
    if value is None:
        return []
    if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
        msg = f"{key} must be a list of strings"
        raise ValueError(msg)
    return value.copy()


_CONFIG_KEYS = {
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


class _InvalidConfigError(ValueError):
    """The supplied configuration does not meet the configuration schema."""


def _mapping(value: object, reason: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise _InvalidConfigError(reason)
    return value


def _raw_config(text: str) -> dict[str, Any]:
    loader = ConfigLoader(text)
    try:
        raw = loader.get_single_data()
    except yaml.YAMLError as err:
        raise _InvalidConfigError(str(err).splitlines()[0]) from err
    finally:
        loader.dispose()
    raw = _mapping({} if raw is None else raw, "the config must be a mapping")
    if any(not isinstance(key, str) for key in raw):
        msg = "a config key must be a string"
        raise _InvalidConfigError(msg)
    if unknown := raw.keys() - _CONFIG_KEYS:
        msg = f"unknown config key: {min(unknown)}"
        raise _InvalidConfigError(msg)
    return raw


def _limits(cfg: Config, raw: dict[str, Any]) -> None:
    for name in ("mode", "max_words"):
        if name in raw and raw[name] is None:
            msg = f'the key "{name}" has no value'
            raise _InvalidConfigError(msg)
    if "mode" in raw:
        if raw["mode"] not in ("flavored", "strict"):
            msg = f'the mode "{raw["mode"]}" is not "flavored" or "strict"'
            raise _InvalidConfigError(msg)
        cfg.mode = raw["mode"]
    if "max_words" in raw:
        if type(raw["max_words"]) is not int or raw["max_words"] <= 0:
            msg = "max_words must be a positive number"
            raise _InvalidConfigError(msg)
        cfg.max_words = raw["max_words"]


def _glossary(cfg: Config, raw: dict[str, Any]) -> None:
    allow = _mapping(raw.get("allow") or {}, "allow accepts only nouns and verbs")
    if allow.keys() - {"nouns", "verbs"}:
        msg = "allow accepts only nouns and verbs"
        raise _InvalidConfigError(msg)
    cfg.allow_nouns = _strings(allow.get("nouns"), "allow.nouns")
    cfg.allow_verbs = _strings(allow.get("verbs"), "allow.verbs")
    for name in ("exclude", "disable_rules", "presets"):
        setattr(cfg, name, _strings(raw.get(name), name))
    for name in cfg.presets:
        cfg.allow_nouns.extend(preset(name))


def _gates(cfg: Config, raw: dict[str, Any]) -> None:
    for name in ("warnings_as_errors", "dictionary", "analyzer"):
        if raw.get(name) is not None:
            if type(raw[name]) is not bool:
                msg = f"{name} must be a boolean"
                raise _InvalidConfigError(msg)
            setattr(cfg, name, raw[name])
    for name in ("min_confidence", "fail_over"):
        if raw.get(name) is not None:
            if type(raw[name]) not in (int, float):
                msg = f"{name} must be a number"
                raise _InvalidConfigError(msg)
            setattr(cfg, name, raw[name])
    if not 0 <= cfg.min_confidence <= 1:
        msg = "min_confidence must be between 0 and 1"
        raise _InvalidConfigError(msg)
    if raw.get("baseline") is not None:
        if not isinstance(raw["baseline"], str):
            msg = "baseline must be a path"
            raise _InvalidConfigError(msg)
        cfg.baseline = raw["baseline"]


def _rules(cfg: Config, raw: dict[str, Any]) -> None:
    rules = _mapping(raw.get("rules") or {}, "rules must be a mapping")
    for rule, severity in rules.items():
        if severity not in ("off", "info", "warning", "error"):
            reason = (
                f'the severity "{severity}" of rule "{rule}" '
                'is not "off", "info", "warning", or "error"'
            )
            raise _InvalidConfigError(reason)
        cfg.rules[rule] = severity
    preferred = _mapping(raw.get("prefer") or {}, "prefer must be a mapping of names to lists")
    if any(not isinstance(key, str) for key in preferred):
        msg = "prefer must be a mapping of names to lists"
        raise _InvalidConfigError(msg)
    cfg.prefer = [
        Preferred(name, _strings(preferred[name], f"prefer.{name}")) for name in sorted(preferred)
    ]


def parse(text: str) -> Config:
    """Read and validate a project configuration from YAML text."""
    raw = _raw_config(text)
    cfg = Config()
    _limits(cfg, raw)
    _glossary(cfg, raw)
    _gates(cfg, raw)
    _rules(cfg, raw)
    return cfg


def load(path: str | Path | None) -> Config:
    """Read and validate an optional configuration file."""
    if not path:
        return Config()
    try:
        return parse(Path(path).read_text(encoding="utf-8"))
    except ValueError as err:
        msg = f"{path}: {err}"
        raise ValueError(msg) from err
