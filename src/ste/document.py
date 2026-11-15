# Copyright (c) 2026 Tudor Andrei Dumitrascu
"""Read Markdown prose and preserve positions in the original source."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from markdown_it import MarkdownIt
from markdown_it.rules_inline import (
    autolink,
    backtick,
    emphasis,
    html_inline,
    image,
    link,
    strikethrough,
)

from ste.models import Document, Sentence, Token

if TYPE_CHECKING:
    from collections.abc import Callable

    from markdown_it.rules_inline.state_inline import StateInline
    from markdown_it.token import Token as MarkdownToken

_ABBREVIATIONS = {
    "e.g",
    "i.e",
    "etc",
    "vs",
    "fig",
    "no",
    "ref",
    "approx",
    "min",
    "max",
    "sec",
    "para",
    "ch",
    "al",
    "inc",
    "ltd",
    "dr",
    "mr",
    "mrs",
    "ms",
    "st",
    "vol",
    "cf",
    "ca",
    "dept",
}
_UNITS = {
    "mm",
    "cm",
    "m",
    "km",
    "in",
    "ft",
    "mg",
    "g",
    "kg",
    "lb",
    "lbs",
    "ml",
    "l",
    "gal",
    "ms",
    "s",
    "sec",
    "min",
    "h",
    "hr",
    "hrs",
    "day",
    "days",
    "week",
    "weeks",
    "month",
    "months",
    "year",
    "years",
    "hz",
    "khz",
    "mhz",
    "ghz",
    "b",
    "kb",
    "mb",
    "gb",
    "tb",
    "kib",
    "mib",
    "gib",
    "tib",
    "bit",
    "bits",
    "byte",
    "bytes",
    "v",
    "a",
    "ma",
    "w",
    "kw",
    "psi",
    "bar",
    "kpa",
    "mpa",
    "n",
    "nm",
    "px",
    "pt",
    "em",
    "rem",
    "dpi",
    "rpm",
    "c",
    "f",
    "k",
    "%",
}
_ADMONITIONS = {
    "warning",
    "caution",
    "danger",
    "note",
    "notes",
    "important",
    "attention",
    "tip",
    "info",
}
_SPACE = " \t\n\r"
_CLOSING = "*_) ]\"'`".replace(" ", "")
_JOIN = "'\u2019\u02bc-._"
# "[^\W_]" is a letter or a number. It also matches a number that is not a
# digit, such as "½", that _is_word does not accept. _word_span finds and
# corrects this case.
_LETTER = r"[^\W_]"
_JOINED = rf"(?:{_LETTER}|[{re.escape(_JOIN)}](?={_LETTER}))*"
_JOINED_RUN = re.compile(_JOINED)
_WORD = re.compile(_LETTER + _JOINED)
_COUNT_START = re.compile(rf'[("“]|{_LETTER}{_JOINED}')
_PARENTHESIS = re.compile(r"[()]")
_NUMBER = re.compile(r"[0-9.,]+")
_SPACES = re.compile(r"[ \t\n\r]*")
_PUNCTUATION = re.compile(r"[.!?]")
_LIST_PUNCTUATION = re.compile(r"[.!?:]")


@dataclass
class _Block:
    segments: list[tuple[int, int]] = field(default_factory=list)
    procedural: bool = False
    kind: str = "paragraph"
    admonition: str = ""


def _front_matter_end(src: str) -> int:
    if not re.match(r"^(---|\+\+\+)\r?\n", src):
        return 0
    fence = src[:3]
    pos = src.index("\n") + 1
    for line in src[pos:].splitlines(keepends=True):
        pos += len(line)
        if line.rstrip(" \t\r\n") in {fence, "..."}:
            return pos
    return 0


def _admonition_word(text: str) -> str:
    trimmed = text.lstrip(" \t*_>:!-[")
    match = re.match(r"[a-zA-Z]+", trimmed)
    if match is None:
        return ""
    word = match[0].lower()
    rest = trimmed[match.end() :].lstrip(" \t")
    return word if word in _ADMONITIONS and (not rest or rest[0] in ":]*!") else ""


@dataclass
class _InlineTracker:
    visible: list[bool]
    root_state: StateInline | None = None
    delimiters: list[tuple[MarkdownToken, int, int]] = field(default_factory=list)

    def wrap(
        self, name: str, rule: Callable[[StateInline, bool], bool]
    ) -> Callable[[StateInline, bool], bool]:
        """Wrap an inline rule with source-position recording."""

        # The parser calls each rule with a positional silent flag.
        def wrapped(state: StateInline, silent: bool) -> bool:  # noqa: FBT001
            if self.root_state is None and not silent:
                self.root_state = state
            start = state.pos
            count = len(state.tokens)
            label_end = -1
            if name == "link" and state.src[start : start + 1] == "[":
                label_end = state.md.helpers.parseLinkLabel(state, start, disableNested=True)
            matched = rule(state, silent)
            if matched and not silent and state is self.root_state:
                self.record(state, name, start, count, label_end)
            return matched

        return wrapped

    def record(self, state: StateInline, name: str, start: int, count: int, label_end: int) -> None:
        """Exclude inline syntax while retaining a link's visible label."""
        end = state.pos
        if name == "link":
            if label_end >= 0:
                self.visible[start] = False
                self.visible[label_end:end] = [False] * (end - label_end)
        elif name in {"emphasis", "strikethrough"}:
            self.record_delimiters(state, start, count)
        elif name != "backticks" or any(t.type == "code_inline" for t in state.tokens[count:]):
            self.visible[start:end] = [False] * (end - start)

    def record_delimiters(self, state: StateInline, start: int, count: int) -> None:
        """Keep delimiter spans until the parser resolves emphasis pairs."""
        tokens = [
            token
            for token in state.tokens[count:]
            if token.type == "text" and token.content and set(token.content) <= {state.src[start]}
        ]
        offset = start
        for token in tokens:
            self.delimiters.append((token, offset, offset + len(token.content)))
            offset += len(token.content)


def _inline_visibility(content: str, md: MarkdownIt, env: dict) -> list[bool]:
    """Record source spans while CommonMark inline rules consume them.

    Link labels use the same state. Image alternatives use a separate state,
    whose source positions must not enter the outer document.
    """
    tracker = _InlineTracker([True] * len(content))
    rules = {
        "link": link,
        "image": image,
        "autolink": autolink,
        "html_inline": html_inline,
        "backticks": backtick,
        "emphasis": emphasis.tokenize,
        "strikethrough": strikethrough.tokenize,
    }
    for name, rule in rules.items():
        md.inline.ruler.at(name, tracker.wrap(name, rule))
    children: list[MarkdownToken] = []
    md.inline.parse(content, md, env, children)
    for token, start, end in tracker.delimiters:
        if token.type != "text" or not token.content:
            tracker.visible[start:end] = [False] * (end - start)
    return tracker.visible


def _source_positions(
    content: str, src: str, lines: list[int], line_map: list[int], cursor: int
) -> list[int]:
    """Map stripped block content back to its original source characters."""
    positions: list[int] = []
    line_no = line_map[0]
    for chunk in content.splitlines(keepends=True):
        if line_no >= len(lines) - 1:
            break
        start = max(lines[line_no], cursor)
        end = lines[line_no + 1]
        body = chunk.rstrip("\n")
        found = src.find(body, start, end) if body else start
        if found >= 0:
            positions.extend(range(found, found + len(body)))
        else:
            # The table rule removes an escape before a pipe. Keep each
            # surviving character at its original position.
            at = start
            for char in body:
                next_pos = src.find(char, at, end)
                if next_pos < 0:
                    next_pos = min(at, end - 1)
                positions.append(next_pos)
                at = next_pos + 1
        if chunk.endswith("\n"):
            newline = src.find("\n", lines[line_no], end)
            positions.append(newline if newline >= 0 else end - 1)
        line_no += 1
        cursor = lines[line_no] if line_no < len(lines) else len(src)
    return positions


def _copy_segments(
    src: str, masked: list[str], positions: list[int], visible: list[bool], front: int
) -> list[tuple[int, int]]:
    segments: list[tuple[int, int]] = []
    for index, pos in enumerate(positions):
        if pos < front or not visible[index]:
            continue
        masked[pos] = src[pos]
        if segments and pos == segments[-1][1]:
            segments[-1] = (segments[-1][0], pos + 1)
        else:
            segments.append((pos, pos + 1))
    return segments


def _block_kind(stack: list[str]) -> str:
    if "heading_open" in stack:
        return "heading"
    if "td_open" in stack or "th_open" in stack:
        return "table-cell"
    if "list_item_open" in stack:
        return "list-item"
    return "paragraph"


def _collect_blocks(src: str, md: MarkdownIt, env: dict, masked: list[str]) -> list[_Block]:
    tokens = md.parse(src, env)
    lines = [0, *(match.end() for match in re.finditer(r"\r\n|\r|\n", src))]
    if lines[-1] != len(src):
        lines.append(len(src))
    elif len(lines) == 1:
        lines.append(0)
    blocks: list[_Block] = []
    stack: list[str] = []
    front = _front_matter_end(src)
    cursor = 0
    for token in tokens:
        if token.nesting == 1:
            stack.append(token.type)
        if token.type == "inline" and token.map is not None and token.content:
            positions = _source_positions(token.content, src, lines, token.map, cursor)
            if positions:
                cursor = positions[-1] + 1
            visible = _inline_visibility(token.content, md, env)
            segments = _copy_segments(src, masked, positions, visible, front)
            if segments:
                start = segments[0][0]
                blocks.append(
                    _Block(
                        segments,
                        "ordered_list_open" in stack,
                        _block_kind(stack),
                        _admonition_word(src[start : start + 48]),
                    )
                )
        if token.nesting == -1 and stack:
            stack.pop()
    return blocks


def parse(src: str) -> Document:
    """Return prose sentences with character offsets in *src*."""
    md = MarkdownIt("commonmark").enable(["table", "strikethrough"])
    md.core.ruler.disable("inline")
    md.inline.ruler2.disable("fragments_join")
    masked = [char if char in "\r\n" else " " for char in src]
    blocks = _collect_blocks(src, md, {}, masked)
    doc = Document(src, "".join(masked))
    for number, block in enumerate(blocks):
        doc.sentences.extend(_sentences(doc, block, number))
    return doc


def _is_word(char: str) -> bool:
    return char.isalpha() or char.isdigit()


def _match_end(pattern: re.Pattern[str], text: str, pos: int, end: int) -> int:
    match = pattern.match(text, pos, end)
    return match.end() if match else pos


def _all_words(run: str) -> bool:
    return run.isascii() or all(_is_word(char) for char in run if char not in _JOIN)


def _end_of_word(text: str, pos: int, end: int) -> int:
    stop = _match_end(_JOINED_RUN, text, pos, end)
    if _all_words(text[pos:stop]):
        return stop
    while pos < end:
        if _is_word(text[pos]) or (
            text[pos] in _JOIN and pos + 1 < end and _is_word(text[pos + 1])
        ):
            pos += 1
        else:
            break
    return pos


def _word_span(text: str, match: re.Match[str], end: int) -> tuple[int, int]:
    """Return the word of a _WORD match, or an empty span at a character that is not a word."""
    start, stop = match.span()
    if _all_words(text[start:stop]):
        return start, stop
    if not _is_word(text[start]):
        return start, start
    return start, _end_of_word(text, start, end)


def tokenize(masked: str, start: int = 0, end: int | None = None) -> list[Token]:
    """Return word tokens without removing their original source positions."""
    end = len(masked) if end is None else end
    out: list[Token] = []
    pos = start
    while match := _WORD.search(masked, pos, end):
        pos, stop = _word_span(masked, match, end)
        if stop == pos:
            pos += 1
            continue
        word = masked[pos:stop]
        out.append(
            Token(word, word.replace("\u2019", "'").replace("\u02bc", "'").lower(), pos, stop)
        )
        pos = stop
    return out


def _parenthesis_end(masked: str, pos: int, end: int) -> int:
    depth = 0
    for match in _PARENTHESIS.finditer(masked, pos, end):
        depth += 1 if match.group() == "(" else -1
        if depth == 0:
            return match.end()
    return pos


def _group_end(masked: str, pos: int, end: int) -> int:
    char = masked[pos]
    if char == "(":
        return _parenthesis_end(masked, pos, end)
    if char in {'"', "“"}:
        close = masked.find("”" if char == "“" else '"', pos + 1, end)
        if close >= 0:
            return close + 1
    return pos


def _quantity_end(masked: str, start: int, pos: int, end: int) -> int:
    if not _NUMBER.fullmatch(masked, start, pos):
        return pos
    next_pos = _match_end(_SPACES, masked, pos, end)
    if pos < next_pos < end:
        unit_end = _end_of_word(masked, next_pos, end)
        if unit_end > next_pos and masked[next_pos:unit_end].lower() in _UNITS:
            return unit_end
    return pos


def count_words(masked: str, start: int = 0, end: int | None = None) -> int:
    """Apply word-count rules for quantities, quotations, and parentheses."""
    end = len(masked) if end is None else end
    count = 0
    pos = start
    while match := _COUNT_START.search(masked, pos, end):
        pos = match.start()
        if masked[pos] in '("“':
            group_end = _group_end(masked, pos, end)
            if group_end > pos:
                count += 1
                pos = group_end
            else:
                pos += 1
            continue
        pos, stop = _word_span(masked, match, end)
        if stop == pos:
            pos += 1
            continue
        pos = _quantity_end(masked, pos, stop, end)
        count += 1
    return count


def _ends_sentence(src: str, masked: str, pos: int) -> bool:
    next_pos = pos + 1
    while next_pos < len(src) and src[next_pos] in " \t":
        next_pos += 1
    if next_pos < len(src) and src[next_pos].islower():
        return False
    start = pos
    while start > 0 and (
        masked[start - 1].isascii() and (masked[start - 1].isalnum() or masked[start - 1] in "._")
    ):
        start -= 1
    word = masked[start:pos].lower()
    if len(word) == 1 and "a" <= word <= "z":
        return False
    return word not in _ABBREVIATIONS


def _sentence_boundary(
    doc: Document, block: _Block, segment_start: int, pos: int, end: int
) -> tuple[int, bool]:
    masked = doc.masked
    char = masked[pos]
    colon = char == ":" and block.kind == "list-item"
    if not colon and char not in ".!?":
        return pos + 1, False
    stop = pos + 1
    if not colon:
        while stop < end and masked[stop] in ".!?":
            stop += 1
    punctuation_end = stop
    while stop < end and masked[stop] in _CLOSING:
        stop += 1
    if stop < end and masked[stop] not in _SPACE:
        return punctuation_end, False
    if colon and block.admonition:
        label = re.sub(r"^[^\w]+|[^\w]+$", "", masked[segment_start:pos].strip())
        if label.lower() == block.admonition:
            return pos + 1, False
    if char == "." and not _ends_sentence(doc.source, masked, pos):
        return punctuation_end, False
    return stop, True


def _sentences(doc: Document, block: _Block, number: int) -> list[Sentence]:
    out: list[Sentence] = []
    src, masked = doc.source, doc.masked
    start, end = block.segments[0][0], block.segments[-1][1]
    segment_start = start

    def flush(stop: int) -> None:
        nonlocal segment_start
        left, right = segment_start, stop
        left = _match_end(_SPACES, masked, left, right)
        right = left + len(masked[left:right].rstrip(_SPACE))
        tokens = tokenize(masked, left, right)
        if tokens:
            out.append(
                Sentence(
                    src[left:right],
                    left,
                    right,
                    tokens,
                    count_words(masked, left, right),
                    block.procedural,
                    block.admonition in {"note", "notes"},
                    number,
                    block.kind,
                    block.admonition,
                )
            )
        segment_start = stop

    candidate = _LIST_PUNCTUATION if block.kind == "list-item" else _PUNCTUATION
    pos = start
    while match := candidate.search(masked, pos, end):
        stop, boundary = _sentence_boundary(doc, block, segment_start, match.start(), end)
        if boundary:
            flush(stop)
        pos = stop
    if segment_start < end:
        flush(end)
    if out:
        out[0].first = True
        out[-1].last = True
    return out
