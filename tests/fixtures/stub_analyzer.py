# Copyright (c) 2026 Tudor Andrei Dumitrascu
"""A stub analyzer for the tests. It needs no library.

It gives a passive construction for the word "signed" only, thus a test can
see the veto of the analyzer without spaCy and its model.
"""

from __future__ import annotations

import json
import sys
import time

# A sentence that starts with "Slow" gets its answer after this delay.
SLOW_DELAY = 0.3


def main() -> int:
    """Answer analyzer requests with an independent token stream."""
    sys.stdout.write(json.dumps({"ready": True, "model": "stub"}) + "\n")
    sys.stdout.flush()
    for raw_line in sys.stdin:
        line = raw_line.strip()
        if not line:
            continue
        request = json.loads(line)
        if request.get("stop"):
            return 0
        text = request.get("text", "")
        if text.startswith("Slow"):
            time.sleep(SLOW_DELAY)
        tokens = []
        offset = 0
        for index, word in enumerate(text.split(" ")):
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
        sys.stdout.write(json.dumps({"id": request.get("id"), "tokens": tokens}) + "\n")
        sys.stdout.flush()
    return 0


if __name__ == "__main__":
    sys.exit(main())
