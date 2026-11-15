# Copyright (c) 2026 Tudor Andrei Dumitrascu
"""Advice from a language model for the rules that need a reader.

This module never imports the Anthropic SDK at import time. The SDK is an
optional extra, and only a real review request loads it.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Protocol

from platformdirs import user_cache_path

from ste import report
from ste.document import parse
from ste.models import Diagnostic

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

    from anthropic import Anthropic

# Change this value when the rule text or the prompt changes. It is part of each cache key.
RULES_VERSION = "2"
DEFAULT_MODEL = "claude-haiku-5-5"
DEFAULT_JOBS = 4
DEFAULT_TIMEOUT = 120.0
MAX_TOKENS = 8000
MAX_RETRIES = 4
MIN_WORDS = 4
# A model answer is not reproducible. The value is below the 0.6 limit of the flavored mode.
CONFIDENCE = 0.5
KIND = "advice"
FIELDS = (*report.FIELDS, "kind")
CHARS_PER_TOKEN = 4
REQUEST_OVERHEAD_TOKENS = 40
EXTRA_HINT = (
    'the review needs the "llm" extra. Install it with:\n'
    '  uv tool install "ste-cli[llm] @ git+https://github.com/TudorAndrei/ste-cli"'
)
KEY_HINT = (
    "the review needs an Anthropic API key. Set ANTHROPIC_API_KEY, "
    "or give --dry-run to see the plan without a request."
)

# Each description is in our own words. Do not copy the text of ASD-STE100 here.
RULES: tuple[tuple[str, str, str], ...] = (
    (
        "STE-1.3",
        "One meaning for each word",
        (
            "A word has one approved meaning, and that meaning is frequently more narrow than "
            "in usual English. Report a word that the text uses in two senses, for example a "
            "word that names a part in one sentence and an action in the next one."
        ),
    ),
    (
        "STE-1.5",
        "The category of a technical noun",
        (
            "A word that is not approved is permitted when it is a technical noun of the "
            "subject field. Report a noun that is not a term of the field. When the noun is a "
            "term of the field, say that it can go in allow.nouns of the config. Do not "
            "propose a rewrite of a real technical noun."
        ),
    ),
    (
        "STE-1.12",
        "The category of a technical verb",
        (
            "A technical verb must be a verb of the subject field. Report a verb that is not "
            "a term of the field and that an approved verb can replace."
        ),
    ),
    (
        "STE-1.10",
        "No slang and no jargon",
        (
            "A technical noun must be a term of the field, and not the language of one team. "
            '"The job got stuck" is not a technical statement.'
        ),
    ),
    (
        "STE-2.2",
        "The full form of a long technical noun",
        (
            "A technical noun of more than three words must appear in full one time, before "
            "its short form. Report a short form or an abbreviation that has no full form "
            "before it in the text that you see."
        ),
    ),
    (
        "STE-4.4",
        "Connecting words",
        (
            "Two sentences with related ideas need a connecting word between them. Report a "
            "place where the reader must guess the relation of a sentence to the sentence "
            "before it."
        ),
    ),
    (
        "STE-4.5",
        "Articles and demonstrative adjectives",
        (
            'An article ("the", "a") or a demonstrative adjective ("this", "these") is '
            "necessary before most nouns. A general statement can have no article. Report a "
            "noun that needs an article and does not have one."
        ),
    ),
    (
        "STE-6.1",
        "Give information gradually",
        (
            "The text must give a fact before a fact that depends on it. Report a paragraph "
            "that uses a thing before it explains it, so that a reader must read it two times."
        ),
    ),
    (
        "STE-6.2",
        "Key words for a logical structure",
        (
            "Each paragraph must start with its subject. A reader who reads only the first "
            "sentence must know what the paragraph is about. Report a paragraph whose first "
            "sentence does not give its subject."
        ),
    ),
    (
        "STE-6.4",
        "Paragraphs for related information",
        (
            "A paragraph must hold the facts that belong together, and only those facts. "
            "Report a paragraph that holds a fact that belongs to a different paragraph, or a "
            "paragraph that holds only a part of one idea."
        ),
    ),
    (
        "STE-6.5",
        "One topic for each paragraph",
        (
            "Report a paragraph that changes its subject in the middle. Propose the place to "
            "divide it."
        ),
    ),
    (
        "STE-8.3",
        "The permitted uses of parentheses",
        (
            "Parentheses are only for a reference, such as a figure or a step, and for text "
            "that the reader sees on a display or on a label. Report parentheses that hold an "
            "explanation or a second idea. Propose a separate sentence for it."
        ),
    ),
    (
        "STE-9.1",
        "A different sentence construction",
        (
            "When an approved word does not fit, the answer is a new sentence, and not a "
            "strange word. Report a sentence that is still difficult to read."
        ),
    ),
    (
        "STE-9.2",
        "Each word in its correct place",
        (
            "An approved word in the wrong place or in the wrong part of speech is still "
            "wrong. Report a word that has an unusual position or function."
        ),
    ),
    (
        "STE-9.4",
        "A consistent style",
        (
            "The same action must have the same words in each place, for example "
            '"Remove the panel" and not "Take the panel off" later. Report two different '
            "phrases for one action or one item in the paragraph."
        ),
    ),
)
RULE_IDS = tuple(rule[0] for rule in RULES)

ANSWER_SCHEMA: dict[str, object] = {
    "type": "object",
    "properties": {
        "findings": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "rule_id": {"type": "string", "enum": list(RULE_IDS)},
                    "quote": {"type": "string"},
                    "message": {"type": "string"},
                    "suggestion": {"type": "string"},
                },
                "required": ["rule_id", "quote", "message", "suggestion"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["findings"],
    "additionalProperties": False,
}


def system_prompt() -> str:
    """Return the fixed instructions. They do not change between requests, thus they cache."""
    rules = "\n".join(f"- {rule_id} ({name}): {text}" for rule_id, name, text in RULES)
    return (
        "You review technical documentation against the ASD-STE100 rules that need the "
        "judgment of a reader. A deterministic checker already finds punctuation, sentence "
        "length, the passive voice, contractions, phrasal verbs, and unapproved words. "
        "Do not report those subjects.\n\n"
        "Each answer is advice for a writer, and not a defect. Report only a clear problem. "
        "An empty list is a good answer for a good paragraph.\n\n"
        f"The rules:\n{rules}\n\n"
        "Instructions:\n"
        "- Read the paragraph in the <paragraph> element. The <heading> element gives its "
        "section, for context only. Do not report the heading.\n"
        "- For each problem, give the rule_id, a quote, a message, and a suggestion.\n"
        "- The quote is an exact copy of 2 to 12 consecutive words of the paragraph, with "
        "the same characters. The tool finds the quote in the source and drops each "
        "finding whose quote it cannot find.\n"
        "- The message says what you see, in one or two short sentences.\n"
        "- The suggestion gives one correction. Keep the meaning.\n"
        "- Do not change a quotation, a name, code, an identifier, or a command.\n"
        "- Do not copy the text of the ASD-STE100 standard.\n"
        "- Give at most five findings for a paragraph.\n"
        "- Write the message and the suggestion in Simplified Technical English: short "
        "sentences, the active voice, and no contractions."
    )


@dataclass(frozen=True)
class Unit:
    """One paragraph, or one list, and the heading of its section."""

    heading: str
    text: str
    start: int


def user_prompt(unit: Unit) -> str:
    """Return the request text for one paragraph."""
    return f"<heading>{unit.heading}</heading>\n<paragraph>\n{unit.text}\n</paragraph>"


def units(source: str) -> list[Unit]:
    """Group the prose of a source into paragraphs with their section heading.

    Consecutive list items become one unit, because a list is one topic.
    """
    doc = parse(source)
    groups: list[tuple[str, int, int, int, int]] = []  # kind, first block, start, end, words
    for sentence in doc.sentences:
        last = groups[-1] if groups else None
        if last and last[1] == sentence.block:
            groups[-1] = (last[0], last[1], last[2], sentence.end, last[4] + sentence.words)
        else:
            groups.append(
                (sentence.kind, sentence.block, sentence.start, sentence.end, sentence.words)
            )
    out: list[Unit] = []
    heading = ""
    previous: tuple[str, int] = ("", -2)
    for kind, block, start, end, words in groups:
        if kind == "heading":
            heading = " ".join(source[start:end].split())
            previous = (kind, block)
            continue
        if kind == "table-cell":
            previous = (kind, block)
            continue
        joined = kind == "list-item" and previous == ("list-item", block - 1) and out
        if joined:
            merged = out[-1]
            out[-1] = Unit(merged.heading, source[merged.start : end], merged.start)
        elif words >= MIN_WORDS or kind == "list-item":
            out.append(Unit(heading, source[start:end], start))
        previous = (kind, block)
    return [u for u in out if len(u.text.split()) >= MIN_WORDS]


def locate(text: str, quote: str) -> tuple[int, int] | None:
    """Find a quote in a paragraph. Line breaks and spaces of the source can differ."""
    words = quote.split()
    if not words:
        return None
    exact = text.find(quote)
    if exact >= 0:
        return exact, exact + len(quote)
    pattern = r"\s+".join(re.escape(word) for word in words)
    match = re.search(pattern, text)
    return (match.start(), match.end()) if match else None


def parse_answer(text: str) -> list[dict[str, str]]:
    """Read the JSON answer of the model and keep only the valid findings."""
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return []
    items = data.get("findings") if isinstance(data, dict) else None
    if not isinstance(items, list):
        return []
    keys = ("rule_id", "quote", "message", "suggestion")
    kept = []
    for item in items:
        if not isinstance(item, dict) or not all(isinstance(item.get(k), str) for k in keys):
            continue
        if item["rule_id"] not in RULE_IDS or not item["quote"].strip():
            continue
        kept.append({k: item[k].strip() for k in keys})
    return kept


class Client(Protocol):
    """The contract of a model client. A test gives a fake client."""

    def ask(self, system: str, prompt: str) -> str:
        """Send one paragraph and return the JSON text of the answer."""
        ...


class AnthropicClient:
    """A client for the Messages API of Anthropic."""

    def __init__(self, model: str, sdk: Anthropic) -> None:
        """Keep the model name and the SDK client."""
        self.model = model
        self.sdk = sdk

    def ask(self, system: str, prompt: str) -> str:
        """Send one paragraph with the cached system prompt and a JSON schema for the answer."""
        response = self.sdk.messages.create(
            model=self.model,
            max_tokens=MAX_TOKENS,
            system=[{"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}],
            messages=[{"role": "user", "content": prompt}],
            output_config={"format": {"type": "json_schema", "schema": ANSWER_SCHEMA}},
        )
        if response.stop_reason != "end_turn":
            msg = f"the model stopped with {response.stop_reason}"
            raise RuntimeError(msg)
        return next((b.text for b in response.content if b.type == "text"), "")


def make_client(model: str, timeout: float) -> Client:
    """Make the real client. Fail with a clear message when the extra or the key is missing."""
    try:
        import anthropic  # noqa: PLC0415 - The SDK is an optional extra.
    except ImportError as err:
        raise ValueError(EXTRA_HINT) from err
    if not (os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_AUTH_TOKEN")):
        raise ValueError(KEY_HINT)
    # The SDK retries a rate limit (429), an overload, and a connection error with a backoff.
    return AnthropicClient(model, anthropic.Anthropic(timeout=timeout, max_retries=MAX_RETRIES))


def cache_directory() -> Path:
    """Return the directory of the cached answers."""
    return user_cache_path("ste") / "review"


@dataclass
class Cache:
    """Answers on disk, because a second request can give a different answer."""

    directory: Path | None

    @staticmethod
    def key(model: str, unit: Unit) -> str:
        """Return the hash of the rule set version, the model, and the paragraph."""
        data = json.dumps([RULES_VERSION, model, unit.heading, unit.text], ensure_ascii=False)
        return hashlib.sha256(data.encode("utf-8")).hexdigest()

    def _path(self, key: str) -> Path | None:
        return self.directory / key[:2] / f"{key}.json" if self.directory else None

    def get(self, key: str) -> list[dict[str, str]] | None:
        """Return a cached answer, or None."""
        path = self._path(key)
        if path is None or not path.is_file():
            return None
        try:
            return parse_answer(path.read_text(encoding="utf-8"))
        except OSError:
            return None

    def put(self, key: str, findings: list[dict[str, str]]) -> None:
        """Write an answer. A failure to write is not an error of the review."""
        path = self._path(key)
        if path is None:
            return
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            temp = path.with_suffix(f".{os.getpid()}.tmp")
            temp.write_text(json.dumps({"findings": findings}, ensure_ascii=False), "utf-8")
            temp.replace(path)
        except OSError:
            return


@dataclass
class Source:
    """One file and its paragraphs."""

    path: str
    text: str
    words: int
    units: list[Unit]


def read_source(path: str, text: str) -> Source:
    """Split one source into its review units."""
    return Source(path, text, parse(text).word_count(), units(text))


@dataclass
class Plan:
    """What a review sends, before it sends a request."""

    model: str
    sources: list[Source]
    keys: list[list[str]]
    cached: list[list[list[dict[str, str]] | None]]

    def counts(self) -> dict[str, int]:
        """Count the paragraphs, the requests, and the approximate input tokens."""
        paragraphs = sum(len(s.units) for s in self.sources)
        pending = [
            unit
            for source, answers in zip(self.sources, self.cached, strict=True)
            for unit, answer in zip(source.units, answers, strict=True)
            if answer is None
        ]
        system = len(system_prompt()) // CHARS_PER_TOKEN
        unit_tokens = sum(len(user_prompt(u)) // CHARS_PER_TOKEN for u in pending)
        return {
            "files": len(self.sources),
            "paragraphs": paragraphs,
            "cached": paragraphs - len(pending),
            "requests": len(pending),
            "approx_input_tokens": unit_tokens + len(pending) * (system + REQUEST_OVERHEAD_TOKENS),
            "approx_system_tokens": system,
        }


def plan(sources: list[Source], model: str, cache: Cache) -> Plan:
    """Find the cached answers and the requests that a run must send."""
    keys = [[Cache.key(model, u) for u in s.units] for s in sources]
    cached = [[cache.get(k) for k in row] for row in keys]
    return Plan(model, sources, keys, cached)


@dataclass
class Outcome:
    """The findings of a review and the count of failed requests."""

    results: list[report.FileResult] = field(default_factory=list)
    failed: int = 0
    errors: list[str] = field(default_factory=list)


def _findings(path: str, source: str, unit: Unit, answer: list[dict[str, str]]) -> list:
    seen: set[tuple[str, int, int]] = set()
    out = []
    for item in answer:
        span = locate(unit.text, item["quote"])
        if span is None:
            continue
        start, end = unit.start + span[0], unit.start + span[1]
        if (item["rule_id"], start, end) in seen:
            continue
        seen.add((item["rule_id"], start, end))
        diag = Diagnostic(
            item["rule_id"], item["message"], "info", CONFIDENCE, start, end, item["suggestion"]
        )
        finding = report.make_finding(path, source, diag)
        finding.data["kind"] = KIND
        out.append(finding)
    return out


def run(
    work: Plan, cache: Cache, client_factory: Callable[[], Client], jobs: int = DEFAULT_JOBS
) -> Outcome:
    """Send each paragraph that has no cached answer, and map the answers to the source."""
    pending = [
        (i, j)
        for i, row in enumerate(work.cached)
        for j, answer in enumerate(row)
        if answer is None
    ]
    answers = [list(row) for row in work.cached]
    outcome = Outcome()
    if pending:
        client = client_factory()
        system = system_prompt()

        def ask(index: tuple[int, int]) -> tuple[tuple[int, int], list | None, str]:
            unit = work.sources[index[0]].units[index[1]]
            try:
                return index, parse_answer(client.ask(system, user_prompt(unit))), ""
            except Exception as err:  # noqa: BLE001 - One failed request must not stop the review.
                return index, None, f"{work.sources[index[0]].path}: {err}"

        with ThreadPoolExecutor(max_workers=max(1, jobs)) as pool:
            for (i, j), answer, error in pool.map(ask, pending):
                if answer is None:
                    outcome.failed += 1
                    outcome.errors.append(error)
                    continue
                answers[i][j] = answer
                cache.put(work.keys[i][j], answer)
    for source, row in zip(work.sources, answers, strict=True):
        findings = [
            f
            for unit, answer in zip(source.units, row, strict=True)
            if answer is not None
            for f in _findings(source.path, source.text, unit, answer)
        ]
        outcome.results.append(report.FileResult(source.path, source.words, findings))
    return outcome


@dataclass
class ReviewReport(report.Report):
    """A report with the request counts of the review in its summary."""

    extra: dict[str, int | float | bool | str] = field(default_factory=dict)

    def summary(self) -> dict:
        """Add the request counts to the usual summary."""
        return {**super().summary(), **self.extra}
