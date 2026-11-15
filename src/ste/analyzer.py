# Copyright (c) 2026 Tudor Andrei Dumitrascu
"""Optional local NLP and the external analyzer protocol."""

from __future__ import annotations

import importlib
import importlib.util
import json
import os
import queue
import shlex
import subprocess
import sys
import threading
from contextlib import suppress
from pathlib import Path
from typing import TYPE_CHECKING, TypedDict, cast

if TYPE_CHECKING:
    from ste.analyzer_worker import NLPModel

from ste.models import SyntaxToken

MODEL = "en_core_web_sm"
START_TIMEOUT = 60.0
RESPONSE_TIMEOUT = 60.0
_MISSING_MODEL = 3
_INVALID_INTERPRETER = 4


class AnalyzerStatus(TypedDict):
    """Installation status of the grammar analyzer and model."""

    ready: bool
    python: str
    script: str
    spacy: bool
    problem: str
    fix: list[str]


class _ProtocolError(ValueError):
    """The external analyzer returned data outside its wire contract."""


def _integer(token: dict[str, object], key: str) -> int:
    value = token.get(key, 0)
    if type(value) is not int:
        msg = "the analyzer token offsets must be integers"
        raise _ProtocolError(msg)
    return value


def _label(token: dict[str, object], key: str) -> str:
    value = token.get(key, "")
    if not isinstance(value, str):
        msg = "the analyzer token labels must be strings"
        raise _ProtocolError(msg)
    return value


def _parse_tokens(raw: object) -> list[SyntaxToken]:
    if not isinstance(raw, list):
        msg = "the analyzer tokens must be a list"
        raise _ProtocolError(msg)
    tokens = []
    for token in raw:
        if not isinstance(token, dict):
            msg = "the analyzer gave invalid tokens"
            raise _ProtocolError(msg)
        tokens.append(
            SyntaxToken(
                index=_integer(token, "i"),
                text=_label(token, "text"),
                pos=_label(token, "pos"),
                tag=_label(token, "tag"),
                dep=_label(token, "dep"),
                head=_integer(token, "head"),
                start=_integer(token, "start"),
            )
        )
    return tokens


class Analyzer:
    """Provide cached grammar data for checker rules."""

    def __init__(self) -> None:
        """Create the sentence cache for one run."""
        self._cache: dict[str, list[SyntaxToken]] = {}

    def analyze(self, text: str) -> list[SyntaxToken]:
        """Return grammar tokens for a sentence."""
        raise NotImplementedError

    def grammar(self, sentence: str) -> tuple[list[SyntaxToken], bool]:
        """Return tokens and whether grammar data is available."""
        try:
            tokens = self.analyze(sentence)
            return tokens, bool(tokens)
        except (ValueError, OSError, RuntimeError):
            return [], False

    def passive_at(self, sentence: str, offset: int) -> tuple[bool, bool]:
        """Check passive relations at a sentence character offset."""
        tokens, known = self.grammar(sentence)
        if not known:
            return False, False
        verb = next((t.index for t in tokens if t.start == offset), None)
        if verb is None:
            return False, False
        return any(
            t.head == verb and t.dep in {"auxpass", "nsubjpass", "csubjpass"} for t in tokens
        ), True

    def close(self) -> None:
        """Release analyzer resources."""


def _load_model() -> NLPModel:
    try:
        spacy = importlib.import_module("spacy")
    except ImportError as err:
        msg = 'spaCy is not installed. Run: uv pip install "ste-cli[nlp]"'
        raise ValueError(msg) from err
    try:
        return cast("NLPModel", spacy.load(MODEL, exclude=["ner", "lemmatizer", "textcat"]))
    except OSError as err:
        msg = f"the model {MODEL} is not installed. Run: python -m spacy download {MODEL}"
        raise ValueError(msg) from err


class SpacyAnalyzer(Analyzer):
    """Load a model once and retain each sentence result for this run."""

    def __init__(self) -> None:
        """Load the configured local model once."""
        super().__init__()
        self.nlp = _load_model()
        self.model = MODEL

    def analyze(self, text: str) -> list[SyntaxToken]:
        """Analyze a sentence with the local model, using its cached result."""
        if text not in self._cache:
            self._cache[text] = [
                SyntaxToken(t.i, t.text, t.pos_, t.tag_, t.dep_, t.head.i, t.idx)
                for t in self.nlp(text)
            ]
        return self._cache[text]


class ExternalAnalyzer(Analyzer):
    """Run an analyzer with one JSON object per line in each direction."""

    def __init__(self, argv: list[str]) -> None:
        """Start a user-selected command and validate its ready response."""
        super().__init__()
        if not argv:
            msg = "the analyzer command is empty"
            raise ValueError(msg)
        # The user explicitly selects this executable; no shell is used.
        self._process = subprocess.Popen(  # noqa: S603
            argv, stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True, encoding="utf-8"
        )
        self._responses: queue.Queue[str | None] = queue.Queue()
        self._lock = threading.Lock()
        self._next = 0
        self._reader = threading.Thread(target=self._read_output, daemon=True)
        self._reader.start()
        try:
            self.model = self._ready_model()
        except (ValueError, OSError):
            self.close()
            raise

    def _ready_model(self) -> str:
        ready = self._receive(START_TIMEOUT)
        if not ready.get("ready"):
            msg = "the analyzer did not give a ready line"
            raise ValueError(msg)
        return str(ready.get("model", ""))

    def _read_output(self) -> None:
        stdout = self._process.stdout
        try:
            if stdout is not None:
                for line in stdout:
                    self._responses.put(line)
        finally:
            self._responses.put(None)

    def _receive(self, timeout: float) -> dict[str, object]:
        try:
            line = self._responses.get(timeout=timeout)
        except queue.Empty as err:
            msg = "the analyzer did not answer before the timeout"
            raise ValueError(msg) from err
        if line is None:
            msg = "the analyzer stopped before it gave an answer"
            raise ValueError(msg)
        try:
            result = json.loads(line)
        except ValueError as err:
            msg = "the analyzer did not give valid JSON"
            raise ValueError(msg) from err
        if not isinstance(result, dict):
            msg = "the analyzer did not give a JSON object"
            raise _ProtocolError(msg)
        return result

    def analyze(self, text: str) -> list[SyntaxToken]:
        """Request a sentence and retain its validated token response."""
        with self._lock:
            if text in self._cache:
                return self._cache[text]
            self._next += 1
            stdin = self._process.stdin
            if stdin is None:
                msg = "the analyzer input pipe is unavailable"
                raise RuntimeError(msg)
            stdin.write(json.dumps({"id": self._next, "text": text}) + "\n")
            stdin.flush()
            result = self._receive(RESPONSE_TIMEOUT)
            if result.get("error"):
                raise ValueError(str(result["error"]))
            if result.get("id") != self._next:
                msg = "the analyzer gave a different request ID"
                raise ValueError(msg)
            tokens = _parse_tokens(result.get("tokens", []))
            self._cache[text] = tokens
            return tokens

    def close(self) -> None:
        """Stop the external analyzer and close its process pipes."""
        process = self._process
        if process.stdin and not process.stdin.closed:
            try:
                if process.poll() is None:
                    process.stdin.write('{"stop": true}\n')
                    process.stdin.flush()
            except (OSError, ValueError):
                pass
            finally:
                with suppress(OSError, ValueError):
                    process.stdin.close()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()
        if process.stdout:
            process.stdout.close()


def create(command: str | None = None) -> Analyzer:
    """Select the requested external analyzer or a local spaCy model."""
    if command is not None:
        return ExternalAnalyzer(shlex.split(command))
    if python := os.environ.get("STE_PYTHON"):
        return ExternalAnalyzer([python, str(Path(__file__).with_name("analyzer_worker.py"))])
    return SpacyAnalyzer()


def check() -> AnalyzerStatus:
    """Describe the model requirements for the selected interpreter."""
    python = os.environ.get("STE_PYTHON") or sys.executable
    script = str(Path(__file__).with_name("analyzer_worker.py"))
    problem = ""
    fix: list[str] = []
    if python != sys.executable:
        try:
            # STE_PYTHON is an explicit interpreter selection; no shell is used.
            result = subprocess.run(  # noqa: S603
                [
                    python,
                    "-c",
                    (
                        "import spacy, importlib.util as u; "
                        "raise SystemExit(0 if u.find_spec('en_core_web_sm') else 3)"
                    ),
                ],
                capture_output=True,
                timeout=START_TIMEOUT,
                check=False,
            )
            code = result.returncode
        except (OSError, subprocess.TimeoutExpired):
            code = _INVALID_INTERPRETER
    else:
        try:
            code = 0 if importlib.util.find_spec("spacy") else 1
            if code == 0 and not importlib.util.find_spec(MODEL):
                code = _MISSING_MODEL
        except (ImportError, ValueError):
            code = 1
    if code == _MISSING_MODEL:
        problem = f"the model {MODEL} is not installed"
        fix = [f"{python} -m spacy download {MODEL}"]
    elif code == _INVALID_INTERPRETER:
        problem = f"the Python interpreter {python} cannot run"
        fix = ["Set STE_PYTHON to a Python interpreter that can run"]
    elif code:
        problem = f"spaCy is not installed for {python}"
        fix = ['uv pip install "ste-cli[nlp]"', f"{python} -m spacy download {MODEL}"]
    return {
        "ready": not problem,
        "python": python,
        "script": script,
        "spacy": not problem,
        "problem": problem,
        "fix": fix,
    }
