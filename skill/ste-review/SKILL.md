---
name: ste-review
description: Review documentation against the ASD-STE100 rules that a deterministic checker cannot verify: one topic for each paragraph, information in a logical order, consistent terminology, and the correct meaning of a word. Use after "ste lint" gives its findings, or when asked to review prose for Simplified Technical English, technical-writing quality, or clarity of documentation. Do not use to check punctuation, sentence length, the passive voice, or an approved word: the ste command checks those.
---

# ste-review

ASD-STE100 has 53 writing rules. The `ste` command can check about 31 of
them, because they have a mechanical answer. This skill covers the rules that
have no mechanical answer: they need a reader who understands the text.

**Read this before you start: your findings are advice, and not defects.** A
rule of this group has no test that gives the same answer each time. Say what
you see, give the rule number, and let the writer decide.

## Step 1: run the checker first

```bash
ste lint --format json --limit 20 <path>
```

Each finding of that command is a mechanical rule: punctuation, sentence
length, the passive voice, a contraction, a phrasal verb, an unapproved word.
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
- **6.5 One topic for each paragraph.** Find a paragraph that changes its
  subject in the middle. Propose the place to divide it.

### The words

- **1.3 One meaning for each word.** A word of the dictionary has one approved
  meaning. "Follow" means "come after", and not "obey". Look for a word that
  the text uses with a second meaning.
- **1.10 No slang, and no jargon.** A technical noun must be a term of the
  field, and not the language of one team. "The job got stuck" is not a
  technical statement.
- **1.11 One name for each thing.** Find a thing that the text names in two
  ways: "the config file" and "the settings file". Propose one name, and use
  it in each place.
- **9.2 Use each approved word correctly.** An approved word in the wrong
  place is still wrong.
- **9.4 A consistent style.** The same action must have the same words in each
  place: "Remove the panel" and not "Take the panel off" three lines later.

### The sentences

- **1.5, 1.12 Technical nouns and verbs.** A word that the dictionary does not
  approve is permitted when it is a technical noun of the field. Judge if it
  is. If it is, propose it for `allow.nouns` in the config. Do not rewrite it.
- **2.2 A long technical noun.** A technical noun of more than three words
  must appear in full one time, before its short form.
- **4.4 Connecting words.** Two sentences with related ideas need a connecting
  word: "then", "thus", "but". Find a place where the reader must guess the
  relation.
- **4.5 Articles.** An article ("the", "a") is necessary before most nouns.
  The standard permits no article in a general statement. Judge which one the
  sentence is.
- **9.1 A different sentence construction.** When an approved word does not
  fit, the answer is a new sentence, and not a strange word. Look for a
  sentence that obeys each mechanical rule and is still difficult.

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

The command gives a number. You give a judgment. A reader needs both.
