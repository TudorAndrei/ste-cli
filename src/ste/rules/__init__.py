# Copyright (c) 2026 Tudor Andrei Dumitrascu
"""ASD-STE100 checks in their established execution order."""

from collections.abc import Callable

from ste.models import Diagnostic, Document, Options
from ste.rules.structure import (
    condition_order,
    note_instruction,
    paragraph_length,
    safety_instruction,
    safety_word,
    vertical_list,
)
from ste.rules.surface import contractions, semicolons, sentence_length
from ste.rules.syntax import gerund, imperative, noun_cluster
from ste.rules.verbs import verbs
from ste.rules.words import (
    latin_abbreviations,
    nominalizations,
    one_name,
    short_noun,
    spelling,
    terms,
)

Rule = Callable[[Document, Options], list[Diagnostic]]


def all_rules() -> list[Rule]:
    """Return the rules in their established execution order."""
    return [
        sentence_length,
        semicolons,
        contractions,
        verbs,
        terms,
        spelling,
        nominalizations,
        latin_abbreviations,
        paragraph_length,
        note_instruction,
        safety_instruction,
        safety_word,
        vertical_list,
        condition_order,
        one_name,
        short_noun,
        imperative,
        noun_cluster,
        gerund,
    ]
