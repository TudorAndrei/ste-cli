---
title: Coverage
description: Each of the 53 rules of ASD-STE100, and how this tool covers it: a full check, a check of one part, or a judgment that needs a reader.
---

# Coverage

[Back to the start page](index.md)

ASD-STE100 Issue 9 has 53 writing rules. This page gives each one and its
group. Each rule is in one group only, and the groups add up to 53.

| Group | Rules | Who checks it |
|---|---|---|
| Built, the full rule | 10 | `ste lint` |
| Built, a part of the rule | 29 | `ste lint`, and a reader for the other part |
| Not built, a judgment of a reader | 14 | the [ste-review skill](https://github.com/TudorAndrei/ste-cli/tree/main/skill) |
| Total | 53 | |

Many checks need the optional analyzer of the grammar. The section
[The analyzer](#the-analyzer) gives the list.

## A check and a rule are not the same

The tool has 31 checks, and each check has one identifier, such as
`STE-5.1`. `ste schema` gives the list. 30 checks have the number of a rule.
`STE-GR-6` is a general recommendation, and not one of the 53 rules.

One check can cover more than one rule. `STE-5.1` counts the words of a
sentence. Thus it applies rules 5.1 and 6.3, and the count obeys rules 8.4 to
8.7. The tool covers 39 rules with 30 identifiers. A rule with no
identifier of its own appears in the column "Check" with the identifier
that covers it.

## Built, the full rule

The check covers each part of the rule. A check can still give a wrong
finding, and [rules.md](rules.md) gives the limits of each one.

| Rule | Subject | Check |
|---|---|---|
| 2.1 | A noun of more than three words | `STE-2.1`, with the analyzer |
| 3.2 | The permitted verb forms and tenses | `STE-3.2` reports a modal such as "would" with a verb. `STE-3.4`, `STE-3.5`, and `STE-3.6` report the other forms. |
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

- **Tagger**: a better part-of-speech tagger or parser. The analyzer
  supplies one, but it makes errors, and its word lists are not complete.
- **Dictionary**: the ASD-STE100 dictionary, which the user must import.
- **Reader**: a judgment of a reader. No program gives the same answer each
  time.

| Rule | Subject | What the tool checks | Missing | Needs |
|---|---|---|---|---|
| 1.1 | An approved word | 38 terms. With `--use-dict`, each word of the dictionary. | Is a word that the dictionary does not give a technical noun or a technical verb? | Reader |
| 1.2 | The approved part of speech | `STE-1.2`, with `--use-dict` and the analyzer, with the `info` severity | A word that the tagger or the lemmatizer reads incorrectly. A noun and an adjective. | Tagger |
| 1.4 | The approved forms of an adjective | `STE-1.4`, with `--use-dict`, the analyzer, and an index with the forms. A regular ending finds the headword when the lemma is wrong. | An irregular form that the lemmatizer reads incorrectly, and an entry with no forms | Tagger, dictionary |
| 1.6 | An unapproved word as a technical noun | With `--use-dict`, `STE-1.1` says when the dictionary permits a word as a technical noun. `allow.nouns` permits a word. | Does the word have a category of technical nouns? | Reader |
| 1.7 | A technical noun as a verb | `STE-1.7`, with the analyzer. It reads the one-word nouns of `allow.nouns`. | A technical noun of many words. The nouns of the software preset do not count. | Tagger |
| 1.8 | The technical nouns of the company | `STE-1.11` reports a different name that `prefer` gives. | A name that the config does not give | Reader |
| 1.9 | A short technical noun | `STE-1.9` reports a technical noun of the config that is longer than `max_noun_words`. | Is the noun easy to understand? | Reader |
| 1.11 | Two names for the same item | `STE-1.11` reads `prefer`. | Two names that the config does not give | Reader |
| 1.13 | A technical verb as a noun | `STE-1.13`, with the analyzer. It reads the one-word verbs of `allow.verbs`. | A technical verb of many words | Tagger |
| 1.14 | American spelling | `STE-1.14` reports 54 British spellings. With the analyzer, it also reports a spelling that changes with the part of speech, such as "licence". | A British spelling in a word with a capital letter, such as a title | Reader |
| 3.1 | The verb forms of the dictionary | `STE-3.1`, with `--use-dict`, the analyzer, and an index with the forms. A regular ending finds the headword when the lemma is wrong. | An irregular form that the lemmatizer reads incorrectly, and an entry with no forms | Tagger, dictionary |
| 3.3 | A past participle as an adjective | `STE-3.3`, with the analyzer. It reports a participle that is the verb of a short clause, with the `info` severity. | A participle after a noun when the parser gives no clause. Does the dictionary approve the participle as an adjective? | Tagger, dictionary |
| 3.4 | No auxiliary verb for a complex construction | `STE-3.4` reports "have" and a participle, and "is to be" and a participle. `STE-3.6` reports `can be adjusted`. | "have to" and "need to". The meaning of these words is a question of rule 1.3. | Reader |
| 3.6 | The active voice | `STE-3.6` reports each passive verb. | The standard permits the passive in descriptive text when the agent is not known. | Reader |
| 3.7 | A verb for an action | `STE-3.7` reports 17 word groups. With the analyzer, it reports a verb such as "perform" and a noun for an action. | A noun that is not in the list of 57 nouns. The parser makes errors. | Tagger |
| 4.1 | Short and clear sentences | `STE-5.1` measures the length. | Is the sentence clear? | Reader |
| 4.2 | No omitted word, and no contraction | `STE-4.2` reports a contraction. With the analyzer, it reports a singular noun with no article, with the `info` severity and a confidence of 0.50. | An omitted verb, an omitted subject, or an omitted "that" | Tagger |
| 4.3 | A vertical list for complex text | `STE-4.3` reports a list that starts its items in two ways. | Does the text need a list? Is each item the same construction? | Reader, tagger |
| 5.2 | One instruction in each sentence | `STE-5.2`, with the analyzer. It reads a numbered step. | A step that is not in a numbered list. A verb that the tagger reads incorrectly. | Reader, tagger |
| 5.3 | An instruction is a command | `STE-5.3` reads a numbered step, with the analyzer. | An instruction that is not in a numbered list | Reader |
| 5.4 | The condition first | `STE-5.4` reads "when", "if", and "unless" in a numbered step. With the analyzer, it also reads "before", "after", and "once". | A condition in text that is not a numbered step | Reader |
| 5.5 | A note gives information only | `STE-5.5` reads 5 words, such as "must". With the analyzer, it reports a note that starts with a command. | A command that the tagger reads incorrectly | Tagger |
| 7.1 | A word for the level of the risk | `STE-7.1` reports a risk under a note label, and a risk to a person under a caution label. | Does a warning tell of a risk to a person? A risk with no label | Reader |
| 7.2 | A command or a condition at the start of a safety instruction | `STE-7.2`, with the analyzer. It reads the first sentence of a warning, a caution, and a danger block. | Is the text really a safety instruction? | Reader |
| 7.3 | An explanation of the risk | `STE-7.3` reports a short block of one sentence. | Does the text give a risk? | Reader |
| 8.2 | A hyphen between words that are directly related | `STE-8.2`, with the analyzer and the `info` severity. It reads a list of pairs for an adjective and a noun. | A pair of an adjective and a noun that is not in the list, and a pair of nouns | Tagger |
| 8.6 | Elements that count as one word | A number, a quantity and its unit, quoted text, and the number of a step. With the analyzer, a name of many words. | A title or an identifier in small letters | Tagger |
| 9.3 | A phrasal verb | `STE-9.3` reports 24 phrasal verbs. With the analyzer, it also finds a separated particle and a phrasal verb that is not in the list. | The list is not complete, and the parser makes errors. | Tagger |
| 9.4 | A consistent style | `STE-1.11` reads `prefer`. | Wording that the config does not give | Reader |

## The analyzer

With the `--analyze` flag, an external program gives the grammar of a
sentence. 23 rules use it. 11 of them give no finding without it, and the
other 12 have a basic check that works without a model.

| Rule | Without the analyzer | What the grammar gives |
|---|---|---|
| 1.1 | A basic check | The part of speech of a word that the dictionary rejects only as a verb |
| 1.2 | No finding | The part of speech and the lemma of each word |
| 1.4 | No finding | The lemma and the form of an adjective |
| 1.7 | No finding | A technical noun that the sentence uses as a verb |
| 1.13 | No finding | A technical verb that the sentence uses as a noun |
| 1.14 | A basic check | The part of speech of "licence" and "practise" |
| 2.1 | No finding | The words of a noun cluster |
| 3.1 | No finding | The lemma and the form of a verb |
| 3.2 | A basic check | A modal and its verb, also when other words are between them |
| 3.3 | No finding | A participle that is the verb of a short clause |
| 3.4 | A basic check | A participle after "is to be" |
| 3.5 | A basic check | An "-ing" word that is a verb, and not a noun or a modifier |
| 3.6 | A basic check | A veto. A finding goes when the parser sees no passive relation. |
| 3.7 | A basic check | A verb such as "perform" and a noun for an action as its object |
| 4.2 | A basic check | A singular noun with no article |
| 5.1 | A basic check | A name of many words, which counts as one word (rule 8.6) |
| 5.2 | No finding | The commands that join in one step |
| 5.3 | No finding | The part of speech of the first word of a step |
| 5.4 | A basic check | A condition clause after the command |
| 5.5 | A basic check | A note that starts with a command |
| 7.2 | No finding | The first sentence of a safety instruction |
| 8.2 | No finding | Two words that modify a noun as one unit |
| 9.3 | A basic check | A particle with words between it and its verb |

[The analyzer](analyzer.md) gives the installation and the time of a run.

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

The `ste review` command does not check these rules. It prints an
instruction for an agent: start a subagent, and load the skill.

## Why the tool does not try each rule

A tool that reports a judgment as a defect makes each finding less
believable, and a person then reads none of them. The command reports only
what it can prove, the skill gives advice and says that it is advice, and
the reader keeps the decision.
