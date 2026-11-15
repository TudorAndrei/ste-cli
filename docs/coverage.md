---
title: Coverage
description: Each of the 53 rules of ASD-STE100, and how this tool covers it: a full check, a check of one part, a check that needs a part-of-speech tagger, or a judgment that needs a reader.
---

# Coverage

[Back to the start page](index.md)

ASD-STE100 Issue 9 has 53 writing rules. This page gives each one and its
group. Each rule is in one group only, and the groups add up to 53.

| Group | Rules | Who checks it |
|---|---|---|
| Built, the full rule | 9 | `ste lint` |
| Built, a part of the rule | 21 | `ste lint`, and a reader for the other part |
| Not built, possible with a part-of-speech tagger | 9 | an optional analyzer, later |
| Not built, a judgment of a reader | 14 | the [ste-review skill](https://github.com/TudorAndrei/ste-cli/tree/main/skill), or the optional [`ste review`](review.md) |
| Total | 53 | |

## A check and a rule are not the same

The tool has 21 checks, and each check has one identifier, such as
`STE-5.1`. `ste schema` gives the list. 20 checks have the number of a rule.
`STE-GR-6` is a general recommendation, and not one of the 53 rules.

One check can cover more than one rule. `STE-5.1` counts the words of a
sentence. Thus it applies rules 5.1 and 6.3, and the count obeys rules 8.4 to
8.7. The checks for rules 3.4, 3.5, and 3.6 together apply rule 3.2. Thus the
tool covers 30 rules with 20 identifiers. A rule with no identifier of its
own appears in the column "Check" with the identifier that covers it.

## Built, the full rule

The check covers each part of the rule. A check can still give a wrong
finding, and [rules.md](rules.md) gives the limits of each one.

| Rule | Subject | Check |
|---|---|---|
| 2.1 | A noun of more than three words | `STE-2.1`, with the analyzer |
| 3.5 | The "-ing" form | `STE-3.5`. Each position needs the analyzer. |
| 5.1 | 20 words in an instruction | `STE-5.1` |
| 6.3 | 25 words in a descriptive sentence | `STE-5.1` |
| 6.6 | 6 sentences in a paragraph | `STE-6.6` |
| 8.1 | The semicolon | `STE-8.1` |
| 8.4 | A colon ends a sentence in a vertical list | `STE-5.1` |
| 8.5 | Text in parentheses is one word, and also a sentence of its own | `STE-5.1` |
| 8.7 | A hyphenated word is one word | `STE-5.1` |

## Built, a part of the rule

The column "Missing" gives the part that the tool does not check. The
column "Needs" gives what that part needs:

- **Tagger**: a part-of-speech tagger or a parser. The optional analyzer can
  supply it.
- **Reader**: a judgment of a reader. No program gives the same answer each
  time.

| Rule | Subject | What the tool checks | Missing | Needs |
|---|---|---|---|---|
| 1.1 | An approved word | 38 terms. With `--use-dict`, each word of the dictionary. | Is a word that the dictionary does not give a technical noun or a technical verb? | Reader |
| 1.6 | An unapproved word as a technical noun | With `--use-dict`, `STE-1.1` says when the dictionary permits a word as a technical noun. `allow.nouns` permits a word. | Is the word a noun in this sentence, and does it have a category? | Tagger, reader |
| 1.8 | The technical nouns of the company | `STE-1.11` reports a different name that `prefer` gives. | A name that the config does not give | Reader |
| 1.9 | A short technical noun | `STE-1.9` reports a technical noun of the config that is longer than `max_noun_words`. | Is the noun easy to understand? | Reader |
| 1.11 | Two names for the same item | `STE-1.11` reads `prefer`. | Two names that the config does not give | Reader |
| 1.14 | American spelling | `STE-1.14` reports 54 British spellings. | A spelling that changes with the part of speech, such as "licence" | Tagger |
| 3.2 | The permitted verb forms and tenses | `STE-3.4`, `STE-3.5`, and `STE-3.6` | A different form, such as "would" with a verb | Tagger |
| 3.4 | No auxiliary verb for a complex construction | `STE-3.4` reports "have" and a participle. `STE-3.6` reports `can be adjusted`. | A participle that the tool reads as an adjective, as in "is to be installed" | Tagger |
| 3.6 | The active voice | `STE-3.6` reports each passive verb. | The standard permits the passive in descriptive text when the agent is not known. | Reader |
| 3.7 | A verb for an action | `STE-3.7` reports 17 word groups. | A different noun for an action | Tagger |
| 4.1 | Short and clear sentences | `STE-5.1` measures the length. | Is the sentence clear? | Reader |
| 4.2 | No omitted word, and no contraction | `STE-4.2` reports a contraction. | An omitted noun, verb, or article | Tagger |
| 4.3 | A vertical list for complex text | `STE-4.3` reports a list that starts its items in two ways. | Does the text need a list? Is each item the same construction? | Reader, tagger |
| 5.3 | An instruction is a command | `STE-5.3` reads a numbered step, with the analyzer. | An instruction that is not in a numbered list | Reader |
| 5.4 | The condition first | `STE-5.4` reads "when", "if", and "unless" in a numbered step. | A condition with a different word or in different text | Tagger |
| 5.5 | A note gives information only | `STE-5.5` reads 5 words, such as "must". | A command with none of those words | Tagger |
| 7.1 | A word for the level of the risk | `STE-7.1` reports a risk under a note label, and a risk to a person under a caution label. | Does a warning tell of a risk to a person? A risk with no label | Reader |
| 7.3 | An explanation of the risk | `STE-7.3` reports a short block of one sentence. | Does the text give a risk? | Reader |
| 8.6 | Elements that count as one word | A number, a quantity and its unit, quoted text, and the number of a step | A title, a name, or an identifier of many words | Tagger |
| 9.3 | A phrasal verb | `STE-9.3` reports 24 phrasal verbs. | A verb and its particle with words between them, and a verb that is not in the list | Tagger |
| 9.4 | A consistent style | `STE-1.11` reads `prefer`. | Wording that the config does not give | Reader |

## Not built, possible with a part-of-speech tagger

| Rule | Subject |
|---|---|
| 1.2 | The approved part of speech |
| 1.4 | The approved forms of a verb and an adjective. It also needs the forms of the dictionary. |
| 1.7 | A technical noun as a verb |
| 1.13 | A technical verb as a noun |
| 3.1 | The verb forms of the dictionary. It also needs the forms of the dictionary. |
| 3.3 | A past participle as an adjective |
| 5.2 | One instruction in each sentence |
| 7.2 | A command or a condition at the start of a safety instruction |
| 8.2 | A hyphen between words that are directly related |

With the `--analyze` flag, an external program gives the grammar of a
sentence. 4 rules use it today:

| Rule | What the grammar gives |
|---|---|
| 2.1 | The words of a noun cluster |
| 3.5 | An "-ing" word that is a verb, and not a noun or a modifier |
| 3.6 | A veto. A finding goes when the parser sees no passive relation. |
| 5.3 | The part of speech of the first word of a step |

On a repository of 180 files, the analyzer removed 26 wrong findings for
rule 3.6, and the other 3 rules gave 502 more findings. The run went from
0.11s to 14.9s, because each sentence goes to the model.
Refer to [the analyzer](analyzer.md).

Each rule of this group can use the analyzer in the same way. The basic
checks work without a model. Rules 2.1 and 5.3 give no finding without the
analyzer.

## Not built, a judgment of a reader

No parser gives an answer for these rules. They need a reader who
understands the text.

| Rule | Subject |
|---|---|
| 1.3 | The approved meaning of a word |
| 1.5 | The category of a technical noun |
| 1.10 | Slang and jargon |
| 1.12 | The category of a technical verb |
| 2.2 | The full form of a long technical noun |
| 4.4 | Connecting words |
| 4.5 | Articles and demonstrative adjectives |
| 6.1 | Information in a gradual order |
| 6.2 | Key words for a logical structure |
| 6.4 | Paragraphs for related information |
| 6.5 | One topic for each paragraph |
| 8.3 | The permitted uses of parentheses |
| 9.1 | A different sentence construction |
| 9.2 | Each approved word in its correct place |

The
[ste-review skill](https://github.com/TudorAndrei/ste-cli/tree/main/skill)
gives these rules to an agent. The skill states that each finding is advice,
and not a defect, because no test of this group gives the same answer each
time.

The optional [`ste review`](review.md) command sends each paragraph to a
language model with these rules. Each finding has the `info` severity and
the `advice` kind. The advice is not reproducible, and it never changes the
exit code of `ste lint` or the baseline.

## Why the tool does not try each rule

A tool that reports a judgment as a defect makes each finding less
believable, and a person then reads none of them. The command reports only
what it can prove, the skill gives advice and says that it is advice, and
the reader keeps the decision.
