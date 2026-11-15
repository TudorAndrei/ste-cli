---
name: ste-review
description: Review documentation against the ASD-STE100 rules that a deterministic checker cannot verify: one topic for each paragraph, information in a logical order, consistent terminology, and the correct meaning of a word. Use after "ste lint" gives its findings, or when asked to review prose for Simplified Technical English, technical-writing quality, or clarity of documentation. Do not use to check punctuation, sentence length, the passive voice, or an approved word: the ste command checks those.
---

# ste-review

ASD-STE100 has 53 writing rules. The `ste` command checks 39 of them, in
full or in part, because they have a mechanical answer. This skill covers the rules that
have no mechanical answer: they need a reader who understands the text.

**Read this before you start: your findings are advice, and not defects.** A
rule of this group has no test that gives the same answer each time. Say what
you see, give the rule number, and let the writer decide.

## Step 1: run the checker first

```bash
ste lint --format json --limit 20 <path>
```

When `ste analyzer` says that the analyzer can run, add `--analyze`. Then
the command also checks the grammar. It reads the commands of a step, the
start of a note and of a warning, a participle, an omitted article, and a
hyphen.

Each finding of that command is for a mechanical rule. Examples are
punctuation, sentence length, the passive voice, a verb tense, a
contraction, a phrasal verb, and an unapproved word.
**Do not repeat that work, and do not disagree with it.** If a finding looks
wrong, the answer is a config change (`rules:`, `allow.nouns:`, `exclude:`) or
a comment in the text (`<!-- ste-disable-next-line -->`), and not a rewrite.

Then read the text yourself for the rules below.

## Step 2: the rules that need a reader

### The order of the information

- **6.1 Give information gradually.** Does the text give a fact before the
  fact that it depends on? A reader must not have to read a paragraph two
  times. Look for a paragraph that names a thing, and explains it later.
- **6.2 Give a logical structure with key words.** Does each paragraph start
  with its subject? A reader who reads only the first sentence of each
  paragraph must get the shape of the whole text.
- **6.4 Paragraphs for related information.** Two paragraphs that tell of
  the same subject can become one. Information that is not related must
  not share a paragraph.
- **6.5 One topic for each paragraph.** Find a paragraph that changes its
  subject in the middle. Propose the place to divide it.

### The words

- **1.3 One meaning for each word.** A word of the dictionary has one approved
  meaning, and that meaning is frequently more narrow than the meaning in
  usual English. Look for a word that the text uses in two senses. A word that
  names a part in one sentence, and an action in the next one, is an example.
  Give the rule number. The writer can then compare the word with their own
  copy of the dictionary.
- **1.9 A short technical noun.** Is a technical noun easy to understand?
  `STE-1.9` measures only the length of a noun that the config gives. A long
  name for a part, when one word is enough, is an example.
- **1.10 No slang, and no jargon.** A technical noun must be a term of the
  field, and not the language of one team. "The job got stuck" is not a
  technical statement.
- **1.11 One name for each thing.** Find a thing that the text names in two
  ways: "the config file" and "the settings file". Propose one name, and use
  it in each place.
- **9.2 Use each approved word correctly.** An approved word in the wrong
  place is still wrong.
- **9.4 A consistent style.** The same action must have the same words in each
  place: "Remove the panel" and not "Take the panel off" three lines later. <!-- ste-disable-line STE-9.3 -->

### The sentences

- **1.5, 1.12 Technical nouns and verbs.** A word that the dictionary does not
  approve is permitted when it is a technical noun of the field. Judge if it
  is. If it is, propose it for `allow.nouns` in the config. Do not rewrite it.
- **2.2 A long technical noun.** A technical noun of more than three words
  must appear in full one time, before its short form.
- **4.4 Connecting words.** Two sentences with related ideas need a connecting
  word between them. Find a place where the reader must guess the relation of
  one sentence to the sentence before it.
- **4.5 Articles.** An article ("the", "a") is necessary before most nouns.
  The standard permits no article in a general statement. Judge which one the
  sentence is.
- **8.3 Parentheses.** The standard permits parentheses for a small number
  of uses only. Judge if the text in parentheses is one of them. If it is
  not, propose a separate sentence.
- **9.1 A different sentence construction.** When an approved word does not
  fit, the answer is a new sentence, and not a strange word. Look for a
  sentence that obeys each mechanical rule and is still difficult.

### The reader part of a checked rule

The command checks a part of these rules. Read the text for the other part.

- **3.4 "have to" and "need to".** The command does not report them. Judge
  if the sentence gives an obligation, and propose "must".
- **4.1 A clear sentence.** The command measures the length. Judge if a
  short sentence is still unclear.
- **5.2, 5.3, 5.4 An instruction.** The command reads only a numbered step.
  Find an instruction in a paragraph or in a bulleted list. It must be a
  command, it must give one action, and its condition must come first.
- **7.1, 7.2, 7.3 A safety instruction.** The command reads only a block
  with a label. Find a risk in text that has no label. Judge if a warning
  tells of a risk to a person.

## Step 3: report

Give one line for each finding:

```
docs/guide.md:42  6.5  The paragraph starts with the cache and ends with
                       the network. Divide it after the third sentence.
```

- Give the rule number. A reader can then find the rule in the standard.
- Say what you see, and where.
- Propose one correction. Do not write the correction into the file, unless
  the user asks for that.
- Give a short list. Ten good findings are more useful than fifty.

## What you must not do

- **Do not repeat a mechanical finding.** The command found it already.
- **Do not rewrite a quotation.** A quotation keeps the words of its source.
  If a rule reports one, the answer is `<!-- ste-disable-next-line -->`.
- **Do not rewrite a name.** "VS Code" and "AeroSpace and Defence Industries"
  are names, and not spelling mistakes.
- **Do not rewrite code, an identifier, or a command.** The rules apply to
  prose.
- **Do not invent a rule.** Each finding must have a rule number of the standard.
  If it does not, it is your preference, and you must say so.
- **Do not copy the text of ASD-STE100.** The specification is under
  copyright. Give the rule number and your own words.

## The division of the work

| The `ste` command checks | You check |
|---|---|
| Punctuation, sentence length, word count | The order of the information |
| The passive voice, the verb tenses | One topic for each paragraph |
| A contraction, a phrasal verb | One name for each thing |
| An unapproved word, a British spelling | The correct meaning of a word |
| The count of words in a paragraph | If a term is a technical noun |
| A numbered step, a note, a labeled warning | An instruction or a risk in other text |

The command gives a number. You give a judgment. A reader needs both.
