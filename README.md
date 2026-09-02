# ste

`ste` finds high-confidence ASD-STE100 (Simplified Technical English)
violations in Markdown and plain text.

It is one Go program with no dependencies. It has 8 rules, not the 53 rules
of the standard. It is an aid for a writer. **It is not an ASD-certified
checker.**

## Installation

The project uses [mise](https://mise.jdx.dev) for its toolchain.

```bash
mise install
mise run build      # writes bin/ste
```

Or use Go directly:

```bash
go install ./cmd/ste
```

## Usage

```bash
ste lint README.md
ste lint --mode strict --format json docs/
ste lint --fail-over 2.5 draft.md
cat draft.md | ste lint -
ste eval testdata
```

A path can be a file or a directory. A directory gives all `.md`,
`.markdown`, and `.txt` files below it. A path of `-` reads standard input.

### Flags of the lint command

| Flag | Function |
|---|---|
| `--mode` | `flavored` (default) or `strict` |
| `--format` | `text` (default) or `json` |
| `--fail-over` | Exit with code 1 when the score is more than this value |
| `--max-words` | Replace the sentence limit of the mode |
| `--config` | Path of the glossary file |
| `--no-config` | Do not read a glossary file |

### Exit codes

| Code | Condition |
|---|---|
| 0 | The tool ran. Findings do not change this code. |
| 1 | You give `--fail-over`, and the score is more than the limit. |
| 2 | A flag, a file, or the glossary has an error. |

The score is the number of findings for each 100 words.

## Modes

| Mode | Sentence limit | Findings | Severity |
|---|---|---|---|
| `flavored` | 25 words | Confidence of 0.60 or more | as given by the rule |
| `strict` | 20 words | all | one step stronger |

## Glossary

A project can permit its own technical words. The tool reads the first of
`.ste.yml`, `.ste.yaml`, `glossary.yml`, or `docs/glossary.yml` in the
current directory.

```yaml
mode: flavored
max_words: 25
allow:
  nouns: [parser, webhook]
  verbs: [provision]
disable_rules: [STE-1.1]
```

The reader accepts only this subset of YAML: scalars, block lists, inline
lists, comments, and one level of nested keys.

## Output

The text format gives one line for each finding, and then a summary:

```text
draft.md:3:15: warning [STE-8.1] The semicolon is not an approved punctuation mark.
    Write two sentences, or use a list.

1 finding in 42 words of 1 file (2.38 for each 100 words)
```

The JSON format gives the rule identifier, the message, the severity, the
confidence, the byte offsets, the line and the column, and the suggestion.
A CI job can read it.

## Rules

See [docs/rules.md](docs/rules.md) for the 8 rules, their confidence values,
and their limits.

| Rule | Name |
|---|---|
| `STE-1.1` | Unapproved word or word group |
| `STE-1.4` | Phrasal verb |
| `STE-3.1` | Perfect tense |
| `STE-3.2` | Passive voice |
| `STE-3.5` | Progressive "-ing" form |
| `STE-4.2` | Contraction |
| `STE-5.1` | Sentence too long |
| `STE-8.1` | Semicolon |

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
```

Result on 2026-09-02: all tests pass. 6 packages, 0 failures.

## Limits

- The tool has no part-of-speech tagger. It uses word lists and short word
  sequences.
- The tool does **not** have the ASD-STE100 approved-word dictionary. It
  cannot tell you if the standard approves a word. See
  [docs/upstream-audit.md](docs/upstream-audit.md) for the reason.
- Precision and recall are in [docs/evaluation.md](docs/evaluation.md).
  Recall on new text is low, because the tool has 8 rules of 53.
- ASD-STE100 is a specification of the AeroSpace and Defence Industries
  Association of Europe. This project is not part of ASD, and it does not
  contain the specification.
