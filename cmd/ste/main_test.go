package main

import (
	"bytes"
	"encoding/json"
	"os"
	"os/exec"
	"path/filepath"
	"strings"
	"testing"
)

func runCLI(t *testing.T, stdin string, args ...string) (int, string, string) {
	t.Helper()
	var out, errOut bytes.Buffer
	code := run(args, strings.NewReader(stdin), &out, &errOut)
	return code, out.String(), errOut.String()
}

func writeFile(t *testing.T, dir, name, content string) string {
	t.Helper()
	path := filepath.Join(dir, name)
	if err := os.WriteFile(path, []byte(content), 0o644); err != nil {
		t.Fatalf("write %s: %v", path, err)
	}
	return path
}

func TestLintJSONOutput(t *testing.T) {
	dir := t.TempDir()
	path := writeFile(t, dir, "draft.md", "The file has been sent; it isn't ready.\n")

	code, stdout, stderr := runCLI(t, "", "lint", "--no-config", "--format", "json", path)
	if code != 0 {
		t.Fatalf("exit %d, want 0: %s", code, stderr)
	}
	var rep lintReport
	if err := json.Unmarshal([]byte(stdout), &rep); err != nil {
		t.Fatalf("the output is not JSON: %v\n%s", err, stdout)
	}
	if rep.Version != 1 || rep.Mode != "flavored" || rep.Tool != "ste" {
		t.Errorf("version %d, tool %q, mode %q", rep.Version, rep.Tool, rep.Mode)
	}
	if len(rep.Files) != 1 || rep.Files[0].Path != path {
		t.Fatalf("files %+v", rep.Files)
	}
	if len(rep.Findings) != 3 {
		t.Fatalf("got %d findings, want 3: %+v", len(rep.Findings), rep.Findings)
	}
	if rep.Summary.Findings != 3 || rep.Summary.Words == 0 || rep.Summary.Score <= 0 {
		t.Errorf("summary %+v", rep.Summary)
	}
	for _, f := range rep.Findings {
		if f.Line < 1 || f.Column < 1 {
			t.Errorf("finding %s has the position %d:%d", f.RuleID, f.Line, f.Column)
		}
		if f.File != path {
			t.Errorf("finding %s names the file %q", f.RuleID, f.File)
		}
	}
}

// lintReport is the JSON that "ste lint --format json" gives.
type lintReport struct {
	Version int    `json:"version"`
	Tool    string `json:"tool"`
	Mode    string `json:"mode"`
	Files   []struct {
		Path  string `json:"path"`
		Words int    `json:"words"`
		Count int    `json:"count"`
	} `json:"files"`
	Findings []struct {
		RuleID     string  `json:"rule_id"`
		Severity   string  `json:"severity"`
		Confidence float64 `json:"confidence"`
		File       string  `json:"file"`
		Line       int     `json:"line"`
		Column     int     `json:"column"`
		Text       string  `json:"text"`
	} `json:"findings"`
	Summary struct {
		Files     int     `json:"files"`
		Findings  int     `json:"findings"`
		Words     int     `json:"words"`
		Score     float64 `json:"score"`
		Shown     int     `json:"shown"`
		Truncated bool    `json:"truncated"`
		Errors    int     `json:"errors"`
	} `json:"summary"`
}

func TestLintCleanFileGivesEmptyJSONFindings(t *testing.T) {
	dir := t.TempDir()
	path := writeFile(t, dir, "clean.md", "Open the valve. Start the pump.\n")
	code, stdout, _ := runCLI(t, "", "lint", "--no-config", "--format", "json", path)
	if code != 0 {
		t.Fatalf("exit %d, want 0", code)
	}
	if !strings.Contains(stdout, "\"findings\": []") {
		t.Fatalf("the findings are not an empty array: %s", stdout)
	}
}

func TestFailOverExitCode(t *testing.T) {
	dir := t.TempDir()
	path := writeFile(t, dir, "draft.md", "The file has been sent; it isn't ready.\n")

	// The score of this file is more than 2.5 findings for each 100 words.
	code, _, stderr := runCLI(t, "", "lint", "--no-config", "--fail-over", "2.5", path)
	if code != 1 {
		t.Fatalf("exit %d, want 1: %s", code, stderr)
	}
	if !strings.Contains(stderr, "more than the limit") {
		t.Errorf("stderr %q", stderr)
	}

	// A high limit permits the same file.
	if code, _, _ := runCLI(t, "", "lint", "--no-config", "--fail-over", "100", path); code != 0 {
		t.Fatalf("exit %d, want 0", code)
	}
	// Without the flag, the findings do not change the exit code.
	if code, _, _ := runCLI(t, "", "lint", "--no-config", path); code != 0 {
		t.Fatalf("exit %d, want 0", code)
	}
}

func TestLintReadsStandardInput(t *testing.T) {
	code, stdout, stderr := runCLI(t, "The valve isn't open.\n", "lint", "--no-config", "-")
	if code != 0 {
		t.Fatalf("exit %d, want 0: %s", code, stderr)
	}
	if !strings.Contains(stdout, "STE-4.2") {
		t.Fatalf("stdout %q", stdout)
	}
	if !strings.Contains(stdout, "(standard input)") {
		t.Fatalf("the file name is missing: %q", stdout)
	}
}

func TestLintDirectory(t *testing.T) {
	dir := t.TempDir()
	writeFile(t, dir, "a.md", "The valve isn't open.\n")
	writeFile(t, dir, "b.txt", "Open the valve.\n")
	writeFile(t, dir, "c.go", "package main // it isn't code prose\n")

	code, stdout, stderr := runCLI(t, "", "lint", "--no-config", "--format", "json", dir)
	if code != 0 {
		t.Fatalf("exit %d, want 0: %s", code, stderr)
	}
	var rep struct {
		Summary struct {
			Files int `json:"files"`
		} `json:"summary"`
	}
	if err := json.Unmarshal([]byte(stdout), &rep); err != nil {
		t.Fatalf("the output is not JSON: %v", err)
	}
	if rep.Summary.Files != 2 {
		t.Fatalf("files %d, want 2 (the Go file is not prose)", rep.Summary.Files)
	}
}

func TestWalkSkipsBuildOutput(t *testing.T) {
	dir := t.TempDir()
	writeFile(t, dir, "guide.md", "The valve isn't open.\n")
	for _, name := range []string{"dist", "node_modules", ".cache"} {
		sub := filepath.Join(dir, name)
		if err := os.MkdirAll(sub, 0o755); err != nil {
			t.Fatalf("mkdir: %v", err)
		}
		writeFile(t, sub, "notes.md", "The report isn't ready.\n")
	}

	code, stdout, stderr := runCLI(t, "", "lint", "--no-config", "--format", "json", dir)
	if code != 0 {
		t.Fatalf("exit %d, want 0: %s", code, stderr)
	}
	var rep struct {
		Summary struct {
			Files int `json:"files"`
		} `json:"summary"`
	}
	if err := json.Unmarshal([]byte(stdout), &rep); err != nil {
		t.Fatalf("the output is not JSON: %v", err)
	}
	if rep.Summary.Files != 1 {
		t.Fatalf("files %d, want 1: the walk must not read build output", rep.Summary.Files)
	}
}

func TestWalkSkipsGitIgnoredFiles(t *testing.T) {
	if _, err := exec.LookPath("git"); err != nil {
		t.Skip("git is not on this system")
	}
	dir := t.TempDir()
	for _, args := range [][]string{
		{"init"}, {"config", "user.email", "test@example.com"}, {"config", "user.name", "test"},
	} {
		cmd := exec.Command("git", append([]string{"-C", dir}, args...)...)
		if out, err := cmd.CombinedOutput(); err != nil {
			t.Fatalf("git %v: %v: %s", args, err, out)
		}
	}
	writeFile(t, dir, ".gitignore", "generated.md\nprivate/\n")
	writeFile(t, dir, "guide.md", "The valve isn't open.\n")
	writeFile(t, dir, "generated.md", "The report isn't ready.\n")
	sub := filepath.Join(dir, "private")
	if err := os.MkdirAll(sub, 0o755); err != nil {
		t.Fatalf("mkdir: %v", err)
	}
	writeFile(t, sub, "secret.md", "The report isn't ready.\n")

	files := func(args ...string) []string {
		t.Helper()
		code, stdout, stderr := runCLI(t, "", append([]string{"lint", "--no-config", "--format", "json"}, args...)...)
		if code != 0 {
			t.Fatalf("exit %d: %s", code, stderr)
		}
		var rep struct {
			Files []struct {
				Path string `json:"path"`
			} `json:"files"`
		}
		if err := json.Unmarshal([]byte(stdout), &rep); err != nil {
			t.Fatalf("the output is not JSON: %v", err)
		}
		out := []string{}
		for _, f := range rep.Files {
			out = append(out, filepath.Base(f.Path))
		}
		return out
	}

	got := files(dir)
	if len(got) != 1 || got[0] != "guide.md" {
		t.Fatalf("files %v, want [guide.md]: git ignores the other files", got)
	}

	// --all reads every file: guide.md, generated.md, private/secret.md.
	if got := files("--all", dir); len(got) != 3 {
		t.Fatalf("files %v with --all, want 3 files", got)
	}
}

func TestAGivenFileIsReadEvenWhenGitIgnoresIt(t *testing.T) {
	if _, err := exec.LookPath("git"); err != nil {
		t.Skip("git is not on this system")
	}
	dir := t.TempDir()
	if out, err := exec.Command("git", "-C", dir, "init").CombinedOutput(); err != nil {
		t.Fatalf("git init: %v: %s", err, out)
	}
	writeFile(t, dir, ".gitignore", "draft.md\n")
	path := writeFile(t, dir, "draft.md", "The valve isn't open.\n")

	_, stdout, _ := runCLI(t, "", "lint", "--no-config", path)
	if !strings.Contains(stdout, "STE-4.2") {
		t.Fatalf("a file that you give by its path must be read: %q", stdout)
	}
}

func TestAGivenDirectoryIsAlwaysRead(t *testing.T) {
	// The walk skips "dist" below a directory, but it reads "dist" when
	// you give that path to the command.
	dir := t.TempDir()
	sub := filepath.Join(dir, "dist")
	if err := os.MkdirAll(sub, 0o755); err != nil {
		t.Fatalf("mkdir: %v", err)
	}
	writeFile(t, sub, "notes.md", "The report isn't ready.\n")

	code, stdout, stderr := runCLI(t, "", "lint", "--no-config", sub)
	if code != 0 {
		t.Fatalf("exit %d, want 0: %s", code, stderr)
	}
	if !strings.Contains(stdout, "STE-4.2") {
		t.Fatalf("the given directory was not read: %q", stdout)
	}
}

func TestTheSentenceTypeSelectsTheLimit(t *testing.T) {
	dir := t.TempDir()
	// The sentence has 22 words: correct as descriptive text (limit 25),
	// too long as an instruction in a procedure (limit 20).
	words := "one two three four five six seven eight nine ten one two three four five six seven eight nine ten one two.\n"
	prose := writeFile(t, dir, "prose.md", words)
	step := writeFile(t, dir, "step.md", "1. "+words)

	if code, stdout, _ := runCLI(t, "", "lint", "--no-config", prose); !strings.Contains(stdout, "0 findings") || code != 0 {
		t.Fatalf("descriptive text: exit %d, stdout %q", code, stdout)
	}
	if _, stdout, _ := runCLI(t, "", "lint", "--no-config", "--mode", "strict", prose); !strings.Contains(stdout, "0 findings") {
		t.Fatalf("the mode must not change the limit: %q", stdout)
	}
	_, stdout, _ := runCLI(t, "", "lint", "--no-config", step)
	if !strings.Contains(stdout, "STE-5.1") {
		t.Fatalf("the numbered step gave no length finding: %q", stdout)
	}
}

func TestMaxWordsFlagReplacesTheLimit(t *testing.T) {
	dir := t.TempDir()
	path := writeFile(t, dir, "short.md", "The pump gives pressure to the system.\n")
	if code, stdout, _ := runCLI(t, "", "lint", "--no-config", path); !strings.Contains(stdout, "0 findings") || code != 0 {
		t.Fatalf("exit %d, stdout %q", code, stdout)
	}
	_, stdout, _ := runCLI(t, "", "lint", "--no-config", "--max-words", "5", path)
	if !strings.Contains(stdout, "STE-5.1") {
		t.Fatalf("--max-words did not apply: %q", stdout)
	}
}

func TestConfigFileChangesTheResult(t *testing.T) {
	dir := t.TempDir()
	path := writeFile(t, dir, "draft.md", "Leverage the parser.\n")
	cfg := writeFile(t, dir, "glossary.yml", "allow:\n  verbs: [leverage]\n")

	if code, stdout, _ := runCLI(t, "", "lint", "--no-config", path); !strings.Contains(stdout, "STE-1.1") || code != 0 {
		t.Fatalf("without the glossary: exit %d, stdout %q", code, stdout)
	}
	_, stdout, stderr := runCLI(t, "", "lint", "--config", cfg, path)
	if strings.Contains(stdout, "STE-1.1") {
		t.Fatalf("the glossary did not permit the term: %q %q", stdout, stderr)
	}
}

func TestBadFlagsGiveExitCode2(t *testing.T) {
	cases := [][]string{
		{"lint", "--format", "xml", "idea.md"},
		{"lint", "--mode", "pedantic", "idea.md"},
		{"lint", "--no-config", "does-not-exist.md"},
		{"nonsense"},
		{},
	}
	for _, args := range cases {
		if code, _, _ := runCLI(t, "", args...); code != 2 {
			t.Errorf("args %v: exit %d, want 2", args, code)
		}
	}
}

func TestFlagsAfterPaths(t *testing.T) {
	dir := t.TempDir()
	path := writeFile(t, dir, "draft.md", "The valve isn't open.\n")
	code, stdout, stderr := runCLI(t, "", "lint", path, "--no-config", "--format", "json")
	if code != 0 {
		t.Fatalf("exit %d, want 0: %s", code, stderr)
	}
	if !strings.Contains(stdout, "\"rule_id\": \"STE-4.2\"") {
		t.Fatalf("stdout %q", stdout)
	}
}

func TestFlagWithEqualsSign(t *testing.T) {
	dir := t.TempDir()
	path := writeFile(t, dir, "draft.md", "The valve isn't open.\n")
	code, stdout, _ := runCLI(t, "", "lint", path, "--no-config", "--format=json")
	if code != 0 || !strings.Contains(stdout, "STE-4.2") {
		t.Fatalf("exit %d, stdout %q", code, stdout)
	}
}

func TestVersionAndHelp(t *testing.T) {
	if code, stdout, _ := runCLI(t, "", "version"); code != 0 || !strings.Contains(stdout, Version) {
		t.Errorf("version: exit %d, stdout %q", code, stdout)
	}
	if code, stdout, _ := runCLI(t, "", "help"); code != 0 || !strings.Contains(stdout, "Usage:") {
		t.Errorf("help: exit %d, stdout %q", code, stdout)
	}
}

func TestEvalCommand(t *testing.T) {
	code, stdout, stderr := runCLI(t, "", "eval", "--format", "json", filepath.Join("..", "..", "testdata"))
	if code != 0 {
		t.Fatalf("exit %d, want 0: %s", code, stderr)
	}
	var rep struct {
		Files  int `json:"files"`
		Totals struct {
			Precision float64 `json:"precision"`
			Recall    float64 `json:"recall"`
		} `json:"totals"`
	}
	if err := json.Unmarshal([]byte(stdout), &rep); err != nil {
		t.Fatalf("the output is not JSON: %v\n%s", err, stdout)
	}
	if rep.Files == 0 {
		t.Fatal("the corpus has no files")
	}
	if rep.Totals.Precision < 1 || rep.Totals.Recall < 1 {
		t.Fatalf("the corpus does not agree with the rules: precision %.2f, recall %.2f",
			rep.Totals.Precision, rep.Totals.Recall)
	}
}

func TestBaselineWorkflow(t *testing.T) {
	dir := t.TempDir()
	writeFile(t, dir, "old.md", "The valve isn't open.\n")
	base := filepath.Join(dir, "baseline.json")

	// 1. Record the findings that the project accepts today.
	code, stdout, stderr := runCLI(t, "", "baseline", "--no-config", "--baseline", base, dir)
	if code != 0 {
		t.Fatalf("baseline: exit %d: %s", code, stderr)
	}
	if !strings.Contains(stdout, "holds 1 findings") {
		t.Fatalf("baseline output %q", stdout)
	}
	if _, err := os.Stat(base); err != nil {
		t.Fatalf("the baseline file is missing: %v", err)
	}

	// 2. The same text now gives no finding.
	code, stdout, _ = runCLI(t, "", "lint", "--no-config", "--baseline", base, dir)
	if code != 0 || !strings.Contains(stdout, "0 findings") {
		t.Fatalf("exit %d, stdout %q", code, stdout)
	}
	if !strings.Contains(stdout, "1 findings are in the baseline") {
		t.Fatalf("the report does not name the baseline: %q", stdout)
	}

	// 3. A new violation is reported, and it fails the gate.
	writeFile(t, dir, "new.md", "The report isn't ready.\n")
	code, stdout, _ = runCLI(t, "", "lint", "--no-config", "--baseline", base, "--fail-on-new", dir)
	if code != 1 {
		t.Fatalf("exit %d, want 1: %q", code, stdout)
	}
	if !strings.Contains(stdout, "new.md") || strings.Contains(stdout, "old.md") {
		t.Fatalf("the report must show only the new file: %q", stdout)
	}

	// 4. Without the gate, a new finding does not change the exit code.
	if code, _, _ := runCLI(t, "", "lint", "--no-config", "--baseline", base, dir); code != 0 {
		t.Fatalf("exit %d, want 0: the tool must not block by default", code)
	}

	// 5. --no-baseline shows everything again.
	_, stdout, _ = runCLI(t, "", "lint", "--no-config", "--baseline", base, "--no-baseline", dir)
	if !strings.Contains(stdout, "old.md") || !strings.Contains(stdout, "new.md") {
		t.Fatalf("--no-baseline must show every finding: %q", stdout)
	}
}

func TestConfigRulesAndExclude(t *testing.T) {
	dir := t.TempDir()
	writeFile(t, dir, "guide.md", "Open the valve; the report isn't ready.\n")
	sub := filepath.Join(dir, "fixtures")
	if err := os.MkdirAll(sub, 0o755); err != nil {
		t.Fatalf("mkdir: %v", err)
	}
	writeFile(t, sub, "sample.md", "The valve isn't open.\n")
	cfg := writeFile(t, dir, "ste.yml", "rules:\n  STE-4.2: off\n  STE-8.1: error\nexclude:\n  - \"**/fixtures/**\"\n")

	code, stdout, stderr := runCLI(t, "", "lint", "--config", cfg, "--format", "json", dir)
	if code != 0 {
		t.Fatalf("exit %d: %s", code, stderr)
	}
	var rep lintReport
	if err := json.Unmarshal([]byte(stdout), &rep); err != nil {
		t.Fatalf("the output is not JSON: %v", err)
	}
	if rep.Summary.Files != 1 {
		t.Fatalf("files %d, want 1: the exclude pattern must remove the fixture", rep.Summary.Files)
	}
	if rep.Summary.Findings != 1 {
		t.Fatalf("findings %d, want 1: STE-4.2 is off", rep.Summary.Findings)
	}
	if f := rep.Findings[0]; f.RuleID != "STE-8.1" || f.Severity != "error" {
		t.Fatalf("finding %s %s, want STE-8.1 error", f.RuleID, f.Severity)
	}
}

func TestFailOverFromTheConfig(t *testing.T) {
	dir := t.TempDir()
	path := writeFile(t, dir, "draft.md", "The file has been sent; it isn't ready.\n")
	cfg := writeFile(t, dir, "ste.yml", "fail_over: 2.5\n")
	if code, _, _ := runCLI(t, "", "lint", "--config", cfg, path); code != 1 {
		t.Fatalf("exit %d, want 1: the config gives the gate", code)
	}
	// Without the key, the tool never blocks.
	cfg2 := writeFile(t, dir, "ste2.yml", "mode: flavored\n")
	if code, _, _ := runCLI(t, "", "lint", "--config", cfg2, path); code != 0 {
		t.Fatalf("exit %d, want 0", code)
	}
}

func TestWarningsAsErrors(t *testing.T) {
	dir := t.TempDir()
	// A contraction is a warning. A Latin abbreviation is info, because a
	// general recommendation is advice and not a rule.
	path := writeFile(t, dir, "draft.md", "The valve isn't open, e.g. the second one.\n")

	// By default the tool does not block.
	if code, _, _ := runCLI(t, "", "lint", "--no-config", path); code != 0 {
		t.Fatalf("exit %d, want 0", code)
	}

	code, stdout, stderr := runCLI(t, "", "lint", "--no-config", "--warnings-as-errors", path)
	if code != 1 {
		t.Fatalf("exit %d, want 1: %s", code, stderr)
	}
	if !strings.Contains(stdout, "error [STE-4.2]") {
		t.Errorf("the warning did not become an error: %q", stdout)
	}
	if !strings.Contains(stdout, "info [STE-GR-6]") {
		t.Errorf("a general recommendation must stay advice: %q", stdout)
	}
}

func TestWarningsAsErrorsFromTheConfig(t *testing.T) {
	dir := t.TempDir()
	path := writeFile(t, dir, "draft.md", "The valve isn't open.\n")
	cfg := writeFile(t, dir, "ste.yml", "warnings_as_errors: true\n")
	if code, _, _ := runCLI(t, "", "lint", "--config", cfg, path); code != 1 {
		t.Fatalf("exit %d, want 1", code)
	}
}

func TestWarningsAsErrorsObeysTheBaseline(t *testing.T) {
	// An accepted finding must not block, even with this flag. The gate is
	// for the new work, and not for the text that the project accepted.
	dir := t.TempDir()
	writeFile(t, dir, "old.md", "The valve isn't open.\n")
	base := filepath.Join(dir, "baseline.json")
	if code, _, stderr := runCLI(t, "", "baseline", "--no-config", "--baseline", base, dir); code != 0 {
		t.Fatalf("baseline: exit %d: %s", code, stderr)
	}
	if code, _, _ := runCLI(t, "", "lint", "--no-config", "--baseline", base, "--warnings-as-errors", dir); code != 0 {
		t.Fatalf("exit %d, want 0: the baseline must hide the finding", code)
	}
	writeFile(t, dir, "new.md", "The report isn't ready.\n")
	if code, _, _ := runCLI(t, "", "lint", "--no-config", "--baseline", base, "--warnings-as-errors", dir); code != 1 {
		t.Fatalf("exit %d, want 1: a new finding must block", code)
	}
}

func TestWarningsAsErrorsKeepsAnExplicitInfoRule(t *testing.T) {
	dir := t.TempDir()
	path := writeFile(t, dir, "draft.md", "The valve isn't open.\n")
	cfg := writeFile(t, dir, "ste.yml", "rules:\n  STE-4.2: info\n")
	code, stdout, _ := runCLI(t, "", "lint", "--config", cfg, "--warnings-as-errors", path)
	if code != 0 {
		t.Fatalf("exit %d, want 0: an explicit info rule must not become an error", code)
	}
	if !strings.Contains(stdout, "info [STE-4.2]") {
		t.Errorf("stdout %q", stdout)
	}
}

// The fixture is not the ASD-STE100 dictionary. It has the shape of the
// table of part 2, with invented words.
const dictFixture = `## Part 2 – Dictionary

|Word (part of speech)|Approved meaning/ ALTERNATIVES|STE EXAMPLE|Non-STE example|
|---|---|---|---|
|FRAMMIS (n)|A part of the machine|INSTALL THE FRAMMIS.||
|wibble (n)|FRAMMIS (n)|INSTALL THE FRAMMIS.|Install the wibble.|
`

func TestDictImportAndUse(t *testing.T) {
	dir := t.TempDir()
	source := writeFile(t, dir, "spec.md", dictFixture)
	index := filepath.Join(dir, "dictionary.json")

	// Before the import, there is no index.
	if code, stdout, _ := runCLI(t, "", "dict", "info", "--out", index); code != 0 || !strings.Contains(stdout, "no index") {
		t.Fatalf("exit %d, stdout %q", code, stdout)
	}

	code, stdout, stderr := runCLI(t, "", "dict", "import", "--out", index, source)
	if code != 0 {
		t.Fatalf("import: exit %d: %s", code, stderr)
	}
	if !strings.Contains(stdout, "2 words") || !strings.Contains(stdout, "do not commit") {
		t.Fatalf("import output %q", stdout)
	}

	page := writeFile(t, dir, "page.md", "Install the wibble in the frammis.\n")

	// The dictionary is off by default, thus the word gives no finding.
	if code, stdout, _ := runCLI(t, "", "lint", "--no-config", "--dict", index, page); code != 0 || !strings.Contains(stdout, "0 findings") {
		t.Fatalf("the dictionary must be off by default: exit %d, stdout %q", code, stdout)
	}

	// --use-dict makes rule STE-1.1 use it.
	_, stdout, _ = runCLI(t, "", "lint", "--no-config", "--dict", index, "--use-dict", page)
	if !strings.Contains(stdout, "STE-1.1") || !strings.Contains(stdout, "wibble") {
		t.Fatalf("the dictionary gave no finding: %q", stdout)
	}
	if !strings.Contains(stdout, "frammis") {
		t.Fatalf("the report gives no alternative: %q", stdout)
	}
}

func TestDictUseWithNoIndexIsAnError(t *testing.T) {
	dir := t.TempDir()
	page := writeFile(t, dir, "page.md", "Install the wibble.\n")
	missing := filepath.Join(dir, "none.json")
	code, _, stderr := runCLI(t, "", "lint", "--no-config", "--dict", missing, "--use-dict", page)
	if code != 2 {
		t.Fatalf("exit %d, want 2", code)
	}
	if !strings.Contains(stderr, "dict import") {
		t.Fatalf("the error must name the command: %q", stderr)
	}
}

func TestDictImportRejectsAPDF(t *testing.T) {
	dir := t.TempDir()
	pdf := writeFile(t, dir, "spec.pdf", "%PDF-1.4\n")
	code, _, stderr := runCLI(t, "", "dict", "import", "--out", filepath.Join(dir, "d.json"), pdf)
	if code != 2 {
		t.Fatalf("exit %d, want 2", code)
	}
	if !strings.Contains(stderr, "anydoc") {
		t.Fatalf("the error must give the conversion command: %q", stderr)
	}
}

func TestDictGlossaryWins(t *testing.T) {
	// A technical noun of the project stays, even when the dictionary does
	// not approve it. Rule 1.6 permits it.
	dir := t.TempDir()
	source := writeFile(t, dir, "spec.md", dictFixture)
	index := filepath.Join(dir, "dictionary.json")
	if code, _, _ := runCLI(t, "", "dict", "import", "--out", index, source); code != 0 {
		t.Fatal("import failed")
	}
	page := writeFile(t, dir, "page.md", "Install the wibble.\n")
	cfg := writeFile(t, dir, "ste.yml", "dictionary: true\nallow:\n  nouns: [wibble]\n")
	code, stdout, _ := runCLI(t, "", "lint", "--config", cfg, "--dict", index, page)
	if code != 0 || !strings.Contains(stdout, "0 findings") {
		t.Fatalf("the glossary must permit the technical noun: exit %d, %q", code, stdout)
	}
}

func TestAnUnknownFlagGivesAMessage(t *testing.T) {
	// pflag with ContinueOnError returns the error and prints nothing.
	// A command that only returns an exit code leaves the user with no
	// message at all.
	cases := [][]string{
		{"lint", "--use-diict", "."},
		{"lint", "--formt", "json", "."},
		{"eval", "--frmat", "json", "testdata"},
		{"dict", "--ot", "/tmp/x.json", "info"},
	}
	for _, args := range cases {
		code, _, stderr := runCLI(t, "", args...)
		if code != 2 {
			t.Errorf("args %v: exit %d, want 2", args, code)
		}
		if !strings.Contains(stderr, "unknown flag") {
			t.Errorf("args %v: stderr %q, want the name of the flag", args, stderr)
		}
	}
}

func TestAgentOutputControls(t *testing.T) {
	dir := t.TempDir()
	writeFile(t, dir, "a.md", "The valve isn't open; the report isn't ready.\n")
	writeFile(t, dir, "b.md", "The pump isn't on; the fan isn't off.\n")

	// The full result.
	_, stdout, _ := runCLI(t, "", "lint", "--no-config", "--format", "json", dir)
	var full lintReport
	if err := json.Unmarshal([]byte(stdout), &full); err != nil {
		t.Fatalf("not JSON: %v", err)
	}
	if full.Summary.Findings < 4 {
		t.Fatalf("findings %d, want 4 or more", full.Summary.Findings)
	}

	// --limit caps the findings and says that it did.
	_, stdout, _ = runCLI(t, "", "lint", "--no-config", "--format", "json", "--limit", "2", dir)
	var small lintReport
	if err := json.Unmarshal([]byte(stdout), &small); err != nil {
		t.Fatalf("not JSON: %v", err)
	}
	if len(small.Findings) != 2 {
		t.Errorf("findings %d, want 2", len(small.Findings))
	}
	if !small.Summary.Truncated || small.Summary.Shown != 2 {
		t.Errorf("summary %+v, want truncated with shown 2", small.Summary)
	}
	if small.Summary.Findings != full.Summary.Findings {
		t.Errorf("the summary must keep the real total: %d, want %d",
			small.Summary.Findings, full.Summary.Findings)
	}
	// The file rows follow the findings that the output shows.
	if len(small.Files) > 2 {
		t.Errorf("files %d, want 2 or fewer with --limit 2", len(small.Files))
	}

	// --fields gives only the named fields.
	_, stdout, _ = runCLI(t, "", "lint", "--no-config", "--format", "json", "--fields", "rule_id,line", dir)
	var projected struct {
		Findings []map[string]any `json:"findings"`
	}
	if err := json.Unmarshal([]byte(stdout), &projected); err != nil {
		t.Fatalf("not JSON: %v", err)
	}
	for _, f := range projected.Findings {
		if len(f) != 2 || f["rule_id"] == nil || f["line"] == nil {
			t.Fatalf("finding %v, want only rule_id and line", f)
		}
	}

	// --summary gives no findings and no file list.
	_, stdout, _ = runCLI(t, "", "lint", "--no-config", "--format", "json", "--summary", dir)
	if strings.Contains(stdout, "\"findings\": [") || strings.Contains(stdout, "\"files\": [") {
		t.Errorf("--summary must give no list: %q", stdout)
	}

	// An unknown field is an error that names the fields.
	code, _, stderr := runCLI(t, "", "lint", "--no-config", "--fields", "rule_id,nope", dir)
	if code != 2 || !strings.Contains(stderr, "nope") {
		t.Errorf("exit %d, stderr %q", code, stderr)
	}
}

func TestNDJSONOutput(t *testing.T) {
	dir := t.TempDir()
	writeFile(t, dir, "a.md", "The valve isn't open; the report isn't ready.\n")

	_, stdout, _ := runCLI(t, "", "lint", "--no-config", "--format", "ndjson", dir)
	lines := strings.Split(strings.TrimSpace(stdout), "\n")
	if len(lines) < 2 {
		t.Fatalf("got %d lines, want a finding and a summary", len(lines))
	}
	findings, summaries := 0, 0
	for _, line := range lines {
		var obj map[string]any
		if err := json.Unmarshal([]byte(line), &obj); err != nil {
			t.Fatalf("line is not JSON: %v: %s", err, line)
		}
		switch obj["type"] {
		case "finding":
			findings++
		case "summary":
			summaries++
		default:
			t.Errorf("line has no type: %s", line)
		}
	}
	if summaries != 1 {
		t.Errorf("summaries %d, want 1", summaries)
	}
	if findings < 1 {
		t.Errorf("findings %d, want 1 or more", findings)
	}
}

func TestSchemaIsSelfDescribing(t *testing.T) {
	code, stdout, stderr := runCLI(t, "", "schema")
	if code != 0 {
		t.Fatalf("exit %d: %s", code, stderr)
	}
	var s struct {
		Tool  string `json:"tool"`
		Rules []struct {
			ID       string `json:"id"`
			Standard string `json:"standard_rule"`
		} `json:"rules"`
		ExitCodes  map[string]string `json:"exit_codes"`
		ConfigKeys map[string]any    `json:"config_keys"`
		Output     map[string]any    `json:"output"`
	}
	if err := json.Unmarshal([]byte(stdout), &s); err != nil {
		t.Fatalf("the schema is not JSON: %v", err)
	}
	if s.Tool != "ste" {
		t.Errorf("tool %q", s.Tool)
	}
	if len(s.Rules) != 15 {
		t.Errorf("rules %d, want 15", len(s.Rules))
	}
	for _, r := range s.Rules {
		if !strings.HasPrefix(r.ID, "STE-") || r.Standard == "" {
			t.Errorf("rule %+v", r)
		}
	}
	for _, code := range []string{"0", "1", "2"} {
		if s.ExitCodes[code] == "" {
			t.Errorf("the schema has no exit code %s", code)
		}
	}
	if s.ConfigKeys["rules"] == nil || s.ConfigKeys["baseline"] == nil {
		t.Errorf("the schema is missing a config key")
	}
	if s.Output["finding_fields"] == nil {
		t.Errorf("the schema does not name the fields of a finding")
	}
}

func TestDryRunWritesNothing(t *testing.T) {
	dir := t.TempDir()
	writeFile(t, dir, "a.md", "The valve isn't open.\n")
	base := filepath.Join(dir, "baseline.json")

	code, stdout, stderr := runCLI(t, "", "baseline", "--no-config", "--baseline", base, "--dry-run", "--format", "json", dir)
	if code != 0 {
		t.Fatalf("exit %d: %s", code, stderr)
	}
	var plan map[string]any
	if err := json.Unmarshal([]byte(stdout), &plan); err != nil {
		t.Fatalf("not JSON: %v", err)
	}
	if plan["dry_run"] != true || plan["action"] != "baseline" {
		t.Errorf("plan %v", plan)
	}
	if _, err := os.Stat(base); !os.IsNotExist(err) {
		t.Fatalf("--dry-run wrote the file")
	}

	// The real run writes it.
	if code, _, _ := runCLI(t, "", "baseline", "--no-config", "--baseline", base, dir); code != 0 {
		t.Fatal("the real run failed")
	}
	if _, err := os.Stat(base); err != nil {
		t.Fatalf("the real run wrote nothing: %v", err)
	}
}

func TestDictDryRun(t *testing.T) {
	dir := t.TempDir()
	source := writeFile(t, dir, "spec.md", dictFixture)
	index := filepath.Join(dir, "dictionary.json")

	code, stdout, _ := runCLI(t, "", "dict", "import", "--out", index, "--dry-run", "--format", "json", source)
	if code != 0 {
		t.Fatalf("exit %d", code)
	}
	var plan map[string]any
	if err := json.Unmarshal([]byte(stdout), &plan); err != nil {
		t.Fatalf("not JSON: %v", err)
	}
	if plan["dry_run"] != true || plan["words"].(float64) != 2 {
		t.Errorf("plan %v", plan)
	}
	if _, err := os.Stat(index); !os.IsNotExist(err) {
		t.Fatal("--dry-run wrote the index")
	}
}

func TestAnalyzerVetoesAFinding(t *testing.T) {
	python, err := exec.LookPath("python3")
	if err != nil {
		t.Skip("python3 is not on this system")
	}
	stub, err := filepath.Abs(filepath.Join("..", "..", "internal", "analyzer", "testdata", "stub_analyzer.py"))
	if err != nil {
		t.Fatal(err)
	}
	dir := t.TempDir()
	// The stub calls "signed" a passive verb, and no other word. Thus the
	// first sentence keeps its finding and the second loses it.
	path := writeFile(t, dir, "a.md", "The report was signed by the team.\n\nThere is measured user demand.\n")

	_, stdout, _ := runCLI(t, "", "lint", "--no-config", path)
	if strings.Count(stdout, "STE-3.6") != 2 {
		t.Fatalf("without the analyzer, want 2 findings: %q", stdout)
	}

	code, stdout, stderr := runCLI(t, "", "lint", "--no-config", "--analyzer", python+" "+stub, path)
	if code != 0 {
		t.Fatalf("exit %d: %s", code, stderr)
	}
	if strings.Count(stdout, "STE-3.6") != 1 {
		t.Fatalf("with the analyzer, want 1 finding: %q", stdout)
	}
	if !strings.Contains(stdout, "signed") {
		t.Errorf("the analyzer removed the wrong finding: %q", stdout)
	}
}

func TestAnalyzerCommandReportsWhatItNeeds(t *testing.T) {
	code, stdout, stderr := runCLI(t, "", "analyzer", "--format", "json")
	if code != 0 {
		t.Fatalf("exit %d: %s", code, stderr)
	}
	var s struct {
		Ready   bool     `json:"ready"`
		Python  string   `json:"python"`
		Problem string   `json:"problem"`
		Fix     []string `json:"fix"`
	}
	if err := json.Unmarshal([]byte(stdout), &s); err != nil {
		t.Fatalf("not JSON: %v", err)
	}
	// The answer must be useful in each case: it says that the analyzer is
	// ready, or it names the problem.
	if !s.Ready && s.Problem == "" {
		t.Errorf("the command gives no reason: %s", stdout)
	}
	if !s.Ready && len(s.Fix) == 0 && s.Python != "" {
		t.Errorf("the command gives no correction: %s", stdout)
	}
}

func TestTheEmbeddedAnalyzerIsWritten(t *testing.T) {
	// The binary holds the analyzer, thus a user needs no file from the
	// repository.
	code, stdout, _ := runCLI(t, "", "analyzer", "--format", "json")
	if code != 0 {
		t.Fatal("the analyzer command failed")
	}
	var s struct {
		Script string `json:"script"`
	}
	if err := json.Unmarshal([]byte(stdout), &s); err != nil {
		t.Fatal(err)
	}
	if s.Script == "" {
		t.Skip("the tool found no python, thus it wrote no script")
	}
	raw, err := os.ReadFile(s.Script)
	if err != nil {
		t.Fatalf("the script is not on the disk: %v", err)
	}
	if !strings.Contains(string(raw), "ste-analyzer") && !strings.Contains(string(raw), "spacy") {
		t.Errorf("the file is not the analyzer")
	}
}

func TestABadAnalyzerCommandIsAnError(t *testing.T) {
	dir := t.TempDir()
	path := writeFile(t, dir, "a.md", "The report was signed by the team.\n")
	code, _, stderr := runCLI(t, "", "lint", "--no-config", "--analyzer", "no-such-analyzer-1234", path)
	if code != 2 {
		t.Fatalf("exit %d, want 2", code)
	}
	if !strings.Contains(stderr, "analyzer") {
		t.Errorf("stderr %q", stderr)
	}
}
