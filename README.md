# ste

`ste` finds high-confidence ASD-STE100 (Simplified Technical English)
violations in Markdown and plain text.

It is a Python command with optional NLP analysis. It has 21 checks. The standard has
53 rules and a dictionary. The rule numbers agree with ASD-STE100 Issue 9.
It is an aid for a writer. **It is not an ASD-certified checker.**

Documentation: <https://tudorandrei.github.io/ste-cli/>

## Installation

Python 3.14 is necessary. Python 3.15 is not supported yet. Install from the repository with uv:

```bash
uv tool install git+https://github.com/TudorAndrei/ste-cli
ste version
```

To select a release, append its tag to the repository URL:

```bash
uv tool install git+https://github.com/TudorAndrei/ste-cli@v0.11.0
```

Each new Python release contains a wheel, a source archive, and
`checksums.txt`. You can also install a downloaded wheel:

```bash
uv tool install ./ste_cli-0.11.0-py3-none-any.whl
```

### From the source

```bash
git clone https://github.com/TudorAndrei/ste-cli
cd ste-cli
uv sync --locked
uv run ste version
```

### Optional NLP

Install spaCy and its English model in the project environment:

```bash
uv sync --extra nlp
uv run python -m spacy download en_core_web_sm
uv run ste lint --analyze docs/
```

Basic checks need no NLP model. The analyzer runs in the same Python process.
`--analyzer` can still select an external analyzer.

## Usage

```bash
ste lint README.md
ste init                          # write a start config, .ste.yml
ste dict import ste100.md         # your own copy of the standard
ste baseline .                    # accept the findings of today
ste lint --fail-on-new docs/      # block only a new violation
ste lint --mode strict --format json docs/
cat draft.md | ste lint -
ste eval testdata
```

A path can be a file or a directory. A directory gives all `.md`,
`.markdown`, and `.txt` files below it. A path of `-` reads standard input.
With no path, the command reads standard input from a pipe. In a terminal,
it asks for a path.

A walk of a directory does not give:

- a file that git ignores, in a git repository. The tool asks git itself,
  so the full syntax of `.gitignore` applies.
- `node_modules`, `vendor`, `dist`, `build`, `target`, `bin`, `obj`, `out`,
  `coverage`, `__pycache__`, or a directory whose name starts with a
  period.
- a file that a tool writes: `CHANGELOG`, `CHANGES`, `HISTORY`, `NEWS`, and
  `RELEASE-NOTES`, with any of the 3 extensions. A writer cannot correct
  text that the next release writes again.

The tool always reads a file or a directory that you give by its path. Only
`exclude` of the config applies to such a file, because a git hook gives
each changed file by its path. `--all` removes the other filters.

### Flags of the lint command

| Flag | Function |
|---|---|
| `--mode` | `flavored` (default) or `strict` |
| `--format` | `text` (default), `json`, `ndjson`, `sarif`, or `github` |
| `--limit` | Maximum number of findings in the output |
| `--fields` | The fields of a finding to give, separated by a comma |
| `--summary` | Give only the summary |
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
| `--dry-run` | For the baseline command: show the plan and write nothing |

A flag that a command does not use is an error.

### Exit codes

| Code | Condition |
|---|---|
| 0 | The tool ran. Findings do not change this code. |
| 1 | You gave a gate (`--fail-on-new`, `--warnings-as-errors`, or `--fail-over`) and the text does not pass it. |
| 2 | A flag, a file, or the glossary has an error. |

The score is the number of findings for each 100 words.

## Modes

| Mode | Findings | Severity |
|---|---|---|
| `flavored` | Confidence of 0.60 or more | as given by the rule |
| `strict` | all | one step stronger |

The mode does not change the sentence limit. ASD-STE100 selects the
limit from the type of the sentence. An instruction in a procedure gets 20
words (rule 5.1). A note and descriptive text get 25 words (rules 5.5 and
6.3). The tool reads the structure of the Markdown: a numbered list item is
an instruction. `--max-words` replaces both limits.

## How to adopt it

On a repository that has documentation, the first run can give 1000
findings. Thus the tool does not block a team by default:

- It exits with code 0 even when it finds something. It blocks only when you
  ask for a gate with `--fail-on-new`, `--warnings-as-errors`, or
  `--fail-over`.
- A baseline accepts the findings that exist today. Only a new finding
  reaches you after that.
- Each rule has its own severity. You can accept the rules one at a time.
- To remove a wrong finding, write a comment in the text, set the rule to
  `off` in the config, or add the path to `exclude`.

The sequence for a repository that has documentation already:

```bash
ste lint .                    # see the size of the problem
ste baseline .                # accept it, and write .ste-baseline.json
ste lint --fail-on-new .      # from now, only a new violation fails
```

The number in the baseline goes down when you correct the text. Write the
file again with `ste baseline .` to record the new, lower number. The
report gives the number of accepted findings that the text no longer has.

A baseline of one directory keeps the accepted findings of the other
directories, and it removes the accepted findings of a deleted file. The
file holds each path from its own directory. Thus a run from a
subdirectory, or a run with an absolute path, finds the same findings.

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
written authority. But ASD gives the specification free of charge to
each writer and user at [asd-ste100.org](https://www.asd-ste100.org). You
make the index from your own copy:

```bash
# 1. Get your own copy from asd-ste100.org, then make the text:
npx -y @firecrawl/anydoc@0.2.4 ASD-STE100_ISSUE9.pdf -o ste100.md

# 2. Make the index. It goes in your cache directory, not in the project.
ste dict import ste100.md

# 3. Rule STE-1.1 uses it only when you ask:
ste lint --use-dict docs/
```

The command pins anydoc 0.2.4. That version reads the PDF on your computer,
two runs give the same bytes, and `ste dict import` reads its output. A
different version can divide the text in a different way.

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
same repository with the dictionary gave 9490.

Use the dictionary for a procedure. For a README, it gives too many
findings. Use the baseline and `min_confidence` for the other documents.

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
approve the verb "graph", but "a graph" is a correct technical noun.

The tool uses the shape of the sentence in place of a tagger: a determiner
in the same noun phrase makes the word a noun. Thus "The dependency graph
is large" gives no finding, and "Graph the test results" gives one. A modal
verb ends the phrase, and "The tool can graph the results" gives a
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

`ste init` writes a start config, `.ste.yml`. The file changes nothing
until you edit it.

The tool reads the first of `.ste.yml`, `.ste.yaml`, `glossary.yml`, or
`docs/glossary.yml`. It looks in the current directory, then in each
directory above it, and it stops at the top of the git work tree. The
directory where the search stops is the project directory. A path in the
config and each `exclude` pattern start from that directory. Every key is
optional.

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

prefer:                 # rule STE-1.11: one name for each item
  "config file": ["settings file", "configuration file"]

min_confidence: 0.6     # remove each finding below this value
max_words: 25           # replace the sentence limits of the standard
max_noun_words: 3       # rule STE-1.9: the word limit of a technical noun
baseline: .ste-baseline.json
fail_over: 2.5          # without this key, the tool never blocks
warnings_as_errors: false
```

`disable_rules: [STE-5.1]` removes a list of rules. It does the same as
`off` in `rules`.

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

| Format | Reader |
|---|---|
| `text` | A person |
| `json` | A program. One object for the run, with one flat list of findings. |
| `ndjson` | A program that reads one finding for each line |
| `sarif` | GitHub code scanning, and each editor that reads SARIF 2.1.0 |
| `github` | GitHub Actions. Each finding shows on its line in the pull request. |

`sarif` and `github` give each path from the top of the git work tree, and
each column counts characters, because a code host counts so.

## Use in CI

This repository is also a GitHub Action. It installs a Python wheel and verifies it
against `checksums.txt`, and runs `ste lint` with the `github` format:

```yaml
- uses: actions/checkout@v7
- uses: TudorAndrei/ste-cli@main
  with:
    version: latest               # the release of ste to install
    args: --fail-on-new docs/     # the default is --fail-on-new .
```

For GitHub code scanning, write SARIF and send it with the
`github/codeql-action/upload-sarif` action:

```bash
ste lint --format sarif . > ste.sarif
```

The repository also has a hook for [pre-commit](https://pre-commit.com).
The hook installs the command with Python, and it gives `--fail-on-new`:

```yaml
repos:
  - repo: https://github.com/TudorAndrei/ste-cli
    rev: main                     # "pre-commit autoupdate" gives the newest tag
    hooks:
      - id: ste
```

## Rules

See [docs/rules.md](docs/rules.md) for each check, its confidence values,
and its limits. The numbers are the rule numbers of Issue 9.

| Rule | Name |
|---|---|
| `STE-1.1` | Unapproved word or word group |
| `STE-1.11` | Two names for the same item |
| `STE-1.14` | British spelling |
| `STE-2.1` | A noun of more than three words (needs the analyzer) |
| `STE-3.4` | Complex verb construction (perfect tense) |
| `STE-3.5` | Progressive "-ing" form |
| `STE-3.6` | Passive voice |
| `STE-3.7` | A noun for an action |
| `STE-4.2` | Contraction |
| `STE-4.3` | A list with two constructions |
| `STE-5.1` | Sentence too long |
| `STE-5.3` | An instruction that is not a command (needs the analyzer) |
| `STE-5.4` | A condition after the command |
| `STE-5.5` | An instruction in a note |
| `STE-6.6` | Paragraph too long |
| `STE-7.1` | A safety instruction with no word for the level of the risk |
| `STE-7.3` | A safety instruction with no explanation |
| `STE-8.1` | Semicolon |
| `STE-9.3` | Phrasal verb |
| `STE-GR-6` | Latin abbreviation (a general recommendation, not a rule) |

## Dependencies

- The markdown-it-py library reads CommonMark, tables, and strikethrough text.
- PyYAML reads the configuration.
- Typer reads the commands and flags, and supplies command help.
- The platformdirs library gives the data directory of the user.
- The spaCy library supplies optional grammar analysis.

Ruff checks and formats the source. ty checks types. Vulture finds unused code.
pytest runs the tests.
uv manages the environment, dependencies, and builds.

## More exact rules with an analyzer

<!-- ste-disable STE-3.6 -->

Some rules need the grammar of a sentence. "The demand is measured" and
"there is measured demand" have the same words, and only the grammar gives
the difference.

<!-- ste-enable STE-3.6 -->

The optional spaCy analyzer gives the grammar of English:

```bash
ste analyzer                 # what it needs, and how to install it
ste lint --analyze docs/     # use it
```

The command sends the sentences of a file to the model in one batch. A
cache on the disk keeps each answer for the next run. The analyzer removes
wrong findings of rule 3.6. See [the analyzer](docs/analyzer.md) for the times.

The analyzer is optional. Basic checks need no model. Rules 2.1 and 5.3
need the analyzer. Rules 3.5 and 3.6 can use it for more exact results.

## For an agent

`ste schema` prints the full interface as JSON, for an agent. It gives each command and each flag, with the permitted
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
src/ste/cli.py           the commands and project paths
src/ste/document.py      the Markdown parser and source positions
src/ste/checker.py       the checker entry point
src/ste/rules/           the rules and their data
src/ste/config.py        the configuration reader
src/ste/dictionary.py    the dictionary importer
src/ste/evaluation.py    the measurement of the rules
src/ste/report.py        the output formats
src/ste/baseline.py      the accepted findings
src/ste/analyzer.py      local NLP and the external analyzer protocol
tests/                  the Python tests
testdata/               the labeled corpus
docs/                   the rules, the audit, and the measurement
```

## Development

```bash
uv sync --locked
uv run ruff format --check .
uv run ruff check .
uv run ty check
uv run vulture
uv run pytest
uv run ste eval --fail-under 1.0 testdata
```

`mise run ci` runs these checks and the documentation check.

## Release

Set the version in `pyproject.toml` and `src/ste/__init__.py` before you tag
a release. A tag that starts with `v` starts the release workflow. The tag
must agree with the package version. The workflow builds a wheel and a
source archive, then adds them and `checksums.txt` to the GitHub release.

```bash
mise run dist       # writes dist/
```

## What the tool does not check

ASD-STE100 has 53 rules. This tool checks 30 of them today, 9 in full and
21 in part. 9 more need a part-of-speech tagger. The other rules need a
reader: "Make sure that each paragraph has only one topic" is an example.

[docs/coverage.md](docs/coverage.md) gives each rule and its group. The
[ste-review skill](https://github.com/TudorAndrei/ste-cli/tree/main/skill)
gives the rules of judgment to an agent, which reports them as advice, and
not as a defect.

## Limits

- Without the optional analyzer, the tool uses word lists and short word
  sequences. The analyzer supplies parts of speech and grammar relations.
- The tool does not ship the ASD-STE100 approved-word dictionary. Its
  own list holds 27 words and 11 word groups. `ste dict import` makes an
  index from your copy
  of the specification, and `--use-dict` then gives rule 1.1 the full list.
  See [docs/upstream-audit.md](docs/upstream-audit.md) for the reason that
  the tool cannot ship it.
- Precision and recall are in [docs/evaluation.md](docs/evaluation.md).
  Recall on new text is low, because the tool has 21 checks and the standard
  has 53 rules.
- ASD-STE100 is a specification of the AeroSpace and Defence Industries
  Association of Europe. This project is not part of ASD, and it does not
  contain the specification.

## License

The code of this tool is under the MIT license. See [LICENSE](LICENSE).

The MIT license covers the code only. ASD-STE100 is the property of the
AeroSpace and Defence Industries Association of Europe. Its copyright notice
does not permit reproduction in whole or in part without written authority.
This repository holds no text of the specification and no part of the
dictionary. It holds rule numbers, numeric limits, and our own words.
ASD gives the specification free of charge to each writer and user at
[asd-ste100.org](https://www.asd-ste100.org/).
