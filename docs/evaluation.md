---
title: Evaluation
description: The measured precision and recall of the rules, and the limits of that measurement.
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
| `STE-1.14` | 2 | 0 | 0 | 1.00 | 1.00 |
| `STE-3.4` | 2 | 0 | 0 | 1.00 | 1.00 |
| `STE-3.5` | 2 | 0 | 0 | 1.00 | 1.00 |
| `STE-3.6` | 1 | 0 | 0 | 1.00 | 1.00 |
| `STE-3.7` | 1 | 0 | 0 | 1.00 | 1.00 |
| `STE-4.2` | 2 | 0 | 0 | 1.00 | 1.00 |
| `STE-5.1` | 2 | 0 | 0 | 1.00 | 1.00 |
| `STE-8.1` | 1 | 0 | 0 | 1.00 | 1.00 |
| `STE-9.3` | 4 | 0 | 0 | 1.00 | 1.00 |
| `STE-GR-6` | 1 | 0 | 0 | 1.00 | 1.00 |
| **all** | **20** | **0** | **0** | **1.00** | **1.00** |

5 fixture files, 2 valid and 3 invalid.

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

**This measurement gives no recall.** The documents have no labels, thus
nobody knows how many violations the tool did not find. The true recall on
new text is much less than 1.00. The tool has 11 checks, and the standard
has 53 rules.

### The false positives that this measurement found

The first run on these documents gave 6 wrong findings. Each one showed a
defect, and each defect now has a test:

| Wrong finding | Cause | Correction |
|---|---|---|
| `STE-3.6` on "is MIT-licensed" | A hyphenated adjective ends with "ed". | `isCompound` in `rules/verbs.go`. |
| `STE-1.1` on `Additional documentation` | An indented code block was prose. | Indented-block mask in `checker/document.go`. |
| 3 × `STE-5.1` on a 26 to 35-word "sentence" | Inline code after a period hid the start of the next sentence, thus two sentences became one. | The look-ahead in `endsSentence` uses the source text. |
| `STE-5.1` on a 34-word "sentence" | The cells of a Markdown table row became one sentence. | A cell separator is a sentence boundary. |

## 3. Known limits of the measurement

- The corpus is small: 5 files and 20 labeled findings.
- The unlabeled documents are all software documentation in English. Nobody
  measured the tool on aircraft maintenance procedures, which is the first
  purpose of ASD-STE100.
- This evaluation does not measure recall on new text.
- The tool has no dictionary rule, thus this evaluation says nothing about
  the largest part of ASD-STE100: the approved-word list.

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
`idea.md`, which is not written in Simplified Technical English.

The run found 2 defects in the tool, and version 0.2.1 corrects them:

| Defect | Correction |
|---|---|
| `STE-1.14` reported "Defence" in the name of an organization. A name keeps its spelling, and rule 8.6 makes a proper noun one unit. | The rule does not report a capitalized word that does not start its sentence. |
| The walk of a directory read `dist/`, which holds build output. | The walk does not go into a directory that holds build output or dependencies. |

`docs/rules.md` gives the rules that the audit found to be not mechanically
checkable. The tool does not try to check them.

## 5. The rule for a new rule

A new rule must not ship without:

1. Positive examples in `testdata/` or in a rule fixture file.
2. Known false-positive examples that the rule must not report.
3. A line in `docs/rules.md` that gives its limits.
4. A new measurement on this page.
