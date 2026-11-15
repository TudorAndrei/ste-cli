# Copyright (c) 2026 Tudor Andrei Dumitrascu
"""Property-based checks for offsets, parsing, suppressions, patterns, and baselines."""

from __future__ import annotations

import json
import tempfile
from collections import Counter
from pathlib import Path

from hypothesis import given, settings
from hypothesis import strategies as st

import ste
from ste import baseline, cli, config, document, report
from ste.checker import lint
from ste.models import Diagnostic
from ste.suppress import suppressions

CHARS = [*"abcXYZ 019.,;:!?'\"`*_#>-|()[]<>\\\n\r\t", "é", "☕", "😀", chr(0x2019)]
TEXT = st.text(alphabet=CHARS, max_size=200)
FRAGMENTS = [
    "# Heading",
    "- list item",
    "1. numbered item",
    "```",
    "~~~",
    "<!-- ste-disable -->",
    "<!-- ste-enable -->",
    "<!-- ste-disable-next-line STE-4.2 -->",
    "| cell | cell |",
    "| --- | --- |",
    "> quoted line",
    "It isn't done; it can't be.",
    "The pump is off.",
    "Open the valve.",
    "    indented code",
    "Text with `code` and ☕.",
    "",
]
LINE_ENDS = st.sampled_from(["\n", "\r\n", "\r"])
MARKDOWN = st.builds(
    lambda lines, line_end: line_end.join(lines),
    st.lists(st.sampled_from(FRAGMENTS), max_size=20),
    LINE_ENDS,
)
ANY_TEXT = st.one_of(TEXT, MARKDOWN)
NAME = st.from_regex(r"[a-z][a-z0-9_]{0,5}", fullmatch=True)
SEGMENT = st.from_regex(r"[a-z0-9_]{1,6}", fullmatch=True)
PRINTABLE = st.characters(categories=("L", "N", "P", "S", "Z"))
PREFIX = "<!-- ste-disable -->\n\n"
SCHEMA_PATH = Path(ste.__file__).parent / "schema.json"
RULE_IDS = [rule["id"] for rule in json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))["rules"]]
SEVERITIES = ["off", "info", "warning", "error"]


@given(TEXT, st.data())
def test_position_matches_prefix_reference(source: str, data: st.DataObject) -> None:
    """Line and column equal a whole-prefix reference, in characters and in UTF-8 bytes."""
    offset = data.draw(st.integers(0, len(source)))
    prefix = source[:offset]
    tail = prefix.rsplit("\n", 1)[-1]
    line = prefix.count("\n") + 1
    assert report.position(source, offset) == (line, len(tail) + 1)
    assert report.position(source, offset, byte_column=True) == (
        line,
        len(tail.encode("utf-8")) + 1,
    )


@given(TEXT, st.data())
def test_finding_offsets_are_byte_offsets(source: str, data: st.DataObject) -> None:
    """Finding start and end are UTF-8 byte offsets of the character offsets."""
    start = data.draw(st.integers(0, len(source)))
    end = data.draw(st.integers(start, len(source)))
    diag = Diagnostic("STE-4.2", "A message.", "warning", 1.0, start, end)
    finding = report.make_finding("a.md", source, diag)
    assert finding.data["start"] == len(source[:start].encode("utf-8"))
    assert finding.data["end"] == len(source[:end].encode("utf-8"))


@settings(deadline=None)
@given(ANY_TEXT)
def test_parse_spans_are_consistent(text: str) -> None:
    """Parsing keeps the length, and each sentence and token matches its source span."""
    doc = document.parse(text)
    assert len(doc.masked) == len(doc.source)
    assert doc.word_count() >= 0
    for sentence in doc.sentences:
        assert 0 <= sentence.start < sentence.end <= len(text)
        assert sentence.text == text[sentence.start : sentence.end]
        for token in sentence.tokens:
            assert sentence.start <= token.start < token.end <= sentence.end
            assert doc.masked[token.start : token.end] == token.text


@settings(deadline=None)
@given(ANY_TEXT)
def test_lint_spans_are_ordered(text: str) -> None:
    """Each diagnostic lies inside the text, and the list is sorted by position and rule."""
    diagnostics = lint(text)
    for diag in diagnostics:
        assert 0 <= diag.start <= diag.end <= len(text)
    keys = [(diag.start, diag.end, diag.rule_id) for diag in diagnostics]
    assert keys == sorted(keys)


@settings(deadline=None)
@given(MARKDOWN)
def test_file_level_disable_suppresses_findings(doc: str) -> None:
    """A leading file-wide disable hides every finding before the first ste-enable text."""
    # A later ste-enable comment legitimately ends the suppression, so the bound
    # is the first raw occurrence of that text. Findings must start at or after it.
    enable = doc.find("ste-enable")
    limit = len(PREFIX) + enable if enable >= 0 else len(PREFIX) + len(doc)
    assert all(diag.start >= limit for diag in lint(PREFIX + doc))


@settings(deadline=None)
@given(ANY_TEXT)
def test_suppression_regions_lie_inside_the_text(text: str) -> None:
    """Each suppression region is an ordered span inside the source."""
    for region in suppressions(text):
        assert 0 <= region.start <= region.end <= len(text)


@given(st.lists(SEGMENT, min_size=1, max_size=4))
def test_match_pattern_accepts_path_forms(segments: list[str]) -> None:
    """A path matches itself, its last segment behind a wildcard, and its first segment."""
    path = "/".join(segments)
    assert cli.match_pattern(path, path)
    assert cli.match_pattern("**/" + segments[-1], path)
    assert cli.match_pattern(segments[0], path)
    assert not cli.match_pattern("", path)


@given(st.lists(st.tuples(NAME, NAME, st.text(alphabet=PRINTABLE, max_size=30)), max_size=20))
def test_baseline_takes_each_added_finding_once(
    triples: list[tuple[str, str, str]],
) -> None:
    """Each added finding is taken once, and no accepted finding is left over."""
    accepted = baseline.Set()
    for file, rule, text in triples:
        accepted.add(file, rule, text)
    files = {file for file, _, _ in triples}
    assert accepted.stale(files) == len(triples)
    for file, rule, text in triples:
        assert accepted.take(file, rule, text)
    assert accepted.stale(files) == 0
    for file, rule, text in triples:
        assert not accepted.take(file, rule, text)


@given(NAME, NAME, st.text(max_size=40))
def test_baseline_key_ignores_whitespace(file: str, rule: str, text: str) -> None:
    """Runs of whitespace and surrounding whitespace do not change a baseline key."""
    assert baseline.key(file, rule, "a  b\n c") == baseline.key(file, rule, "a b c")
    assert baseline.key(file, rule, text) == baseline.key(file, rule, "  " + text + "\n")


@given(st.lists(st.tuples(NAME, NAME, st.text(max_size=30)), max_size=20))
def test_baseline_save_then_load_keeps_counts(triples: list[tuple[str, str, str]]) -> None:
    """Saving and loading a baseline keeps the normalised count of each finding."""
    results = [baseline.Result(file, [(rule, text)]) for file, rule, text in triples]
    expected = Counter(baseline.key(file, rule, text) for file, rule, text in triples)
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / baseline.DEFAULT_NAME
        baseline.save(path, results, "2026-01-01T00:00:00Z")
        loaded = baseline.load(path)
    assert loaded.counts == expected


@given(st.sampled_from(RULE_IDS), st.sampled_from(SEVERITIES))
def test_config_rule_severity_round_trip(rule: str, severity: str) -> None:
    """A known rule with a valid severity reads back with the same severity."""
    cfg = config.parse(f"rules:\n  {rule}: {severity}\n")
    assert cfg.rules[rule] == severity
