---
title: Rules
description: The 8 rules, their confidence values, and their limits.
---

# Rules

[Back to the start page](index.md)

This tool has 8 rules. It does not have the 53 rules of ASD-STE100.

The identifiers follow the section numbers of ASD-STE100 approximately. They
are stable identifiers for this tool. They are not a statement of certified
compliance. See "Limits" at the end of this page.

## Summary

| Rule | Name | Mode | Confidence | Severity (flavored) |
|---|---|---|---|---|
| `STE-1.1` | Unapproved word or word group | all | 0.90 | warning |
| `STE-1.4` | Phrasal verb | all | 0.85 | warning |
| `STE-3.1` | Perfect tense | all | 0.90, or 0.55 | warning |
| `STE-3.2` | Passive voice | all | 0.95, 0.85, or 0.70 | warning |
| `STE-3.5` | Progressive "-ing" form | all | 0.90 | warning |
| `STE-4.2` | Contraction | all | 0.98 | warning |
| `STE-5.1` | Sentence too long | all | 1.00 | warning |
| `STE-8.1` | Semicolon | all | 1.00 | warning |

In `flavored` mode, the tool removes each finding with a confidence of less
than 0.60. In `strict` mode, it keeps all findings and it makes each
severity one step stronger: `info` becomes `warning`, and `warning` becomes
`error`.

## STE-1.1 Unapproved word or word group

Reports 27 words and 11 word groups that have a shorter replacement, for
example "utilize" and "in order to".

**Limits.** The list is written by hand. It is not the ASD-STE100
approved-word dictionary, and this tool cannot tell you if a word is in that
dictionary. See [upstream-audit.md](upstream-audit.md).

**Control.** `allow.nouns` and `allow.verbs` in the glossary remove a term
from this rule.

## STE-1.4 Phrasal verb

Reports 24 phrasal verbs in all their forms: the base form, the third-person
form, the past form, and the "-ing" form. Example: "carry out", "carries
out", "carried out", "carrying out".

**Limits.**

- The verb and its particle must touch. The tool does not find a separated
  form, such as "turn the pump on".
- The list is short on purpose. Each entry must be a phrasal verb in almost
  all contexts.

## STE-3.1 Perfect tense

Reports "has", "have", or "had", and then a past participle. An adverb or
"not" can come between the two words. Example: "has been sent", "had gone",
"have not written".

**Limits.**

- "have to" is an obligation. The tool does not report it.
- "has been" and then a word that is not a participle gets a confidence of
  0.55. Only `strict` mode shows it.

## STE-3.2 Passive voice

Reports a form of "to be" and then a past participle.

| Condition | Confidence |
|---|---|
| A "by" agent follows, as in "was sent by the parser" | 0.95 |
| The participle is irregular, as in "was sent" | 0.85 |
| The participle ends with "ed", as in "was approved" | 0.70 |

**Limits.**

- Grammar alone cannot separate a passive verb from an adjective. The tool
  has a list of 36 participles that are usually adjectives, such as
  "configured", "enabled", and "closed". It does not report them, but it
  does report them when a "by" agent follows.
- A hyphenated form, such as "MIT-licensed", is an adjective for this tool.
- When the same words also give a perfect-tense finding, and no "by" agent
  follows, the tool removes the passive finding. One message for one problem
  is enough.

## STE-3.5 Progressive "-ing" form

Reports a form of "to be" and then a verb that ends with "-ing". An adverb
or "not" can come between the two words. Example: "is running", "is still
running", "was not reading".

**Limits.** The tool has a list of "-ing" words that are adjectives or
nouns, such as "missing", "existing", and "nothing". It does not report
them. A determiner between the two words, as in "is a warning", stops the
rule.

## STE-4.2 Contraction

Reports "n't", "'re", "'ve", "'ll", "'m", "'d", and the known "'s" forms,
such as "it's" and "let's".

**Limits.** The tool does not report a possessive form, such as "the
parser's output". ASD-STE100 also has limits on the possessive form. This
tool does not check that.

## STE-5.1 Sentence too long

Reports a sentence with more words than the limit. The limit is 25 words in
`flavored` mode and 20 words in `strict` mode. `max_words` in the glossary,
or `--max-words`, replaces the limit.

**Limits.** ASD-STE100 gives 20 words for a procedural sentence and 25 words
for a descriptive sentence. This tool does not know which sentence is a
procedure, thus the mode makes the decision.

## STE-8.1 Semicolon

Reports each semicolon in prose. ASD-STE100 permits the comma, the period,
the colon, the hyphen, the parentheses, and the slash.

**Limits.** The tool does not report a semicolon in code, in inline code, in
a link target, or in an HTML entity such as `&nbsp;`.

## What the tool does not examine

The tool replaces these spans with spaces before it applies the rules:

- fenced code blocks (``` and ~~~)
- indented code blocks (4 or more spaces after an empty line)
- inline code
- link targets, autolinks, and bare URLs

Each cell of a table row is a different sentence. A heading, a list item, and
an empty line are sentence boundaries.

## Limits of the tool

- The tool has no part-of-speech tagger. It uses word lists and short word
  sequences. Thus it cannot find all violations, and some findings are
  wrong.
- The tool does not have the ASD-STE100 dictionary. It cannot tell you if
  the standard approves a word.
- The tool is an aid for a writer. **It is not an ASD-certified checker**,
  and it cannot give certification.
