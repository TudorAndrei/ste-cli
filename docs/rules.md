---
title: Rules
description: The 31 checks of the tool, with the Issue 9 rule number, the confidence value, and the known limits of each one.
---

# Rules

[Back to the start page](index.md)

This tool has 31 checks. 11 of them need the analyzer of the grammar, and
they give no finding without it. 3 of these 11 also need the dictionary. ASD-STE100 Issue 9 has 53 rules and a
dictionary of approved words. The tool does not ship the dictionary. `ste dict import`
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
| `STE-3.4` | Complex verb construction | 0.90, 0.85, or 0.55 | warning |
| `STE-3.5` | Progressive "-ing" form | 0.90 | warning |
| `STE-3.6` | Passive voice | 0.95, 0.85, or 0.70 | warning |
| `STE-3.7` | A noun for an action | 0.90, or 0.85 | warning |
| `STE-4.2` | Contraction, or an omitted article | 0.98, or 0.50 | warning for a contraction, info for an article |
| `STE-5.1` | Sentence too long | 0.90 | warning |
| `STE-8.1` | Semicolon | 1.00 | warning |
| `STE-9.3` | Phrasal verb | 0.85, or 0.70 | warning |
| `STE-GR-6` | Latin abbreviation | 0.90 | info |
| `STE-4.3` | A list with two constructions | 0.80 | info |
| `STE-5.5` | An instruction in a note | 0.80, or 0.75 | warning |
| `STE-6.6` | Paragraph too long | 1.00 | warning |
| `STE-7.1` | A safety instruction with no word for the level of the risk | 0.70 | warning |
| `STE-7.3` | A safety instruction with no explanation | 0.70 | warning |
| `STE-5.4` | A condition after the command | 0.70, or 0.75 | info |
| `STE-1.11` | Two names for the same item | 0.95 | warning |
| `STE-1.9` | A technical noun that is too long | 0.95 | warning |
| `STE-2.1` | A noun of more than three words | 0.80 | warning |
| `STE-5.3` | An instruction that is not a command | 0.75 | warning |
| `STE-3.2` | A verb form that is not an approved tense | 0.90, or 0.80 | warning |
| `STE-3.3` | A past participle that is not an adjective | 0.80, or 0.70 | info |
| `STE-1.7` | A technical noun as a verb | 0.70 | warning |
| `STE-1.13` | A technical verb as a noun | 0.70 | warning |
| `STE-5.2` | More than one instruction in a step | 0.80 | warning |
| `STE-7.2` | A safety instruction that does not start with a command | 0.80 | warning |
| `STE-1.2` | A word that is not the approved part of speech | 0.70 | info |
| `STE-1.4` | An adjective form that the dictionary does not give | 0.80 | warning |
| `STE-3.1` | A verb form that the dictionary does not give | 0.80 | warning |
| `STE-8.2` | A compound modifier with no hyphen | 0.70 | info |

In `flavored` mode, the tool removes each finding with a confidence of less
than 0.60. In `strict` mode, it keeps all findings and it makes the severity
of a rule one step stronger. The mode does not change a word limit.

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

**Limits.** Rule 1.1 also has parts that need more than the word list. They
are the approved part of speech (rule 1.2) and the approved meaning (rule
1.3). `STE-1.2` checks the part of speech with the analyzer. The tool does
not check the meaning.

**With the analyzer.** Some entries reject a word only as a verb. Without the
analyzer, a determiner before the word shows a noun, and a finding gets a
confidence of 0.60. With the analyzer, a verb gets 0.95, and a noun or an
adjective gives no finding.

**Control.** `allow.nouns` and `allow.verbs` in the glossary remove a term
from this rule. Rule 1.8 tells writers to use the technical nouns of their
company or industry. A project glossary agrees with the standard.

## STE-1.14 British spelling

Reports 54 British spellings that have one American form, for example
"colour" and "centre". Rule 1.14 tells you to use American English spelling.

**Limits.**

- The list does not include a pair that needs a part of speech, such as
  "licence" and "practise". British English writes the noun "licence" and
  the verb "license". American English writes "license" for the two.
  **With the analyzer**, the rule reads the part of speech and reports
  "licence", "practise", and "dependant", with their other forms. The
  message names the part of speech. A word in quotation marks is a mention
  of the word, and this part of the rule does not report it.
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

The rule also reports "is to be" and then a past participle, as in "is to be
installed". This construction has three auxiliary words. The confidence is
0.85. With the analyzer, the confidence is 0.90, and the rule gives no
finding when the analyzer does not read the last word as a participle. When
the same words give an `STE-3.6` finding, and no "by" agent follows, the
tool removes the passive finding.

**Limits.**

- "have to" is an obligation. The tool does not report it. The problem is
  the meaning of "have", and not the construction. Rule 1.3 gives the
  approved meaning of a word, and a reader must examine it.
- "is to" and then a verb, as in "The aim is to start the pump", is
  usually not an obligation. The tool does not report it.
- "has been" and then a word that is not a participle gets a confidence of
  0.55. Only `strict` mode shows it.

## STE-3.5 Progressive "-ing" form

Reports a form of "to be" and then a verb that ends with "-ing". Example:
"is running", "is still running", "was not reading". Rule 3.5 permits the
"-ing" form only as a technical noun or as a modifier in a technical noun.

**With the analyzer**, the rule also finds an "-ing" verb in each other
position, such as "Before starting the pump" and "by using the network". The
analyzer separates a verb from a noun and from a modifier, which rule 3.5
permits. On a repository of 180 files, this part gave 354 more findings.

**Limits.**

- A word directly after a quotation mark, or directly before one, is a
  mention and not a verb. An example is `must be "warning"`. The tool does
  not report it, with or without the analyzer.
- The tool has a list of "-ing" words that are adjectives or nouns, such as
  "missing" and "existing". It does not report them.
- The tool does not report "is being", because that is the passive voice,
  and rule 3.6 reports it.
- A determiner or a possessive before an "-ing" word shows a noun, also
  when the analyzer gives a verb. The tool does not report "warning" in
  "Make each warning an error", or "cleaning" in "before its cleaning".
- Without the analyzer, the tool finds only the form after "to be".

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
  agent follows. The standard gives the same "by" test.
- The tool does not find a passive sentence with no agent when the
  participle is in that list. This is a known miss.
- A hyphenated form, such as "MIT-licensed", is an adjective for this tool.
- When the same words also give an `STE-3.4` finding, and no "by" agent
  follows, the tool removes the passive finding. Thus one problem gives one
  message.

## STE-3.7 A noun for an action

Reports 17 word groups that use a noun for an action, for example "do a
check of". Rule 3.7 tells you to use an approved verb.

**With the analyzer**, the rule also reports a verb with little meaning and
its direct object. The object is a noun that names an action. An
example is "do an installation of the software", which is "install the
software". The verbs are "perform", "do", "conduct", "carry out",
"undertake", "effect", and "accomplish". "make", "give", "provide", and
"take" count only with some nouns, because "make a preparation" can make an
item. The rule also reads a passive form, such as "the inspection was
performed". The confidence is 0.85.

**Limits.**

- Without the analyzer, the tool cannot find a noun for an action that is
  not in the list.
- The analyzer part has a list of 57 nouns, each with one verb. A noun
  that is also the name of an item, such as "application", is not in the
  list.

## STE-4.2 Contraction, or an omitted article

Reports "n't", "'re", "'ve", "'ll", "'m", "'d", and the known "'s" forms,
such as "it's".

The rule has two parts, and each part has its own severity:

| Part | Severity | Confidence | Needs |
|---|---|---|---|
| A contraction | warning | 0.98 | Nothing |
| An omitted article | info | 0.50 | The analyzer |

The two parts have one identifier. `ste schema` gives `warning` as the
default severity of the rule, and the `parts` field of the rule gives the
two parts. Read the severity of a finding from the finding. A `rules` entry
in the config changes the severity of the two parts.

Rule 4.2 also tells you not to omit a word to make a sentence shorter. With
the analyzer, the rule also reports a singular noun with no article, as the
subject or the object of a verb. "Remove cover from the unit" gives
"cover". This finding has the `info` severity and a confidence of 0.50.
Thus only `--mode strict` or a lower `min_confidence` shows it.

The rule does not report these nouns:

- A noun after a word such as "the", "this", "each", "its", or a number.
- A plural noun, a name, and a word with a capital letter.
- A noun that usually has no plural, such as "data", "software", or
  "access". A word list and some word endings, such as "-ing" and "-tion",
  find these nouns.
- A noun before code, a number, or a quotation, such as "set option
  `color`". The code is the name of the item.
- A noun in a heading, in a table cell, or in a list item with no verb.

**Limits.** The tool does not report a possessive form, such as "the
parser's output". It does not find an omitted verb, an omitted subject, or
an omitted "that". The analyzer makes errors, and the word lists are not
complete. On the documentation of 23 Python packages, 92 of 108 findings
were correct. Many of the incorrect findings were the names of tools in
lower case, such as "libc". Read the sentence before you change it.

## STE-5.1 Sentence too long

Reports a sentence that is longer than its limit. The standard selects the
limit from the type of the sentence, and not from the mode:

| Sentence | Limit | Rule |
|---|---|---|
| An instruction in a procedure | 20 words | 5.1 |
| A note | 25 words | 5.5 |
| Descriptive text | 25 words | 6.3 |

The tool has no part-of-speech tagger. It uses the structure of the
Markdown. A numbered list item is an instruction in a procedure. A
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
the same effect as a period. It ends the sentence, and the count starts
again. The item "The flag: it starts the pump" is two sentences. A colon
with no space after it is not a mark of punctuation, and "12:30" stays one
word. The colon of a label keeps its sentence, thus "**NOTE:** The pump
needs pressure" is one sentence.

**A name of many words (rule 8.6).** With the analyzer, a name of many
words counts as one word. A name is two or more words that the analyzer
tags as proper nouns, with only spaces between them. "Amazon Web Services"
is one word. A comma between two names keeps two words, and a text in
capital letters is not a name.

**Limits.** Without the analyzer, the tool counts each word of a name. The
count can therefore be too high for a sentence that has a long title or a
long name. The analyzer does not find a title or an identifier in lower
case.

**Text in parentheses (rule 8.5).** The text in parentheses counts as one
word of its sentence. It is also a sentence of its own, with the same limit.
The tool reports text in parentheses that is longer than the limit, and the
finding starts at the open parenthesis.

## STE-8.1 Semicolon

Reports each semicolon in prose. Rule 8.1 permits all the standard English
punctuation marks, but not the semicolon. It is a ban of one mark, and not a
list of permitted marks.

**Limits.** The tool does not report a semicolon in code, in inline code, in
a link target, or in an HTML entity such as `&nbsp;`.

## STE-9.3 Phrasal verb

Reports 51 phrasal verbs in all their forms: the base form, the third-person
form, the past form, and the "-ing" form. Example: "carry out", "carries
out", "carried out", "carrying out". Rule 9.3 tells you not to make a
phrasal verb from two words.

**Limits.**

- Without the analyzer, the verb and its particle must touch, and the tool
  does not find a separated form, such as "turn the pump on".
- **With the analyzer**, the rule reads the particle of each verb. It finds
  "turn the pump on", with a confidence of 0.85 for a verb of the list. It
  also finds a phrasal verb that is not in the list, such as "log in", with
  a confidence of 0.70.
- "comes on" and "comes off" tell the state of a light or a switch, and the
  rule does not report them.
- The analyzer can join a particle to the object, as in "look the key up",
  or give it the relation of an adverb, as in "throw the logs away". The
  rule then reports only a phrasal verb of the list. The adverbs "on" and
  "in" do not count, because "keep the light on" gives a state.
- "up to" before a number gives a limit, as in "show up to 10 results".
  The rule does not report it.
- A technical verb in `allow.verbs` removes its phrasal verbs from the
  rule. A technical noun does not, thus "log" in `allow.nouns` does not
  permit "log in".

## STE-GR-6 Latin abbreviation

Reports "e.g.", "i.e.", "etc.", and 5 more Latin abbreviations. GR-6 is a
general recommendation. The severity is `info`, and no mode and no flag
makes it an error.

**Limits.** A Latin abbreviation is lower-case and it ends with a period.
The tool obeys both conditions. It does not report the name "VS Code", and
it does not report "vs" as a column title. Before version 0.5.0, the
name "VS Code" gave 147 wrong findings in one repository.

## STE-2.1 A noun of more than three words

**This rule needs the analyzer.** Run `ste lint --analyze`.

Reports a group of more than three nouns that follow each other. Rule 2.1
gives that limit, because a long noun cluster has more than one meaning.
"engine fuel pump control unit" does not say which word belongs to which.

**Limits.**

- A name of many words is one unit by rule 8.6, and the rule does not report
  it. Each word must be a name for that test.
- `allow.nouns` removes a cluster from the rule.
- The analyzer does not read the text of inline code. It reads one name in
  its position, and a name from code is not a word of a cluster. Thus
  "Run `ste lint --format json`" gives no finding.
- Software documentation has many long noun clusters. On a repository of 180
  files, the rule gave 141 findings.

## STE-5.3 An instruction that is not a command

**This rule needs the analyzer.** Run `ste lint --analyze`.

Reports a step of a procedure that does not start with a command verb. Rule
5.3 tells you to write an instruction in the imperative form, so the reader
knows that the sentence is an action and not a description.

A numbered list does not always hold a procedure. A design record uses one
for its requirements, and those are descriptions. The rule reads a list only
when more than half of its items are commands. Thus a list of steps with one
description gives a finding, and a list of requirements gives none.

**Limits.**

- The rule steps over a phrase that ends with a comma: "When the light comes
  on, set the switch" and "In the pull request, give the date" are commands.
  It also steps over an adverb: "Atomically replace the file".
- "Do not touch the surface" is a command in the negative form, and the rule
  accepts it.
- The analyzer reads a short step with no context, and it then gives a wrong
  part of speech: "Delete quarantined files" looks like an adjective and a
  noun. The rule reads the sentence again with "please" at its start, and
  "please" makes the sentence a command. This method removed 68 of the 69 findings
  on one repository, and each of those 68 was wrong.
- A step of two words, such as "Complete preflight", stays ambiguous. The
  rule can report it.

## STE-1.7 A technical noun as a verb

**This rule needs the analyzer.** Run `ste lint --analyze`.

Reports a technical noun of `allow.nouns` that the sentence uses as a verb.
Rule 1.7 tells you to use a technical noun only as a noun. An example is
"Shim the bracket" when the glossary gives "shim" as a noun.

**Limits.**

- A word that is in `allow.nouns` and in `allow.verbs` has the two parts of
  speech, and the rule does not report it.
- The nouns of the `software` preset do not count. Software text uses most
  of them as verbs too, such as "build", "commit", and "run".
- The rule reads only a technical noun of one word.
- The tagger can tag a capitalized first word as a name. The rule then
  accepts it as a verb only when it has a direct object.
- The confidence is 0.70, because the tagger can confuse a noun and a verb.

## STE-1.13 A technical verb as a noun

**This rule needs the analyzer.** Run `ste lint --analyze`.

Reports a technical verb of `allow.verbs` that the sentence uses as a noun.
Rule 1.13 tells you to use a technical verb only as a verb. An example is
"Do the install again" when the glossary gives "install" as a verb.

**Limits.**

- A word that is in `allow.nouns` and in `allow.verbs` has the two parts of
  speech, and the rule does not report it.
- The rule does not report a verb before a noun, as in "the lint command".
- An "-ing" form is for rule 3.5, and this rule does not report it.
- The confidence is 0.70, because the tagger can confuse a noun and a verb.

## STE-5.2 More than one instruction in a step

**This rule needs the analyzer.** Run `ste lint --analyze`.

Reports a step of a procedure that gives two commands or more. Rule 5.2
tells you to write one instruction in each sentence. Two actions that occur
at the same time are one instruction.

"Open the valve and remove the cap" gives a finding at "remove". Write two
steps: "Open the valve" and "Remove the cap".

**Limits.**

- The rule reads a numbered step that starts with a command. A second
  command must join the first command, and it must have no subject of its
  own.
- "at the same time" and "simultaneously" stop the rule.
- "Push and hold the button" gives no finding. The two verbs have one
  object, and they are one action.
- "Turn the knob or push the button" gives no finding. The reader does one
  of the two. "Otherwise" also gives a choice, as in "Keep the count.
  Otherwise, return the default."
- The tagger can read the name of a tool as a verb, as in "Use oxlint for
  linting and oxfmt for formatting". The rule ignores a second verb that is
  not in the word list of the model. A word that a prefix or a suffix makes
  from a word of the list, such as "reconnect" or "tokenize", stays a verb.
- The rule ignores a verb in capital letters, in quotation marks, or in
  parentheses. "Click Build and Deploy" names a button.
- A verb after a list of nouns is often the last noun of the list, as in
  "Freeze the ID, the checksum, and stop limits". The rule ignores it.
- The rule ignores a step in a block quote, and a step that starts with
  code or a link. Such a step often quotes a prompt or describes the code.
- On 150 files of software documentation, the rule gave 39 findings. A
  person found 37 correct. The tagger read "oxfmt" as a verb, and one
  finding was a choice between two actions.

## STE-4.3 A list with two constructions

Reports an item of a vertical list that does not agree with the other items.
The test is the first letter. A list that starts some items with a capital
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

- Without the analyzer, the list of 5 words is the whole test. A command
  with none of them, such as "Disconnect the power", gives no finding.
- With the analyzer, the rule also reports a note sentence that starts with
  a command verb, at the confidence 0.75. The command can follow a condition
  clause or an adverb. The rule does not read the label "NOTE" as a part of
  the sentence. "See the guide" and "Refer to the guide" send the reader to
  other text, and they give no finding. A sentence that has one of the 5
  words gives one finding only.
- A warning, a caution, and a danger block can hold an instruction, and the
  rule does not read them. Rule 7.3 reads those.

## STE-6.6 Paragraph too long

Reports a paragraph of more than 6 sentences. Rule 6.6 gives that limit for
descriptive text. The confidence is 1.00, because the rule counts sentences
and does not guess.

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

## STE-1.9 A technical noun that is too long

Reports a technical noun of the project that has more words than the limit.
Rule 1.9 tells you to select a technical noun that is short and easy to
understand. The explanation of the rule gives a limit of three words.

The rule reports nothing until the config gives the limit:

```yaml
max_noun_words: 3
allow:
  nouns: ["fuel pump control unit"]   # 4 words: a finding
prefer:
  "config file": ["settings file"]    # 2 words: no finding
```

**What the rule reads.** The tool has no part-of-speech tagger, and it
cannot find a noun in free text. Thus the rule reads only the nouns that
the project gives as technical nouns: each item of `allow.nouns`, and each
name to use in `prefer`. A hyphenated word counts as one word (rule 8.7).
The rule reports the first use of each noun in a file, and not each use.

**Why the limit has no default.** Rule 1.9 applies when you must select a
new technical noun. Rule 1.8 tells you to use the technical noun of your
company or industry, also when it is long. The tool cannot know which of the
two rules applies to a noun. When you set the limit, you say that the nouns
of the config are your own selection.

**Limits.**

- The rule cannot see if a noun is easy to understand. A reader must decide.
- A long noun that the config does not give gets no finding. With the
  analyzer, rule `STE-2.1` reports a noun of more than three words.

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
  before the condition. A word in small letters after "to" is a verb, and a
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
- With the analyzer, the rule also reads a clause that starts with "before",
  "after", or "once", and the words "in case" and "as soon as". The clause
  must come after the command verb, and it must have a subject: "Close the
  valve before you start the pump" gives a finding, and "Read the guide
  before using the tool" gives none. A phrase with no verb, such as "after
  the test", gives no finding. "until" and "while" give a duration, and the
  rule does not read them. On 150 files of software documentation, the
  analyzer gave 9 findings, and each one was correct.
- The severity is `info`, because the tool has no parser and the test is the
  position of a word.

## STE-7.1 A safety instruction with no word for the level of the risk

Reports a note, a tip, an info, an attention, or an important block that
tells of a risk. Rule 7.1 tells you to use a word that gives the level of
the risk. Use "warning" for a risk of injury or death, and "caution" for a
risk of damage. The words of a risk are "injury", "death", "damage", "hazard",
"destroy", "corrupt", "data loss", and some forms of them.

```markdown
> [!IMPORTANT]
> This step can cause data loss.
```

The rule reports each block one time, at the first word of the risk.

**A caution with a risk to a person.** A caution tells of a risk of damage.
When there is a risk of injury or death, use the label "warning". Thus
the rule also reports a caution block that has the word "injury", "death", or
a different form of them. The rule does not read "fatal" or "kill", because
software text uses them for an error and for a process.

**Limits.** The rule reads a word list, and not the meaning. "This does not
damage the file" gives a finding. A block with no label is not a safety
instruction for the rule, and the rule does not read it. The rule does not
report a warning that tells of damage only. A risk analysis decides the
level, and software text often uses "warning" for a loss of data.

## STE-7.2 A safety instruction that does not start with a command

**This rule needs the analyzer.** Run `ste lint --analyze`.

Reports a warning, a caution, or a danger block whose first sentence is a
description. Rule 7.2 tells you to start a safety instruction with a clear
and simple command, so that the reader knows at once what to do. A
condition can come before the command.

"**WARNING:** The surface is hot. It can burn your skin." gives a finding.
"**WARNING:** Do not touch the surface. It is hot." gives none, and
"**CAUTION:** If the pump runs, do not open the valve." gives none.

**Limits.**

- The rule reads the first sentence of the block only.
- The rule reports a sentence with a subject and a verb that is not a
  command, such as "This command deletes all data" or "You must wear
  gloves". A phrase with no verb, such as "High voltage", gives no finding,
  because a label of the hazard is not a description.
- A condition and then a description, such as "If you run this, the data
  is lost", gives a finding. The condition must come before a command.

## STE-7.3 A safety instruction with no explanation

Reports a warning, a caution, or a danger block that gives no reason. Rule
7.3 tells you to give the risk, so the reader knows what happens when they
do not obey. The rule reports a block of one sentence that has 12 words or
less. A second sentence, or a longer first one, is the explanation.

**Limits.** The rule counts sentences and words. It cannot read the sentence
to see if it gives a risk, and a long instruction with no reason
gives no finding. A note and a tip are not safety instructions, and the rule
ignores them.

## STE-3.2 A verb form that is not an approved tense

Reports "would", "should", "shall", "may", or "might" and then a verb.
Example: "would see", "should not restart", "may fail".

Rule 3.2 approves only six forms of a verb. They are the infinitive, the
imperative, the simple present, the simple past, the simple future, and the
past participle. A modal of this list makes a different form, such as a
conditional.

| Condition | Confidence |
|---|---|
| The analyzer gives the modal and the verb that it goes with | 0.90 |
| The words alone: a modal and then a word that is not a determiner or a pronoun | 0.80 |

With the analyzer, the rule also finds a modal that is not next to its
verb, as in "Should the pump fail". The analyzer also stops a finding when
"may" is not a modal.

**Limits.**

- The standard approves "can", "could", "must", and "will". The rule does
  not report them.
- A perfect after the modal, as in "would have sent", goes to `STE-3.4`.
  Thus one problem gives one message.
- A capital "May" that does not start its sentence is usually a month. The
  rule does not report it.
- Without the analyzer, the rule does not find an inversion, as in "Should
  the pump fail".

## STE-3.3 A past participle that is not an adjective

**This rule needs the analyzer.** Run `ste lint --analyze`.

Reports a past participle that is the verb of a short clause, and not an
adjective. Example: "The file created by the tool", "Once installed, the
agent starts". Rule 3.3 permits a past participle as an adjective, and the
passive voice uses it after "to be".

| Condition | Confidence |
|---|---|
| A "by" agent follows the participle | 0.80 |
| No agent | 0.70 |

**Limits.**

- A participle before its noun, as in "the attached cable", is an
  adjective. The rule does not report it.
- A participle with "to be" or "have" goes to `STE-3.6` or `STE-3.4`.
- The word must have the form of a past participle. Thus a word that the
  analyzer tags in error, such as "page", gives no finding.
- The severity is `info`. Rule 3.3 permits a past participle as an
  adjective. It is not certain that the rule also forbids a short clause,
  such as "the file created by the tool". Thus a finding is a question for
  the writer, and not a defect. Read the sentence, and change it when a
  clause with a subject and a verb is clearer.

## STE-1.2 A word that is not the approved part of speech

Reports a verb when the dictionary approves the word only as a noun or an
adjective. It also reports a noun when the dictionary approves the word only
as a verb. Rule 1.2 permits an approved word only as the part of speech that
the dictionary gives. When the dictionary has the word as an unapproved verb
with alternatives, the suggestion gives those alternatives.

The rule needs `--use-dict` and the analyzer. Without one of them, it gives
no finding. It finds the entries by the lemma of the word, thus "plates"
finds the entry "plate".

**Limits.**

- The tagger can make a mistake. A word that ends with "-s" can be a plural
  noun or a verb. Thus the confidence is 0.70. Read the sentence before you
  change it.
- The severity is `info`. We measured the precision of the rule only with
  an invented dictionary, and not with the real dictionary.
- The rule does not compare a noun and an adjective. The tagger often gives
  a noun before a noun as an adjective.
- The rule does not compare an adverb, a preposition, or a conjunction. The
  tagger often mixes up these classes. It also ignores a word that the
  dictionary approves as one of these classes.
- The rule does not read a heading, a table cell, or a sentence of less than
  3 words. These are usually fragments, and the tagger has no context.
- A noun as the first word of a sentence does not get a finding. The first
  word of an instruction is a verb, and the tagger sometimes gives it as a
  noun.
- A word with a capital letter after the first word is usually a name. A
  word with a hyphen or a digit is usually a compound or a name. The rule
  does not report them.
- An "-ing" verb does not get a finding. `STE-3.5` reports it.
- `allow.nouns` and `allow.verbs` remove a word, by its text or its lemma.

## STE-1.4 and STE-3.1 A form that the dictionary does not give

Reports a verb or an adjective in a form that its dictionary entry does not
give. `STE-3.1` reports a verb, for example a past tense that the entry does
not give. `STE-1.4` reports a comparative or a superlative adjective, for
example "-est" when the entry gives only "-er". The suggestion gives the
forms of the entry. Rules 1.4 and 3.1 permit only the forms that the
dictionary gives. Thus `STE-3.1` also applies rule 1.4 to a verb.

The rule needs `--use-dict`, the analyzer, and an index with the forms. `ste
dict import` keeps the forms that your copy gives after a headword, such as
`WORD (v), WORDS, WORDED`. An index from an earlier version of the tool has
no forms. Import the dictionary again to get them. `ste dict info` gives the
number of forms.

**Limits.**

- The rule checks only an entry that gives one or more forms.
- For a word that the analyzer does not know, the lemma can be wrong. For
  example, it can give "zorpe" for "zorped". When the lemma has no entry,
  the rule removes a regular ending to find the headword: "-ed", "-d",
  "-s", and "-es" for a verb, and "-er" and "-est" for an adjective. It also
  removes a double consonant ("klapped" gives "klap"), and it changes "i"
  to "y" ("flimbier" gives "flimby"). An irregular form that the analyzer
  does not know gives no finding.
- A word that is a headword or a listed form of a different entry does not
  get a finding.
- A word with a hyphen or a digit, and a word with a capital letter after
  the first word, do not get a finding.
- An "-ing" verb does not get a finding. `STE-3.5` reports it.
- A noun does not get a finding. The dictionary does not list the plural.

## STE-8.2 A compound modifier with no hyphen

**This rule needs the analyzer.** Run `ste lint --analyze`.

Rule 8.2 tells you to put a hyphen between two words that modify a noun as
one unit. "high-pressure valve" is a valve for high pressure. Without the
hyphen, a reader can think that the valve is high.

The rule reports two words before a noun, with no hyphen, when one of these
is true:

- A noun modifies an adjective or a participle, as in "user friendly page"
  or "time consuming scan".
- "well" or "ill" modifies a participle, as in "well known problem".
- A number modifies a singular noun before a singular noun, as in "32 bit
  integer".
- The two words are a known pair, such as "high pressure", "open source",
  "third party", or "real time".

The finding has the `info` severity. On the documentation of 23 Python
packages, each of the 11 findings was correct.

**Limits.** The analyzer usually attaches an adjective to the last noun.
Thus "new user account" and "high pressure valve" have the same grammar.
The rule reports an adjective and a noun only for a pair of its list. It
does not report a pair of nouns, such as "command line tool".

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

The walk also does not read a file that a tool writes: `CHANGELOG`,
`CHANGES`, `HISTORY`, `NEWS`, and `RELEASE-NOTES`. The tool removes the
extension from the name, and it ignores the letter case. A writer cannot
correct text that the next release writes again, and a generated changelog
gave 11 wrong findings for rule 4.3 on one repository. `--all` reads these
files, and the tool always reads a path that you give by its name.

The tool always reads a file or a directory that you give by its path. Only
the `exclude` patterns of the config apply to such a file. The `--all` flag
removes the other filters.

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

The tool checks 39 of the 53 rules, 10 in full and 29 in part. It does not
check the other 14. Each of them needs a judgment of a reader, and a guess
gives wrong findings. Thus the tool does not try.

| Rule | Subject | Why not |
|---|---|---|
| 1.3 | The approved meaning | A judgment of a reader |
| 1.5, 1.12 | The category of a technical noun or verb | A judgment about the subject field |
| 1.10 | Slang and jargon | A judgment of a reader |
| 2.2 | The full form of a long technical noun | A judgment of a reader |
| 4.4 | Connecting words | Needs semantics |
| 4.5 | Articles and demonstrative adjectives | The exceptions of the standard make a check too noisy |
| 6.1, 6.2, 6.4, 6.5 | The order, the key words, and the topic of a paragraph | Needs semantics |
| 8.3 | The permitted uses of parentheses | Needs semantics |
| 9.1, 9.2 | A different construction, and each word in its correct place | Needs semantics |

[coverage.md](coverage.md) gives each of the 53 rules, and the part of each
rule that the tool checks.

## Limits of the tool

- Without the analyzer, the tool has no part-of-speech tagger. It uses word
  lists and short word sequences. The analyzer also makes errors. Thus the
  tool does not find all violations, and some findings are wrong.
- The tool does not ship the ASD-STE100 dictionary. Without your own copy
  and `--use-dict`, it cannot tell you if the standard approves a word.
- The tool is an aid for a writer. **It is not an ASD-certified checker**,
  and it cannot give certification.
