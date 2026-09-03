---
title: Rules
description: The 17 checks of the tool, with the Issue 9 rule number, the confidence value, and the known limits of each one.
---

# Rules

[Back to the start page](index.md)

This tool has 17 checks. ASD-STE100 Issue 9 has 53 rules and a dictionary of
approved words. The tool does not ship the dictionary. `ste dict import`
makes an index from your own copy of the specification, and `--use-dict`
then gives rule 1.1 the full word list.

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
| `STE-4.3` | A list with two constructions | 0.80 | info |
| `STE-5.5` | An instruction in a note | 0.80 | warning |
| `STE-6.6` | Paragraph too long | 1.00 | warning |
| `STE-7.3` | A safety instruction with no explanation | 0.70 | warning |
| `STE-5.4` | A condition after the command | 0.70 | info |
| `STE-1.11` | Two names for the same item | 0.95 | warning |

In `flavored` mode, the tool removes each finding with a confidence of less
than 0.60. In `strict` mode, it keeps all findings and it makes the severity
of a rule one step stronger. The mode does **not** change a word limit.

<!-- ste-disable -->

## STE-1.1 Unapproved word or word group

Reports 27 words and 11 word groups that have a shorter replacement, for
example "utilize" and "in order to".

**The full dictionary.** A person wrote the list of 38 terms by hand, and it
is not the approved-word dictionary. `ste dict import` reads your own copy
of the specification and writes an index. `--use-dict` then makes this rule
report each word that the dictionary does not approve, with the approved
alternatives of the entry. See [upstream-audit.md](upstream-audit.md) for
the reason that the tool cannot ship the data.

**Limits.** Rule 1.1 also has parts that need more than the word list: the
approved part of speech (rule 1.2) and the approved meaning (rule 1.3). This
tool checks neither. With `--use-dict`, the rule uses a determiner to see
that a word is a noun, and it does not use a part-of-speech tagger.

**Control.** `allow.nouns` and `allow.verbs` in the glossary remove a term
from this rule. Rule 1.8 tells writers to use the technical nouns of their
company or industry. A project glossary agrees with the standard.

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
  as an adjective. This tool has no dictionary. It uses a list of 35
  participles that are usually adjectives, such as "configured" and
  "enabled". It does not report them, but it does report them when a "by"
  agent follows. The "by" test is the test that the standard itself gives.
- The tool does not find a passive sentence with no agent when the
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

The tool has no part-of-speech tagger. It uses the structure of the
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

**A colon in a vertical list (rule 8.4).** In a vertical list, a colon has
the same effect as a period: it ends the sentence, and the count starts
again. The item "The flag: it starts the pump" is two sentences. A colon
with no space after it is not a mark of punctuation, and "12:30" stays one
word. The colon of a label keeps its sentence, thus "**NOTE:** The pump
needs pressure" is one sentence.

**Limits.** Rule 8.6 also makes a multi-word title, a multi-word proper
noun, and a multi-word alphanumeric identifier one word. The tool cannot
find these without a dictionary, and it counts each of their words. The
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
  combinations. A hand-written list is the only method.

## STE-GR-6 Latin abbreviation

Reports "e.g.", "i.e.", "etc.", and 5 more Latin abbreviations. GR-6 is a
general recommendation. The severity is `info`, and no mode and no flag
makes it an error.

**Limits.** A Latin abbreviation is lower-case and it ends with a period.
The tool obeys both conditions. It does not report the name "VS Code", and
it does not report "vs" as a column title. Before version 0.5.0, the
name "VS Code" gave 147 wrong findings in one repository.

## STE-4.3 A list with two constructions

Reports an item of a vertical list that does not agree with the other items.
The test is the first letter: a list that starts some items with a capital
letter and other items with a small letter mixes two constructions. Rule 4.3
tells you to keep one construction for each list.

**Limits.**

- The rule reads one list at a time. Two lists that are separated by a
  paragraph do not join, and they can disagree with each other.
- An item of less than three words is not a sentence, and the rule ignores
  it. "go" and "stop" are examples.
- The rule ignores an item that starts with code, a link, or an image. The
  parser replaced that part with spaces, and the first letter of the prose
  is not the first letter of the item.
- The first letter is a weak proof of the construction. The rule cannot see
  that one item is a command and another item is a noun phrase. The severity
  is `info` for this reason.
- An early version reported each item of each list that did not agree with
  the first item. It gave 174 findings on one repository. The rule now
  reports only the items that are in the minority of their own list, which
  gave 10.

## STE-5.5 An instruction in a note

Reports a note that tells the reader to do something. Rule 5.5 makes a note
give information only. An instruction belongs to a step of the procedure,
where the reader can find it in the correct order.

The rule reads `**NOTE:**`, `NOTE:`, and the GitHub form `> [!NOTE]`. A
sentence is an instruction when it has one of these 5 words: "must",
"shall", "always", "never", and "do" with "not" after it.

**Limits.**

- The list of 5 words is the whole test. A command with none of them, such
  as "Disconnect the power", stays hidden.
- A warning, a caution, and a danger block can hold an instruction, and the
  rule does not read them. Rule 7.3 reads those.

## STE-6.6 Paragraph too long

Reports a paragraph of more than 6 sentences. Rule 6.6 gives that limit for
descriptive text. The confidence is 1.00, because the count is a count.

**Limits.** A vertical list is not a paragraph, and the rule does not count
its items. Two paragraphs of 4 sentences are two paragraphs, and not one
paragraph of 8.

## STE-1.11 Two names for the same item

Reports a name that the project replaced with a different name for the same
item. Rule 1.11 tells you to select one technical noun and to use it in each
place, so the reader does not ask if two names are two items.

The rule reports nothing until the config gives the names. No tool can know
that "the config file" and "the settings file" are the same item, and only
the project can say so:

```yaml
prefer:
  "config file": ["settings file", "configuration file"]
  actuator: ["servo control unit", "control unit"]
```

The key is the name to use, and the list holds the other names. A name can
have more than one word, and the letter case does not matter.

**Limits.** The rule reads the config and nothing more. A project that gives
no `prefer` key gets no finding from this rule. The rule cannot see that two
names mean the same item in a text that the config does not describe.

## STE-5.4 A condition after the command

Reports an instruction that gives its condition after the command. Rule 5.4
tells you to write the condition first, then a comma, then the command, so
the reader knows the condition before they start the work.

"Set the switch to NORMAL when the light comes on" gives a finding. "When
the light comes on, set the switch to NORMAL" gives none.

**Limits.**

- The rule reads a numbered step only. A tool cannot see that a sentence of
  descriptive text is an instruction.
- A condition that follows an infinitive belongs to the infinitive, and the
  rule does not report it. "Use the flag to stop when you have enough" does
  not become "When you have enough, use the flag". The test is the word
  before the condition: a word in small letters after "to" is a verb, and a
  word in capital letters is a value.
- "Check if the valve is open" gives no finding. A verb such as "check" or
  "verify" takes the clause as its object, and not as a condition.
- The rule reads 3 words: "when", "if", and "unless". "while", "before",
  "after", and "until" give a time and not a condition. On a repository of
  180 files, each of those 4 words gave a wrong finding: "while keeping the
  rules unchanged" is a gerund, and "while exact lookup keeps the string" is
  a contrast. The 3 words that stay gave 4 findings on that repository, and
  a person confirmed each one.
- The condition must hold a verb of its own.
- The severity is `info`, because the tool has no parser and the test is the
  position of a word.

## STE-7.3 A safety instruction with no explanation

Reports a warning, a caution, or a danger block that gives no reason. Rule
7.3 tells you to give the risk, so the reader knows what happens when they
do not obey. The rule reports a block of one sentence that has 12 words or
less. A second sentence, or a longer first one, is the explanation.

**Limits.** The rule counts sentences and words. It cannot read the sentence
to see that it truly gives a risk, and a long instruction with no reason
gives no finding. A note and a tip are not safety instructions, and the rule
ignores them.

<!-- ste-enable -->

## What the tool does not examine

A CommonMark parser reads the document, and the tool keeps only the prose.
Thus no rule sees:

- the front matter at the top of a file, between "---" or "+++" fences.
  Front matter is data for a tool, and it is not prose.
- a fenced code block or an indented code block
- inline code
- the target of a link, an autolink, or an image
- an HTML block or an HTML tag
- the markers of a heading, a list, a quotation, or a table

A heading, an empty line, and the start of a list item are sentence
boundaries. A list item keeps the lines that continue it. Each cell of a
table row is a different sentence. This is a decision of this tool, and not
a rule of the standard.

When you give a directory, the tool does not read a file that git ignores.
It asks git for the list, and the full syntax of `.gitignore` applies. It
also does not go into a directory that holds build output or dependencies:
`node_modules`, `vendor`, `dist`, `build`, `target`, `bin`, `obj`, `out`,
`coverage`, `__pycache__`, and each directory whose name starts with a
period.

The tool always reads a file or a directory that you give by its path. The
`--all` flag removes both filters.

## How to silence a finding

No rule set is correct for every sentence. A wrong finding must not stop the
work. The tool gives four methods:

| Method | Use it for |
|---|---|
| `<!-- ste-disable-next-line -->` in the text | one sentence |
| `rules: {STE-3.6: off}` in the config | one rule, for the project |
| `exclude:` in the config | a directory or a file type |
| `ste baseline .` | each finding that exists today |

The [start page](index.md) gives the full config and the other directives.

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
| 4.5 | Articles and demonstrative adjectives | The exceptions of the standard make a check too noisy |
| 5.2 | One instruction for each sentence | Cannot separate simultaneous actions |
| 5.3 | The imperative form | Needs a verb list |
| 6.1, 6.2, 6.5 | Key words, one topic for each paragraph | Needs semantics |
| 7.1, 7.2 | The words and the order of a safety instruction | Needs the risk level of the subject field |
| 9.1, 9.2, 9.4 | Consistent style | Needs semantics |

## Limits of the tool

- The tool has no part-of-speech tagger. It uses word lists and short word
  sequences. Thus it does not find all violations, and some findings are
  wrong.
- The tool does not have the ASD-STE100 dictionary. It cannot tell you if
  the standard approves a word.
- The tool is an aid for a writer. **It is not an ASD-certified checker**,
  and it cannot give certification.
