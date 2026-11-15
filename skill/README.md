# The ste-review skill

ASD-STE100 has 53 writing rules. The `ste` command checks 39 of them, 10 in
full and 29 in part. These rules have a mechanical answer: a count, a word list,
a sequence of tokens, or the grammar that the optional analyzer gives. The other rules need a reader who understands the text.
"Make sure that each paragraph has only one topic" is an example.

This directory holds a skill for an agent. It covers the other 14 rules,
and the part of a checked rule that needs a reader. The
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

`ste review docs/` prints the same request as an instruction for an agent.
The command reads no file and sends nothing.

## The division of the work

| Group | Rules | Who |
|---|---|---|
| Built, the full rule | 10 | `ste lint` |
| Built, a part of the rule | 29 | `ste lint`, and this skill for the other part |
| A judgment of a reader | 14 | this skill |

The skill must not repeat the work of the command, and it must not disagree
with it. `docs/coverage.md` gives each rule and its group.
