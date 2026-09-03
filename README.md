# ste

`ste` finds high-confidence ASD-STE100 (Simplified Technical English)
violations in Markdown and plain text.

It is one Go binary with 4 dependencies. It has 15 checks. The standard has
53 rules and a dictionary. The rule numbers agree with ASD-STE100 Issue 9.
It is an aid for a writer. **It is not an ASD-certified checker.**

Documentation: <https://tudorandrei.github.io/ste-cli/>

## Installation

### With mise

The GitHub backend of [mise](https://mise.jdx.dev) gets the binary from the
GitHub releases of this repository:

```bash
mise use -g github:TudorAndrei/ste-cli        # the newest release
mise use -g github:TudorAndrei/ste-cli@0.7.0  # one version
ste version
```

To pin the tool for one project, put this in the `mise.toml` of that
project:

```toml
[tools]
"github:TudorAndrei/ste-cli" = "latest"
```

mise finds the correct asset for your platform without an option. The
archive names use the words that its asset matcher knows, for example
`ste-0.7.0-darwin-arm64.tar.gz` and `ste-0.7.0-linux-x64.tar.gz`. Each
Each release also has a `checksums.txt` file. mise verifies the download
against it and records the result in `mise.lock`.

The releases give binaries for macOS (arm64, x64), Linux (arm64, x64), and
Windows (x64).

### With Go

This path does not need a release:

```bash
mise use -g "go:github.com/TudorAndrei/ste-cli/cmd/ste"
# or
go install github.com/TudorAndrei/ste-cli/cmd/ste@latest
```

### From the source

```bash
mise install        # gets the Go version from mise.toml
mise run build      # writes bin/ste
```

## Usage

```bash
ste lint README.md
ste dict import ste100.md         # your own copy of the standard
ste baseline .                    # accept the findings of today
ste lint --fail-on-new docs/      # block only a new violation
ste lint --mode strict --format json docs/
cat draft.md | ste lint -
ste eval testdata
```

A path can be a file or a directory. A directory gives all `.md`,
`.markdown`, and `.txt` files below it. A path of `-` reads standard input.

A walk of a directory does not give:

- a file that git ignores, in a git repository. The tool asks git itself,
  so the full syntax of `.gitignore` applies.
- `node_modules`, `vendor`, `dist`, `build`, `target`, `bin`, `obj`, `out`,
  `coverage`, `__pycache__`, or a directory whose name starts with a
  period.

The tool always reads a file or a directory that you give by its path.
`--all` removes both filters.

### Flags of the lint command

| Flag | Function |
|---|---|
| `--mode` | `flavored` (default) or `strict` |
| `--format` | `text` (default) or `json` |
| `--fail-over` | Exit with code 1 when the score is more than this value |
| `--max-words` | Replace the sentence limit of both sentence types |
| `--config` | Path of the glossary file |
| `--no-config` | Do not read a config file |
| `--baseline` | Path of the file of accepted findings |
| `--no-baseline` | Report every finding, and not only the new ones |
| `--fail-on-new` | Exit with code 1 when a finding is not in the baseline |
| `--warnings-as-errors` | Make each warning an error, and exit with code 1 |
| `--use-dict` | Use the imported ASD-STE100 dictionary for rule STE-1.1 |
| `--preset` | Add the technical nouns of a subject field: `software` |
| `--analyze` | Use the analyzer for the rules that need the grammar of a sentence |
| `--analyzer` | Command of a different analyzer |
| `--dict` | Path of the dictionary index |
| `--all` | Read every file, and not only the files that git shows |

### Exit codes

| Code | Condition |
|---|---|
| 0 | The tool ran. Findings do not change this code. |
| 1 | You gave a gate (`--fail-on-new` or `--fail-over`) and the text does not pass it. |
| 2 | A flag, a file, or the glossary has an error. |

The score is the number of findings for each 100 words.

## Modes

| Mode | Findings | Severity |
|---|---|---|
| `flavored` | Confidence of 0.60 or more | as given by the rule |
| `strict` | all | one step stronger |

The mode does **not** change the sentence limit. ASD-STE100 selects the
limit from the type of the sentence. An instruction in a procedure gets 20
words (rule 5.1). A note and descriptive text get 25 words (rules 5.5 and
6.3). The tool reads the structure of the Markdown: a numbered list item is
an instruction. `--max-words` replaces both limits.

## How to adopt it

A checker that reports 1000 findings on its first day is a checker that a
team removes. This tool is an aid, and not a gate:

- It exits with code 0 even when it finds something. It blocks only when you
  ask for a gate with `--fail-on-new`, `--warnings-as-errors`, or
  `--fail-over`.
- A baseline accepts the findings that exist today. Only a new finding
  reaches you after that.
- Each rule has its own severity. You can accept the rules one at a time.
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

A gate reads the report after the baseline. An accepted finding never
blocks. You can give more than one gate.

## The dictionary

ASD-STE100 has two parts. This tool has the writing rules of part 1. Part 2
is the dictionary: about 900 approved words, and about 1300 words that the
standard does not approve, each with its approved alternative. Rule 1.1 needs that dictionary.

**This tool does not ship the dictionary.** The specification is the
property of ASD, and its terms permit no reproduction or publication without
written authority. But ASD gives the specification **free of charge** to
each writer and user at [asd-ste100.org](https://www.asd-ste100.org). You
make the index from your own copy:

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
reads a JSON index of about 135 kB. The dictionary adds no measurable
time to a run.

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
A modal verb ends the phrase, and "The tool can graph the results" gives a
finding.

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
  STE-3.6: info         # this rule needs a rewrite. Advice for today.
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

An unknown key is an error. A spelling mistake in the file never stays
hidden.

## Output

The text format gives one line for each finding, and then a summary:

```text
draft.md:3:15: warning [STE-8.1] The semicolon is the one punctuation mark that ASD-STE100 does not approve.
    Write two sentences, or use a list.

1 finding in 42 words of 1 file (2.38 for each 100 words)
```

The JSON format gives the rule identifier, the message, the severity, the
confidence, the byte offsets, the line and the column, and the suggestion.
A CI job can read it.

## Rules

See [docs/rules.md](docs/rules.md) for each check, its confidence values,
and its limits. The numbers are the rule numbers of Issue 9.

| Rule | Name |
|---|---|
| `STE-1.1` | Unapproved word or word group |
| `STE-1.14` | British spelling |
| `STE-3.4` | Complex verb construction (perfect tense) |
| `STE-3.5` | Progressive "-ing" form |
| `STE-3.6` | Passive voice |
| `STE-3.7` | A noun for an action |
| `STE-4.2` | Contraction |
| `STE-4.3` | A list with two constructions |
| `STE-5.5` | An instruction in a note |
| `STE-6.6` | Paragraph too long |
| `STE-7.3` | A safety instruction with no explanation |
| `STE-5.1` | Sentence too long |
| `STE-8.1` | Semicolon |
| `STE-9.3` | Phrasal verb |
| `STE-GR-6` | Latin abbreviation (a general recommendation, not a rule) |

## Dependencies

| Module | License | Function |
|---|---|---|
| [goldmark](https://github.com/yuin/goldmark) | MIT | Reads the Markdown. It follows CommonMark 0.31.2, and its syntax tree keeps the byte offsets that each finding needs. |
| [go-yaml](https://github.com/goccy/go-yaml) | MIT | Reads the glossary file. |
| [pflag](https://github.com/spf13/pflag) | BSD-3-Clause | Reads the command flags. |
| [xdg](https://github.com/adrg/xdg) | MIT | Gives the data directory of the user for each system. |

All 4 are pure Go. The build needs no C compiler, and it gives one binary
for each platform.

## More exact rules with an analyzer

<!-- ste-disable STE-3.6 -->

Some rules need the grammar of a sentence. "The demand is measured" and
"there is measured demand" have the same words, and only the grammar gives
the difference.

<!-- ste-enable STE-3.6 --> Go has no library that gives the grammar of English with a
trained model. An external program gives it:

```bash
ste analyzer                 # what it needs, and how to install it
ste lint --analyze docs/     # use it
```

The command sends only the sentences of a possible finding, and it keeps
each answer. On a repository of 180 files, the analyzer removed 26 wrong
findings of rule 3.6, and the run went from 0.24s to 1.30s.

The analyzer is never necessary. Each rule also works without it, and the
command stays one binary with no runtime.

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

## Structure

```text
cmd/ste/                  the command
internal/checker/         the parser and the entry point
internal/checker/rules/   the rules and their data
internal/config/          the glossary reader
internal/dict/            the reader of the dictionary of the user
internal/eval/            the measurement of the rules
internal/report/          the text and JSON output
testdata/                 the labeled corpus
docs/                     the rules, the audit, and the measurement
```

## Tests

```bash
mise run check      # gofmt, go vet, go test
mise run ci         # the same, but no file changes: gofmt only reports
```

Result on 2026-09-02: all tests pass. 6 packages, 0 failures.

## Release

A tag that starts with `v` starts the release workflow in
`.github/workflows/release.yml`. The workflow runs the tests, builds the
archives for the 5 platforms, and makes the GitHub release with a
`checksums.txt` file.

```bash
git tag v0.7.0
git push origin v0.7.0
```

To make the same archives on your computer:

```bash
mise run dist       # writes dist/
```

The version in the binary comes from the tag:
`go build -ldflags "-X main.Version=0.7.0"`. A build from the source
without that flag says `dev`.

## What the tool does not check

ASD-STE100 has 53 rules. This tool checks 15 of them today, and about 31 can
have a mechanical answer. The other rules need a reader: "Make sure that each
paragraph has only one topic" is an example.

[docs/coverage.md](docs/coverage.md) gives each rule and its group. The
[ste-review skill](https://github.com/TudorAndrei/ste-cli/tree/main/skill)
gives the rules of judgment to an agent, which reports them as advice, and
not as a defect.

## Limits

- The tool has no part-of-speech tagger. It uses word lists and short word
  sequences.
- The tool does **not** ship the ASD-STE100 approved-word dictionary. Its
  own list holds 27 words and 11 word groups. `ste dict import` makes an
  index from your copy
  of the specification, and `--use-dict` then gives rule 1.1 the full list.
  See [docs/upstream-audit.md](docs/upstream-audit.md) for the reason that
  the tool cannot ship it.
- Precision and recall are in [docs/evaluation.md](docs/evaluation.md).
  Recall on new text is low, because the tool has 15 checks and the standard
  has 53 rules.
- ASD-STE100 is a specification of the AeroSpace and Defence Industries
  Association of Europe. This project is not part of ASD, and it does not
  contain the specification.
