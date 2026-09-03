---
title: The analyzer
description: An optional program that gives the grammar of a sentence, for the rules of ASD-STE100 that words alone cannot check.
---

# The analyzer

[Back to the start page](index.md)

<!-- ste-disable STE-3.6 -->

Some rules of ASD-STE100 need the grammar of a sentence, and not only its
words. Rule 3.6 is the example: "the demand is measured" and "there is
measured demand" have the same words in the same order, and only the grammar
gives the difference.

<!-- ste-enable STE-3.6 -->

Go has no library that gives the grammar of English with a trained model.
spaCy does. Thus the grammar comes from this program, and not from the
binary.

## Use

```bash
ste analyzer                 # what it needs, and the commands to install it
ste lint --analyze docs/     # use it
```

`ste analyzer` gives the answer for your computer:

```text
The analyzer cannot run: spaCy is not installed for /usr/bin/python3

To make it work:
  uv pip install spacy
  /usr/bin/python3 -m spacy download en_core_web_sm
```

The binary holds the analyzer, thus you need no file from this repository.
The tool writes it to the cache directory and starts it. `$STE_PYTHON`
gives a different interpreter, and `analyzer: true` in the config makes
`--analyze` the default.

The command starts the program one time for each run, thus the model loads
one time. The command sends only the sentences of a possible finding, and it
keeps the answer for each sentence, thus a large repository stays fast.

| Run of 180 files | Findings | Time |
|---|---|---|
| No analyzer | 1070 | 0.24s |
| With the analyzer | 1044 | 1.30s |

<!-- ste-disable-next-line STE-3.6 -->
The analyzer removed 26 wrong findings of rule 3.6, such as "there is
measured user demand", where "measured" is an adjective of "demand".

## The rules that use it

| Rule | Use |
|---|---|
| 3.6 passive voice | A veto. The finding goes when the parser sees no passive relation. |

Each rule works without the analyzer. The analyzer makes a rule more exact,
and it is never necessary.

## The protocol

One JSON object for each line, in both directions:

```
in : {"id": 1, "text": "The valve is closed by the operator."}
out: {"id": 1, "tokens": [{"i":0,"text":"The","pos":"DET","dep":"det",
                           "head":1,"start":0}, ...]}
```

The program gives `{"ready": true}` first. `{"stop": true}` ends it. Thus a
different program can replace spaCy: it must only give a part of speech and
a relation for each token. `internal/analyzer/testdata/stub_analyzer.py` is
an example that needs no library. `--analyzer "<command>"` gives your own
program to the tool.
