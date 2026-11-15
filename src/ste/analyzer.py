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
import time
from contextlib import suppress
from importlib import metadata
from pathlib import Path
from typing import TYPE_CHECKING, TypedDict, cast

from ste import grammar_cache
from ste.analyzer_worker import (
    BATCH_SIZE,
    DEFAULT_PARTS,
    MODEL,
    excluded,
    in_lexicon,
    lexicon,
    model_identity,
    model_version,
)
from ste.models import SyntaxToken

if TYPE_CHECKING:
    from ste.analyzer_worker import NLPModel

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
    cache: str


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


def _flag(token: dict[str, object], key: str) -> bool:
    value = token.get(key, True)
    if not isinstance(value, bool):
        msg = "the analyzer token flags must be true or false"
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
                lemma=_label(token, "lemma"),
                in_lexicon=_flag(token, "in_lexicon"),
            )
        )
    return tokens


class Analyzer:
    """Provide grammar data for checker rules, with a cache for each run.

    A subclass gives ``analyze`` for one sentence, and it can replace
    ``analyze_batch`` to analyze many sentences in one request. ``identity``
    names the model, its version, and its pipeline. When it is not empty,
    the results also go to the disk cache of ``ste.grammar_cache``.
    """

    identity = ""

    def __init__(self) -> None:
        """Create the sentence cache for one run."""
        self._cache: dict[str, list[SyntaxToken]] = {}
        self._disk: grammar_cache.GrammarCache | None = None

    def analyze(self, text: str) -> list[SyntaxToken]:
        """Return grammar tokens for a sentence."""
        raise NotImplementedError

    def analyze_batch(self, texts: list[str]) -> list[list[SyntaxToken]]:
        """Return grammar tokens for each sentence. An empty list is not known."""
        out = []
        for text in texts:
            try:
                out.append(self.analyze(text))
            except ValueError, OSError, RuntimeError:
                out.append([])
        return out

    def grammar(self, sentence: str) -> tuple[list[SyntaxToken], bool]:
        """Return tokens and whether grammar data is available."""
        tokens = self.grammar_many([sentence])[0]
        return tokens, bool(tokens)

    def grammar_many(self, sentences: list[str]) -> list[list[SyntaxToken]]:
        """Return the tokens of each sentence. Only the new sentences go to the model."""
        missing = list(dict.fromkeys(s for s in sentences if s not in self._cache))
        if missing and self.identity and self._disk is None:
            self._disk = grammar_cache.GrammarCache(self.identity)
        if missing and self._disk is not None:
            self._cache.update(self._disk.get_many(missing))
            missing = [s for s in missing if s not in self._cache]
        if missing:
            try:
                results = self.analyze_batch(missing)
            except ValueError, OSError, RuntimeError:
                results = [[] for _ in missing]
            found = {text: tokens for text, tokens in zip(missing, results, strict=True) if tokens}
            self._cache.update(found)
            if self._disk is not None:
                self._disk.put_many(found)
        return [self._cache.get(s, []) for s in sentences]

    def close(self) -> None:
        """Release analyzer resources."""
        if self._disk is not None:
            self._disk.close()
            self._disk = None


def _load_model(parts: frozenset[str]) -> NLPModel:
    try:
        spacy = importlib.import_module("spacy")
    except ImportError as err:
        msg = 'spaCy is not installed. Run: uv pip install "ste-cli[nlp]"'
        raise ValueError(msg) from err
    try:
        return cast("NLPModel", spacy.load(MODEL, exclude=excluded(parts)))
    except OSError as err:
        msg = f"the model {MODEL} is not installed. Run: python -m spacy download {MODEL}"
        raise ValueError(msg) from err


class SpacyAnalyzer(Analyzer):
    """Analyze the sentences of a document in one batch with a local model.

    ``parts`` selects the optional pipeline parts. ``frozenset()`` loads only
    the tagger: the tokens then have no dependency relation. The model loads
    at the first sentence that the disk cache does not hold. Thus a run that
    reads only the cache does not import spaCy.
    """

    def __init__(self, parts: frozenset[str] = DEFAULT_PARTS) -> None:
        """Find the local model and name it, without loading it."""
        super().__init__()
        self._nlp: NLPModel | None = None
        self._words: frozenset[str] = frozenset()
        try:
            version = model_version()
        except metadata.PackageNotFoundError:
            # The load gives the message and the command that installs the part.
            self._nlp = _load_model(parts)
            self._words = lexicon(self._nlp)
            version = model_version()
        self._parts = parts
        self.model = MODEL
        self.identity = model_identity(version, parts)

    @property
    def nlp(self) -> NLPModel:
        """Return the model, and load it at the first use."""
        if self._nlp is None:
            self._nlp = _load_model(self._parts)
            self._words = lexicon(self._nlp)
        return self._nlp

    def analyze(self, text: str) -> list[SyntaxToken]:
        """Analyze one sentence with the local model."""
        return self.analyze_batch([text])[0]

    def analyze_batch(self, texts: list[str]) -> list[list[SyntaxToken]]:
        """Analyze many sentences with one call of ``nlp.pipe``."""
        nlp = self.nlp
        return [
            [
                SyntaxToken(
                    t.i,
                    t.text,
                    t.pos_,
                    t.tag_,
                    t.dep_,
                    t.head.i,
                    t.idx,
                    t.lemma_,
                    in_lexicon(t.text, t.pos_, self._words),
                )
                for t in doc
            ]
            for doc in nlp.pipe(texts, batch_size=BATCH_SIZE)
        ]


class ExternalAnalyzer(Analyzer):
    """Run an analyzer with one JSON object per line in each direction.

    When the ready line gives ``"batch": true``, one request holds many
    sentences. Otherwise each request holds one sentence. A ready line with
    a ``"version"`` also enables the disk cache.
    """

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
        self._batch = False
        self._reader = threading.Thread(target=self._read_output, daemon=True)
        self._reader.start()
        try:
            self.model = self._ready_model()
        except ValueError, OSError:
            self.close()
            raise

    def _ready_model(self) -> str:
        ready = self._receive(START_TIMEOUT)
        if not ready.get("ready"):
            msg = "the analyzer did not give a ready line"
            raise ValueError(msg)
        model = str(ready.get("model", ""))
        self._batch = ready.get("batch") is True
        version = ready.get("version")
        pipeline = ready.get("pipeline")
        if model and isinstance(version, str) and version:
            parts = ",".join(map(str, pipeline)) if isinstance(pipeline, list) else ""
            self.identity = f"{model}\x00{version}\x00{parts}"
        return model

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

    def _response_for(self, request_id: int) -> dict[str, object]:
        """Read until the answer to one request, discarding stale earlier answers."""
        deadline = time.monotonic() + RESPONSE_TIMEOUT
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                msg = "the analyzer did not answer before the timeout"
                raise ValueError(msg)
            result = self._receive(remaining)
            response_id = result.get("id")
            # An earlier request timed out, and its late answer arrives now.
            if type(response_id) is int and response_id < request_id:
                continue
            if type(response_id) is int and response_id == request_id:
                return result
            if response_id is None and result.get("error"):
                return result
            msg = "the analyzer gave a different request ID"
            raise ValueError(msg)

    def _request(self, payload: dict[str, object]) -> dict[str, object]:
        """Send one request and return its answer."""
        with self._lock:
            self._next += 1
            stdin = self._process.stdin
            if stdin is None:
                msg = "the analyzer input pipe is unavailable"
                raise RuntimeError(msg)
            stdin.write(json.dumps({"id": self._next, **payload}) + "\n")
            stdin.flush()
            result = self._response_for(self._next)
        if result.get("error"):
            raise ValueError(str(result["error"]))
        return result

    def analyze(self, text: str) -> list[SyntaxToken]:
        """Request one sentence and return its validated tokens."""
        return _parse_tokens(self._request({"text": text}).get("tokens", []))

    def analyze_batch(self, texts: list[str]) -> list[list[SyntaxToken]]:
        """Request many sentences at a time when the analyzer accepts a batch."""
        if not self._batch:
            return super().analyze_batch(texts)
        out: list[list[SyntaxToken]] = []
        for i in range(0, len(texts), BATCH_SIZE):
            chunk = texts[i : i + BATCH_SIZE]
            results = self._request({"texts": chunk}).get("results")
            if not isinstance(results, list) or len(results) != len(chunk):
                msg = "the analyzer gave a different number of results"
                raise _ProtocolError(msg)
            for result in results:
                try:
                    out.append(_parse_tokens(result))
                except _ProtocolError:
                    # An object with "error" is a failed sentence, and not a token list.
                    out.append([])
        return out

    def close(self) -> None:
        """Stop the external analyzer and close its process pipes."""
        super().close()
        process = self._process
        if process.stdin and not process.stdin.closed:
            try:
                if process.poll() is None:
                    process.stdin.write('{"stop": true}\n')
                    process.stdin.flush()
            except OSError, ValueError:
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
        except OSError, subprocess.TimeoutExpired:
            code = _INVALID_INTERPRETER
    else:
        try:
            code = 0 if importlib.util.find_spec("spacy") else 1
            if code == 0 and not importlib.util.find_spec(MODEL):
                code = _MISSING_MODEL
        except ImportError, ValueError:
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
    cache = grammar_cache.default_path()
    return {
        "ready": not problem,
        "python": python,
        "script": script,
        "spacy": not problem,
        "problem": problem,
        "fix": fix,
        "cache": str(cache) if cache else "",
    }
