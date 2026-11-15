"""Read Markdown prose and preserve positions in the original source."""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass, field

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
from markdown_it.rules_inline.state_inline import StateInline
from markdown_it.token import Token as MarkdownToken

from ste.models import Document, Sentence, Token

_ABBREVIATIONS = set(
    "e.g i.e etc vs fig no ref approx min max sec para ch al inc ltd dr mr mrs ms st vol cf ca dept".split()
)
_UNITS = set(
    "mm cm m km in ft mg g kg lb lbs ml l gal ms s sec min h hr hrs day days week weeks month months year years hz khz mhz ghz b kb mb gb tb kib mib gib tib bit bits byte bytes v a ma w kw psi bar kpa mpa n nm px pt em rem dpi rpm c f k %".split()
)
_ADMONITIONS = set("warning caution danger note notes important attention tip info".split())
_SPACE = " \t\n\r"
_CLOSING = "*_) ]\"'`".replace(" ", "")
_JOIN = "'’ʼ-._"


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


def _inline_visibility(content: str, md: MarkdownIt, env: dict) -> list[bool]:
    """Record source spans while the CommonMark inline rules consume them.

    Link labels are parsed in the same state. Image alternatives use a new
    state, whose positions must not enter the outer document.
    """
    visible = [True] * len(content)
    root_state: list[StateInline] = []
    delimiters: list[tuple[MarkdownToken, int, int]] = []

    def track(
        name: str, rule: Callable[[StateInline, bool], bool]
    ) -> Callable[[StateInline, bool], bool]:
        def wrapped(state: StateInline, silent: bool) -> bool:
            if not root_state and not silent:
                root_state.append(state)
            start = state.pos
            count = len(state.tokens)
            label_end = -1
            if name == "link" and state.src[start : start + 1] == "[":
                label_end = state.md.helpers.parseLinkLabel(state, start, True)
            matched = rule(state, silent)
            if not matched or silent or not root_state or state is not root_state[0]:
                return matched
            end = state.pos
            if name == "link":
                if label_end >= 0:
                    visible[start] = False
                    visible[label_end:end] = [False] * (end - label_end)
            elif name in {"emphasis", "strikethrough"}:
                tokens = [
                    t
                    for t in state.tokens[count:]
                    if t.type == "text" and t.content and set(t.content) <= {state.src[start]}
                ]
                offset = start
                for token in tokens:
                    delimiters.append((token, offset, offset + len(token.content)))
                    offset += len(token.content)
            elif name != "backticks" or any(t.type == "code_inline" for t in state.tokens[count:]):
                visible[start:end] = [False] * (end - start)
            return matched

        return wrapped

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
        md.inline.ruler.at(name, track(name, rule))
    children: list[MarkdownToken] = []
    md.inline.parse(content, md, env, children)
    for token, start, end in delimiters:
        if token.type != "text" or not token.content:
            visible[start:end] = [False] * (end - start)
    return visible


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


def parse(src: str) -> Document:
    """Return prose sentences with character offsets in *src*."""
    md = MarkdownIt("commonmark").enable(["table", "strikethrough"])
    md.core.ruler.disable("inline")
    md.inline.ruler2.disable("fragments_join")
    env: dict = {}
    tokens = md.parse(src, env)
    lines = [0]
    lines.extend(m.end() for m in re.finditer(r"\r\n|\r|\n", src))
    if lines[-1] != len(src):
        lines.append(len(src))
    elif len(lines) == 1:
        lines.append(0)
    masked = [c if c in "\r\n" else " " for c in src]
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
            segments: list[tuple[int, int]] = []
            for index, pos in enumerate(positions):
                if pos < front or not visible[index]:
                    continue
                masked[pos] = src[pos]
                if segments and pos == segments[-1][1]:
                    segments[-1] = (segments[-1][0], pos + 1)
                else:
                    segments.append((pos, pos + 1))
            if segments:
                kind = "paragraph"
                if "heading_open" in stack:
                    kind = "heading"
                elif "td_open" in stack or "th_open" in stack:
                    kind = "table-cell"
                elif "list_item_open" in stack:
                    kind = "list-item"
                start = segments[0][0]
                blocks.append(
                    _Block(
                        segments,
                        "ordered_list_open" in stack,
                        kind,
                        _admonition_word(src[start : start + 48]),
                    )
                )
        if token.nesting == -1 and stack:
            stack.pop()
    doc = Document(src, "".join(masked))
    for number, block in enumerate(blocks):
        doc.sentences.extend(_sentences(doc, block, number))
    return doc


def _is_word(char: str) -> bool:
    return char.isalpha() or char.isdigit()


def _end_of_word(text: str, pos: int, end: int) -> int:
    while pos < end:
        if _is_word(text[pos]):
            pos += 1
        elif text[pos] in _JOIN and pos + 1 < end and _is_word(text[pos + 1]):
            pos += 1
        else:
            break
    return pos


def tokenize(masked: str, start: int = 0, end: int | None = None) -> list[Token]:
    """Return word tokens without removing their original source positions."""
    end = len(masked) if end is None else end
    out: list[Token] = []
    pos = start
    while pos < end:
        if not _is_word(masked[pos]):
            pos += 1
            continue
        stop = _end_of_word(masked, pos, end)
        word = masked[pos:stop]
        out.append(Token(word, word.replace("’", "'").replace("ʼ", "'").lower(), pos, stop))
        pos = stop
    return out


def count_words(masked: str, start: int = 0, end: int | None = None) -> int:
    """Apply the word-count rules for quantities, quotations, and parentheses."""
    end = len(masked) if end is None else end
    count = 0
    pos = start
    while pos < end:
        char = masked[pos]
        if char == "(":
            depth = 0
            for close in range(pos, end):
                depth += (masked[close] == "(") - (masked[close] == ")")
                if depth == 0:
                    count += 1
                    pos = close + 1
                    break
            else:
                pos += 1
            continue
        if char in {'"', "“"}:
            close = masked.find("”" if char == "“" else '"', pos + 1, end)
            if close >= 0:
                count += 1
                pos = close + 1
                continue
        if not _is_word(char):
            pos += 1
            continue
        start_word = pos
        pos = _end_of_word(masked, pos, end)
        count += 1
        if re.fullmatch(r"[0-9.,]+", masked[start_word:pos]):
            next_pos = pos
            while next_pos < end and masked[next_pos] in _SPACE:
                next_pos += 1
            if pos < next_pos < end:
                unit_end = _end_of_word(masked, next_pos, end)
                if unit_end > next_pos and masked[next_pos:unit_end].lower() in _UNITS:
                    pos = unit_end
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


def _sentences(doc: Document, block: _Block, number: int) -> list[Sentence]:
    out: list[Sentence] = []
    src, masked = doc.source, doc.masked
    start, end = block.segments[0][0], block.segments[-1][1]
    segment_start = start

    def flush(stop: int) -> None:
        nonlocal segment_start
        left, right = segment_start, stop
        while left < right and masked[left] in _SPACE:
            left += 1
        while right > left and masked[right - 1] in _SPACE:
            right -= 1
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

    pos = start
    while pos < end:
        char = masked[pos]
        colon = char == ":" and block.kind == "list-item"
        if not colon and char not in ".!?":
            pos += 1
            continue
        stop = pos + 1
        if not colon:
            while stop < end and masked[stop] in ".!?":
                stop += 1
        punctuation_end = stop
        while stop < end and masked[stop] in _CLOSING:
            stop += 1
        if stop < end and masked[stop] not in _SPACE:
            pos = punctuation_end
            continue
        if colon and block.admonition:
            label = masked[segment_start:pos].strip()
            label = re.sub(r"^[^\w]+|[^\w]+$", "", label)
            if label.lower() == block.admonition:
                pos += 1
                continue
        if char == "." and not _ends_sentence(src, masked, pos):
            pos = punctuation_end
            continue
        flush(stop)
        pos = stop
    if segment_start < end:
        flush(end)
    if out:
        out[0].first = True
        out[-1].last = True
    return out
