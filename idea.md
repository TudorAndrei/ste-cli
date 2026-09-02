
# Deterministic STE checker implementation plan

> **For Hermes:** Use subagent-driven-development skill to implement this plan task-by-task.

**Goal:** Build a small Go program that finds high-confidence ASD-STE100 violations in Markdown and plain text, with a project glossary for allowed technical nouns and verbs.

**Architecture:** Put all rules in one Go package. CLI, CI, MCP, and LSP call that package later. The checker returns structured findings with a rule ID, exact span, message, severity, and confidence. An LLM can receive findings to suggest edits, but it does not decide whether text passes.

**Tech stack:** Go, standard library, `go test`; start with plain text and Markdown code-fence exclusion. Add MCP/LSP only after the CLI rules are reliable.

---

## Task 0: Audit existing engines and vocabulary sources

**Objective:** Decide whether to reuse a vocabulary, engine, or interface before writing new rule code.

**Files:**

- Create: `docs/upstream-audit.md`
- Create: `THIRD_PARTY_NOTICES.md` if any upstream data/code is adopted

**Projects to inspect:**

| Project | What to evaluate | Vocabulary / license position |
|---|---|---|
| [sourdough-bread/asd-ste100-checker](https://github.com/sourdough-bread/asd-ste100-checker) | Python deterministic engine, MCP, LSP, rule IDs, spaCy-based POS and dependency analysis | Its repository says it commits dictionary/rule data extracted from the official Issue 9 PDF and explicitly acknowledges redistribution risk. **Do not copy that data** until legal review approves it. Apache-2.0 covers its code, not necessarily derived dictionary data. |
| [valeratrades/ste_checker](https://github.com/valeratrades/ste_checker) | Rust architecture, POS-aware checking, glossary workflow, test corpus | It vendors [openste/openste](https://github.com/openste/openste) v1.01 wordlist and states that the wordlist is MIT-licensed. Verify the upstream repository, version, and included license before reuse. This is the strongest vocabulary lead. |
| [swarooppatilx/ste100](https://github.com/swarooppatilx/ste100) | spaCy rule design, JSON dictionary layout, approved alternatives, annotated samples | MIT project with `approved.json`, `unapproved.json`, and `technical.json`. Verify where its vocabulary came from before copying it. Reuse its fixture structure and rule ideas even if data cannot be reused. |
| [stazelabs/ste](https://github.com/stazelabs/ste) | Go CLI, token/span handling, SARIF/GitHub/JSON output, `.ste.yml` | MIT code; it states that it contains no STE specification data. Good implementation reference, not a vocabulary source. |
| [TechScribe term checker design](https://www.simplified-english.co.uk/design.html) | POS disambiguation and per-project technical-term model | Commercial/proprietary rule data. Use it as an architecture reference only. Its key idea: technical nouns and technical verbs need separate POS-aware project configuration. |

**Steps:**

1. Record each repository URL, commit/tag, language, license, vocabulary path, and test coverage.
2. Separate code license from data provenance. A permissive repository license does not prove that copied dictionary data is safe to redistribute.
3. Choose one of three outcomes for every candidate: `reuse`, `borrow design only`, or `do not use`.
4. Add the decision and evidence to `docs/upstream-audit.md`.
5. Do not import a vocabulary until the audit says `reuse` and the third-party notice is ready.

**Verification:** The project has a written source and license record before its first vocabulary file is committed.

---

## Scope for v1

- Sentence length, contractions, semicolons, basic banned terms.
- High-confidence verb checks: perfect tense, passive voice, progressive `-ing`, known phrasal verbs.
- `flavored` and `strict` modes.
- `glossary.yml` for project-specific technical nouns and verbs.
- CLI output in text and JSON.
- Labeled fixtures and per-rule tests.

## Do not build in v1

- An LLM rewriter.
- PDF processing.
- Full certification claims.
- Every one of the 53 STE rules.
- An editor extension, MCP server, or LSP server.

## Proposed layout

```text
ste/
  cmd/ste/main.go
  internal/checker/checker.go
  internal/checker/diagnostic.go
  internal/checker/document.go
  internal/checker/rules/
    length.go
    surface.go
    verbs.go
    terms.go
  internal/config/config.go
  testdata/
    valid/
    invalid/
  docs/glossary.yml
```

---

### Task 1: Create the Go module and diagnostic type

**Objective:** Establish one stable result format before adding rules.

**Files:**

- Create: `go.mod`
- Create: `internal/checker/diagnostic.go`
- Create: `internal/checker/checker_test.go`

**Steps:**

1. Write a failing test that passes a string to `checker.Lint` and expects an empty finding list.
2. Run `go test ./internal/checker` and confirm it fails because the package/API does not exist.
3. Add `Diagnostic` with: `RuleID`, `Message`, `Severity`, `Confidence`, `Start`, `End`, `Suggestion`.
4. Add `Lint(text string, options Options) []Diagnostic` that returns an empty list.
5. Run `go test ./...`.

**Verification:** A clean input returns `[]`, and diagnostics can serialize to JSON.

---

### Task 2: Add document normalization

**Objective:** Check prose without flagging code or inline commands.

**Files:**

- Create: `internal/checker/document.go`
- Create: `internal/checker/document_test.go`
- Modify: `internal/checker/checker.go`

**Steps:**

1. Write failing tests for fenced code blocks, inline code, and normal prose.
2. Implement a scanner that replaces excluded spans with same-length whitespace. Keep original offsets intact.
3. Split the remaining prose into sentences with byte offsets.
4. Run `go test ./...`.

**Verification:** `has been sent` inside a code fence produces no verb finding; the same text in prose does.

---

### Task 3: Add simple surface rules

**Objective:** Move existing high-confidence rules into the engine.

**Files:**

- Create: `internal/checker/rules/surface.go`
- Create: `internal/checker/rules/surface_test.go`
- Modify: `internal/checker/checker.go`

**Rules:**

- `STE-8.1`: semicolon
- `STE-4.2`: contraction
- `STE-5.1`: sentence over configured word limit

**Steps:**

1. Add one failing test for each rule with exact expected spans.
2. Implement each rule independently.
3. Confirm each test fails before implementation and passes after it.
4. Run the full test suite.

**Verification:** Findings include the right rule ID and point at the offending character range.

---

### Task 4: Add verb-rule data and tests

**Objective:** Define the cases the engine must support before writing verb logic.

**Files:**

- Create: `internal/checker/rules/verbs_test.go`
- Create: `internal/checker/rules/testdata/verbs.json`

**Fixture groups:**

- Perfect tense: `has been sent`, `had gone`, `have written`.
- Progressive form: `is running`, `is still running`, `was not reading`.
- Passive voice: `was sent by the parser`, `has been read by the parser`.
- Adjectival participles that must not be flagged: `is configured`, `is enabled`, `is closed`.
- Phrasal verbs: base, third-person, past, and `-ing` forms.

**Steps:**

1. Build a table-driven test that loads the fixture cases.
2. Run it before implementation and confirm failures.
3. Record expected rule IDs and expected spans, not just finding counts.

**Verification:** Every future rule change is evaluated against both positives and known false-positive cases.

---

### Task 5: Implement high-confidence verb rules

**Objective:** Detect the useful verb cases without pretending to parse all English.

**Files:**

- Create: `internal/checker/rules/verbs.go`
- Modify: `internal/checker/checker.go`

**Approach:**

- Store irregular participles and phrasal-verb forms as explicit versioned data.
- Recognize narrow auxiliary chains such as `has been <participle>` and `is still <verb-ing>`.
- Use a conservative stative/adjectival exception list.
- Set lower confidence where grammar alone cannot distinguish adjective from passive.

**Steps:**

1. Implement perfect-tense detection until its fixture tests pass.
2. Implement progressive-form detection until its fixture tests pass.
3. Implement passive detection and protect known adjectival forms.
4. Implement phrasal-verb matching from a canonical phrase/form table.
5. Run `go test ./...` after each slice.

**Verification:** The engine catches inflected phrasal forms and auxiliary-separated `-ing` forms that the original regex misses.

---

### Task 6: Add modes and glossary support

**Objective:** Avoid flagging legitimate project language and let strict procedures use stronger rules.

**Files:**

- Create: `internal/config/config.go`
- Create: `internal/config/config_test.go`
- Create: `docs/glossary.yml`
- Modify: `internal/checker/checker.go`

**Config shape:**

```yaml
mode: flavored
allow:
  nouns: [parser, webhook]
  verbs: [provision]
disable_rules: []
```

**Steps:**

1. Write failing tests for `flavored` versus `strict` behavior.
2. Write a failing test that an allowed project verb does not create an unknown-term finding.
3. Implement config loading and pass config into `checker.Options`.
4. Run `go test ./...`.

**Verification:** A repository can permit its own technical language without weakening global grammar rules.

---

### Task 7: Add the CLI

**Objective:** Make the core engine usable locally and in CI.

**Files:**

- Create: `cmd/ste/main.go`
- Create: `cmd/ste/main_test.go`
- Modify: `README.md`

**Commands:**

```text
ste lint README.md
ste lint --mode strict --format json docs/
ste lint --fail-over 2.5 draft.md
```

**Steps:**

1. Write a failing CLI test for JSON output and a non-zero exit when `--fail-over` is exceeded.
2. Implement file and stdin input.
3. Add text and JSON renderers.
4. Run `go test ./...` and manually run the three commands above on fixtures.

**Verification:** CI can consume JSON; a human can read text output; exit status works.

---

### Task 8: Measure and publish the limits

**Objective:** Make rule quality visible and prevent the checker from overclaiming.

**Files:**

- Create: `docs/rules.md`
- Create: `docs/evaluation.md`
- Modify: `README.md`

**Steps:**

1. Document each implemented rule, its mode, and known limits.
2. Add a small evaluation command or test report that gives precision/recall per rule from the labeled fixture corpus.
3. State that the tool is an aid, not an ASD-certified checker.
4. Run all tests and record the result in the README.

**Verification:** New rules cannot ship without examples and a stated error trade-off.

---

## Validation checklist

```bash
gofmt -w .
go test ./...
go vet ./...
go run ./cmd/ste lint testdata/invalid --format json
go run ./cmd/ste lint testdata/valid --mode strict
```

Expected results:

- All tests pass.
- Valid fixtures produce no unexpected findings.
- Invalid fixtures produce the expected rule IDs and spans.
- `--fail-over` exits non-zero only when the configured threshold is exceeded.

## Risks and decisions

- **Grammar ambiguity:** Label low-confidence findings instead of calling them errors.
- **STE vocabulary licensing:** Do not ship the copyrighted approved-word dictionary. Let users build/import their own index if licensing permits.
- **False positives:** Keep v1 conservative. A warning users ignore has no value.
- **Existing projects and vocabulary:** Complete **Task 0** first. The likely reusable wordlist is [openste/openste](https://github.com/openste/openste), referenced as MIT-licensed by [valeratrades/ste_checker](https://github.com/valeratrades/ste_checker). Treat [sourdough-bread/asd-ste100-checker](https://github.com/sourdough-bread/asd-ste100-checker)'s extracted Issue 9 data as legally unreviewed, even though its code is Apache-2.0. Use [stazelabs/ste](https://github.com/stazelabs/ste) for Go implementation ideas, not dictionary data.
