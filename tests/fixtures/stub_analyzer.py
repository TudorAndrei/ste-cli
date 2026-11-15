"""A stub analyzer for the tests. It needs no library.

It gives a passive construction for the word "signed" only, thus a test can
see the veto of the analyzer without spaCy and its model.
"""

import json
import sys


def main() -> int:
    print(json.dumps({"ready": True, "model": "stub"}), flush=True)
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        request = json.loads(line)
        if request.get("stop"):
            return 0
        text = request.get("text", "")
        tokens = []
        offset = 0
        index = 0
        for word in text.split(" "):
            start = text.find(word, offset)
            tokens.append(
                {
                    "i": index,
                    "text": word,
                    "pos": "VERB",
                    "tag": "VBN",
                    "dep": "ROOT",
                    "head": index,
                    "start": start,
                }
            )
            offset = start + len(word)
            index += 1
        # "signed" gets a child with the relation auxpass, thus it is a
        # passive verb. Each other word gets none.
        for token in list(tokens):
            if token["text"].strip(".,").lower() == "signed":
                tokens.append(
                    {
                        "i": len(tokens),
                        "text": "is",
                        "pos": "AUX",
                        "tag": "VBZ",
                        "dep": "auxpass",
                        "head": token["i"],
                        "start": -1,
                    }
                )
        print(json.dumps({"id": request.get("id"), "tokens": tokens}), flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
