# Copyright (c) 2026 Tudor Andrei Dumitrascu
"""Grammar rules for procedures, notes, and safety instructions.

Each rule needs the analyzer. Without it, the rules give no finding. The
word rules for 5.4 and 5.5 in ``ste.rules.structure`` work without it.
"""

from ste.models import Diagnostic, Document, Options, Sentence, SyntaxToken
from ste.rules.data import CONDITION_WORDS, SAFETY_WORDS
from ste.rules.structure import hidden_start, instruction_word
from ste.rules.syntax import syntax_span

_SUBJECT_DEPS = frozenset({"nsubj", "nsubjpass", "csubj", "csubjpass", "expl"})
_NOT_WORDS = frozenset({"SPACE", "PUNCT", "X"})
# Words that show two actions at the same time. Rule 5.2 permits them in one sentence.
_SIMULTANEOUS = ("at the same time", "simultaneously")
# A dependent that does not make the first verb an instruction of its own.
_LIGHT_DEPS = frozenset({"cc", "punct", "aux", "neg", "advmod", "intj"})
_CONJ_TAGS = frozenset({"VB", "VBP"})
# Subordinate words that start a condition clause. "until" and "while" give a
# duration, and the clause cannot go first.
_CLAUSE_CONDITIONS = frozenset({"before", "after", "once"})
# A command in a note that sends the reader to other text, and is not a task.
_REFERENCES = frozenset({"see", "refer"})


class _Parse:
    """The analyzer tokens of one sentence, with their tree."""

    def __init__(self, s: Sentence) -> None:
        self.tokens = s.syntax
        position = {t.index: k for k, t in enumerate(self.tokens)}
        self.heads = [position.get(t.head, -1) for t in self.tokens]

    def head(self, k: int) -> int:
        """Return the position of the head of a token, or -1 for the root."""
        h = self.heads[k]
        return -1 if h == k else h

    def children(self, k: int) -> list[int]:
        """Return the positions of the dependents of a token."""
        return [j for j, h in enumerate(self.heads) if h == k and j != k]

    def root(self) -> int:
        """Return the position of the first root that is a word."""
        return next(
            (k for k, t in enumerate(self.tokens) if t.dep == "ROOT" and t.pos not in _NOT_WORDS),
            -1,
        )

    def has_subject(self, k: int) -> bool:
        """Return whether a verb has a subject."""
        return any(self.tokens[j].dep in _SUBJECT_DEPS for j in self.children(k))

    def imperative(self, k: int, tags: frozenset[str] = frozenset({"VB"})) -> bool:
        """Return whether a verb is a command: a base form with no subject and no modal."""
        t = self.tokens[k]
        if t.tag not in tags or t.pos not in {"VERB", "AUX"} or self.has_subject(k):
            return False
        return not any(
            self.tokens[j].dep in {"aux", "auxpass"}
            and (self.tokens[j].tag == "MD" or self.tokens[j].text.lower() == "to")
            for j in self.children(k)
        )

    def in_clause(self, k: int, root: int) -> bool:
        """Return whether a token is in a clause that modifies the root."""
        seen = set()
        while k >= 0 and k not in seen:
            seen.add(k)
            h = self.head(k)
            if h == root:
                return self.tokens[k].dep == "advcl"
            k = h
        return False


def _plain_word(s: Sentence, t: SyntaxToken) -> bool:
    """Return whether a token is a whole word in small letters, outside a quotation.

    A word in capital letters in a step is often a name, such as a label of
    the screen, and a quotation holds text that the reader does not obey.
    """
    if not t.text.isalpha() or not t.text.islower():
        return False
    if not any(w.start - s.start == t.start and w.end - w.start == len(t.text) for w in s.tokens):
        return False
    before = s.text[: t.start]
    return (
        before.count('"') % 2 == 0
        and before.count("\u201c") <= before.count("\u201d")
        and before.count("(") <= before.count(")")
    )


def _second_instruction(s: Sentence, p: _Parse, root: int) -> int:
    """Return the position of a second command that joins the first, or -1."""
    chain = [root]
    for k, t in enumerate(p.tokens):
        if t.dep == "conj" and p.head(k) in chain:
            chain.append(k)
    if any(
        p.tokens[j].dep == "cc" and p.tokens[j].text.lower() in {"or", "nor"}
        for c in chain
        for j in p.children(c)
    ):
        return -1
    for k in chain[1:]:
        # The tagger often reads a second command as a present tense ("VBP").
        if not p.imperative(k, _CONJ_TAGS) or not _plain_word(s, p.tokens[k]):
            continue
        # A verb after a list of nouns is often the last noun of the list, as
        # in "freeze the ID, the checksum, and stop limits".
        if any(
            p.tokens[j].dep in {"conj", "appos"} and p.tokens[j].pos in {"NOUN", "PROPN"}
            for j in range(root + 1, k)
        ):
            return -1
        before = p.head(k)
        if any(before < j < k and p.tokens[j].dep not in _LIGHT_DEPS for j in p.children(before)):
            return k
    return -1


def _quoted_or_named(doc: Document, s: Sentence) -> bool:
    """Return whether a step is in a block quote, or starts after code or a link.

    A block quote holds text to copy, such as a prompt. A step that starts with
    code, as in "`runtime`: load the pools", often describes the code.
    """
    line_start = doc.source.rfind("\n", 0, s.start) + 1
    return ">" in doc.source[line_start : s.start] or (
        s.first and hidden_start(doc.source, s.start)
    )


def step_instructions(doc: Document, _opts: Options) -> list[Diagnostic]:
    """Report a step of a procedure that gives more than one command."""
    out = []
    for s in doc.sentences:
        if not s.procedural or s.note or s.admonition or s.kind != "list-item" or not s.tagged:
            continue
        if any(words in s.text.lower() for words in _SIMULTANEOUS) or _quoted_or_named(doc, s):
            continue
        p = _Parse(s)
        root = p.root()
        if root < 0 or not p.imperative(root) or not _starts_with(p, root):
            continue
        second = _second_instruction(s, p, root)
        if second < 0:
            continue
        t = p.tokens[second]
        start, end = syntax_span(s, t)
        out.append(
            Diagnostic(
                "STE-5.2",
                f'The step has more than one instruction. "{t.text}" starts a second one.',
                "warning",
                0.8,
                start,
                end,
                "Write each instruction in a step of its own. "
                "Only actions that occur at the same time stay in one sentence.",
            )
        )
    return out


def safety_command(doc: Document, _opts: Options) -> list[Diagnostic]:
    """Report a safety instruction that starts with a description."""
    out = []
    for s in doc.sentences:
        if not s.first or s.admonition not in SAFETY_WORDS or not s.tagged:
            continue
        p = _Parse(s)
        root = p.root()
        if root < 0 or p.imperative(root):
            continue
        if p.tokens[root].pos not in {"VERB", "AUX"} or not p.has_subject(root):
            continue
        out.append(
            Diagnostic(
                "STE-7.2",
                f"The {s.admonition} starts with a description, and not with a command.",
                "warning",
                0.8,
                s.start,
                s.end,
                "Start with a clear command. A condition can come before the command. "
                "Then give the risk.",
            )
        )
    return out


def _late_condition(p: _Parse, root: int) -> int:
    """Return the position of the first word of a condition after the command, or -1."""
    tokens = p.tokens
    for k in range(root + 1, len(tokens)):
        word = tokens[k].text.lower()
        following = [t.text.lower() for t in tokens[k + 1 : k + 3]]
        if word in _CLAUSE_CONDITIONS and tokens[k].dep == "mark":
            clause = p.head(k)
            if (
                clause >= 0
                and tokens[clause].dep == "advcl"
                and p.head(clause) == root
                and p.has_subject(clause)
            ):
                return k
        if word == "in" and following[:1] == ["case"] and p.head(k) == root:
            return k
        if word == "as" and following == ["soon", "as"]:
            return k
    return -1


def condition_clause_order(doc: Document, _opts: Options) -> list[Diagnostic]:
    """Report a step that gives a time or case condition after its command."""
    out = []
    for s in doc.sentences:
        if not s.procedural or s.note or not s.tagged:
            continue
        # The word rule of STE-5.4 reads these words.
        if any(t.lower in CONDITION_WORDS for t in s.tokens[1:]):
            continue
        p = _Parse(s)
        root = p.root()
        if root < 0 or not p.imperative(root):
            continue
        k = _late_condition(p, root)
        if k < 0:
            continue
        t = p.tokens[k]
        start, _ = syntax_span(s, t)
        out.append(
            Diagnostic(
                "STE-5.4",
                f'The instruction gives its condition ("{t.text}") after the command.',
                "info",
                0.75,
                start,
                s.tokens[-1].end,
                "Write the condition first, then a comma, then the command.",
            )
        )
    return out


def _starts_with(p: _Parse, root: int) -> bool:
    """Return whether the root starts the sentence, after a condition or an adverb."""
    for k in range(root):
        t = p.tokens[k]
        if t.pos in _NOT_WORDS:
            continue
        if p.head(k) == root and t.dep in _LIGHT_DEPS:
            continue
        if not p.in_clause(k, root):
            return False
    return True


def note_command(doc: Document, _opts: Options) -> list[Diagnostic]:
    """Report a note that gives a command with no instruction word."""
    out = []
    for s in doc.sentences:
        if s.admonition not in {"note", "notes"} or not s.tagged:
            continue
        # The word rule of STE-5.5 reports this sentence.
        if instruction_word(s) is not None:
            continue
        p = _Parse(s)
        root = p.root()
        if root < 0 or not p.imperative(root) or not _starts_with(p, root):
            continue
        t = p.tokens[root]
        if (t.lemma or t.text).lower() in _REFERENCES:
            continue
        start, end = syntax_span(s, t)
        out.append(
            Diagnostic(
                "STE-5.5",
                f'The note gives a command ("{t.text}").',
                "warning",
                0.75,
                start,
                end,
                "A note gives information only. Move the instruction to a step of the procedure.",
            )
        )
    return out
