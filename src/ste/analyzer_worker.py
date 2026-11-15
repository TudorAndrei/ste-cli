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


# Parts that make a new English word from a word of the lexicon, as in
# "reconnect" and "tokenize". A word that only these parts explain is English.
_PREFIXES = (
    "re",
    "un",
    "de",
    "dis",
    "pre",
    "post",
    "auto",
    "back",
    "over",
    "under",
    "sub",
    "co",
    "mis",
    "out",
    "up",
    "multi",
    "non",
    "inter",
    "cross",
    "self",
)
_SUFFIXES = ("ize", "ise", "ify", "ate", "en")
_ENDINGS = ("ing", "ed", "es", "s", "d")
_MIN_STEM = 3
# The parts of speech of the lexicon. It has no function word, such as "for".
_OPEN_CLASSES = frozenset({"NOUN", "VERB", "ADJ", "ADV"})


def lexicon(nlp: NLPModel) -> frozenset[str]:
    """Return each word of the lemmatizer tables, or nothing without a lemmatizer.

    The English model keeps the words of WordNet for each part of speech, and
    the irregular forms. The tables load with the lemmatizer, thus the word
    list costs no new file.
    """
    if "lemmatizer" not in nlp.pipe_names:
        return frozenset()
    try:
        lookups = getattr(nlp, "get_pipe")("lemmatizer").lookups  # noqa: B009
        tables = [lookups.get_table(name) for name in ("lemma_index", "lemma_exc")]
    except AttributeError, KeyError:
        return frozenset()
    words: set[str] = set()
    for table in tables:
        for value in table.values():
            if isinstance(value, dict):
                words.update(value)
                for forms in value.values():
                    words.update(forms)
            else:
                words.update(value)
    return frozenset(words)


def _stems(word: str) -> Iterator[str]:
    """Give the word, and the word without each inflection ending."""
    yield word
    for end in _ENDINGS:
        stem = word.removesuffix(end)
        if stem != word and len(stem) >= _MIN_STEM:
            yield stem
            yield stem + "e"
            if stem[-1] == stem[-2]:
                yield stem[:-1]


def _derived(word: str, words: frozenset[str]) -> bool:
    """Return whether a word, or the word without a suffix, is in the lexicon."""
    if word in words:
        return True
    return any(
        word.endswith(end) and word.removesuffix(end) in words
        for end in _SUFFIXES
        if len(word) - len(end) >= _MIN_STEM
    )


def in_lexicon(word: str, pos: str, words: frozenset[str]) -> bool:
    """Return whether a word is English for the lexicon of the model.

    An empty lexicon knows each word. The lexicon has only nouns, verbs,
    adjectives, and adverbs, thus a word of a different part of speech stays
    known. A word with a digit or a mark, such as "window_count", is code
    and not a word of the lexicon, thus it also stays known.
    """
    word = word.lower()
    if not words or pos not in _OPEN_CLASSES or not word.isalpha():
        return True
    return any(
        _derived(stem, words)
        or any(
            stem.startswith(part)
            and len(stem) - len(part) >= _MIN_STEM
            and _derived(stem.removeprefix(part), words)
            for part in _PREFIXES
        )
        for stem in _stems(word)
    )


def _tokens(doc: Iterable[NLPToken], words: frozenset[str]) -> list[dict[str, str | int]]:
    out: list[dict[str, str | int]] = []
    for token in doc:
        item: dict[str, str | int] = {
            "i": token.i,
            "text": token.text,
            "pos": token.pos_,
            "tag": token.tag_,
            "dep": token.dep_,
            "head": token.head.i,
            "start": token.idx,
            "lemma": token.lemma_,
        }
        if not in_lexicon(token.text, token.pos_, words):
            item["in_lexicon"] = False
        out.append(item)
    return out


def analyze(
    nlp: NLPModel, texts: list[str], words: frozenset[str] = frozenset()
) -> list[list[dict[str, str | int]]]:
    """Give one object for each token of each sentence."""
    return [_tokens(doc, words) for doc in nlp.pipe(texts, batch_size=BATCH_SIZE)]


def _write_response(payload: dict[str, object]) -> None:
    sys.stdout.write(json.dumps(payload) + "\n")
    sys.stdout.flush()


def _one(
    nlp: NLPModel, text: object, words: frozenset[str]
) -> list[dict[str, str | int]] | dict[str, str]:
    try:
        return analyze(nlp, [cast("str", text)], words)[0]
    # An NLP component can raise its own exception. One failed sentence must
    # return an error response without terminating the persistent protocol.
    except Exception as err:  # noqa: BLE001
        return {"error": str(err)}


def _answer(nlp: NLPModel, request: dict[str, object], words: frozenset[str]) -> dict[str, object]:
    texts = request.get("texts")
    if isinstance(texts, list):
        try:
            return {"id": request.get("id"), "results": analyze(nlp, texts, words)}
        except Exception:  # noqa: BLE001
            # Find the failed sentence: each other sentence keeps its result.
            return {"id": request.get("id"), "results": [_one(nlp, text, words) for text in texts]}
    result = _one(nlp, request.get("text"), words)
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
    words = lexicon(nlp)
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
        _write_response(_answer(nlp, request, words))
    return 0


if __name__ == "__main__":
    sys.exit(main())
