"""Word and phrase checks."""

from ste.models import Diagnostic, Document, Options, Sentence
from ste.rules.common import span, tokens_match
from ste.rules.data import (
    BANNED_PHRASES,
    BANNED_WORDS,
    BRITISH_SPELLINGS,
    DETERMINERS,
    LATIN_ABBREVIATIONS,
    NOMINALIZATIONS,
    PHRASE_STOPPERS,
)

TERM_DATA_VERSION = "1.0.0"


def preceded_by_determiner(s: Sentence, i: int) -> bool:
    for back in range(1, min(3, i) + 1):
        previous = s.tokens[i - back].lower
        if previous in DETERMINERS or previous.endswith("'s"):
            return True
        if previous in PHRASE_STOPPERS:
            return False
    return False


def lookup_dictionary(opts: Options, s: Sentence, i: int) -> Diagnostic | None:
    if opts.dictionary is None:
        return None
    word = s.tokens[i].lower
    result, unapproved = opts.dictionary.unapproved(word)
    if not unapproved or result.only_verb and preceded_by_determiner(s, i):
        return None
    confidence = 0.6 if result.only_verb else 0.95
    suggestion = "The dictionary gives no alternative. Write the idea in approved words."
    if result.alternatives:
        suggestion = 'Write "' + '", or "'.join(result.alternatives) + '".'
    elif result.technical_noun:
        suggestion = f'The dictionary approves "{word}" as a technical noun only. If this sentence uses it as a verb, write a different verb.'
    token = s.tokens[i]
    return Diagnostic(
        "STE-1.1",
        f'"{token.text}" is not an approved word.',
        "warning",
        confidence,
        token.start,
        token.end,
        suggestion,
    )


def terms(doc: Document, opts: Options) -> list[Diagnostic]:
    out = []
    for s in doc.sentences:
        i = 0
        while i < len(s.tokens):
            matched = False
            for words, replacement in BANNED_PHRASES:
                if not tokens_match(s, i, words):
                    continue
                last = i + len(words) - 1
                phrase = span(s, i, last)
                if opts.allowed(phrase):
                    continue
                out.append(
                    Diagnostic(
                        "STE-1.1",
                        f'"{phrase}" is not an approved word group.',
                        "warning",
                        0.9,
                        s.tokens[i].start,
                        s.tokens[last].end,
                        f'Write "{replacement}".',
                    )
                )
                i += len(words)
                matched = True
                break
            if matched:
                continue
            t = s.tokens[i]
            if not opts.allowed(t.lower):
                dictionary = lookup_dictionary(opts, s, i)
                if dictionary is not None:
                    out.append(dictionary)
                elif t.lower in BANNED_WORDS:
                    out.append(
                        Diagnostic(
                            "STE-1.1",
                            f'"{t.text}" is not an approved word.',
                            "warning",
                            0.9,
                            t.start,
                            t.end,
                            f'Write "{BANNED_WORDS[t.lower]}".',
                        )
                    )
            i += 1
    return out


def spelling(doc: Document, opts: Options) -> list[Diagnostic]:
    out = []
    for s in doc.sentences:
        for i, t in enumerate(s.tokens):
            if t.lower not in BRITISH_SPELLINGS or opts.allowed(t.lower):
                continue
            if i > 0 and t.text and t.text[0].isupper():
                continue
            out.append(
                Diagnostic(
                    "STE-1.14",
                    f'"{t.text}" is a British spelling.',
                    "warning",
                    0.9,
                    t.start,
                    t.end,
                    f'Write "{BRITISH_SPELLINGS[t.lower]}".',
                )
            )
    return out


def nominalizations(doc: Document, opts: Options) -> list[Diagnostic]:
    out = []
    for s in doc.sentences:
        i = 0
        while i < len(s.tokens):
            for words, replacement in NOMINALIZATIONS:
                if not tokens_match(s, i, words):
                    continue
                last = i + len(words) - 1
                out.append(
                    Diagnostic(
                        "STE-3.7",
                        f'"{span(s, i, last)}" uses a noun for an action.',
                        "warning",
                        0.9,
                        s.tokens[i].start,
                        s.tokens[last].end,
                        f'Write "{replacement}".',
                    )
                )
                i = last
                break
            i += 1
    return out


def latin_abbreviations(doc: Document, opts: Options) -> list[Diagnostic]:
    out = []
    for s in doc.sentences:
        for t in s.tokens:
            if t.lower not in LATIN_ABBREVIATIONS or opts.allowed(t.lower):
                continue
            if t.text != t.lower or t.end >= len(doc.source) or doc.source[t.end] != ".":
                continue
            out.append(
                Diagnostic(
                    "STE-GR-6",
                    f'"{t.text}" is a Latin abbreviation.',
                    "info",
                    0.9,
                    t.start,
                    t.end,
                    f'Write "{LATIN_ABBREVIATIONS[t.lower]}".',
                )
            )
    return out


def one_name(doc: Document, opts: Options) -> list[Diagnostic]:
    out = []
    for s in doc.sentences:
        for preferred in opts.prefer:
            for old in preferred.instead:
                words = old.lower().split()
                if not words:
                    continue
                for i in range(len(s.tokens) - len(words) + 1):
                    if tokens_match(s, i, words):
                        last = i + len(words) - 1
                        out.append(
                            Diagnostic(
                                "STE-1.11",
                                f'The text uses "{span(s, i, last)}" and "{preferred.name}" for the same item.',
                                "warning",
                                0.95,
                                s.tokens[i].start,
                                s.tokens[last].end,
                                f'Write "{preferred.name}".',
                            )
                        )
    return out
