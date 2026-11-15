# Copyright (c) 2026 Tudor Andrei Dumitrascu
"""An instruction for an agent: review the rules that need a reader.

The command reads no file and sends nothing. The agent does the review with
the ste-review skill.
"""

from __future__ import annotations

SKILL = "ste-review"
SKILL_SOURCE = "https://github.com/TudorAndrei/ste-cli/tree/main/skill/ste-review"


def instruction(paths: list[str]) -> str:
    """Give the instruction for an agent, for these paths."""
    targets = " ".join(paths)
    return (
        f"1. Run `ste lint --format json --summary {targets}`. "
        "That command checks the rules that a tool can check.\n"
        f"2. Start a subagent. Tell it to load the `{SKILL}` skill "
        f"and to review these paths: {targets}.\n"
        "3. If the skill is not installed, tell the subagent to read its SKILL.md. "
        f"It is at {SKILL_SOURCE}.\n"
        "4. Give the findings of the subagent to the user as advice, and not as defects.\n"
    )


def plan(paths: list[str]) -> dict[str, object]:
    """Give the instruction as data."""
    return {
        "action": "review",
        "skill": SKILL,
        "skill_source": SKILL_SOURCE,
        "paths": paths,
        "instruction": instruction(paths),
    }
