---
title: Upstream audit
description: The license and the provenance decision for each related project.
---

# Upstream audit

[Back to the start page](index.md)

This document records the audit of the related projects. The audit came
before the first vocabulary file of this project.

Audit date: 2026-09-02. All the data comes from the GitHub API and from the
files of each repository, at the commit that this document gives below.

## Result

**This project adopts no upstream code and no upstream data.** A person
wrote all the rule data in `internal/checker/rules/` by hand for this
project. Thus there is no `THIRD_PARTY_NOTICES.md` file. Make that file
before the first import of an upstream data file.

## Method

1. Record the URL, the commit, the language, the license, the vocabulary
   path, and the tests of each candidate.
2. Keep the license of the code separate from the provenance of the data. A
   permissive license on a repository is not proof that the dictionary data
   in that repository is safe to redistribute.
3. Give each candidate one of three results: `reuse`, `borrow design only`,
   or `do not use`.

## Candidates

### sourdough-bread/asd-ste100-checker

| Item | Value |
|---|---|
| Commit | `e193ecdd66b0` (2026-07-24) |
| Language | Python |
| Code license | Apache-2.0 |
| Vocabulary path | `ste100/` data modules, extracted from the specification |
| Result | **do not use** (data), **borrow design only** (interfaces) |

The repository holds `ASD-STE100-ISSUE-9.pdf` at its root. This is the
specification, which is under copyright. The repository says that it commits
dictionary and rule data that comes from that PDF, and it gives a warning
about the risk. The Apache-2.0 license applies to the code of the project.
It does not give the project the right to sub-license the specification data.

Kept as ideas only: the rule identifiers, the structured result format, and
the later MCP and LSP interfaces.

### valeratrades/ste_checker

| Item | Value |
|---|---|
| Commit | `3adb827991ee` (2026-08-21) |
| Language | Rust |
| Code license | **Blue Oak Model License 1.0.0** |
| Vocabulary path | `ste_checker/src/wordset.rs` with the openste word list |
| Result | **borrow design only** |

Correction to the plan: the license is Blue Oak 1.0.0, not MIT. The MIT
statement in the plan refers to the openste word list that this project
vendors, not to the project itself.

Kept as ideas only: the glossary workflow, and the labeled test corpus with
a `corpus.truth` file. This project uses the same idea in
`testdata/*.expected.json`.

### swarooppatilx/ste100

| Item | Value |
|---|---|
| Commit | `6bbed1e63941` (2026-08-09) |
| Language | Python |
| Code license | MIT |
| Vocabulary path | `src/data/approved.json`, `unapproved.json`, `technical.json` |
| Result | **borrow design only** |

The repository gives no statement about the source of its three JSON data
files. The MIT license of the code is thus not enough proof for the data.
This project does not use that data.

Kept as ideas only: one test file for each rule, and the annotated sample
files.

### stazelabs/ste

| Item | Value |
|---|---|
| Commit | `922c9773d000` (2026-07-30) |
| Language | Go |
| Code license | MIT |
| Vocabulary path | none. The repository says that it contains no ASD-STE100 specification data. |
| Result | **borrow design only** |

This is the nearest implementation reference: a Go CLI with no
dependencies, byte spans, JSON output, and a score for each 100 words. This
project copied no code. The score for each 100 words and the `.ste.yml`
config file are the same ideas.

The README of that project is also one of the unlabeled text samples that
found false positives. See `docs/evaluation.md`.

### openste/openste

| Item | Value |
|---|---|
| Commit | `19f01781a616` (2026-03-16) |
| Language | data only |
| Code license | MIT (`LICENSE`, "Copyright (c) 2026 openSTE.org") |
| Vocabulary path | `vocabulary/openste.json`, 436 kB |
| Result | **do not use in v1.** Possible `reuse` after a provenance review. |

Content of the file: `set_name` "openste - v1.01", 1951 word records (909
`approved`, 1042 `unapproved`), each with a `spacypos` part of speech, and
1589 alternative-word records.

This is the strongest vocabulary lead, but two facts stop its use in v1:

- The repository gives no statement about the source of the word list. The
  README and the `vocabulary/README.md` describe the idea of a controlled
  vocabulary, but they do not say who made the list or from what.
- The `CHANGELOG.md` puts the "Controlled vocabulary list" in its
  **Planned** section, but `vocabulary/openste.json` already holds 1951
  records with an approved/unapproved status. The structure is very near to
  the structure of the specification dictionary.

The MIT license is a statement by the openste project. It is not proof of
the provenance of the data. Because v1 does not need a full dictionary
rule, the safe decision is to wait.

**Condition for a later `reuse`:** the openste project states the source of
its word list. As an alternative, the user imports the list with a command.
In both cases, write `THIRD_PARTY_NOTICES.md` first.

### TechScribe term checker (design page)

| Item | Value |
|---|---|
| Source | <https://www.simplified-english.co.uk/design.html> |
| License | commercial and proprietary |
| Result | **borrow design only** |

Kept as an idea only: a technical noun and a technical verb need different
project configuration. `docs/glossary.yml` has the two lists `allow.nouns`
and `allow.verbs` for this reason.

## The specification itself

The owner of this repository has a licensed copy of ASD-STE100 Issue 9. On
2026-09-02, a review of that copy corrected the rule numbers of this tool.
The review also found which rules a deterministic checker can check. The
result is in [rules.md](rules.md) and in [evaluation.md](evaluation.md).

What entered this repository from that work:

- **Rule numbers and the subject of each rule.** A rule number is a fact
  about the specification. It is not the text of the specification.
- **Numeric limits**, such as the 20-word and 25-word sentence limits, and
  the count rules of section 8.
- **Statements in our own words** about what each rule requires.

What did **not** enter this repository:

- The text of the specification, its tables, and its example sentences.
- **The dictionary of part 2.** Part 2 gives about 2000 words in a
  form that a program can parse. It is the largest and most valuable part of
  the specification, and it stays out of this repository.

The local copy and its Markdown conversion are in `.standard/`, which
`.gitignore` excludes. This repository is public, thus git must never see
that directory.

A future dictionary rule must read a copy that **the user** supplies from
their own licensed copy. This tool must not ship the dictionary.

## Dependencies

| Module | Version | License | Function |
|---|---|---|---|
| `github.com/yuin/goldmark` | v1.8.5 | MIT | Reads the Markdown |
| `github.com/goccy/go-yaml` | v1.19.2 | MIT | Reads the glossary |
| `github.com/spf13/pflag` | v1.0.10 | BSD-3-Clause | Reads the command flags |

Each of the 3 is code, and not data. None of them has ASD-STE100 data. The
tool used its own reader for Markdown and for YAML before version 0.4.0. A
CommonMark parser is better, because 5 of the 8 defects of the first
versions came from that hand-written reader.

`gopkg.in/yaml.v3` is not in this list. That project became an archive in
April 2025.

## Data in this project

| File | Source | Risk |
|---|---|---|
| `internal/checker/rules/verbdata.go` | Written by hand. English irregular participles, auxiliary verbs, and a list of 24 phrasal verbs. | Low. English grammar is not under copyright. |
| `internal/checker/rules/terms.go` | Written by hand. 27 words and 11 word groups that have a shorter replacement. | Low. It is not the ASD-STE100 dictionary and it does not come from it. |
| `internal/checker/rules/spelling.go` | Written by hand. 54 British spellings, 17 word groups that use a noun for an action, and 8 Latin abbreviations. | Low. The lists are examples of the rule, and not the dictionary. |
| `docs/glossary.yml` | Written by hand for this repository. | None. |

This tool does not ship the ASD-STE100 approved-word dictionary. It cannot
tell you if a word is in that dictionary.
