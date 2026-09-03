---
title: Coverage
description: Each of the 53 rules of ASD-STE100, and how this tool covers it: a check, a check that is possible, or a judgment that needs a reader.
---

# Coverage

[Back to the start page](index.md)

ASD-STE100 Issue 9 has 53 writing rules. This page gives each one and its
group. The tool must not claim 53 rules, because about 13 of them have no
mechanical answer.

| Group | Rules | Who checks it |
|---|---|---|
| **Built** | 20 | `ste lint` |
| **Possible with no new library** | 2 | `ste lint`, later |
| **Built, and they need the analyzer** | 4 of those 20 | `ste lint --analyze` |
| **Possible with a part-of-speech tagger** | 8 | an optional analyzer, later |
| **A judgment of a reader** | 13 | the [ste-review skill](https://github.com/TudorAndrei/ste-cli/tree/main/skill) |
| **Partial only** | 9 | both |

## Built

| Rule | Subject |
|---|---|
| 1.1 | An approved word |
| 1.14 | American spelling |
| 3.4 | A complex verb construction |
| 3.5 | The "-ing" form. The analyzer finds it in each position. |
| 3.6 | The passive voice |
| 3.7 | A noun for an action |
| 4.2 | A contraction (the other parts of the rule need a parser) |
| 5.1, 6.3 | The length of a sentence |
| 1.11 | Two names for the same item (the config gives the names) |
| 2.1 | A noun of more than three words (needs the analyzer) |
| 4.3 | A list with two constructions |
| 5.3 | An instruction that is not a command (needs the analyzer) |
| 5.4 | A condition after the command |
| 5.5 | An instruction in a note |
| 6.6 | 6 sentences in a paragraph |
| 7.3 | A safety instruction with no explanation |
| 8.1 | The semicolon |
| 8.4 | A colon ends a sentence in a vertical list |
| 8.5, 8.7 | The count of words |
| 9.3 | A phrasal verb |

## Possible with no new library

Each of these needs the structure of the Markdown, which the parser gives
already.

| Rule | Subject | What it needs |
|---|---|---|
| 1.9 | A short technical noun | A limit for the length, which the standard does not give |
| 7.1 | The word that identifies a risk | A test that a block is a safety instruction |

## Possible with a part-of-speech tagger

| Rule | Subject |
|---|---|
| 1.2 | The approved part of speech |
| 1.7, 1.13 | A technical noun as a verb, and a technical verb as a noun |
| 4.2 | An omitted word |
| 5.2 | One instruction in each sentence |
| 7.2 | A command or a condition at the start |
| 8.2 | A hyphen in a compound adjective |
| 8.6 | A multi-word name that counts as one word |

The `--analyze` flag gives this group a path. An external program gives the
grammar of a sentence, and 4 rules use it:

| Rule | What the grammar gives |
|---|---|
| 2.1 | The words of a noun cluster |
| 3.5 | An "-ing" word that is a verb, and not a noun or a modifier |
| 3.6 | A veto: a finding goes when the parser sees no passive relation |
| 5.3 | The part of speech of the first word of a step |

On a repository of 180 files, the analyzer removed 26 wrong findings for
rule 3.6, and the other 3 rules gave 502 more findings. The run went from
0.11s to 14.9s, because each sentence goes to the model.
Refer to [the analyzer](analyzer.md).

Each rule of this group can use the same path. A rule must also work without
the analyzer, because the command must stay one binary with no runtime.

## A judgment of a reader

No parser gives an answer for these rules. They need a reader who
understands the text.

| Rule | Subject |
|---|---|
| 1.3 | The approved meaning of a word |
| 1.5, 1.12 | The category of a technical noun or verb |
| 1.10 | Slang and jargon |
| 2.2 | The full form of a long technical noun |
| 4.4 | Connecting words |
| 4.5 | Articles and demonstrative adjectives |
| 6.1 | Information in a gradual order |
| 6.2 | Key words for a logical structure |
| 6.5 | One topic for each paragraph |
| 9.1 | A different sentence construction |
| 9.2 | Each approved word in its correct place |
| 9.4 | A consistent style |

The
[ste-review skill](https://github.com/TudorAndrei/ste-cli/tree/main/skill)
gives these rules to an agent. The skill states that each finding is advice,
and not a defect, because no test of this group gives the same answer each
time.

## Why the tool does not try each rule

A tool that reports a judgment as a defect makes each finding less
believable, and a person then reads none of them. The command reports only
what it can prove, the skill gives advice and says that it is advice, and
the reader keeps the decision.
