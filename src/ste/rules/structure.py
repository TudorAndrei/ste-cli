# Copyright (c) 2026 Tudor Andrei Dumitrascu
"""Rules for document structure and conditions."""

from ste.models import Diagnostic, Document, Options, Sentence
from ste.rules.data import (
    CLAUSE_MARKERS,
    CLAUSE_VERBS,
    CONDITION_WORDS,
    INSTRUCTION_WORDS,
    RISK_WORDS,
    SAFETY_WORDS,
)

MAX_PARAGRAPH_SENTENCES = 6
MAX_UNEXPLAINED_SAFETY_WORDS = 12
MIN_LIST_WORDS = 3
MIN_LIST_ITEMS = 2
MIN_WORDS_BEFORE_CONDITION = 3
MIN_INFLECTION_LENGTH = 3
INFINITIVE_LOOKBEHIND = 2


def paragraphs(doc: Document) -> list[list[Sentence]]:
    """Group sentences by their paragraph blocks."""
    groups: list[list[Sentence]] = []
    for s in doc.sentences:
        if s.kind != "paragraph":
            continue
        if not groups or groups[-1][-1].block != s.block:
            groups.append([])
        groups[-1].append(s)
    return groups


def paragraph_length(doc: Document, _opts: Options) -> list[Diagnostic]:
    """Report paragraphs with too many sentences."""
    return [
        Diagnostic(
            "STE-6.6",
            f"The paragraph has {len(group)} sentences. The limit is 6 sentences.",
            "warning",
            1.0,
            group[0].start,
            group[-1].end,
            "Divide the paragraph.",
        )
        for group in paragraphs(doc)
        if len(group) > MAX_PARAGRAPH_SENTENCES
    ]


def note_instruction(doc: Document, _opts: Options) -> list[Diagnostic]:
    """Report an instruction in an information note."""
    out = []
    for s in doc.sentences:
        if s.admonition not in {"note", "notes"}:
            continue
        for i, t in enumerate(s.tokens):
            if t.lower not in INSTRUCTION_WORDS:
                continue
            if t.lower == "do" and (i + 1 >= len(s.tokens) or s.tokens[i + 1].lower != "not"):
                continue
            out.append(
                Diagnostic(
                    "STE-5.5",
                    f'The note has an instruction: "{t.text}".',
                    "warning",
                    0.8,
                    t.start,
                    t.end,
                    "A note gives information only. "
                    "Move the instruction to a step of the procedure.",
                )
            )
            break
    return out


def safety_instruction(doc: Document, _opts: Options) -> list[Diagnostic]:
    """Report a safety instruction with no risk explanation."""
    by_block: dict[int, list[Sentence]] = {}
    for s in doc.sentences:
        if s.admonition in SAFETY_WORDS:
            by_block.setdefault(s.block, []).append(s)
    out = []
    for group in by_block.values():
        if len(group) > 1 or sum(s.words for s in group) > MAX_UNEXPLAINED_SAFETY_WORDS:
            continue
        out.append(
            Diagnostic(
                "STE-7.3",
                f"The {group[0].admonition} gives no explanation of the risk.",
                "warning",
                0.7,
                group[0].start,
                group[-1].end,
                "Add a sentence that gives the risk or the possible result.",
            )
        )
    return out


def safety_word(doc: Document, _opts: Options) -> list[Diagnostic]:
    """Report a risk under a label that gives no risk level."""
    out = []
    reported = set()
    for s in doc.sentences:
        if not s.admonition or s.admonition in SAFETY_WORDS or s.block in reported:
            continue
        for i, t in enumerate(s.tokens):
            risk = t.lower in RISK_WORDS
            if not risk and i + 1 < len(s.tokens):
                next_word = s.tokens[i + 1].lower
                risk = (t.lower == "data" and next_word == "loss") or (
                    t.lower in {"lose", "loses"} and next_word == "data"
                )
            if risk:
                reported.add(s.block)
                out.append(
                    Diagnostic(
                        "STE-7.1",
                        f'The {s.admonition} tells of a risk ("{t.text}"), '
                        "but its label does not give the level of the risk.",
                        "warning",
                        0.7,
                        t.start,
                        t.end,
                        'Use "warning" for a risk of injury or death, '
                        'and "caution" for a risk of damage.',
                    )
                )
                break
    return out


def hidden_start(source: str, start: int) -> bool:
    """Check for masked content before the first prose word."""
    if start > len(source):
        return False
    line_start = source.rfind("\n", 0, start) + 1
    return bool(source[line_start:start].lstrip(" \t-*+>0123456789.)").strip())


def lists(doc: Document) -> list[list[Sentence]]:
    """Group consecutive list items that start with prose."""
    groups: list[list[Sentence]] = []
    previous = -2
    for s in doc.sentences:
        if (
            s.kind != "list-item"
            or not s.first
            or len(s.tokens) < MIN_LIST_WORDS
            or hidden_start(doc.source, s.start)
        ):
            continue
        if not groups or s.block != previous + 1:
            groups.append([])
        groups[-1].append(s)
        previous = s.block
    return groups


def vertical_list(doc: Document, _opts: Options) -> list[Diagnostic]:
    """Report inconsistent initial letters in a vertical list."""
    out = []
    for group in lists(doc):
        upper = sum(bool(s.text) and "A" <= s.text[0] <= "Z" for s in group)
        lower = sum(bool(s.text) and "a" <= s.text[0] <= "z" for s in group)
        if not upper or not lower or len(group) < MIN_LIST_ITEMS:
            continue
        report_lower = lower <= upper
        for s in group:
            if (
                not s.text
                or not ("A" <= s.text[0] <= "Z" or "a" <= s.text[0] <= "z")
                or ("a" <= s.text[0] <= "z") != report_lower
            ):
                continue
            shape = "a small letter" if report_lower else "a capital letter"
            out.append(
                Diagnostic(
                    "STE-4.3",
                    f"The item of the list starts with {shape}, and the other items do not.",
                    "info",
                    0.8,
                    s.start,
                    s.start + 1,
                    "Use the same construction for each item of a vertical list.",
                )
            )
    return out


def condition_order(doc: Document, _opts: Options) -> list[Diagnostic]:
    """Report an instruction with a condition after its command."""
    out = []
    for s in doc.sentences:
        if not s.procedural or s.note:
            continue
        for i, t in enumerate(s.tokens):
            if t.lower not in CONDITION_WORDS:
                continue
            if i == 0:
                break
            if i < MIN_WORDS_BEFORE_CONDITION or s.tokens[i - 1].lower in CLAUSE_VERBS:
                continue
            previous = s.tokens[i - 1].text
            if (
                i >= INFINITIVE_LOOKBEHIND
                and s.tokens[i - 2].lower == "to"
                and previous
                and "a" <= previous[0] <= "z"
            ):
                continue
            if not any(
                token.lower in CLAUSE_MARKERS
                or (len(token.lower) > MIN_INFLECTION_LENGTH and token.lower.endswith(("ed", "es")))
                for token in s.tokens[i + 1 :]
            ):
                continue
            out.append(
                Diagnostic(
                    "STE-5.4",
                    f'The instruction gives its condition ("{t.text}") after the command.',
                    "info",
                    0.7,
                    t.start,
                    s.tokens[-1].end,
                    "Write the condition first, then a comma, then the command.",
                )
            )
            break
    return out
