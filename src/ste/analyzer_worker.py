# Copyright (c) 2026 Tudor Andrei Dumitrascu
"""A syntax analyzer for the ste checker.

Some rules of ASD-STE100 need the syntax of a sentence, and not only its
words. Rule 3.6 is an example: the difference between "the valve is closed"
(an adjective) and "the valve is closed by the operator" (the passive voice)
is a relation between two words, and not a word list.

This program gives that syntax to a command through standard input. The command sends
sentences, and this program answers with one object for each sentence: each
token, its part of speech, and its relation to its head.

    ste lint --analyze docs/

The protocol is one JSON object for each line, in both directions:

    in : {"id": 1, "text": "The valve is closed by the operator."}
    out: {"id": 1, "tokens": [{"i":0,"text":"The","pos":"DET","dep":"det",
                               "head":1,"start":0,"lemma":"the"}, ...]}

The ready line gives "batch": true. Thus the command can also send many
sentences in one request, and get one result for each, in the same order:

    in : {"id": 2, "texts": ["Open the valve.", "Close it."]}
    out: {"id": 2, "results": [[...tokens...], [...tokens...]]}

The command starts this program one time for each run, thus the model loads
one time. An error on one sentence gives an object with "error", and the
command then uses its own rules for that sentence.

This file must not import the ste package: $STE_PYTHON can select an
interpreter that has spaCy and not ste.
"""

from __future__ import annotations

import importlib
import json
import sys
from importlib import metadata
from typing import TYPE_CHECKING, Protocol, cast

if TYPE_CHECKING:
    from collections.abc import Iterable, Iterator

MODEL = "en_core_web_sm"
# The parts of the pipeline that a caller can ask for. The tagger and the
# attribute ruler give the part of speech, and they always load.
PARTS = frozenset({"parser", "lemmatizer"})
# The rules of today need the parser. The lemmatizer adds about 15 percent.
DEFAULT_PARTS = frozenset({"parser", "lemmatizer"})
# The model parts that no rule reads.
_NEVER = ("ner", "senter", "textcat")
# The number of sentences in one call of nlp.pipe and in one batch request.
BATCH_SIZE = 256


def excluded(parts: frozenset[str]) -> list[str]:
    """Return the pipeline components that spaCy must not load."""
    return sorted({*_NEVER, *(PARTS - parts)})


class NLPToken(Protocol):
    """Token attributes that the grammar protocol reads from an NLP model."""

    i: int
    text: str
    pos_: str
    tag_: str
    dep_: str
    lemma_: str
    idx: int
    head: NLPToken


class NLPModel(Protocol):
    """A language model that returns annotated tokens."""

    pipe_names: list[str]

    def pipe(self, texts: Iterable[str], batch_size: int) -> Iterator[Iterable[NLPToken]]:
        """Analyze many sentences and return the tokens of each."""
        ...


def model_version() -> str:
    """Return the versions of the model and of spaCy, without loading them."""
    return f"{metadata.version(MODEL)}/spacy-{metadata.version('spacy')}"


def model_identity(version: str, parts: frozenset[str]) -> str:
    """Name the model, its version, and its pipeline parts for a cache key."""
    return "\x00".join([MODEL, version, ",".join(sorted(parts))])


def load_model(parts: frozenset[str] = DEFAULT_PARTS) -> NLPModel:
    """Load spaCy. Only the parts that the rules need stay in the pipeline."""
    try:
        spacy = importlib.import_module("spacy")
    except ImportError:
        msg = (
            "ste-analyzer: spacy is not installed.\n"
            "  uv pip install spacy\n"
            f"  python -m spacy download {MODEL}"
        )
        raise SystemExit(msg) from None
    try:
        return cast("NLPModel", spacy.load(MODEL, exclude=excluded(parts)))
    except OSError:
        msg = (
            f"ste-analyzer: the model {MODEL} is not installed.\n  python -m spacy download {MODEL}"
        )
        raise SystemExit(msg) from None


def _tokens(doc: Iterable[NLPToken]) -> list[dict[str, str | int]]:
    return [
        {
            "i": token.i,
            "text": token.text,
            "pos": token.pos_,
            "tag": token.tag_,
            "dep": token.dep_,
            "head": token.head.i,
            "start": token.idx,
            "lemma": token.lemma_,
        }
        for token in doc
    ]


def analyze(nlp: NLPModel, texts: list[str]) -> list[list[dict[str, str | int]]]:
    """Give one object for each token of each sentence."""
    return [_tokens(doc) for doc in nlp.pipe(texts, batch_size=BATCH_SIZE)]


def _write_response(payload: dict[str, object]) -> None:
    sys.stdout.write(json.dumps(payload) + "\n")
    sys.stdout.flush()


def _one(nlp: NLPModel, text: object) -> list[dict[str, str | int]] | dict[str, str]:
    try:
        return analyze(nlp, [cast("str", text)])[0]
    # An NLP component can raise its own exception. One failed sentence must
    # return an error response without terminating the persistent protocol.
    except Exception as err:  # noqa: BLE001
        return {"error": str(err)}


def _answer(nlp: NLPModel, request: dict[str, object]) -> dict[str, object]:
    texts = request.get("texts")
    if isinstance(texts, list):
        try:
            return {"id": request.get("id"), "results": analyze(nlp, texts)}
        except Exception:  # noqa: BLE001
            # Find the failed sentence: each other sentence keeps its result.
            return {"id": request.get("id"), "results": [_one(nlp, text) for text in texts]}
    result = _one(nlp, request.get("text"))
    if isinstance(result, dict):
        return {"id": request.get("id"), **result}
    return {"id": request.get("id"), "tokens": result}


def _parts(argv: list[str]) -> frozenset[str]:
    """Read "--parts parser,lemmatizer" from the arguments."""
    if len(argv) >= 2 and argv[0] == "--parts":  # noqa: PLR2004
        return frozenset(p for p in argv[1].split(",") if p) & PARTS
    return DEFAULT_PARTS


def main() -> int:
    """Serve grammar requests as one JSON response per input line."""
    parts = _parts(sys.argv[1:])
    nlp = load_model(parts)
    _write_response(
        {
            "ready": True,
            "model": MODEL,
            "version": model_version(),
            "pipeline": sorted(parts),
            "batch": True,
        }
    )
    for raw_line in sys.stdin:
        line = raw_line.strip()
        if not line:
            continue
        try:
            request = json.loads(line)
        except json.JSONDecodeError as err:
            _write_response({"error": f"the line is not JSON: {err}"})
            continue
        if request.get("stop"):
            return 0
        _write_response(_answer(nlp, request))
    return 0


if __name__ == "__main__":
    sys.exit(main())
