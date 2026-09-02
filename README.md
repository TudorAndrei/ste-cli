# ste

`ste` finds high-confidence ASD-STE100 (Simplified Technical English)
violations in Markdown and plain text.

It is one Go binary with 3 dependencies. It has 11 checks. The standard has
53 rules and a dictionary. The rule numbers agree with ASD-STE100 Issue 9.
It is an aid for a writer. **It is not an ASD-certified checker.**

Documentation: <https://tudorandrei.github.io/ste-cli/>

## Installation

### With mise

The GitHub backend of [mise](https://mise.jdx.dev) gets the binary from the
GitHub releases of this repository:

```bash
mise use -g github:TudorAndrei/ste-cli        # the newest release
mise use -g github:TudorAndrei/ste-cli@0.4.0  # one version
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
`ste-0.4.0-darwin-arm64.tar.gz` and `ste-0.4.0-linux-x64.tar.gz`. Each
release also has a `checksums.txt` file, thus mise can verify the download
and write it to `mise.lock`.

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
ste baseline .                    # accept the findings of today
ste lint --fail-on-new docs/      # block only a new violation
ste lint --mode strict --format json docs/
cat draft.md | ste lint -
ste eval testdata
```

A path can be a file or a directory. A directory gives all `.md`,
`.markdown`, and `.txt` files below it. A path of `-` reads standard input.

A walk of a directory does not give:

- a file that git ignores, in a git repository. The tool asks git, thus the
  full syntax of `.gitignore` applies.
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
  ask for a gate with `--fail-on-new` or `--fail-over`.
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
```

An unknown key is an error, thus a spelling mistake does not stay hidden.

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

All 3 are pure Go, thus the build needs no C compiler and it stays one
binary for each platform.

## Structure

```text
cmd/ste/                  the command
internal/checker/         the parser and the entry point
internal/checker/rules/   the rules and their data
internal/config/          the glossary reader
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
git tag v0.4.0
git push origin v0.4.0
```

To make the same archives on your computer:

```bash
mise run dist       # writes dist/
```

The version in the binary comes from the tag:
`go build -ldflags "-X main.Version=0.4.0"`. A build from the source
without that flag says `dev`.

## Limits

- The tool has no part-of-speech tagger. It uses word lists and short word
  sequences.
- The tool does **not** have the ASD-STE100 approved-word dictionary. It
  cannot tell you if the standard approves a word. See
  [docs/upstream-audit.md](docs/upstream-audit.md) for the reason.
- Precision and recall are in [docs/evaluation.md](docs/evaluation.md).
  Recall on new text is low, because the tool has 11 checks and the standard
  has 53 rules.
- ASD-STE100 is a specification of the AeroSpace and Defence Industries
  Association of Europe. This project is not part of ASD, and it does not
  contain the specification.
