---
title: Evaluation
description: The measured precision and recall of the rules, and the limits of that measurement.
---

# Evaluation

[Back to the start page](index.md)

Measurement date: 2026-09-02. Verb data version 1.0.0, term data version
1.0.0.

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
| `STE-1.4` | 4 | 0 | 0 | 1.00 | 1.00 |
| `STE-3.1` | 2 | 0 | 0 | 1.00 | 1.00 |
| `STE-3.2` | 1 | 0 | 0 | 1.00 | 1.00 |
| `STE-3.5` | 2 | 0 | 0 | 1.00 | 1.00 |
| `STE-4.2` | 2 | 0 | 0 | 1.00 | 1.00 |
| `STE-5.1` | 1 | 0 | 0 | 1.00 | 1.00 |
| `STE-8.1` | 1 | 0 | 0 | 1.00 | 1.00 |
| **all** | **15** | **0** | **0** | **1.00** | **1.00** |

4 fixture files, 2 valid and 2 invalid.

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
| README of `stazelabs/ste` | 808 | 0 | 0 | — |
| README of `openste/openste` | 395 | 2 | 0 | 1.00 |
| **Total** | **2459** | **15** | **0** | **1.00** |

**This measurement gives no recall.** The documents have no labels, thus
nobody knows how many violations the tool did not find. The true recall of
the tool on new text is much less than 1.00, because the tool has only 8 of
the 53 rules.

### The false positives that this measurement found

The first run on these documents gave 6 wrong findings. Each one showed a
defect, and each defect now has a test:

| Wrong finding | Cause | Correction |
|---|---|---|
| `STE-3.2` on "is MIT-licensed" | A hyphenated adjective ends with "ed". | `isCompound` in `rules/verbs.go`. |
| `STE-1.1` on "Additional documentation" | An indented code block was prose. | Indented-block mask in `checker/document.go`. |
| 3 × `STE-5.1` on a 26 to 35-word "sentence" | Inline code after a period hid the start of the next sentence, thus two sentences became one. | The look-ahead in `endsSentence` uses the source text. |
| `STE-5.1` on a 34-word "sentence" | The cells of a Markdown table row became one sentence. | A cell separator is a sentence boundary. |

## 3. Known limits of the measurement

- The corpus is small: 4 files and 15 labeled findings.
- The unlabeled documents are all software documentation in English. Nobody
  measured the tool on aircraft maintenance procedures, which is the first
  purpose of ASD-STE100.
- This evaluation does not measure recall on new text.
- The tool has no dictionary rule, thus this evaluation says nothing about
  the largest part of ASD-STE100: the approved-word list.

## 4. The rule for a new rule

A new rule must not ship without:

1. Positive examples in `testdata/` or in a rule fixture file.
2. Known false-positive examples that the rule must not report.
3. A line in `docs/rules.md` that gives its limits.
4. A new measurement on this page.
