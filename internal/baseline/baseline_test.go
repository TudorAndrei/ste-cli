package baseline

import (
	"encoding/json"
	"os"
	"path/filepath"
	"testing"
)

func TestTakeCountsEachFinding(t *testing.T) {
	s := New()
	s.Add("a.md", "STE-4.2", "isn't")
	s.Add("a.md", "STE-4.2", "isn't")
	if !s.Take("a.md", "STE-4.2", "isn't") || !s.Take("a.md", "STE-4.2", "isn't") {
		t.Fatal("the set did not give the two accepted findings")
	}
	if s.Take("a.md", "STE-4.2", "isn't") {
		t.Fatal("a third finding is new")
	}
	// The key ignores the spaces in the text.
	s.Add("a.md", "STE-5.1", "one  two\nthree")
	if !s.Take("a.md", "STE-5.1", "one two three") {
		t.Fatal("the spaces changed the key")
	}
}

func TestStaleCountsOnlyTheGivenFiles(t *testing.T) {
	s := New()
	s.Add("a.md", "STE-4.2", "isn't")
	s.Add("b.md", "STE-8.1", ";")
	if n := s.Stale(map[string]bool{"a.md": true}); n != 1 {
		t.Errorf("stale %d, want 1", n)
	}
	s.Take("a.md", "STE-4.2", "isn't")
	if n := s.Stale(map[string]bool{"a.md": true}); n != 0 {
		t.Errorf("stale %d, want 0", n)
	}
}

func TestClean(t *testing.T) {
	for in, want := range map[string]string{
		"./docs/a.md":      "docs/a.md",
		"docs//a.md":       "docs/a.md",
		"(standard input)": "(standard input)",
	} {
		if got := Clean(in); got != want {
			t.Errorf("Clean(%q) = %q, want %q", in, got, want)
		}
	}
}

func TestLoadAMissingFileGivesAnEmptySet(t *testing.T) {
	s, err := Load(filepath.Join(t.TempDir(), "none.json"))
	if err != nil || s.Take("a.md", "STE-4.2", "isn't") {
		t.Fatalf("err %v", err)
	}
}

func TestLoadCleansTheFileAndTheCount(t *testing.T) {
	path := filepath.Join(t.TempDir(), "b.json")
	raw := `{"version":1,"entries":[{"file":"./a.md","rule_id":"STE-4.2","text":"isn't","count":0}]}`
	if err := os.WriteFile(path, []byte(raw), 0o644); err != nil {
		t.Fatal(err)
	}
	s, err := Load(path)
	if err != nil {
		t.Fatal(err)
	}
	if !s.Take("a.md", "STE-4.2", "isn't") {
		t.Fatal("the entry with ./ and a count of 0 did not load as one finding")
	}
}

func TestLoadABadFileIsAnError(t *testing.T) {
	path := filepath.Join(t.TempDir(), "b.json")
	if err := os.WriteFile(path, []byte("{"), 0o644); err != nil {
		t.Fatal(err)
	}
	if _, err := Load(path); err == nil {
		t.Fatal("no error")
	}
}

func TestSaveMergesWithTheOldFile(t *testing.T) {
	dir := t.TempDir()
	for _, name := range []string{"a.md", "b.md"} {
		if err := os.WriteFile(filepath.Join(dir, name), nil, 0o644); err != nil {
			t.Fatal(err)
		}
	}
	path := filepath.Join(dir, "baseline.json")
	first := []Result{
		{Path: "a.md", Findings: []Finding{{RuleID: "STE-4.2", Text: "isn't"}}},
		{Path: "b.md", Findings: []Finding{{RuleID: "STE-8.1", Text: ";"}}},
		{Path: "gone.md", Findings: []Finding{{RuleID: "STE-8.1", Text: ";"}}},
	}
	if err := Save(path, first, "t1"); err != nil {
		t.Fatal(err)
	}

	// A run of a.md only. b.md stays, and gone.md goes, because the file
	// does not exist.
	second := []Result{{Path: "a.md", Findings: []Finding{{RuleID: "STE-3.6", Text: "was sent"}}}}
	plan, err := Plan(path, second)
	if err != nil {
		t.Fatal(err)
	}
	if plan.Kept != 1 || plan.Removed != 1 {
		t.Errorf("plan kept %d and removed %d, want 1 and 1", plan.Kept, plan.Removed)
	}
	if err := Save(path, second, "t2"); err != nil {
		t.Fatal(err)
	}

	raw, err := os.ReadFile(path)
	if err != nil {
		t.Fatal(err)
	}
	var f File
	if err := json.Unmarshal(raw, &f); err != nil {
		t.Fatal(err)
	}
	want := []Entry{
		{File: "a.md", RuleID: "STE-3.6", Text: "was sent", Count: 1},
		{File: "b.md", RuleID: "STE-8.1", Text: ";", Count: 1},
	}
	if f.Created != "t2" || len(f.Entries) != len(want) {
		t.Fatalf("file %+v", f)
	}
	for i := range want {
		if f.Entries[i] != want[i] {
			t.Errorf("entry %d: %+v, want %+v", i, f.Entries[i], want[i])
		}
	}
}
