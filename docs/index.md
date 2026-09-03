---
title: ste
description: A deterministic ASD-STE100 checker for Markdown and plain text. Start with a baseline, and block only a new violation.
---

# ste

`ste` finds high-confidence ASD-STE100 (Simplified Technical English)
violations in Markdown and plain text.

It is one Go binary with 4 dependencies. It gives you the rule identifier,
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
mise use -g github:TudorAndrei/ste-cli@0.6.0  # one version
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

The tool always reads a file or a directory that you give by its path.
`--all` removes both filters.

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

## How to adopt it

A checker that reports 1000 findings on its first day is a checker that a
team removes. This tool is an aid, and not a gate:

- It exits with code 0 even when it finds something. It blocks only when you
  ask for a gate with `--fail-on-new`, `--warnings-as-errors`, or
  `--fail-over`.
- A baseline accepts the findings that exist today, thus only a new finding
  comes to your attention.
- Each rule has its own severity, thus you can accept the rules one at a
  time.
- A wrong finding has three escape hatches: a comment in the text, a rule in
  the config, or a path in `exclude`.

The sequence for a repository that has documentation already:

```bash
ste lint .                    # see the size of the problem
ste baseline .                # accept it, and write .ste-baseline.json
ste lint --fail-on-new .      # from now, only a new violation fails
```

The number in the baseline goes down when you correct the text. Write the
file again with `ste baseline .` to record the new, lower number.

### Silence one finding in the text

```markdown
<!-- ste-disable-next-line -->
This sentence is not checked.

The tool does not check this line. <!-- ste-disable-line STE-3.6 -->

<!-- ste-disable STE-8.1 -->
The tool does not check this block.
<!-- ste-enable STE-8.1 -->
```

A directive with no rule identifier applies to every rule. A directive with
no `ste-enable` applies to the end of the file.

### The three gates

| Gate | Blocks when |
|---|---|
| `--fail-on-new` | A finding is not in the baseline |
| `--warnings-as-errors` | A finding has the warning severity, which becomes an error. An info finding stays advice. |
| `--fail-over <n>` | The score for each 100 words is more than n |

A gate reads the report after the baseline, thus an accepted finding never
blocks. You can give more than one gate.

## The dictionary

ASD-STE100 has two parts. This tool has the writing rules of part 1. Part 2
is the dictionary: about 900 approved words, and about 1300 words that the
standard does not approve, each with its approved alternative. Rule 1.1 needs that dictionary.

**This tool does not ship the dictionary.** The specification is the
property of ASD, and its terms permit no reproduction or publication without
written authority. But ASD gives the specification **free of charge** to
each writer and user at [asd-ste100.org](https://www.asd-ste100.org), thus
you can make the index from your own copy:

```bash
# 1. Get your own copy from asd-ste100.org, then make the text:
npx -y @firecrawl/anydoc ASD-STE100_ISSUE9.pdf -o ste100.md

# 2. Make the index. It goes in your cache directory, not in the project.
ste dict import ste100.md

# 3. Rule STE-1.1 uses it only when you ask:
ste lint --use-dict docs/
```

`dictionary: true` in the config does the same as `--use-dict`. `ste dict
info` shows the index, and `ste dict remove` deletes it.

### One import for each machine

The index is global. Import it one time, and each project on that machine
reads the same file. No lint run reads the specification again: the run
reads a JSON index of about 135 kB, thus the dictionary adds no measurable
time.

The index is data, and not a cache, because this tool cannot make it again
without your copy. Thus it goes in the data directory of the XDG
specification:

| Path | Condition |
|---|---|
| `$STE_DICT` | an explicit path |
| `$XDG_DATA_HOME/ste/dictionary.json` | you give that variable |
| `~/.local/share/ste/dictionary.json` | Linux and BSD |
| `~/Library/Application Support/ste/dictionary.json` | macOS |

`ste dict path` prints the path that applies.

### The dictionary is off by default, and this is why

ASD-STE100 approves about 900 words, for the maintenance of an aircraft. Ordinary software documentation uses many words that this
dictionary does not approve: "state", "file", "build", "should". On a
repository of 180 files, the rules of part 1 gave 1037 findings, and the
same repository with the dictionary gave **9490**.

The dictionary is correct. It is also too much for a README. Use it for a
procedure, and use the baseline and `min_confidence` for the rest.

### The technical nouns of your field

ASD-STE100 is a language for the maintenance of an aircraft. Its dictionary
does not approve "hook", "file", "build", or "graph", because those words
are not part of that field. Rule 1.5 of the standard gives 22 categories of
technical noun, and category 19 is computer science and information
technology. Thus a writer of software documentation is permitted to use the
technical nouns of software.

```yaml
presets: [software]     # or: ste lint --preset software
```

The preset holds about 170 technical nouns of software and of information
technology. On one repository of 180 files, the dictionary gave 8213
findings, and the dictionary with this preset gave 6709.

### What the tool cannot know

The dictionary gives a part of speech for each word, and this tool has no
part-of-speech tagger. "graph" is an example: the dictionary does not
approve the **verb** "graph", but "a graph" is a correct technical noun.

The tool uses the shape of the sentence in place of a tagger: a determiner
in the same noun phrase makes the word a noun. Thus "The dependency graph
is large" gives no finding, and "Graph the test results" gives one. A modal
verb ends the phrase, thus "The tool can graph the results" gives a finding
too.

The test is not perfect. A word that the dictionary has only as a verb gets
a confidence of 0.60. The other words get 0.95. Thus `min_confidence: 0.7`
removes the first class.

The glossary is the correct answer for your technical nouns. Rule 1.6 and
rule 1.8 of the standard tell you to do the same:

```yaml
allow:
  nouns: [pump, valve, actuator]
```

## Config

The tool reads the first of `.ste.yml`, `.ste.yaml`, `glossary.yml`, or
`docs/glossary.yml`. Every key is optional.

```yaml
mode: flavored          # or strict

rules:                  # off, info, warning, or error
  STE-8.1: error        # your text already obeys this rule
  STE-3.6: info         # this rule needs a rewrite, thus only advice today
  STE-5.1: off          # this rule comes later

exclude:                # the tool also skips the files that git ignores
  - "**/fixtures/**"
  - "*.generated.md"

allow:                  # the technical words of your project
  nouns: [parser, webhook]
  verbs: [provision]

min_confidence: 0.6     # remove each finding below this value
max_words: 25           # replace the sentence limits of the standard
baseline: .ste-baseline.json
fail_over: 2.5          # without this key, the tool never blocks
warnings_as_errors: false
```

| Key | Function |
|---|---|
| `mode` | `flavored` or `strict` |
| `rules` | The severity of one rule: `off`, `info`, `warning`, or `error` |
| `exclude` | The path patterns that the tool does not read |
| `allow.nouns` | The technical nouns of the project |
| `allow.verbs` | The technical verbs of the project |
| `min_confidence` | Remove each finding below this value |
| `max_words` | Replace the sentence limits of the standard |
| `baseline` | The path of the file of accepted findings |
| `fail_over` | The score that makes the command exit with code 1 |
| `warnings_as_errors` | Make each warning an error, and exit with code 1 |
| `dictionary` | Use the imported ASD-STE100 dictionary for rule STE-1.1 |
| `presets` | The subject fields whose technical nouns are permitted |

An unknown key is an error, thus a spelling mistake does not stay hidden.
`--config <path>` reads a different file, and `--no-config` reads no file.

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
| 1 | You gave a gate (`--fail-on-new` or `--fail-over`) and the text does not pass it. |
| 2 | A flag, a file, or the glossary has an error. |

A GitHub Actions step:

```yaml
- uses: jdx/mise-action@v4
- run: mise use -g github:TudorAndrei/ste-cli
- run: ste lint --fail-on-new docs/
```

`--fail-on-new` is the correct gate for a repository that has documentation
already. The findings in the baseline do not stop the work. A new violation
does.

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

<!-- ste-disable -->

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

<!-- ste-enable -->

A check with the `GR` prefix is a general recommendation of the standard. A
general recommendation is advice and not a rule. Thus this tool gives it
the `info` severity.

[rules.md](rules.md) gives each rule, its confidence values, and its known
limits.

## For an agent

An agent is a first-class reader of this tool. `ste schema` prints the full
interface as JSON. It gives each command and each flag, with the permitted
values. It also gives each config key, each rule with its number in the
standard, the fields of a finding, and the exit codes.

```bash
ste schema                                     # what this tool accepts
ste lint --format json --summary docs/         # 226 bytes, not 4 MB
ste lint --format json --limit 20 --fields rule_id,file,line,text docs/
ste lint --format ndjson docs/                 # one object for each line
ste baseline --dry-run --format json .         # the plan, and no change
```

[AGENTS.md](https://github.com/TudorAndrei/ste-cli/blob/main/AGENTS.md)
gives the rules for an agent. It tells how to keep the output small, why
exit code 0 is not proof of a clean document, and which findings need a
person.

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
| `--no-config` | Do not read a config file |
| `--baseline` | Path of the file of accepted findings |
| `--fail-on-new` | Exit with code 1 when a finding is not in the baseline |
| `--warnings-as-errors` | Make each warning an error, and exit with code 1 |
| `--use-dict` | Use the imported ASD-STE100 dictionary for rule STE-1.1 |
| `--preset` | Add the technical nouns of a subject field: `software` |
| `--dict` | Path of the dictionary index |
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

## What the tool does not check

ASD-STE100 has 53 rules. This tool checks 11 of them today, and about 31 can
have a mechanical answer. The other rules need a reader: "Make sure that each
paragraph has only one topic" is an example.

[coverage.md](coverage.md) gives each rule and its group. The
[ste-review skill](https://github.com/TudorAndrei/ste-cli/tree/main/skill)
gives the rules of judgment to an agent, which reports them as advice, and
not as a defect.

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
