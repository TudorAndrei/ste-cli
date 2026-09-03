# The ste-review skill

ASD-STE100 has 53 writing rules. The `ste` command can check about 31 of
them, because they have a mechanical answer: a count, a word list, or a
sequence of tokens. The other rules need a reader who understands the text.
"Make sure that each paragraph has only one topic" is an example.

This directory holds a skill for an agent. It covers the second group. The
command gives a number, and the agent gives a judgment.

## Installation

Copy or link the skill into the directory of your agent:

```bash
# For one project
mkdir -p .claude/skills
ln -s "$PWD/skill/ste-review" .claude/skills/ste-review

# For each project of this user
ln -s "$PWD/skill/ste-review" ~/.claude/skills/ste-review
```

Then ask for a review: "review docs/ for Simplified Technical English".

## The division of the work

| Group | Rules | Who |
|---|---|---|
| Mechanical, and built | 11 | `ste lint` |
| Mechanical, and not built | ~20 | `ste lint`, later |
| A judgment of a reader | ~13 | this skill |

The skill must not repeat the work of the command, and it must not disagree
with it. `docs/coverage.md` gives each rule and its group.
