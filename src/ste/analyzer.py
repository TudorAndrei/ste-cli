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
from pathlib import Path
from typing import Any

from ste.models import SyntaxToken

MODEL = "en_core_web_sm"
START_TIMEOUT = 60.0
RESPONSE_TIMEOUT = 60.0


class Analyzer:
    def __init__(self) -> None:
        self._cache: dict[str, list[SyntaxToken]] = {}

    def analyze(self, text: str) -> list[SyntaxToken]:
        raise NotImplementedError

    def grammar(self, sentence: str) -> tuple[list[SyntaxToken], bool]:
        try:
            tokens = self.analyze(sentence)
            return tokens, bool(tokens)
        except (ValueError, OSError, RuntimeError):
            return [], False

    def passive_at(self, sentence: str, offset: int) -> tuple[bool, bool]:
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


def _load_model() -> Any:
    try:
        spacy = importlib.import_module("spacy")
    except ImportError as err:
        raise ValueError('spaCy is not installed. Run: uv pip install "ste-cli[nlp]"') from err
    try:
        return spacy.load(MODEL, exclude=["ner", "lemmatizer", "textcat"])
    except OSError as err:
        raise ValueError(
            f"the model {MODEL} is not installed. Run: python -m spacy download {MODEL}"
        ) from err


class SpacyAnalyzer(Analyzer):
    """Load a model once and retain each sentence result for this run."""

    def __init__(self) -> None:
        super().__init__()
        self.nlp = _load_model()
        self.model = MODEL

    def analyze(self, text: str) -> list[SyntaxToken]:
        if text not in self._cache:
            self._cache[text] = [
                SyntaxToken(t.i, t.text, t.pos_, t.tag_, t.dep_, t.head.i, t.idx)
                for t in self.nlp(text)
            ]
        return self._cache[text]


class ExternalAnalyzer(Analyzer):
    """Run an analyzer with one JSON object per line in each direction."""

    def __init__(self, argv: list[str]) -> None:
        super().__init__()
        if not argv:
            raise ValueError("the analyzer command is empty")
        self._process = subprocess.Popen(
            argv, stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True, encoding="utf-8"
        )
        self._responses: queue.Queue[str | None] = queue.Queue()
        self._lock = threading.Lock()
        self._next = 0
        self._reader = threading.Thread(target=self._read_output, daemon=True)
        self._reader.start()
        try:
            ready = self._receive(START_TIMEOUT)
            if not ready.get("ready"):
                raise ValueError("the analyzer did not give a ready line")
            self.model = str(ready.get("model", ""))
        except (ValueError, OSError):
            self.close()
            raise

    def _read_output(self) -> None:
        assert self._process.stdout is not None
        try:
            for line in self._process.stdout:
                self._responses.put(line)
        finally:
            self._responses.put(None)

    def _receive(self, timeout: float) -> dict[str, Any]:
        try:
            line = self._responses.get(timeout=timeout)
        except queue.Empty as err:
            raise ValueError("the analyzer did not answer before the timeout") from err
        if line is None:
            raise ValueError("the analyzer stopped before it gave an answer")
        try:
            result = json.loads(line)
        except ValueError as err:
            raise ValueError("the analyzer did not give valid JSON") from err
        if not isinstance(result, dict):
            raise ValueError("the analyzer did not give a JSON object")
        return result

    def analyze(self, text: str) -> list[SyntaxToken]:
        with self._lock:
            if text in self._cache:
                return self._cache[text]
            self._next += 1
            assert self._process.stdin is not None
            self._process.stdin.write(json.dumps({"id": self._next, "text": text}) + "\n")
            self._process.stdin.flush()
            result = self._receive(RESPONSE_TIMEOUT)
            if result.get("error"):
                raise ValueError(str(result["error"]))
            if result.get("id") != self._next:
                raise ValueError("the analyzer gave a different request ID")
            raw = result.get("tokens", [])
            if not isinstance(raw, list):
                raise ValueError("the analyzer tokens must be a list")
            tokens = []
            for token in raw:
                if not isinstance(token, dict):
                    raise ValueError("the analyzer gave invalid tokens")
                if any(type(token.get(k, 0)) is not int for k in ("i", "head", "start")):
                    raise ValueError("the analyzer token offsets must be integers")
                if any(
                    not isinstance(token.get(k, ""), str) for k in ("text", "pos", "tag", "dep")
                ):
                    raise ValueError("the analyzer token labels must be strings")
                tokens.append(
                    SyntaxToken(
                        index=token.get("i", 0),
                        text=token.get("text", ""),
                        pos=token.get("pos", ""),
                        tag=token.get("tag", ""),
                        dep=token.get("dep", ""),
                        head=token.get("head", 0),
                        start=token.get("start", 0),
                    )
                )
            self._cache[text] = tokens
            return tokens

    def close(self) -> None:
        process = self._process
        if process.stdin and not process.stdin.closed:
            try:
                if process.poll() is None:
                    process.stdin.write('{"stop": true}\n')
                    process.stdin.flush()
            except (OSError, ValueError):
                pass
            finally:
                try:
                    process.stdin.close()
                except (OSError, ValueError):
                    pass
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()
        if process.stdout:
            process.stdout.close()


def create(command: str | None = None) -> Analyzer:
    if command is not None:
        return ExternalAnalyzer(shlex.split(command))
    if python := os.environ.get("STE_PYTHON"):
        return ExternalAnalyzer([python, str(Path(__file__).with_name("analyzer_worker.py"))])
    return SpacyAnalyzer()


def check() -> dict[str, Any]:
    python = os.environ.get("STE_PYTHON") or sys.executable
    script = str(Path(__file__).with_name("analyzer_worker.py"))
    problem = ""
    fix: list[str] = []
    if python != sys.executable:
        try:
            result = subprocess.run(
                [
                    python,
                    "-c",
                    "import spacy, importlib.util as u; raise SystemExit(0 if u.find_spec('en_core_web_sm') else 3)",
                ],
                capture_output=True,
                timeout=START_TIMEOUT,
                check=False,
            )
            code = result.returncode
        except (OSError, subprocess.TimeoutExpired):
            code = 4
    else:
        try:
            code = 0 if importlib.util.find_spec("spacy") else 1
            if code == 0 and not importlib.util.find_spec(MODEL):
                code = 3
        except (ImportError, ValueError):
            code = 1
    if code == 3:
        problem = f"the model {MODEL} is not installed"
        fix = [f"{python} -m spacy download {MODEL}"]
    elif code == 4:
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
