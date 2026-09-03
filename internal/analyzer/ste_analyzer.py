"""A syntax analyzer for the ste checker.

Some rules of ASD-STE100 need the syntax of a sentence, and not only its
words. Rule 3.6 is an example: the difference between "the valve is closed"
(an adjective) and "the valve is closed by the operator" (the passive voice)
is a relation between two words, and not a word list.

This program gives that syntax to the Go command. The command sends
sentences, and this program answers with one object for each sentence: each
token, its part of speech, and its relation to its head.

    ste lint --analyzer "python3 analyzer/ste_analyzer.py" docs/

The protocol is one JSON object for each line, in both directions:

    in : {"id": 1, "text": "The valve is closed by the operator."}
    out: {"id": 1, "tokens": [{"i":0,"text":"The","pos":"DET","dep":"det",
                               "head":1,"lemma":"the","start":0}, ...]}

The command starts this program one time for each run, thus the model loads
one time. An error on one sentence gives an object with "error", and the
command then uses its own rules for that sentence.
"""

from __future__ import annotations

import json
import sys

MODEL = "en_core_web_sm"


def load_model():
    """Load spaCy. Only the parts that the rules need stay in the pipeline."""
    try:
        import spacy
    except ImportError:
        raise SystemExit(
            "ste-analyzer: spacy is not installed.\n"
            "  uv pip install spacy\n"
            f"  python -m spacy download {MODEL}"
        )
    try:
        # The rules need the tagger and the parser. The other parts of the
        # pipeline are not necessary, and they make each sentence slower.
        return spacy.load(MODEL, exclude=["ner", "lemmatizer", "textcat"])
    except OSError:
        raise SystemExit(
            f"ste-analyzer: the model {MODEL} is not installed.\n"
            f"  python -m spacy download {MODEL}"
        )


def analyze(nlp, text: str) -> list[dict]:
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


def main() -> int:
    nlp = load_model()
    # The command waits for this line before it sends a sentence.
    print(json.dumps({"ready": True, "model": MODEL}), flush=True)

    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            request = json.loads(line)
        except json.JSONDecodeError as err:
            print(json.dumps({"error": f"the line is not JSON: {err}"}), flush=True)
            continue
        if request.get("stop"):
            return 0
        try:
            answer = {"id": request.get("id"), "tokens": analyze(nlp, request["text"])}
        except Exception as err:  # one bad sentence must not stop the run
            answer = {"id": request.get("id"), "error": str(err)}
        print(json.dumps(answer), flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
