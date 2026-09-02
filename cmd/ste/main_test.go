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
	var rep struct {
		Version int    `json:"version"`
		Mode    string `json:"mode"`
		Files   []struct {
			Path     string `json:"path"`
			Words    int    `json:"words"`
			Findings []struct {
				RuleID string `json:"rule_id"`
				Line   int    `json:"line"`
				Column int    `json:"column"`
				Text   string `json:"text"`
			} `json:"findings"`
		} `json:"files"`
		Summary struct {
			Findings int     `json:"findings"`
			Words    int     `json:"words"`
			Score    float64 `json:"score"`
		} `json:"summary"`
	}
	if err := json.Unmarshal([]byte(stdout), &rep); err != nil {
		t.Fatalf("the output is not JSON: %v\n%s", err, stdout)
	}
	if rep.Version != 1 || rep.Mode != "flavored" {
		t.Errorf("version %d, mode %q", rep.Version, rep.Mode)
	}
	if len(rep.Files) != 1 || rep.Files[0].Path != path {
		t.Fatalf("files %+v", rep.Files)
	}
	if len(rep.Files[0].Findings) != 3 {
		t.Fatalf("got %d findings, want 3: %+v", len(rep.Files[0].Findings), rep.Files[0].Findings)
	}
	if rep.Summary.Findings != 3 || rep.Summary.Words == 0 || rep.Summary.Score <= 0 {
		t.Errorf("summary %+v", rep.Summary)
	}
	for _, f := range rep.Files[0].Findings {
		if f.Line < 1 || f.Column < 1 {
			t.Errorf("finding %s has the position %d:%d", f.RuleID, f.Line, f.Column)
		}
	}
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
