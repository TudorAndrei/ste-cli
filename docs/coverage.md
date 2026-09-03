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
| **Built** | 11 | `ste lint` |
| **Possible with no new library** | 9 | `ste lint`, later |
| **Possible with a part-of-speech tagger** | 11 | an optional analyzer, later |
| **A judgment of a reader** | 13 | the [ste-review skill](https://github.com/TudorAndrei/ste-cli/tree/main/skill) |
| **Partial only** | 9 | both |

## Built

| Rule | Subject |
|---|---|
| 1.1 | An approved word |
| 1.14 | American spelling |
| 3.4 | A complex verb construction |
| 3.5 | The progressive "-ing" form (the part after "to be") |
| 3.6 | The passive voice |
| 3.7 | A noun for an action |
| 4.2 | A contraction (the other parts of the rule need a parser) |
| 5.1, 6.3 | The length of a sentence |
| 8.1 | The semicolon |
| 8.5, 8.7 | The count of words |
| 9.3 | A phrasal verb |

## Possible with no new library

Each of these needs the structure of the Markdown, which the parser gives
already.

| Rule | Subject | What it needs |
|---|---|---|
| 1.9, 1.11 | A short technical noun, one name for each thing | A check of the config |
| 4.3 | A vertical list | The list items of the parser |
| 5.4 | The condition before the instruction | A token test, as advice |
| 5.5 | A note gives information only | A "NOTE:" block and the word "must" |
| 6.6 | 6 sentences in a paragraph | A group of the sentences of a paragraph |
| 7.1, 7.3 | A safety instruction | An admonition block |
| 8.4 | A colon in a vertical list | A sentence boundary at a colon |

## Possible with a part-of-speech tagger

| Rule | Subject |
|---|---|
| 1.2 | The approved part of speech |
| 1.7, 1.13 | A technical noun as a verb, and a technical verb as a noun |
| 2.1 | A multi-word noun of more than 3 words |
| 3.5 | The other parts of the "-ing" rule |
| 4.2 | An omitted word |
| 5.2 | One instruction in each sentence |
| 5.3 | The imperative form |
| 7.2 | A command or a condition at the start |
| 8.2 | A hyphen in a compound adjective |
| 8.6 | A multi-word name that counts as one word |

The tool has no tagger today, and a measurement gave the reason to wait. On
8 sentences with a word that is a noun and a verb, spaCy gave 7 correct
answers and prose gave 4. The test of the noun phrase in this tool gave 7.
A tagger is thus not the largest gain, and it costs the speed and the one
binary. Refer to [evaluation.md](evaluation.md).

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
