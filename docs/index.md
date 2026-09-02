---
title: ste
description: A deterministic ASD-STE100 checker for Markdown and plain text.
---

# ste

`ste` finds high-confidence ASD-STE100 (Simplified Technical English)
violations in Markdown and plain text.

It is one Go binary with no dependencies. It gives you the rule identifier,
the exact character range, a message, a severity, and a confidence value for
each finding. A person or a machine can then make the correction.

The rule numbers agree with ASD-STE100 Issue 9.

**It is an aid for a writer. It is not an ASD-certified checker.** It has 11
checks. The specification has 53 rules and a dictionary of approved words,
and this tool does not contain that dictionary. Read
[the limits](#limits) before you use it.

- [Source code](https://github.com/TudorAndrei/ste-cli)
- [The rules and their limits](rules.md)
- [The measurement of the rule quality](evaluation.md)
- [The audit of the related projects](upstream-audit.md)

## Installation

### With mise

The GitHub backend of [mise](https://mise.jdx.dev) gets the binary from the
releases of this repository:

```bash
mise use -g github:TudorAndrei/ste-cli        # the newest release
mise use -g github:TudorAndrei/ste-cli@0.2.1  # one version
ste version
```

To pin the tool for one project, put this in the `mise.toml` of that
project:

```toml
[tools]
"github:TudorAndrei/ste-cli" = "latest"
```

mise finds the correct asset for your platform without an option. Each
release also has a `checksums.txt` file, thus mise can verify the download
and write it to `mise.lock`. There are binaries for macOS (arm64, x64),
Linux (arm64, x64), and Windows (x64).

### With Go

```bash
go install github.com/TudorAndrei/ste-cli/cmd/ste@latest
```

### From the source

```bash
git clone https://github.com/TudorAndrei/ste-cli
cd ste-cli
mise install
mise run build      # writes bin/ste
```

## First steps

Give the tool a file, a directory, or standard input:

```bash
ste lint README.md
ste lint docs/
cat draft.md | ste lint -
```

A directory gives all `.md`, `.markdown`, and `.txt` files below it, but it
does not give:

- a file that git ignores, in a git repository. The tool asks git, thus the
  full syntax of `.gitignore` applies.
- `node_modules`, `vendor`, `dist`, `build`, `target`, `bin`, `obj`, `out`,
  `coverage`, `__pycache__`, or a directory whose name starts with a
  period.

A file or a directory that you give by its path is always read. `--all`
removes both filters.

The text output has one line for each finding, and then a summary:

```text
draft.md:3:15: warning [STE-8.1] The semicolon is the one punctuation mark that ASD-STE100 does not approve.
    Write two sentences, or use a list.
draft.md:3:48: warning [STE-4.2] The contraction "isn't" is not approved.
    Write "is not".

2 findings in 42 words of 1 file (4.76 for each 100 words)
```

The last number is the score: the number of findings for each 100 words.

## Modes

| Mode | Findings | Severity |
|---|---|---|
| `flavored` (default) | Confidence of 0.60 or more | as given by the rule |
| `strict` | all | one step stronger |

```bash
ste lint --mode strict procedures/
```

Use `flavored` for a README or a design document. Use `strict` for a
procedure, where a wrong instruction has a cost.

The mode does **not** change the sentence limit. ASD-STE100 selects the
limit from the type of the sentence:

| Sentence | Limit | Rule |
|---|---|---|
| An instruction in a procedure (a numbered list item) | 20 words | 5.1 |
| A note (a line that starts with "NOTE:") | 25 words | 5.5 |
| Descriptive text | 25 words | 6.3 |

`--max-words` replaces both limits.

## The glossary

Each project has technical words that are correct for that project. The
glossary permits them, and it does not make the grammar rules weaker.

The tool reads the first of `.ste.yml`, `.ste.yaml`, `glossary.yml`, or
`docs/glossary.yml` in the current directory.

```yaml
mode: flavored
max_words: 25
allow:
  nouns: [parser, webhook]
  verbs: [provision]
disable_rules: [STE-1.1]
```

| Key | Function |
|---|---|
| `mode` | `flavored` or `strict` |
| `max_words` | An optional sentence limit that replaces both limits |
| `allow.nouns` | The technical nouns of the project |
| `allow.verbs` | The technical verbs of the project |
| `disable_rules` | The rule identifiers to remove from the results |

The reader accepts only this subset of YAML: scalars, block lists, inline
lists, comments, and one level of nested keys. Thus the tool keeps no
dependencies.

`--config <path>` reads a different file. `--no-config` reads no file.

## Use in CI

The JSON output gives the rule identifier, the message, the severity, the
confidence, the byte offsets, the line, the column, and the suggestion:

```bash
ste lint --format json docs/
```

```json
{
  "version": 1,
  "mode": "flavored",
  "files": [
    {
      "path": "docs/draft.md",
      "words": 42,
      "findings": [
        {
          "rule_id": "STE-8.1",
          "message": "The semicolon is the one punctuation mark that ASD-STE100 does not approve.",
          "severity": "warning",
          "confidence": 1,
          "start": 23,
          "end": 24,
          "suggestion": "Write two sentences, or use a list.",
          "file": "docs/draft.md",
          "line": 3,
          "column": 15,
          "text": ";"
        }
      ]
    }
  ],
  "summary": { "files": 1, "words": 42, "findings": 1, "score": 2.38 }
}
```

`--fail-over` gives a non-zero exit code when the score is too high. A
gate on the score, and not on the count, permits a long document.

```bash
ste lint --fail-over 2.5 docs/
```

| Exit code | Condition |
|---|---|
| 0 | The tool ran. Findings do not change this code. |
| 1 | You give `--fail-over`, and the score is more than the limit. |
| 2 | A flag, a file, or the glossary has an error. |

A GitHub Actions step:

```yaml
- uses: jdx/mise-action@v4
- run: mise use -g github:TudorAndrei/ste-cli
- run: ste lint --fail-over 2.5 docs/
```

## What the tool does not examine

The tool replaces these spans with spaces before it applies the rules, thus
it does not report a violation in your code examples:

- fenced code blocks (```` ``` ```` and `~~~`)
- indented code blocks (4 or more spaces after an empty line)
- inline code
- link targets, autolinks, and bare URLs

A heading, an empty line, and the start of a list item are sentence
boundaries. A list item keeps the lines that continue it. Each cell of a
table row is a different sentence.

The tool counts a word with the rules of section 8. A hyphenated word, a
quantity with its unit, a quoted string, and text in parentheses each count
as one word.

## The rules

| Rule | Name | Example that it reports |
|---|---|---|
| `STE-1.1` | Unapproved word or word group | "Utilize the tool in order to start" |
| `STE-1.14` | British spelling | "colour", "centre" |
| `STE-3.4` | Complex verb construction | "has been sent" |
| `STE-3.5` | Progressive "-ing" form | "is still running" |
| `STE-3.6` | Passive voice | "was approved by the manager" |
| `STE-3.7` | A noun for an action | "do a check of" |
| `STE-4.2` | Contraction | "isn't" |
| `STE-5.1` | Sentence too long | a 26-word sentence |
| `STE-8.1` | Semicolon | "Open the valve; then start the pump" |
| `STE-9.3` | Phrasal verb | "carry out the test" |
| `STE-GR-6` | Latin abbreviation | "e.g." |

A check with the `GR` prefix is a general recommendation of the standard. A
general recommendation is advice and not a rule. Thus this tool gives it
the `info` severity.

[rules.md](rules.md) gives each rule, its confidence values, and its known
limits.

## Commands

```text
ste lint [flags] [path ...]   Check files, directories, or standard input
ste eval [flags] <dir>        Measure the rules against a labeled corpus
ste version                   Print the version
ste help                      Print the usage
```

| Lint flag | Function |
|---|---|
| `--mode` | `flavored` (default) or `strict` |
| `--format` | `text` (default) or `json` |
| `--fail-over` | Exit with code 1 when the score is more than this value |
| `--max-words` | Replace the sentence limit of both sentence types |
| `--config` | Path of the glossary file |
| `--no-config` | Do not read a glossary file |
| `--all` | Read every file, and not only the files that git shows |

A flag can come before or after a path.

## Measure the rules

`ste eval` measures the precision and the recall for each rule against a
labeled corpus. A fixture file can have a `<name>.expected.json` file with
the findings that the tool must give. A file with no expectation file must
give no findings.

```bash
ste eval testdata
```

```text
rule          tp    fp    fn  precision   recall
STE-1.1        2     0     0       1.00     1.00
STE-3.6        1     0     0       1.00     1.00
all           20     0     0       1.00     1.00
```

[evaluation.md](evaluation.md) gives the measurements and says why the
number on a self-written corpus is weak.

## Limits

- The tool has no part-of-speech tagger. It uses word lists and short word
  sequences. Thus it does not find all violations, and some findings are
  wrong.
- The tool does **not** have the ASD-STE100 approved-word dictionary. It
  cannot tell you if the standard approves a word.
  [upstream-audit.md](upstream-audit.md) gives the reason.
- Recall on new text is low, because the tool has 11 checks and the
  standard has 53 rules.
- ASD-STE100 is a specification of the AeroSpace and Defence Industries
  Association of Europe. This project is not part of ASD, and it does not
  contain the specification.

## Inspirations

This project started with an audit of the tools that came before it. Each
one gave an idea. No code and no data from these projects is in this
repository. [upstream-audit.md](upstream-audit.md) records the license, the
commit, and the decision for each one.

| Project | What it gave to this project |
|---|---|
| [stazelabs/ste](https://github.com/stazelabs/ste) | The nearest reference: a Go CLI with no dependencies, byte spans, JSON output, and the score for each 100 words. Its README is also one of the text samples that found false positives in these rules. |
| [valeratrades/ste_checker](https://github.com/valeratrades/ste_checker) | The glossary workflow, and a labeled test corpus with a truth file. |
| [sourdough-bread/asd-ste100-checker](https://github.com/sourdough-bread/asd-ste100-checker) | The structured result format with a rule identifier for each finding, and the MCP and LSP interfaces for a later version. |
| [swarooppatilx/ste100](https://github.com/swarooppatilx/ste100) | One test file for each rule, and annotated sample documents. |
| [openste/openste](https://github.com/openste/openste) | An open word list with a part of speech for each word. This project does not use the data, because the provenance is not clear. |
| [TechScribe term checker](https://www.simplified-english.co.uk/design.html) | The key idea that a technical noun and a technical verb need different project configuration. `allow.nouns` and `allow.verbs` come from this. |

## License and the specification

The specification is the property of the AeroSpace and Defence Industries
Association of Europe. To get it, go to
[asd-ste100.org](https://www.asd-ste100.org/). This tool does not give you
the specification, and it does not give you certification.
