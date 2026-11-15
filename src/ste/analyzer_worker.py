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
                               "head":1,"start":0}, ...]}

The command starts this program one time for each run, thus the model loads
one time. An error on one sentence gives an object with "error", and the
command then uses its own rules for that sentence.
"""

from __future__ import annotations

import importlib
import json
import sys
from typing import TYPE_CHECKING, Protocol, cast

if TYPE_CHECKING:
    from collections.abc import Iterable

MODEL = "en_core_web_sm"


class NLPToken(Protocol):
    """Token attributes that the grammar protocol reads from an NLP model."""

    i: int
    text: str
    pos_: str
    tag_: str
    dep_: str
    idx: int
    head: NLPToken


class NLPModel(Protocol):
    """A callable language model that returns annotated tokens."""

    def __call__(self, text: str) -> Iterable[NLPToken]:
        """Analyze one sentence and return its grammar tokens."""
        ...


def load_model() -> NLPModel:
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
        # The rules need the tagger and the parser. The other parts of the
        # pipeline are not necessary, and they make each sentence slower.
        return cast("NLPModel", spacy.load(MODEL, exclude=["ner", "lemmatizer", "textcat"]))
    except OSError:
        msg = (
            f"ste-analyzer: the model {MODEL} is not installed.\n  python -m spacy download {MODEL}"
        )
        raise SystemExit(msg) from None


def analyze(nlp: NLPModel, text: str) -> list[dict[str, str | int]]:
    """Give one object for each token of the sentence."""
    doc = nlp(text)
    return [
        {
            "i": token.i,
            "text": token.text,
            "pos": token.pos_,
            "tag": token.tag_,
            "dep": token.dep_,
            "head": token.head.i,
            "start": token.idx,
        }
        for token in doc
    ]


def _write_response(payload: dict[str, object]) -> None:
    sys.stdout.write(json.dumps(payload) + "\n")
    sys.stdout.flush()


def _answer(nlp: NLPModel, request: dict[str, object]) -> dict[str, object]:
    try:
        return {"id": request.get("id"), "tokens": analyze(nlp, cast("str", request["text"]))}
    # An NLP component can raise its own exception. One failed sentence must
    # return an error response without terminating the persistent protocol.
    except Exception as err:  # noqa: BLE001
        return {"id": request.get("id"), "error": str(err)}


def main() -> int:
    """Serve grammar requests as one JSON response per input line."""
    nlp = load_model()
    _write_response({"ready": True, "model": MODEL})
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
