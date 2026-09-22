package main

import (
	"encoding/json"
	"os"
	"path/filepath"
	"strings"
	"testing"
)

// newProject makes a git work tree with one Markdown file in docs/, and
// makes it the current directory.
func newProject(t *testing.T) string {
	t.Helper()
	dir, err := filepath.EvalSymlinks(t.TempDir())
	if err != nil {
		t.Fatal(err)
	}
	for _, d := range []string{".git", "docs"} {
		if err := os.MkdirAll(filepath.Join(dir, d), 0o755); err != nil {
			t.Fatal(err)
		}
	}
	writeFile(t, filepath.Join(dir, "docs"), "a.md", "The valve isn't open; close it.\n")
	t.Chdir(dir)
	return dir
}

func lintJSON(t *testing.T, args ...string) lintReport {
	t.Helper()
	code, stdout, stderr := runCLI(t, "", append([]string{"lint", "--format", "json"}, args...)...)
	if code != 0 {
		t.Fatalf("exit %d: %s", code, stderr)
	}
	var rep lintReport
	if err := json.Unmarshal([]byte(stdout), &rep); err != nil {
		t.Fatalf("the output is not JSON: %v\n%s", err, stdout)
	}
	return rep
}

func TestTheBaselineMatchesEachSpellingOfAPath(t *testing.T) {
	dir := newProject(t)
	if code, _, stderr := runCLI(t, "", "baseline", "."); code != 0 {
		t.Fatalf("baseline: exit %d: %s", code, stderr)
	}

	for _, p := range []string{".", "docs", "./docs", "docs/a.md", filepath.Join(dir, "docs")} {
		if rep := lintJSON(t, p); rep.Summary.Findings != 0 || rep.Summary.Accepted != 2 {
			t.Errorf("path %q: %d findings and %d accepted, want 0 and 2", p, rep.Summary.Findings, rep.Summary.Accepted)
		}
	}

	// A run from a subdirectory finds the baseline of the project.
	t.Chdir(filepath.Join(dir, "docs"))
	if rep := lintJSON(t, "."); rep.Summary.Findings != 0 || rep.Summary.Accepted != 2 {
		t.Errorf("from docs/: %d findings and %d accepted, want 0 and 2", rep.Summary.Findings, rep.Summary.Accepted)
	}
}

func TestTheConfigOfTheProjectAppliesInASubdirectory(t *testing.T) {
	dir := newProject(t)
	writeFile(t, dir, ".ste.yml", "rules:\n  STE-8.1: off\n")

	t.Chdir(filepath.Join(dir, "docs"))
	rep := lintJSON(t, "a.md")
	for _, f := range rep.Findings {
		if f.RuleID == "STE-8.1" {
			t.Fatalf("the config of the project did not apply: %+v", rep.Findings)
		}
	}
	if rep.Summary.Findings != 1 {
		t.Fatalf("findings %d, want 1 (STE-4.2)", rep.Summary.Findings)
	}
}

func TestTheSearchForAConfigStopsAtTheGitWorkTree(t *testing.T) {
	outer, err := filepath.EvalSymlinks(t.TempDir())
	if err != nil {
		t.Fatal(err)
	}
	writeFile(t, outer, ".ste.yml", "rules:\n  STE-8.1: off\n")
	inner := filepath.Join(outer, "repo")
	if err := os.MkdirAll(filepath.Join(inner, ".git"), 0o755); err != nil {
		t.Fatal(err)
	}
	writeFile(t, inner, "a.md", "Close it; now.\n")
	t.Chdir(inner)

	if rep := lintJSON(t, "a.md"); rep.Summary.Findings != 1 {
		t.Fatalf("findings %d, want 1: the config above the work tree must not apply", rep.Summary.Findings)
	}
}

func TestExcludeStartsFromTheProjectDirectory(t *testing.T) {
	dir := newProject(t)
	legacy := filepath.Join(dir, "docs", "legacy")
	if err := os.MkdirAll(legacy, 0o755); err != nil {
		t.Fatal(err)
	}
	writeFile(t, legacy, "old.md", "It isn't open.\n")
	writeFile(t, dir, ".ste.yml", "exclude:\n  - \"docs/legacy/**\"\n")

	// The pattern names docs/, and the run starts in docs/.
	if rep := lintJSON(t, "docs"); rep.Summary.Files != 1 {
		t.Errorf("files %d, want 1: the pattern did not apply to a run of docs/", rep.Summary.Files)
	}

	// A hook of git gives each file by its path.
	if rep := lintJSON(t, "docs/legacy/old.md", "docs/a.md"); rep.Summary.Files != 1 {
		t.Errorf("files %d, want 1: the pattern did not apply to a file given by its path", rep.Summary.Files)
	}

	// Only excluded files give an empty result, and not an error.
	if rep := lintJSON(t, "docs/legacy/old.md"); rep.Summary.Files != 0 {
		t.Errorf("files %d, want 0", rep.Summary.Files)
	}
}

func TestABaselineOfOneDirectoryKeepsTheOthers(t *testing.T) {
	dir := newProject(t)
	other := filepath.Join(dir, "guide")
	if err := os.MkdirAll(other, 0o755); err != nil {
		t.Fatal(err)
	}
	writeFile(t, other, "b.md", "It isn't open.\n")
	if code, _, stderr := runCLI(t, "", "baseline", "."); code != 0 {
		t.Fatalf("baseline: exit %d: %s", code, stderr)
	}

	// A new baseline of docs/ only must not remove the entry of guide/.
	code, stdout, stderr := runCLI(t, "", "baseline", "--format", "json", "docs")
	if code != 0 {
		t.Fatalf("baseline docs: exit %d: %s", code, stderr)
	}
	var plan map[string]any
	if err := json.Unmarshal([]byte(stdout), &plan); err != nil {
		t.Fatalf("not JSON: %v", err)
	}
	if plan["kept"] != float64(1) {
		t.Errorf("plan %v, want kept 1", plan)
	}
	if rep := lintJSON(t, "."); rep.Summary.Findings != 0 {
		t.Fatalf("findings %d, want 0: the entry of guide/ was lost", rep.Summary.Findings)
	}

	// The entry of a deleted file goes.
	if err := os.Remove(filepath.Join(other, "b.md")); err != nil {
		t.Fatal(err)
	}
	_, stdout, _ = runCLI(t, "", "baseline", "--dry-run", "--format", "json", "docs")
	if err := json.Unmarshal([]byte(stdout), &plan); err != nil {
		t.Fatalf("not JSON: %v", err)
	}
	if plan["removed"] != float64(1) || plan["kept"] != float64(0) {
		t.Errorf("plan %v, want removed 1 and kept 0", plan)
	}
}

func TestTheCodeHostFormatsGivePathsFromTheRepository(t *testing.T) {
	dir := newProject(t)
	t.Chdir(filepath.Join(dir, "docs"))

	code, stdout, stderr := runCLI(t, "", "lint", "--format", "github", filepath.Join(dir, "docs", "a.md"))
	if code != 0 {
		t.Fatalf("exit %d: %s", code, stderr)
	}
	if !strings.HasPrefix(stdout, "::warning file=docs/a.md,") {
		t.Errorf("github format:\n%s", stdout)
	}

	_, stdout, _ = runCLI(t, "", "lint", "--format", "sarif", "a.md")
	if !strings.Contains(stdout, `"uri": "docs/a.md"`) {
		t.Errorf("sarif format:\n%s", stdout)
	}
}

func TestTheReportCountsStaleEntries(t *testing.T) {
	dir := newProject(t)
	if code, _, stderr := runCLI(t, "", "baseline", "."); code != 0 {
		t.Fatalf("baseline: exit %d: %s", code, stderr)
	}
	writeFile(t, filepath.Join(dir, "docs"), "a.md", "The valve is not open; close it.\n")

	rep := lintJSON(t, ".")
	if rep.Summary.Accepted != 1 || rep.Summary.Stale != 1 {
		t.Fatalf("accepted %d and stale %d, want 1 and 1", rep.Summary.Accepted, rep.Summary.Stale)
	}
	_, stdout, _ := runCLI(t, "", "lint", ".")
	if want := "1 accepted findings are not in the text now"; !strings.Contains(stdout, want) {
		t.Errorf("the text report does not say %q:\n%s", want, stdout)
	}
}
