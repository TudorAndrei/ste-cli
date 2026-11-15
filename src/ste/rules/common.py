# Copyright (c) 2026 Tudor Andrei Dumitrascu
"""Shared rule operations."""

from functools import cache
from typing import TYPE_CHECKING

from ahocorasick_rs import AhoCorasick

if TYPE_CHECKING:
    from ste.models import Sentence

# A token never holds this character, so it marks each token boundary.
_SEPARATOR = "\x00"


def span(sentence: Sentence, first: int, last: int) -> str:
    """Return source text between two tokens as one line."""
    start = sentence.tokens[first].start - sentence.start
    end = sentence.tokens[last].end - sentence.start
    if start < 0 or end > len(sentence.text) or start > end:
        return sentence.tokens[first].text
    return " ".join(sentence.text[start:end].split())


class PhraseMatcher:
    """Find word sequences in the lower-case tokens of a sentence."""

    def __init__(self, phrases: tuple[tuple[str, ...], ...]) -> None:
        """Build one automaton for all phrases that a token sequence can hold."""
        patterns: dict[str, list[int]] = {}
        for index, words in enumerate(phrases):
            if words and not any(_SEPARATOR in word for word in words):
                key = _SEPARATOR + _SEPARATOR.join(words) + _SEPARATOR
                patterns.setdefault(key, []).append(index)
        self._phrases = list(patterns.values())
        self._automaton = AhoCorasick(list(patterns)) if patterns else None

    def matches(self, sentence: Sentence) -> list[tuple[int, int]]:
        """Return each (token index, phrase index) match, in that order."""
        if self._automaton is None or not sentence.tokens:
            return []
        lowers = [t.lower for t in sentence.tokens]
        haystack = _SEPARATOR + _SEPARATOR.join(lowers) + _SEPARATOR
        found = self._automaton.find_matches_as_indexes(haystack, overlapping=True)
        if not found:
            return []
        token_at: dict[int, int] = {}
        offset = 0
        for index, lower in enumerate(lowers):
            token_at[offset] = index
            offset += len(lower) + 1
        return sorted(
            (token_at[start], phrase)
            for pattern, start, _ in found
            for phrase in self._phrases[pattern]
        )


@cache
def phrase_matcher(phrases: tuple[tuple[str, ...], ...]) -> PhraseMatcher:
    """Return the shared matcher for one tuple of phrases."""
    return PhraseMatcher(phrases)
