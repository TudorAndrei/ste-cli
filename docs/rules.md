---
title: Rules
description: The 11 rules, their confidence values, and their limits.
---

# Rules

[Back to the start page](index.md)

This tool has 11 checks. ASD-STE100 Issue 9 has 53 rules and a dictionary of
approved words. This tool does not have the dictionary.

The rule numbers are the rule numbers of Issue 9. A check with the `GR`
prefix is a general recommendation of the standard. A general
recommendation is advice and not a rule. Thus this tool gives it the `info`
severity, and strict mode does not make it an error.

## Summary

| Rule | Name | Confidence | Severity (flavored) |
|---|---|---|---|
| `STE-1.1` | Unapproved word or word group | 0.90 | warning |
| `STE-1.14` | British spelling | 0.90 | warning |
| `STE-3.4` | Complex verb construction (perfect tense) | 0.90, or 0.55 | warning |
| `STE-3.5` | Progressive "-ing" form | 0.90 | warning |
| `STE-3.6` | Passive voice | 0.95, 0.85, or 0.70 | warning |
| `STE-3.7` | A noun for an action | 0.90 | warning |
| `STE-4.2` | Contraction | 0.98 | warning |
| `STE-5.1` | Sentence too long | 0.90 | warning |
| `STE-8.1` | Semicolon | 1.00 | warning |
| `STE-9.3` | Phrasal verb | 0.85 | warning |
| `STE-GR-6` | Latin abbreviation | 0.90 | info |

In `flavored` mode, the tool removes each finding with a confidence of less
than 0.60. In `strict` mode, it keeps all findings and it makes the severity
of a rule one step stronger. The mode does **not** change a word limit.

## STE-1.1 Unapproved word or word group

Reports 27 words and 11 word groups that have a shorter replacement, for
example "utilize" and "in order to".

**Limits.** A person wrote the list by hand. It is not the ASD-STE100
approved-word dictionary, and this tool cannot tell you if a word is in that
dictionary. Rule 1.1 also has parts that need the dictionary: the approved
part of speech (rule 1.2) and the approved meaning (rule 1.3). This tool
checks neither. See [upstream-audit.md](upstream-audit.md).

**Control.** `allow.nouns` and `allow.verbs` in the glossary remove a term
from this rule. Rule 1.8 tells writers to use the technical nouns of their
company or industry, thus a project glossary agrees with the standard.

## STE-1.14 British spelling

Reports 54 British spellings that have one American form, for example
"colour" and "centre". Rule 1.14 tells you to use American English spelling.

**Limits.**

- The list keeps out each pair that needs a part of speech. Three examples
  are "licence", "practise", and "programme".
- The tool does not report a capitalized word that does not start its
  sentence, because that word is usually a name. An example is "Defence" in
  the name of an organization. Thus the tool does not find a British
  spelling in a title with capital letters on each word.
- A different official directive can replace rule 1.14. Use `disable_rules`
  for that.

## STE-3.4 Complex verb construction

Reports "has", "have", or "had", and then a past participle. An adverb or
"not" can come between the two words. Example: "has been sent", "had gone".
Rule 3.4 does not permit an auxiliary verb that makes a complex construction.

**Limits.**

- "have to" is an obligation. The tool does not report it.
- "has been" and then a word that is not a participle gets a confidence of
  0.55. Only `strict` mode shows it.

## STE-3.5 Progressive "-ing" form

Reports a form of "to be" and then a verb that ends with "-ing". Example:
"is running", "is still running", "was not reading". Rule 3.5 permits the
"-ing" form only as a technical noun or as a modifier in a technical noun.

**Limits.** The tool has a list of "-ing" words that are adjectives or
nouns, such as "missing" and "existing". It does not report them. It does
not report "is being", because that is the passive voice and rule 3.6
reports it. The tool does not find the other parts of rule 3.5. An example
is an "-ing" clause at the start of a sentence, which needs a parser.

## STE-3.6 Passive voice

Reports a form of "to be" and then a past participle. Rule 3.6 tells you to
use the active voice. It permits the passive voice only in descriptive
writing, and only when the agent is unknown.

| Condition | Confidence |
|---|---|
| A "by" agent follows, as in "was sent by the parser" | 0.95 |
| The participle is irregular, as in "was sent" | 0.85 |
| The participle ends with "ed", as in "was approved" | 0.70 |

**Limits.**

- Rule 3.3 makes a past participle an adjective when the dictionary gives it
  as an adjective. This tool has no dictionary, thus it uses a list of 35
  participles that are usually adjectives, such as "configured" and
  "enabled". It does not report them, but it does report them when a "by"
  agent follows. The "by" test is the test that the standard itself gives.
- The tool thus does not find a passive sentence with no agent when the
  participle is in that list. This is a known miss.
- A hyphenated form, such as "MIT-licensed", is an adjective for this tool.
- When the same words also give an `STE-3.4` finding, and no "by" agent
  follows, the tool removes the passive finding. One message for one problem
  is enough.

## STE-3.7 A noun for an action

Reports 17 word groups that use a noun for an action, for example "do a
check of". Rule 3.7 tells you to use an approved verb.

**Limits.** The list is literal and narrow. The tool cannot find a
nominalization that is not in the list, because it cannot make a verb from a
noun without a dictionary.

## STE-4.2 Contraction

Reports "n't", "'re", "'ve", "'ll", "'m", "'d", and the known "'s" forms,
such as "it's".

**Limits.** Rule 4.2 also tells you not to omit a noun, a verb, a subject,
or an article. The tool checks **only** the contraction part. An omitted
word needs a parser. The tool does not report a possessive form, such as
"the parser's output".

## STE-5.1 Sentence too long

Reports a sentence that is longer than its limit. The standard selects the
limit from the type of the sentence, and **not** from the mode:

| Sentence | Limit | Rule |
|---|---|---|
| An instruction in a procedure | 20 words | 5.1 |
| A note | 25 words | 5.5 |
| Descriptive text | 25 words | 6.3 |

The tool has no part-of-speech tagger, thus it uses the structure of the
Markdown: **a numbered list item is an instruction in a procedure.** A
bulleted list is not, because a bulleted list is usually a list of items and
not a sequence of steps. A line that starts with "NOTE:" is a note, and it
keeps the longer limit. `max_words` or `--max-words` replaces both limits.

**How the tool counts a word.** Section 8 gives the count rules. The tool
obeys these:

| Element | Words |
|---|---|
| A hyphenated word (rule 8.7) | 1 |
| A quantity and its unit (rule 8.6) | 1 |
| A quoted string (rule 8.6) | 1 |
| Text in parentheses (rule 8.5) | 1 |
| The number of a step (rule 8.6) | 0 |

**Limits.** Rule 8.6 also makes a multi-word title, a multi-word proper
noun, and a multi-word alphanumeric identifier one word. The tool cannot
find these without a dictionary, thus it counts each of their words. The
count can therefore be too high for a sentence that has a long title or a
long name. Rule 8.5 also makes the text in parentheses a separate sentence
with its own limit. The tool does not check that sentence.

## STE-8.1 Semicolon

Reports each semicolon in prose. Rule 8.1 permits all the standard English
punctuation marks, but not the semicolon. It is a ban of one mark, and not a
list of permitted marks.

**Limits.** The tool does not report a semicolon in code, in inline code, in
a link target, or in an HTML entity such as `&nbsp;`.

## STE-9.3 Phrasal verb

Reports 24 phrasal verbs in all their forms: the base form, the third-person
form, the past form, and the "-ing" form. Example: "carry out", "carries
out", "carried out", "carrying out". Rule 9.3 tells you not to make a
phrasal verb from two words.

**Limits.**

- The verb and its particle must touch. The tool does not find a separated
  form, such as "turn the pump on".
- The list is short on purpose. The dictionary gives single words, not
  combinations, thus a hand-written list is the only method.

## STE-GR-6 Latin abbreviation

Reports "e.g.", "i.e.", "etc.", and 5 more Latin abbreviations. GR-6 is a general
recommendation, thus the severity is `info` and strict mode does not make it
an error.

## What the tool does not examine

The tool replaces these spans with spaces before it applies the rules:

- fenced code blocks (```` ``` ```` and `~~~`)
- indented code blocks (4 or more spaces after an empty line)
- inline code
- link targets, autolinks, and bare URLs

A heading, an empty line, and the start of a list item are sentence
boundaries. A list item keeps the lines that continue it. Each cell of a
table row is a different sentence. This is a decision of this tool, and not
a rule of the standard.

When you give a directory, the tool does not read a file that git ignores.
It asks git for the list, thus the full syntax of `.gitignore` applies. It
also does not go into a directory that holds build output or dependencies:
`node_modules`, `vendor`, `dist`, `build`, `target`, `bin`, `obj`, `out`,
`coverage`, `__pycache__`, and each directory whose name starts with a
period.

A file or a directory that you give by its path is always read. The `--all`
flag removes both filters.

## Rules that this tool does not check

An audit of Issue 9 found these rules to be not mechanically checkable
without a part-of-speech tagger, a parser, or the dictionary. The tool does
not try to check them, because a guess would only make noise:

| Rule | Subject | Why not |
|---|---|---|
| 1.2, 1.3 | Approved part of speech and meaning | Needs the dictionary |
| 1.5, 1.6, 1.8, 1.12 | Technical noun and verb categories | A judgment about the subject field |
| 1.9, 1.10 | Short, clear, no slang | A human judgment |
| 2.1, 2.2 | Multi-word nouns of 3 words maximum | Needs a part of speech to find where the noun starts |
| 3.1 | The verb forms of the dictionary | Needs the dictionary |
| 4.2 (part) | Omitted words | Needs a parser |
| 4.3 | Vertical list construction | Possible later. Not built |
| 4.5 | Articles and demonstrative adjectives | The exceptions of the standard make a check too noisy |
| 5.2 | One instruction for each sentence | Cannot separate simultaneous actions |
| 5.3 | The imperative form | Needs a verb list |
| 5.4 | The condition before the instruction | Possible later, as info. Not built |
| 6.1, 6.2, 6.5 | Key words, one topic for each paragraph | Needs semantics |
| 6.6 | 6 sentences maximum in a paragraph | Too many false reports in software documentation |
| 7.1, 7.2, 7.3 | Safety instructions | Possible later for admonition blocks. Not built |
| 9.1, 9.2, 9.4 | Consistent style | Needs semantics |

## Limits of the tool

- The tool has no part-of-speech tagger. It uses word lists and short word
  sequences. Thus it does not find all violations, and some findings are
  wrong.
- The tool does not have the ASD-STE100 dictionary. It cannot tell you if
  the standard approves a word.
- The tool is an aid for a writer. **It is not an ASD-certified checker**,
  and it cannot give certification.
