# Copyright (c) 2026 Tudor Andrei Dumitrascu
"""Shared rule operations."""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ste.models import Sentence


def span(sentence: Sentence, first: int, last: int) -> str:
    """Return source text between two tokens as one line."""
    start = sentence.tokens[first].start - sentence.start
    end = sentence.tokens[last].end - sentence.start
    if start < 0 or end > len(sentence.text) or start > end:
        return sentence.tokens[first].text
    return " ".join(sentence.text[start:end].split())


def tokens_match(sentence: Sentence, index: int, words: list[str]) -> bool:
    """Return whether consecutive tokens match the given words."""
    return [t.lower for t in sentence.tokens[index : index + len(words)]] == words
