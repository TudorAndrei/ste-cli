# Copyright (c) 2026 Tudor Andrei Dumitrascu
"""Dictionary checks that need the grammar: the part of speech and the forms of a word.

Each check needs the imported dictionary and a tagged sentence. Without one of
the two, a check gives no finding.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from ste.models import Diagnostic, Document, Options, Sentence, Token

if TYPE_CHECKING:
    from collections.abc import Sequence

    from ste.models import Dictionary, WordEntry

# The open word classes that the rule compares. The tagger often mixes up an
# adverb, a preposition, and a particle, thus those classes are not compared.
_DICTIONARY_POS = {"NOUN": "n", "VERB": "v", "ADJ": "adj"}
_POS_NAMES = {"n": "a noun", "v": "a verb", "adj": "an adjective"}
# The comparative and the superlative of an adjective.
_ADJECTIVE_FORMS = frozenset({"JJR", "JJS"})
POS_CONFIDENCE = 0.7
# A shorter sentence is usually a fragment, such as a label.
MIN_WORDS = 3
FORM_CONFIDENCE = 0.8
# The endings of a regular form, the longest first.
_VERB_SUFFIXES = ("ed", "es", "d", "s")
_ADJECTIVE_SUFFIXES = ("est", "er")
# A shorter stem is usually not a headword, such as "b" from "bed".
_MIN_STEM = 2


def _quoted(words: Sequence[str]) -> str:
    items = [f'"{w}"' for w in dict.fromkeys(words)]
    if len(items) == 1:
        return items[0]
    return ", ".join(items[:-1]) + ", or " + items[-1]


def _skipped(opts: Options, s: Sentence, i: int) -> bool:
    """Skip a word of the glossary, a name, and a word with a hyphen or a digit."""
    t = s.tokens[i]
    if opts.allowed(t.lower) or (t.lemma and opts.allowed(t.lemma)):
        return True
    # A capital letter after the first word shows a name.
    return not t.text.isalpha() or (i > 0 and t.text[0].isupper())


def _entries(dictionary: Dictionary, t: Token) -> Sequence[WordEntry]:
    """Find the entries of the word, by its lemma first and then by its text."""
    if t.lemma and (found := dictionary.lookup(t.lemma)):
        return found
    return dictionary.lookup(t.lower)


def _wrong_pos(dictionary: Dictionary, t: Token) -> tuple[str, list[str], str] | None:
    """Get the approved part of speech, the alternatives, and the given one."""
    code = _DICTIONARY_POS.get(t.pos)
    if code is None or t.tag == "VBG":
        # Rule STE-3.5 reports an "-ing" verb.
        return None
    entries = _entries(dictionary, t)
    approved = {e.pos for e in entries if e.approved}
    if not approved or code in approved or not approved <= _POS_NAMES.keys():
        return None
    # Compare a verb with a word that is not a verb. The tagger often gives a
    # noun before a noun as an adjective, thus a noun and an adjective are not
    # compared. A past participle as an adjective is the subject of rule 3.3.
    if code == "adj" or (code == "n" and approved != {"v"}):
        return None
    alternatives = [a for e in entries if not e.approved and e.pos == code for a in e.alternatives]
    names = " or ".join(_POS_NAMES[p] for p in sorted(approved))
    return names, alternatives, code


def part_of_speech(doc: Document, opts: Options) -> list[Diagnostic]:
    """Report a word that the dictionary approves only as a different part of speech."""
    if opts.dictionary is None:
        return []
    out = []
    for s in doc.sentences:
        # A heading or a table cell is usually a fragment, and the tagger
        # often gives a wrong part of speech for it.
        if not s.tagged or s.kind in {"heading", "table-cell"} or len(s.tokens) < MIN_WORDS:
            continue
        for i, t in enumerate(s.tokens):
            if _skipped(opts, s, i):
                continue
            wrong = _wrong_pos(opts.dictionary, t)
            # The first word of an instruction is a verb, but the tagger
            # sometimes gives it as a noun.
            if wrong is None or (i == 0 and wrong[2] == "n"):
                continue
            approved, alternatives, given = wrong
            suggestion = (
                f"Write {_quoted(alternatives)}."
                if alternatives
                else f"Use the word only as {approved}, or write an approved word."
            )
            out.append(
                Diagnostic(
                    "STE-1.2",
                    f'"{t.text}" is approved only as {approved}. Here it is {_POS_NAMES[given]}.',
                    # The precision was measured only with an invented dictionary.
                    "info",
                    POS_CONFIDENCE,
                    t.start,
                    t.end,
                    suggestion,
                )
            )
    return out


def _stems(word: str, suffixes: Sequence[str]) -> list[str]:
    """Get the possible headwords of a regular form, such as "klap" for "klapped"."""
    out = []
    for suffix in suffixes:
        stem = word.removesuffix(suffix)
        if stem == word or len(stem) < _MIN_STEM:
            continue
        # "gribbled" is "gribble" and "-d". "flimbier" is "flimby" and "-er".
        out.extend([stem, stem + "e"])
        if stem.endswith("i"):
            out.append(stem[:-1] + "y")
        # "klapped" is "klap" with a double consonant and "-ed".
        if len(stem) > _MIN_STEM and stem[-1] == stem[-2] and stem[-1] not in "aeiou":
            out.append(stem[:-1])
    return list(dict.fromkeys(out))


def _unlisted_form(dictionary: Dictionary, t: Token) -> tuple[str, WordEntry] | None:
    """Get the rule and the entry when the word is a form that the entry does not give."""
    if t.pos == "VERB" and t.tag != "VBG":
        rule, code, suffixes = "STE-3.1", "v", _VERB_SUFFIXES
    elif t.pos == "ADJ" and t.tag in _ADJECTIVE_FORMS:
        rule, code, suffixes = "STE-1.4", "adj", _ADJECTIVE_SUFFIXES
    else:
        return None
    if dictionary.lookup(t.lower) or dictionary.by_form(t.lower):
        # The word is a headword or a listed form of some entry. Rule STE-1.1
        # reports an unapproved headword.
        return None
    # The lemmatizer can give a wrong lemma for a word that it does not know,
    # such as "zorpe" for "zorped". Then the rules of a regular form find the
    # headword.
    lemma = t.lemma.lower()
    candidates = [lemma] if lemma and lemma != t.lower else []
    for word in [*candidates, *_stems(t.lower, suffixes)]:
        entries = [e for e in dictionary.lookup(word) if e.approved and e.pos == code and e.forms]
        if entries:
            return rule, entries[0]
    return None


def word_forms(doc: Document, opts: Options) -> list[Diagnostic]:
    """Report a verb or an adjective in a form that its dictionary entry does not give."""
    if opts.dictionary is None:
        return []
    out = []
    for s in doc.sentences:
        if not s.tagged:
            continue
        out.extend(_forms_in(s, opts, opts.dictionary))
    return out


def _forms_in(s: Sentence, opts: Options, dictionary: Dictionary) -> list[Diagnostic]:
    out = []
    for i, t in enumerate(s.tokens):
        if _skipped(opts, s, i):
            continue
        found = _unlisted_form(dictionary, t)
        if found is None:
            continue
        rule, entry = found
        kind = "verb" if entry.pos == "v" else "adjective"
        out.append(
            Diagnostic(
                rule,
                f'"{t.text}" is not an approved form of the {kind} "{entry.word}".',
                "warning",
                FORM_CONFIDENCE,
                t.start,
                t.end,
                f"Write {_quoted([entry.word, *entry.forms])}.",
            )
        )
    return out
