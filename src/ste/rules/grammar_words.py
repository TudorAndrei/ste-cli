# Copyright (c) 2026 Tudor Andrei Dumitrascu
"""Word checks that need the part of speech or the dependency of a word.

Each check reads ``Sentence.tagged`` first. A sentence without grammar gives
no finding here, and the word-list checks of ``words`` and ``verbs`` keep
their behavior.
"""

from ste.config import SOFTWARE_NOUNS
from ste.models import Diagnostic, Document, Options, Sentence, Token
from ste.rules.common import phrase_matcher, span
from ste.rules.data import NOMINALIZATIONS, PHRASAL_VERBS
from ste.rules.verbs import match_phrasal

TECHNICAL_WORD_CONFIDENCE = 0.7
ACTION_NOUN_CONFIDENCE = 0.85
PHRASAL_LIST_CONFIDENCE = 0.85
PHRASAL_OTHER_CONFIDENCE = 0.7
_PHRASAL_SUGGESTIONS = {
    (base, " ".join(particles)): suggestion for base, particles, suggestion in PHRASAL_VERBS
}
# A verb and a particle that tell the state of a light or a switch. "ON" and
# "OFF" are words for a state, thus "the light comes on" is not a phrasal
# verb that needs a different verb.
_STATE_PARTICLES = {("come", "on"), ("come", "off")}
_ACTION_DEPS = {"dobj", "nsubjpass"}
_LISTED_NOMINALIZATIONS = phrase_matcher(tuple(tuple(words) for words, _ in NOMINALIZATIONS))

# British spellings that are correct for one part of speech only. British
# English writes the noun "licence" and the verb "license". American English
# writes "license" for both. The value is the British part of speech and the
# American form.
POS_SPELLINGS = {
    "licence": ("NOUN", "license"),
    "licences": ("NOUN", "licenses"),
    "practise": ("VERB", "practice"),
    "practised": ("VERB", "practiced"),
    "practises": ("VERB", "practices"),
    "practising": ("VERB", "practicing"),
    "dependant": ("NOUN", "dependent"),
    "dependants": ("NOUN", "dependents"),
}

# A noun that names an action, and the verb for the same action. Each noun
# has a clear verb. A noun that also names an item, such as "application"
# or "attachment", is not here.
ACTION_NOUNS = {
    "activation": "activate",
    "adjustment": "adjust",
    "alignment": "align",
    "analysis": "analyze",
    "approval": "approve",
    "assessment": "assess",
    "authentication": "authenticate",
    "calculation": "calculate",
    "calibration": "calibrate",
    "comparison": "compare",
    "compilation": "compile",
    "completion": "complete",
    "confirmation": "confirm",
    "connection": "connect",
    "conversion": "convert",
    "correction": "correct",
    "creation": "create",
    "deactivation": "deactivate",
    "decision": "decide",
    "deletion": "delete",
    "deployment": "deploy",
    "description": "describe",
    "disassembly": "disassemble",
    "disconnection": "disconnect",
    "evaluation": "evaluate",
    "examination": "examine",
    "execution": "execute",
    "explanation": "explain",
    "extraction": "extract",
    "implementation": "implement",
    "improvement": "improve",
    "indication": "show",
    "initialization": "initialize",
    "inspection": "inspect",
    "installation": "install",
    "investigation": "investigate",
    "isolation": "isolate",
    "lubrication": "lubricate",
    "measurement": "measure",
    "migration": "migrate",
    "modification": "modify",
    "notification": "notify",
    "optimization": "optimize",
    "preparation": "prepare",
    "recommendation": "recommend",
    "reduction": "reduce",
    "registration": "register",
    "reinstallation": "reinstall",
    "removal": "remove",
    "replacement": "replace",
    "restoration": "restore",
    "rotation": "rotate",
    "selection": "select",
    "synchronization": "synchronize",
    "uninstallation": "uninstall",
    "validation": "validate",
    "verification": "verify",
}

# A verb with little meaning of its own. The noun after it gives the action.
# None means that the verb is empty with each action noun. A set limits the
# verb to these nouns, because "make a preparation" can make an item.
_COMMUNICATION = frozenset(
    {
        "approval",
        "confirmation",
        "description",
        "explanation",
        "indication",
        "notification",
        "recommendation",
    }
)
LIGHT_VERBS: dict[str, frozenset[str] | None] = {
    "accomplish": None,
    "carry": None,
    "conduct": None,
    "do": None,
    "effect": None,
    "perform": None,
    "undertake": None,
    "give": _COMMUNICATION,
    "provide": _COMMUNICATION,
    "take": frozenset({"measurement", "decision"}),
    "make": frozenset(
        {
            "adjustment",
            "assessment",
            "calculation",
            "comparison",
            "connection",
            "correction",
            "decision",
            "deletion",
            "examination",
            "improvement",
            "inspection",
            "measurement",
            "modification",
            "recommendation",
            "reduction",
            "replacement",
            "selection",
        }
    ),
}
_PRESET_NOUNS = frozenset(SOFTWARE_NOUNS)
_QUOTES = "\"'\u201c\u201d\u2018\u2019`"
_POS_NAMES = {"NOUN": "noun", "VERB": "verb", "ADJ": "adjective"}
_VERB_TAGS = {"VB", "VBD", "VBG", "VBN", "VBP", "VBZ"}


def _base(t: Token) -> str:
    """Return the lemma of a word, or its lower-case text without a lemma."""
    return t.lemma.lower() or t.lower


def _single_words(names: list[str]) -> set[str]:
    return {name.lower() for name in names if len(name.split()) == 1}


def _used_as_verb(s: Sentence, i: int) -> bool:
    """Return whether a word is a verb.

    The tagger can tag a capitalized first word as a name, as in "Shim the
    bracket". A first word that is the root and has a direct object is a
    command verb.
    """
    t = s.tokens[i]
    if t.pos == "VERB":
        return t.tag in _VERB_TAGS
    return (
        i == 0
        and t.pos == "PROPN"
        and t.dep == "ROOT"
        and any(other.head == i and other.dep == "dobj" for other in s.tokens)
    )


def technical_words(doc: Document, opts: Options) -> list[Diagnostic]:
    """Report a technical noun as a verb, and a technical verb as a noun.

    The glossary gives the technical nouns (``allow.nouns``) and the technical
    verbs (``allow.verbs``). A word in both lists has both parts of speech.
    The nouns of the software preset are not technical nouns here. Software
    text uses most of them as verbs too, such as "build" and "commit".
    """
    nouns = _single_words(opts.allow_nouns) - _PRESET_NOUNS
    verbs = _single_words(opts.allow_verbs)
    only_nouns, only_verbs = nouns - verbs, verbs - nouns
    if not only_nouns and not only_verbs:
        return []
    out = []
    for s in doc.sentences:
        if not s.tagged:
            continue
        for i, t in enumerate(s.tokens):
            base = _base(t)
            if _used_as_verb(s, i) and (t.lower in only_nouns or base in only_nouns):
                out.append(
                    Diagnostic(
                        "STE-1.7",
                        f'"{t.text}" is a technical noun, but this sentence uses it as a verb.',
                        "warning",
                        TECHNICAL_WORD_CONFIDENCE,
                        t.start,
                        t.end,
                        "Use an approved verb, and keep the technical noun as a noun.",
                    )
                )
            elif (
                t.pos == "NOUN"
                and t.dep != "compound"
                and not t.lower.endswith("ing")
                and (t.lower in only_verbs or base in only_verbs)
            ):
                out.append(
                    Diagnostic(
                        "STE-1.13",
                        f'"{t.text}" is a technical verb, but this sentence uses it as a noun.',
                        "warning",
                        TECHNICAL_WORD_CONFIDENCE,
                        t.start,
                        t.end,
                        f'Write a sentence with "{base}" as its verb.',
                    )
                )
    return out


def _quoted(source: str, t: Token) -> bool:
    """Return whether quotation marks enclose a word, as in a mention of the word."""
    return (
        t.start > 0
        and t.end < len(source)
        and source[t.start - 1] in _QUOTES
        and source[t.end] in _QUOTES
    )


def pos_spelling(doc: Document, opts: Options) -> list[Diagnostic]:
    """Report a British spelling that the part of speech of the word selects."""
    out = []
    for s in doc.sentences:
        if not s.tagged:
            continue
        for i, t in enumerate(s.tokens):
            entry = POS_SPELLINGS.get(t.lower)
            if entry is None or opts.allowed(t.lower) or t.pos not in _POS_NAMES:
                continue
            if (i > 0 and t.text[0].isupper()) or _quoted(doc.source, t):
                continue
            british_pos, american = entry
            if t.pos == british_pos:
                message = (
                    f'"{t.text}" is the British spelling of the {_POS_NAMES[british_pos]}. '
                    f'American English writes "{american}".'
                )
            else:
                message = f'"{t.text}" is not a correct spelling of the {_POS_NAMES[t.pos]}.'
            out.append(
                Diagnostic(
                    "STE-1.14",
                    message,
                    "warning",
                    0.9,
                    t.start,
                    t.end,
                    f'Write "{american}".',
                )
            )
    return out


def _light_verb(s: Sentence, noun: int, name: str) -> tuple[int, int] | None:
    """Return the first and last word of the light verb of an action noun."""
    t = s.tokens[noun]
    verb = t.head
    if t.dep not in _ACTION_DEPS or verb < 0 or verb == noun:
        return None
    head = s.tokens[verb]
    if head.pos != "VERB":
        return None
    base = _base(head)
    particles = [k for k, other in enumerate(s.tokens) if other.head == verb and other.dep == "prt"]
    if base not in LIGHT_VERBS:
        return None
    nouns = LIGHT_VERBS[base]
    if nouns is not None and name not in nouns:
        return None
    if base == "carry":
        out = [k for k in particles if s.tokens[k].lower == "out"]
        return (verb, out[0]) if out else None
    return None if particles else (verb, verb)


def action_nouns(doc: Document, opts: Options) -> list[Diagnostic]:
    """Report an empty verb with a noun that names the action.

    An example is "perform an installation of the software", which is
    "install the software". The parser gives the object of the verb, thus
    the words between the verb and the noun can change.
    """
    out = []
    for s in doc.sentences:
        if not s.tagged:
            continue
        listed = {i for i, _ in _LISTED_NOMINALIZATIONS.matches(s)}
        for n, t in enumerate(s.tokens):
            if t.pos != "NOUN" or opts.allowed(t.lower):
                continue
            name = _base(t) if _base(t) in ACTION_NOUNS else t.lower
            verb = ACTION_NOUNS.get(name)
            if verb is None:
                continue
            found = _light_verb(s, n, name)
            if found is None:
                continue
            first, last = found
            if first in listed:
                continue
            start, end = min(first, n), max(last, n)
            out.append(
                Diagnostic(
                    "STE-3.7",
                    f'"{span(s, start, end)}" uses a noun for an action.',
                    "warning",
                    ACTION_NOUN_CONFIDENCE,
                    s.tokens[start].start,
                    s.tokens[end].end,
                    f'Write the verb "{verb}".',
                )
            )
    return out


def separated_phrasal(doc: Document, opts: Options) -> list[Diagnostic]:
    """Report a verb and its particle that the word list does not find.

    The parser marks the particle of a phrasal verb. This finds "turn the
    pump off", and a phrasal verb that is not in the list, such as "log in".
    """
    verbs = {verb.lower() for verb in opts.allow_verbs}
    out = []
    for s in doc.sentences:
        if not s.tagged:
            continue
        for p, particle in enumerate(s.tokens):
            verb = particle.head
            if particle.dep != "prt" or verb < 0 or verb == p:
                continue
            v = s.tokens[verb]
            # A technical noun such as "log" does not permit the verb "log in".
            if v.pos != "VERB" or v.lower in verbs or match_phrasal(s, verb, opts):
                continue
            first, last = min(verb, p), max(verb, p)
            phrase = span(s, first, last)
            if opts.allowed(phrase):
                continue
            key = (_base(v), particle.lower)
            if key in _STATE_PARTICLES:
                continue
            listed = key in _PHRASAL_SUGGESTIONS
            name = f"{key[0]} {key[1]}"
            out.append(
                Diagnostic(
                    "STE-9.3",
                    f'"{phrase}" is a phrasal verb ("{name}"). '
                    "ASD-STE100 does not approve phrasal verbs.",
                    "warning",
                    PHRASAL_LIST_CONFIDENCE if listed else PHRASAL_OTHER_CONFIDENCE,
                    s.tokens[first].start,
                    s.tokens[last].end,
                    _PHRASAL_SUGGESTIONS.get(key, "Write one verb that has the same meaning."),
                )
            )
    return out
