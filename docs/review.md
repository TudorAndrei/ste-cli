---
title: Review
description: An optional command that asks a language model for advice on the 13 rules that need a reader. The advice is not a defect, and it is not reproducible.
---

# Review

[Back to the start page](index.md)

`ste review` asks a language model for advice on the rules that need a
reader. `ste lint` cannot check these rules, because they have no mechanical
answer. Refer to [the coverage](coverage.md#a-judgment-of-a-reader).

**Each finding of this command is advice, and not a defect.** A language
model does not give the same answer each time. Two runs on the same text can
give different findings. Read each finding, and keep the decision yourself.

## What it needs

The command is optional. The base installation does not contain the
Anthropic library. Install the `llm` extra:

```bash
uv tool install "ste-cli[llm] @ git+https://github.com/TudorAndrei/ste-cli"
```

Then set an API key of Anthropic:

```bash
export ANTHROPIC_API_KEY=...
```

Without the extra or the key, the command stops with exit code 2, and the
message names the cause. Each request costs money. Thus look at the plan
first.

## See the plan first

`--dry-run` sends no request and needs no key. It gives the count of
paragraphs, the count of answers in the cache, the count of requests, and
an approximate count of input tokens:

```bash
ste review --dry-run --format json docs/
```

```json
{"action": "review", "dry_run": true, "model": "claude-haiku-5-5",
 "files": 6, "paragraphs": 231, "cached": 0, "requests": 231,
 "approx_input_tokens": 259509, "approx_system_tokens": 1016}
```

## Run it

```bash
ste review docs/guide.md
ste review --format json --limit 20 --fields rule_id,file,line,message docs/
ste review --model claude-sonnet-5-5 docs/guide.md
```

| Flag | What it does |
|---|---|
| `--model` | The model. The default is `claude-haiku-5-5`, because it is fast and cheap. |
| `--format` | `text`, `json`, or `ndjson`. |
| `--limit`, `--fields`, `--summary` | The same as for `ste lint`. The `kind` field is also available. |
| `--dry-run` | Give the plan, and send no request. |
| `--jobs` | The number of requests at the same time. The default is 4. |
| `--timeout` | The seconds for each request. The default is 120. |
| `--no-cache` | Do not read or write the cached answers. |
| `--config`, `--no-config`, `--all` | The same as for `ste lint`. |

`ste schema` gives each flag in the `command_flags.review` key, and the
rules in the `review` key.

## How it works

1. The tool divides each file into paragraphs. A list is one paragraph. It
   ignores a heading, a table, and code.
2. It sends each paragraph with the heading of its section. The rule
   descriptions are in a fixed system prompt, and the API keeps that prompt
   in its cache.
3. The model gives its answer as JSON that agrees with a schema. Each
   finding has a rule, a quote, a message, and a suggestion.
4. The tool finds the quote in the source and gives its line and column.
   **If the tool cannot find the quote, it drops the finding.**
5. The tool keeps each answer on the disk, in the cache directory of the
   user. The key is the hash of the paragraph, the heading, the model, and
   the version of the rule set. A second run on the same text sends no
   request and gives the same advice.

The client tries a request again after a rate limit or a server error. A
request that fails is in `summary.failed`, and its paragraph gets no advice.
A failed request does not go in the cache.

## The findings

A finding has the usual fields of `ste lint`, and these values:

| Field | Value |
|---|---|
| `severity` | Always `info`. |
| `kind` | Always `advice`. |
| `confidence` | Always 0.5. |
| `rule_id` | A rule of the table below, for example `STE-6.5`. |

The summary also gives `model`, `paragraphs`, `requests`, `cached`, and
`failed`.

| Rule | Subject |
|---|---|
| STE-1.3 | One meaning for each word |
| STE-1.5 | The category of a technical noun |
| STE-1.12 | The category of a technical verb |
| STE-1.10 | No slang and no jargon |
| STE-2.2 | The full form of a long technical noun |
| STE-4.4 | Connecting words |
| STE-4.5 | Articles and demonstrative adjectives |
| STE-6.1 | Give information gradually |
| STE-6.2 | Key words for a logical structure |
| STE-6.5 | One topic for each paragraph |
| STE-9.1 | A different sentence construction |
| STE-9.2 | Each word in its correct place |
| STE-9.4 | A consistent style |

## What it does not change

- The exit code of `ste review` is 0 when it ran, also with findings.
- `ste review` does not read or write the baseline.
- `ste lint` does not read the advice. The exit code and the gates of
  `ste lint` stay the same.

## Limits

- The advice is not reproducible. A new model, or a run with `--no-cache`,
  can give different advice.
- The model sees one paragraph at a time. Thus it cannot compare two
  paragraphs, and rule 2.2 cannot see a full form in a different section.
- The text goes to Anthropic. Do not review a text that must stay private.
- The [ste-review skill](https://github.com/TudorAndrei/ste-cli/tree/main/skill)
  gives the same rules to an agent that reads the whole file.
