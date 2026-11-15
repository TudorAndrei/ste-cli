---
title: The analyzer
description: An optional program that gives the grammar of a sentence, for the rules of ASD-STE100 that words alone cannot check.
---

# The analyzer

[Back to the start page](index.md)

<!-- ste-disable STE-3.6 -->

Some rules of ASD-STE100 need the grammar of a sentence, and not only its
words. Rule 3.6 is an example. "The demand is measured" and "there is
measured demand" have the same words in the same order, and only the grammar
gives the difference.

<!-- ste-enable STE-3.6 -->

The Python command uses spaCy to get the grammar of English. The default
analyzer runs in the same process as the checker.

## Use

```bash
ste analyzer                 # what it needs, and the commands to install it
ste lint --analyze docs/     # use it
```

`ste analyzer` gives the answer for your computer:

```text
The analyzer cannot run: spaCy is not installed for /usr/bin/python3

To make it work:
  uv sync --extra nlp
  /usr/bin/python3 -m spacy download en_core_web_sm
```

The package contains the analyzer. You need no separate script.
`analyzer: true` in the config makes `--analyze` the default.
`$STE_PYTHON` selects a separate interpreter when necessary.

## How it works

1. The command reads a file and divides it into sentences.
2. It sends all the sentences of the file to the model in one batch.
3. It keeps the grammar of each sentence on the sentence and on each word.
4. The rules read that grammar. No rule calls the model.

The model loads one time for each run, and only when a sentence is not in
the cache. The command keeps only the parts of the pipeline that the rules
need: the tagger, the parser, and the lemmatizer. The named entity part
does not load.

The command and spaCy divide a sentence into words in different ways. For
example, spaCy gives `is` and `n't` for `isn't`, and the command keeps one
word. Each word of the command gets the grammar of the spaCy word that
controls the other parts. Thus `isn't` gets the grammar of `is`. The
`align` function in `src/ste/grammar.py` gives the full rule.

## The cache

The command keeps the grammar of each sentence in a cache on the disk. The
next run reads the cache, and the model does not analyze that sentence
again. The key of an entry is the text of the sentence, the model, its
version, the version of spaCy, and the parts of the pipeline. Thus a new
model never reads an old entry.

| Path | Condition |
|---|---|
| `$STE_GRAMMAR_CACHE` | an explicit path |
| `$XDG_CACHE_HOME/ste/grammar.sqlite3` | you give that variable |
| `~/.cache/ste/grammar.sqlite3` | Linux and BSD |
| `~/Library/Caches/ste/grammar.sqlite3` | macOS |

- `STE_GRAMMAR_CACHE=off` stops the cache.
- `ste analyzer --clear-cache` removes the cache.
- `ste analyzer` gives the path of the cache.

The cache is one SQLite file, thus two runs at the same time are safe. It
keeps the newest 100000 sentences, which is about 60 MB. An error in the
cache does not stop a run. The command then analyzes each sentence again.

## Time

These measurements come from one macOS computer with
`en_core_web_sm` 3.8.0. The findings are the same in each row of a table.

| Run of 20 files, 15334 words | Time |
|---|---|
| No analyzer | 0.32s |
| Analyzer of version 0.11, one request for each sentence | 1.77s |
| Analyzer with batches, no cache | 1.21s |
| Analyzer with batches, cache from an earlier run | 0.35s |

| Run of 240 files, 183912 words | Time |
|---|---|
| No analyzer | 1.07s |
| Analyzer of version 0.11, one request for each sentence | 2.60s |
| Analyzer with batches, no cache | 2.16s |
| Analyzer with batches, cache from an earlier run | 1.23s |

The second set of files holds many copies of the same text. It has only
1597 different sentences, thus the cache of one run does most of the work.

<!-- ste-disable-next-line STE-3.6 -->
The analyzer removes wrong findings of rule 3.6, such as "there is
measured user demand", where "measured" is an adjective of "demand".

## The rules that use it

23 rules use the analyzer. 11 of them give no finding without it. Rules
1.2, 1.4, and 3.1 also need `--use-dict` and an imported dictionary.

| Rule | Without the analyzer | Use |
|---|---|---|
| 1.1 approved word | A basic check | The part of speech of a word that the dictionary rejects only as a verb |
| 1.2 part of speech | No finding | The part of speech and the lemma of each word |
| 1.4 adjective form | No finding | The lemma and the form of an adjective |
| 1.7 technical noun | No finding | A technical noun that the sentence uses as a verb |
| 1.13 technical verb | No finding | A technical verb that the sentence uses as a noun |
| 1.14 spelling | A basic check | The part of speech of "licence" and "practise" |
| 2.1 noun cluster | No finding | The words of a noun cluster |
| 3.1 verb form | No finding | The lemma and the form of a verb |
| 3.2 tense | A basic check | A modal and its verb, also with words between them |
| 3.3 past participle | No finding | A participle that is the verb of a short clause |
| 3.4 complex construction | A basic check | A participle after "is to be" |
| 3.5 "-ing" form | A basic check | An "-ing" word that is a verb, and not a noun or a modifier |
| 3.6 passive voice | A basic check | A veto. The finding goes when the parser sees no passive relation. |
| 3.7 noun for an action | A basic check | A verb such as "perform" and a noun for an action as its object |
| 4.2 omitted article | A basic check | A singular noun with no article |
| 5.1 word count | A basic check | A name of many words, which counts as one word (rule 8.6) |
| 5.2 one instruction | No finding | The commands that join in one step |
| 5.3 command | No finding | The part of speech of the first word of a step |
| 5.4 condition first | A basic check | A condition clause after the command, such as "before you start the pump" |
| 5.5 note | A basic check | A note that starts with a command |
| 7.2 safety command | No finding | The first sentence of a safety instruction |
| 8.2 hyphen | No finding | Two words that modify a noun as one unit |
| 9.3 phrasal verb | A basic check | A particle with words between it and its verb |

A rule with a basic check works without the analyzer, and the analyzer
makes it more exact.

## For a rule author

A rule reads the grammar from the document, and not from the analyzer:

| Name | Content |
|---|---|
| `Sentence.tagged` | True when the analyzer gave the grammar of the sentence |
| `Sentence.syntax` | Each spaCy token, with the punctuation |
| `Token.pos`, `tag`, `dep`, `lemma` | The grammar of one word of `Sentence.tokens` |
| `Token.head` | The index of the head word in `Sentence.tokens`, or -1 |

The analyzer does not read the label of a note or a warning, such as
`**NOTE:**` or `[!WARNING]`. It also does not read the quote marks at the
start of each line of a block quote. The offsets of `Sentence.syntax` still
start at the start of `Sentence.text`. A test with `StubSyntax` gives the
sentence without its label as the key.

Each rule must also work when `Sentence.tagged` is false. A test can make
a tagged document without spaCy. The `tagged` function and the
`StubSyntax` class in `tests/grammar.py` take the grammar of each word
from the test.

## The protocol

One JSON object for each line, in both directions:

```
in : {"id": 1, "text": "The valve is closed by the operator."}
out: {"id": 1, "tokens": [{"i":0,"text":"The","pos":"DET","tag":"DT",
                           "dep":"det","head":1,"start":0,"lemma":"the"}, ...]}
```

The program gives `{"ready": true}` first. `{"stop": true}` ends it. A
different program can replace spaCy. It must give only a part of speech and
a relation for each token. The `lemma` field is optional.

`tests/fixtures/stub_analyzer.py` is an example that needs no library.
`--analyzer "<command>"` gives your own program to the tool.

The ready line can have three more fields:

| Field | Result |
|---|---|
| `"batch": true` | The command sends many sentences in one request. |
| `"version"` | The command keeps the answers in the cache. The key uses this value and `"model"`. |
| `"pipeline"` | A list of the parts of the model. The key of the cache also uses it. |

A batch request and its answer:

```
in : {"id": 2, "texts": ["Open the valve.", "Close it."]}
out: {"id": 2, "results": [[...tokens...], [...tokens...]]}
```

The list of results has the same order as the list of texts. An object
with `"error"` in place of a token list marks one failed sentence. A
program without `"batch"` gets one sentence in each request, as before.
