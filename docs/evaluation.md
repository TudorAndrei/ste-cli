---
title: Evaluation
description: The measured precision and recall of the rules, the defects that a run on a real repository found, and the limits of the measurement.
---

# Evaluation

[Back to the start page](index.md)

Measurement date: 2026-09-02. Verb data version 1.1.0, term data version
1.0.0. The rules agree with ASD-STE100 Issue 9. Refer to
[the audit of the standard](#4-audit-against-issue-9).

Run the measurement again with:

```bash
go run ./cmd/ste eval testdata
go run ./cmd/ste eval --format json testdata
```

## 1. Labeled corpus

The corpus is in `testdata/`. Each fixture file can have a
`<name>.expected.json` file that lists the findings that the checker must
give. A file with no expectation file must give no findings.

| Rule | TP | FP | FN | Precision | Recall |
|---|---|---|---|---|---|
| `STE-1.1` | 2 | 0 | 0 | 1.00 | 1.00 |
| `STE-1.11` | 3 | 0 | 0 | 1.00 | 1.00 |
| `STE-1.14` | 2 | 0 | 0 | 1.00 | 1.00 |
| `STE-3.4` | 2 | 0 | 0 | 1.00 | 1.00 |
| `STE-3.5` | 2 | 0 | 0 | 1.00 | 1.00 |
| `STE-3.6` | 1 | 0 | 0 | 1.00 | 1.00 |
| `STE-3.7` | 1 | 0 | 0 | 1.00 | 1.00 |
| `STE-4.2` | 2 | 0 | 0 | 1.00 | 1.00 |
| `STE-4.3` | 1 | 0 | 0 | 1.00 | 1.00 |
| `STE-5.1` | 2 | 0 | 0 | 1.00 | 1.00 |
| `STE-5.4` | 2 | 0 | 0 | 1.00 | 1.00 |
| `STE-5.5` | 1 | 0 | 0 | 1.00 | 1.00 |
| `STE-6.6` | 1 | 0 | 0 | 1.00 | 1.00 |
| `STE-7.3` | 1 | 0 | 0 | 1.00 | 1.00 |
| `STE-8.1` | 1 | 0 | 0 | 1.00 | 1.00 |
| `STE-9.3` | 4 | 0 | 0 | 1.00 | 1.00 |
| `STE-GR-6` | 1 | 0 | 0 | 1.00 | 1.00 |
| **all** | **29** | **0** | **0** | **1.00** | **1.00** |

10 fixture files, 4 valid and 6 invalid. Each of the 15 rules that need no
analyzer has at least one labeled example. The corpus does not measure the 4
rules that need the analyzer, because the corpus runs with no Python.

The 4 valid files are the guard against a wrong finding. Each of them must
give 0 findings. They hold the constructions that gave a wrong finding
before:

- YAML front matter.
- Code or a link between two words.
- The name "VS Code".
- A semicolon in the target of a link.
- A colon in a time of day.
- A note with a label.
- A list that starts each item with a small letter.

`mise run ci` measures the corpus and fails when the precision or the
recall goes below 1.00:

```bash
go run ./cmd/ste eval --fail-under 1.0 testdata
```

**Read these numbers with care.** The same person wrote the rules and the
fixtures. A score of 1.00 on this corpus shows only that the rules agree
with their own examples. It is a guard against a change that breaks a rule,
but it does not measure the quality on new text. The unit tests in
`internal/checker/rules/testdata/verbs.json` (22 cases) have the same limit.

## 2. Unlabeled documents

To find false positives, the tool ran on 3 documents. These documents are
not part of the corpus, and they had no effect on the rules. A person then
read each finding and gave it a verdict.

| Document | Words | Findings | False positives | Precision |
|---|---|---|---|---|
| `idea.md` (the plan of this project) | 1256 | 13 | 0 | 1.00 |
| README of `stazelabs/ste` | 803 | 0 | 0 | — |
| README of `openste/openste` | 395 | 2 | 0 | 1.00 |
| **Total** | **2454** | **15** | **0** | **1.00** |

The measurement ran again after the audit against Issue 9. The 3 new rules
(`STE-1.14`, `STE-3.7`, `STE-GR-6`) gave no finding on these documents.
Thus they add no noise. The word counts are lower than the first
measurement, because the tool now counts a quantity with its unit as one
word.

**This measurement gives no recall.** The documents have no labels, and
nobody knows how many violations the tool did not find. The true recall on
new text is much less than 1.00. The tool has 19 checks, and the standard
has 53 rules.

### The false positives that this measurement found

The first run on these documents gave 6 wrong findings. Each one showed a
defect, and each defect now has a test:

| Wrong finding | Cause | Correction |
|---|---|---|
| `STE-3.6` on "is MIT-licensed" | A hyphenated adjective ends with "ed". | `isCompound` in `rules/verbs.go`. |
| `STE-1.1` on `Additional documentation` | An indented code block was prose. | Indented-block mask in `checker/document.go`. |
| 3 × `STE-5.1` on a 26 to 35-word "sentence" | Inline code after a period hid the start of the next sentence, and two sentences became one. | The look-ahead in `endsSentence` uses the source text. |
| `STE-5.1` on a 34-word "sentence" | The cells of a Markdown table row became one sentence. | A cell separator is a sentence boundary. |

## 3. Known limits of the measurement

- The corpus is small: 10 files and 29 labeled findings.
- The unlabeled documents are all software documentation in English. Nobody
  measured the tool on aircraft maintenance procedures, which is the first
  purpose of ASD-STE100.
- This evaluation does not measure recall on new text.
- The tool has no dictionary rule. This evaluation says nothing about
  the largest part of ASD-STE100: the approved-word list.
- The labeled corpus does not measure the rules that need the analyzer.
  Section 5 gives what a person read on two real repositories.

## 5. The analyzer rules on two repositories

Rules 2.1, 3.5, 5.3, and part of 3.6 need the grammar of a sentence. A
person read the findings of `--analyze` on two repositories of software
documentation.

| Repository | Files | Without the analyzer | With the analyzer |
|---|---|---|---|
| criv | 180 | 1065 | 1534 |
| ouro | 84 | 699 | 878 |

Rule 5.3 gave 69 findings on criv at first, and a person found that 68 of
them were wrong. Three defects made them:

| Wrong finding | Cause | Correction |
|---|---|---|
| "One semantic source change creates..." | A numbered list of requirements is not a procedure. | The rule reads a list only when more than half of its items are commands. |
| "Atomically replace the file" | An adverb comes before the verb. | The rule steps over an adverb, and over a phrase that ends with a comma. |
| "Delete quarantined files" | The analyzer reads a short step with no context, and it gives "Delete" as an adjective. | The rule reads the sentence again with "please" at its start. |
| "Do not enable the mode" | The first word is an auxiliary, and not the verb. | The rule accepts a command in the negative form. |

After the 4 corrections, rule 5.3 gives 0 findings on criv and 11 on ouro.

**The cost.** The run on criv went from 0.11s to 14.9s, because each
sentence of a possible finding goes to the model. The analyzer is off by
default for this reason.

## 4. Audit against Issue 9

The first version of this tool used rule numbers that were an estimate. An
audit of ASD-STE100 Issue 9, one agent for each group of sections, gave the
true numbers and found 6 defects. This version corrects all 6.

| Defect | Correction |
|---|---|
| The phrasal-verb rule had the number 1.4. Rule 1.4 is about the forms of verbs and adjectives. | The rule is **9.3**. |
| The perfect-tense rule had the number 3.1. Rule 3.1 is about the verb forms of the dictionary. | The rule is **3.4**. |
| The passive-voice rule had the number 3.2. Rule 3.2 only lists the permitted forms. | The rule is **3.6**. |
| The word count counted a quantity and its unit as 2 words, a quoted string as many words, and text in parentheses as many words. Section 8 counts each as 1 word. Thus `STE-5.1` reported sentences that are inside the limit. | The count obeys rules 8.5 to 8.7. |
| The mode selected the sentence limit (20 in strict, 25 in flavored). The standard selects the limit from the type of the sentence. | A numbered step gets 20 words (rule 5.1), a note and descriptive text get 25 (rules 5.5 and 6.3). The mode changes only the severity and the confidence filter. |
| The message for `STE-8.1` said that the standard permits 6 punctuation marks. Rule 8.1 permits all standard marks, but not the semicolon. | The message states the ban of one mark. |

Two more defects came from the same audit and have tests:

- A step of a procedure that continues on a second line became two
  sentences. Thus the tool never measured its full length.
- `is being adjusted` gave a progressive finding and a passive finding.
  Only the passive finding is correct.

The audit also confirmed that `STE-1.1`, `STE-3.5`, `STE-4.2`, `STE-5.1`,
and `STE-8.1` had the correct numbers.

### The tool on its own repository

Version 0.2.0 ran on this repository. The run gave 76 findings in 12 files.
56 of the findings are correct and expected: 20 in the invalid fixtures, and
36 in the quoted examples of the rule pages. 13 are correct findings in
`idea.md`. The author of that file did not use Simplified Technical
English.

The run found 2 defects in the tool, and version 0.2.1 corrects them:

| Defect | Correction |
|---|---|
| `STE-1.14` reported "Defence" in the name of an organization. A name keeps its spelling, and rule 8.6 makes a proper noun one unit. | The rule does not report a capitalized word that does not start its sentence. |
| The walk of a directory read `dist/`, which holds build output. | The walk does not go into a directory that holds build output or dependencies. |

`docs/rules.md` gives the rules that the audit found to be not mechanically
checkable. The tool does not try to check them.

### The tool on a repository of 180 files

Version 0.4.0 ran on a repository of software documentation that is not part
of this project: 180 files, 93654 words, mostly architecture decision
records. The run gave 1295 findings in 0.09 seconds. A person then read the
findings.

| Group | Findings | Verdict |
|---|---|---|
| Front matter | 127 | **Wrong.** 169 of the 180 files start with YAML front matter. CommonMark has no front matter, and the parser read the keys as a sentence. |
| The name "VS Code" | 147 | **Wrong.** The rule for a Latin abbreviation matched the name. |
| Semicolons, passive voice, long sentences | ~1000 | Correct on a sample of each rule. |

Version 0.5.0 corrects both defects, and the same repository now gives 1037
findings. The correction is 258 findings, or 20% of the first result.

This measurement is the reason for the controls in version 0.5.0. A tool
that gives 1295 findings on its first day is a tool that a team removes,
even when 80% of the findings are correct. The baseline, the severity of
each rule, and the directives in the text give a team a way to start.

## 5. The rule for a new rule

A new rule must not ship without:

1. Positive examples in `testdata/` or in a rule fixture file.
2. Known false-positive examples that the rule must not report.
3. A line in `docs/rules.md` that gives its limits.
4. A new measurement on this page.
