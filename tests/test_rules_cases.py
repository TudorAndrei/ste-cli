# Copyright (c) 2026 Tudor Andrei Dumitrascu
"""Rule cases retained from the Go test suite."""

from __future__ import annotations

from typing import TypedDict


class VerbFinding(TypedDict):
    """An independently specified rule and text span."""

    rule_id: str
    text: str


class VerbCase(TypedDict):
    """A source sentence and its independently specified findings."""

    name: str
    text: str
    expect: list[VerbFinding]


STRUCTURE_CASES = [
    (
        "the condition comes after the command",
        "STE-5.4",
        "1. Set the switch to NORMAL when the light comes on.\n",
        1,
        False,
    ),
    (
        "the condition comes first",
        "STE-5.4",
        "1. When the light comes on, set the switch to NORMAL.\n",
        0,
        False,
    ),
    (
        'an "if" condition after the command',
        "STE-5.4",
        "1. Disconnect the drive from the gearbox if it does not operate correctly.\n",
        1,
        False,
    ),
    (
        'an "if" condition first',
        "STE-5.4",
        "1. If the drive does not operate correctly, disconnect it from the gearbox.\n",
        0,
        False,
    ),
    ('a clause verb takes the "if"', "STE-5.4", "1. Check if the valve is open.\n", 0, False),
    (
        "a clause verb with more words",
        "STE-5.4",
        "1. Verify if the pressure of the tank is correct.\n",
        0,
        False,
    ),
    ("a time phrase and no clause", "STE-5.4", "1. Close the valve after the test.\n", 0, False),
    (
        '"while" with a gerund',
        "STE-5.4",
        "1. Read the report while investigating one failure of the run.\n",
        0,
        False,
    ),
    (
        '"while" with a contrast',
        "STE-5.4",
        "1. Use the prefix match while exact lookup keeps the raw string.\n",
        0,
        False,
    ),
    (
        '"unless" is a condition',
        "STE-5.4",
        "1. Copy the assets of the module unless the generator includes them.\n",
        1,
        False,
    ),
    (
        "descriptive text keeps its order",
        "STE-5.4",
        "The tool writes the report when the run is complete.\n",
        0,
        False,
    ),
    (
        "a note keeps its order",
        "STE-5.4",
        "1. **NOTE:** The tool writes the report when the run is complete.\n",
        0,
        False,
    ),
    ("a short first phrase", "STE-5.4", "1. Start if the light is on.\n", 0, False),
    (
        "an infinitive takes the condition",
        "STE-5.4",
        "1. Use the flag to read the report and to stop when you have enough.\n",
        0,
        False,
    ),
    (
        "a value in capital letters is not an infinitive",
        "STE-5.4",
        "1. Set the switch to NORMAL when the light comes on.\n",
        1,
        False,
    ),
    (
        "a note with an instruction",
        "STE-5.5",
        "**NOTE:** You must disconnect the power.\n",
        1,
        False,
    ),
    ("a note with information", "STE-5.5", "**NOTE:** The capacitor keeps a charge.\n", 0, False),
    (
        "a note with a negative command",
        "STE-5.5",
        "**NOTE:** Do not touch the surface.\n",
        1,
        False,
    ),
    ("an instruction outside a note", "STE-5.5", "You must disconnect the power.\n", 0, False),
    (
        "a warning can hold an instruction",
        "STE-5.5",
        "**WARNING:** You must disconnect the power. It holds a charge.\n",
        0,
        False,
    ),
    (
        "a warning with no explanation",
        "STE-7.3",
        "**WARNING:** Do not touch the surface.\n",
        1,
        False,
    ),
    (
        "a warning with an explanation",
        "STE-7.3",
        "**WARNING:** Do not touch the surface. The surface is hot and it can burn your skin.\n",
        0,
        False,
    ),
    ("a note is not a safety instruction", "STE-7.3", "**NOTE:** The surface is hot.\n", 0, False),
    ("a tip is not a safety instruction", "STE-7.3", "**TIP:** Use the other tool.\n", 0, False),
    (
        "a note that tells of damage",
        "STE-7.1",
        "**NOTE:** A high voltage can damage the unit.\n",
        "damage",
        False,
    ),
    (
        "an alert of GitHub",
        "STE-7.1",
        "> [!IMPORTANT]\n> This step can cause data loss.\n",
        "data",
        False,
    ),
    (
        "a tip that tells of an injury",
        "STE-7.1",
        "Tip: The blade can cause an injury.\n",
        "injury",
        False,
    ),
    (
        "one finding for each block",
        "STE-7.1",
        "**NOTE:** It can damage the unit. It can destroy the fuse.\n",
        "damage",
        False,
    ),
    ("a note with no risk", "STE-7.1", "**NOTE:** The capacitor keeps a charge.\n", "", False),
    (
        "a caution gives the level",
        "STE-7.1",
        "**CAUTION:** A high voltage can damage the unit.\n",
        "",
        False,
    ),
    (
        "a warning gives the level",
        "STE-7.1",
        "WARNING: The blade can cause an injury.\n",
        "",
        False,
    ),
    ("text outside a label", "STE-7.1", "A high voltage can damage the unit.\n", "", False),
    (
        "each item starts with a small letter",
        "STE-4.3",
        "- open the valve of the pump\n- start the pump of the system\n",
        0,
        False,
    ),
    (
        "each item starts with a capital letter",
        "STE-4.3",
        "- Open the valve of the pump\n- Start the pump of the system\n",
        0,
        False,
    ),
    (
        "one item of three is different",
        "STE-4.3",
        (
            "- Open the valve of the pump\n- Start the pump of the "
            "system\n- close the valve of the tank\n"
        ),
        1,
        False,
    ),
    ("a short item is not a sentence", "STE-4.3", "- go\n- stop\n", 0, False),
    ("a paragraph is not a list", "STE-4.3", "open the valve of the pump\n", 0, False),
    (
        "two lists do not join",
        "STE-4.3",
        (
            "- Open the valve of the pump\n\nSome text between them "
            "here.\n\n- close the valve of the tank\n"
        ),
        0,
        False,
    ),
    (
        "code between the two words",
        "STE-3.6",
        "The command is `scripts/release.sh`, exposed through the API.\n",
        0,
        False,
    ),
    (
        "a link between the two words",
        "STE-3.6",
        "The result is [the report](http://example.com), signed by the team.\n",
        0,
        False,
    ),
    ("nothing between the two words", "STE-3.6", "The report is signed by the team.\n", 1, False),
    (
        "an adverb between the two words",
        "STE-3.6",
        "The report is carefully signed by the team.\n",
        1,
        False,
    ),
    (
        "each item starts with a digit",
        "STE-4.3",
        "- 0.4.0 gives the new parser\n- 0.3.0 gives the first rules\n- fix the count of words\n",
        0,
        False,
    ),
    (
        "each item starts with a mark",
        "STE-4.3",
        "- (a) open the valve of the pump\n- (b) start the pump of the system\n",
        0,
        False,
    ),
    (
        "a digit item does not change the letter items",
        "STE-4.3",
        "- 3 of the tests are new\n- Open the valve of the pump\n- Start the pump of the system\n",
        0,
        False,
    ),
    ("the name to use gives no finding", "STE-1.11", "Open the config file.\n", 0, True),
    ("a second name for the same item", "STE-1.11", "Open the settings file.\n", 1, True),
    ("a third name for the same item", "STE-1.11", "Open the configuration file.\n", 1, True),
    (
        "two names in one document",
        "STE-1.11",
        "Open the settings file. Then read the configuration file.\n",
        2,
        True,
    ),
    ("a name of one word", "STE-1.11", "Start the frammis.\n", 1, True),
    ("the letter case does not matter", "STE-1.11", "Open the Settings File.\n", 1, True),
    ("a name that is not in the config", "STE-1.11", "Open the report file.\n", 0, True),
]

SYNTAX_CASES = [
    (
        "a command verb starts the step",
        "STE-5.3",
        "1. Open the valve.\n",
        {"Open the valve.": ["Open/VERB/VB/ROOT/0", "the/DET/DT/det/2", "valve/NOUN/NN/dobj/0"]},
        0,
    ),
    (
        "one description in a list of steps",
        "STE-5.3",
        "1. Open the valve.\n2. Start the pump.\n3. Installation of the pump is necessary.\n",
        {
            "Installation of the pump is necessary.": [
                "Installation/NOUN/NN/nsubj/4",
                "of/ADP/IN/prep/0",
                "the/DET/DT/det/3",
                "pump/NOUN/NN/pobj/1",
                "is/AUX/VBZ/ROOT/4",
                "necessary/ADJ/JJ/acomp/4",
            ],
            "Open the valve.": ["Open/VERB/VB/ROOT/0", "the/DET/DT/det/2", "valve/NOUN/NN/dobj/0"],
            "Start the pump.": ["Start/VERB/VB/ROOT/0", "the/DET/DT/det/2", "pump/NOUN/NN/dobj/0"],
        },
        1,
    ),
    (
        "a numbered list of requirements is not a procedure",
        "STE-5.3",
        "1. Installation of the pump is necessary.\n2. Removal of the valve is necessary.\n",
        {
            "Installation of the pump is necessary.": [
                "Installation/NOUN/NN/nsubj/4",
                "of/ADP/IN/prep/0",
                "the/DET/DT/det/3",
                "pump/NOUN/NN/pobj/1",
                "is/AUX/VBZ/ROOT/4",
                "necessary/ADJ/JJ/acomp/4",
            ],
            "Removal of the valve is necessary.": [
                "Removal/NOUN/NN/nsubj/4",
                "of/ADP/IN/prep/0",
                "the/DET/DT/det/3",
                "valve/NOUN/NN/pobj/1",
                "is/AUX/VBZ/ROOT/4",
                "necessary/ADJ/JJ/acomp/4",
            ],
        },
        0,
    ),
    (
        "one item alone gives no majority",
        "STE-5.3",
        "1. Installation of the pump is necessary.\n",
        {
            "Installation of the pump is necessary.": [
                "Installation/NOUN/NN/nsubj/4",
                "of/ADP/IN/prep/0",
                "the/DET/DT/det/3",
                "pump/NOUN/NN/pobj/1",
                "is/AUX/VBZ/ROOT/4",
                "necessary/ADJ/JJ/acomp/4",
            ]
        },
        0,
    ),
    (
        "a condition comes first, and the command follows",
        "STE-5.3",
        "1. When the light comes on, set the switch.\n",
        {
            "When the light comes on, set the switch.": [
                "When/SCONJ/WRB/advmod/3",
                "the/DET/DT/det/2",
                "light/NOUN/NN/nsubj/3",
                "comes/VERB/VBZ/advcl/5",
                "on/ADP/RP/prt/3",
                "set/VERB/VB/ROOT/5",
                "the/DET/DT/det/7",
                "switch/NOUN/NN/dobj/5",
            ]
        },
        0,
    ),
    (
        "descriptive text is not an instruction",
        "STE-5.3",
        "The operator opens the valve.\n",
        {
            "The operator opens the valve.": [
                "The/DET/DT/det/1",
                "operator/NOUN/NN/nsubj/2",
                "opens/VERB/VBZ/ROOT/2",
                "the/DET/DT/det/4",
                "valve/NOUN/NN/dobj/2",
            ]
        },
        0,
    ),
    (
        "no analyzer gives no finding",
        "STE-5.3",
        "1. Installation of the pump is necessary.\n",
        {},
        0,
    ),
    (
        "three words are inside the limit",
        "STE-2.1",
        "The pump control unit is on the left.\n",
        {
            "The pump control unit is on the left.": [
                "The/DET/DT/det/3",
                "pump/NOUN/NN/compound/3",
                "control/NOUN/NN/compound/3",
                "unit/NOUN/NN/nsubj/4",
                "is/AUX/VBZ/ROOT/4",
                "on/ADP/IN/prep/4",
                "the/DET/DT/det/7",
                "left/NOUN/NN/pobj/5",
            ]
        },
        0,
    ),
    (
        "five words are more than the limit",
        "STE-2.1",
        "The engine fuel pump control unit is here.\n",
        {
            "The engine fuel pump control unit is here.": [
                "The/DET/DT/det/5",
                "engine/NOUN/NN/compound/5",
                "fuel/NOUN/NN/compound/5",
                "pump/NOUN/NN/compound/5",
                "control/NOUN/NN/compound/5",
                "unit/NOUN/NN/nsubj/6",
                "is/AUX/VBZ/ROOT/6",
                "here/ADV/RB/advmod/6",
            ]
        },
        1,
    ),
    (
        "a name of many words is one unit",
        "STE-2.1",
        "The Aerospace Security Defence Industries Association is here.\n",
        {
            "The Aerospace Security Defence Industries Association is here.": [
                "The/DET/DT/det/5",
                "Aerospace/PROPN/NNP/compound/5",
                "Security/PROPN/NNP/compound/5",
                "Defence/PROPN/NNP/compound/5",
                "Industries/PROPN/NNP/compound/5",
                "Association/PROPN/NNP/nsubj/6",
                "is/AUX/VBZ/ROOT/6",
                "here/ADV/RB/advmod/6",
            ]
        },
        0,
    ),
    (
        'an "-ing" verb in a clause',
        "STE-3.5",
        "Before starting the pump, open the valve.\n",
        {
            "Before starting the pump, open the valve.": [
                "Before/ADP/IN/prep/1",
                "starting/VERB/VBG/pcomp/0",
                "the/DET/DT/det/3",
                "pump/NOUN/NN/dobj/1",
                "open/VERB/VB/ROOT/4",
                "the/DET/DT/det/6",
                "valve/NOUN/NN/dobj/4",
            ]
        },
        1,
    ),
    (
        'an "-ing" word that modifies a noun',
        "STE-3.5",
        "The operating manual is here.\n",
        {
            "The operating manual is here.": [
                "The/DET/DT/det/2",
                "operating/VERB/VBG/amod/2",
                "manual/NOUN/NN/nsubj/3",
                "is/AUX/VBZ/ROOT/3",
                "here/ADV/RB/advmod/3",
            ]
        },
        0,
    ),
    (
        "a progressive form belongs to the verb rule",
        "STE-3.5",
        "The pump is running.\n",
        {
            "The pump is running.": [
                "The/DET/DT/det/1",
                "pump/NOUN/NN/nsubj/3",
                "is/AUX/VBZ/aux/3",
                "running/VERB/VBG/ROOT/3",
            ]
        },
        1,
    ),
]

VERB_CASES: list[VerbCase] = [
    {
        "expect": [{"rule_id": "STE-3.4", "text": "has been sent"}],
        "name": "perfect/present-perfect-passive",
        "text": "The file has been sent to the server.",
    },
    {
        "expect": [{"rule_id": "STE-3.4", "text": "had gone"}],
        "name": "perfect/past-perfect",
        "text": "The task had gone to the queue.",
    },
    {
        "expect": [{"rule_id": "STE-3.4", "text": "have written"}],
        "name": "perfect/present-perfect",
        "text": "We have written the report.",
    },
    {"expect": [], "name": "perfect/have-to-is-not-perfect", "text": "You have to start the pump."},
    {
        "expect": [{"rule_id": "STE-3.5", "text": "is running"}],
        "name": "progressive/simple",
        "text": "The server is running.",
    },
    {
        "expect": [{"rule_id": "STE-3.5", "text": "is still running"}],
        "name": "progressive/with-adverb",
        "text": "The server is still running.",
    },
    {
        "expect": [{"rule_id": "STE-3.5", "text": "was not reading"}],
        "name": "progressive/negated",
        "text": "The parser was not reading the file.",
    },
    {"expect": [], "name": "progressive/noun-is-not-progressive", "text": "The result is nothing."},
    {
        "expect": [{"rule_id": "STE-3.6", "text": "was sent"}],
        "name": "passive/with-agent",
        "text": "The file was sent by the parser.",
    },
    {
        "expect": [
            {"rule_id": "STE-3.4", "text": "has been read"},
            {"rule_id": "STE-3.6", "text": "been read"},
        ],
        "name": "passive/perfect-with-agent",
        "text": "The file has been read by the parser.",
    },
    {
        "expect": [{"rule_id": "STE-3.6", "text": "was approved"}],
        "name": "passive/regular-participle",
        "text": "The report was approved.",
    },
    {"expect": [], "name": "adjectival/configured", "text": "The service is configured."},
    {"expect": [], "name": "adjectival/enabled", "text": "The webhook is enabled."},
    {"expect": [], "name": "adjectival/closed", "text": "The valve is closed."},
    {
        "expect": [{"rule_id": "STE-3.6", "text": "is closed"}],
        "name": "adjectival/agent-makes-it-passive",
        "text": "The valve is closed by the operator.",
    },
    {
        "expect": [{"rule_id": "STE-9.3", "text": "Carry out"}],
        "name": "phrasal/base-form",
        "text": "Carry out the test.",
    },
    {
        "expect": [{"rule_id": "STE-9.3", "text": "carries out"}],
        "name": "phrasal/third-person",
        "text": "The system carries out the test.",
    },
    {
        "expect": [{"rule_id": "STE-9.3", "text": "carried out"}],
        "name": "phrasal/past-form",
        "text": "The operator carried out the test.",
    },
    {
        "expect": [
            {"rule_id": "STE-3.5", "text": "is carrying"},
            {"rule_id": "STE-9.3", "text": "carrying out"},
        ],
        "name": "phrasal/ing-form",
        "text": "The operator is carrying out the test.",
    },
    {
        "expect": [{"rule_id": "STE-9.3", "text": "Get rid of"}],
        "name": "phrasal/two-word-particle",
        "text": "Get rid of the old file.",
    },
    {
        "expect": [{"rule_id": "STE-9.3", "text": "Shut down"}],
        "name": "phrasal/shut-down",
        "text": "Shut down the computer.",
    },
    {"expect": [], "name": "clean/imperative", "text": "Start the pump. Then open the valve."},
]
