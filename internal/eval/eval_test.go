package eval

import (
	"bytes"
	"encoding/json"
	"os"
	"path/filepath"
	"strings"
	"testing"
)

func write(t *testing.T, dir, name, content string) {
	t.Helper()
	if err := os.WriteFile(filepath.Join(dir, name), []byte(content), 0o644); err != nil {
		t.Fatal(err)
	}
}

func scoreOf(r Report, id string) RuleScore {
	for _, s := range r.Rules {
		if s.RuleID == id {
			return s
		}
	}
	return RuleScore{RuleID: id}
}

func TestRunCountsEachOutcome(t *testing.T) {
	dir := t.TempDir()
	// One semicolon is labeled, and one contraction is not: a false
	// positive. The label for rule 3.6 finds nothing: a false negative.
	write(t, dir, "a.md", "Open the valve; it isn't hot.\n")
	write(t, dir, "a.expected.json", `{"expect": [
		{"rule_id": "STE-8.1", "text": ";"},
		{"rule_id": "STE-3.6", "text": "was sent"}
	]}`)
	// A file with no labels must give no finding.
	write(t, dir, "clean.md", "Open the valve.\n")
	write(t, dir, "notes.json", "{}")

	r, err := Run(dir)
	if err != nil {
		t.Fatal(err)
	}
	if r.Files != 2 {
		t.Errorf("files %d, want 2", r.Files)
	}
	if s := scoreOf(r, "STE-8.1"); s.TruePositives != 1 || s.Precision != 1 || s.Recall != 1 {
		t.Errorf("STE-8.1 %+v", s)
	}
	if s := scoreOf(r, "STE-4.2"); s.FalsePositives != 1 || s.Precision != 0 {
		t.Errorf("STE-4.2 %+v", s)
	}
	if s := scoreOf(r, "STE-3.6"); s.FalseNegatives != 1 || s.Recall != 0 {
		t.Errorf("STE-3.6 %+v", s)
	}
	if r.Totals.RuleID != "all" || r.Totals.TruePositives != 1 || r.Totals.FalsePositives != 1 || r.Totals.FalseNegatives != 1 {
		t.Errorf("totals %+v", r.Totals)
	}
}

func TestALabelWithNoTextMatchesEachSpan(t *testing.T) {
	dir := t.TempDir()
	write(t, dir, "a.md", "Close it; now.\n")
	write(t, dir, "a.expected.json", `{"expect": [{"rule_id": "STE-8.1"}]}`)
	r, err := Run(dir)
	if err != nil {
		t.Fatal(err)
	}
	if s := scoreOf(r, "STE-8.1"); s.TruePositives != 1 {
		t.Errorf("STE-8.1 %+v", s)
	}
}

func TestTheLabelsGiveTheOptions(t *testing.T) {
	dir := t.TempDir()
	write(t, dir, "a.md", "Open the settings file.\n")
	write(t, dir, "a.expected.json", `{"prefer": {"config file": ["settings file"]},
		"expect": [{"rule_id": "STE-1.11", "text": "settings file"}]}`)
	r, err := Run(dir)
	if err != nil {
		t.Fatal(err)
	}
	if r.Totals.Precision != 1 || r.Totals.Recall != 1 {
		t.Errorf("totals %+v", r.Totals)
	}
}

func TestRunErrors(t *testing.T) {
	if _, err := Run(t.TempDir()); err == nil || !strings.Contains(err.Error(), "no fixture files") {
		t.Errorf("an empty corpus: %v", err)
	}
	dir := t.TempDir()
	write(t, dir, "a.md", "Text.\n")
	write(t, dir, "a.expected.json", "{")
	if _, err := Run(dir); err == nil || !strings.Contains(err.Error(), "a.expected.json") {
		t.Errorf("a bad label file: %v", err)
	}
}

func TestWrite(t *testing.T) {
	r := Report{Files: 1, Rules: []RuleScore{{RuleID: "STE-8.1", TruePositives: 1, Precision: 1, Recall: 1}},
		Totals: RuleScore{RuleID: "all", TruePositives: 1, Precision: 1, Recall: 1}}
	var text bytes.Buffer
	if err := WriteText(&text, r); err != nil {
		t.Fatal(err)
	}
	if !strings.Contains(text.String(), "STE-8.1") || !strings.Contains(text.String(), "1 fixture files") {
		t.Errorf("text:\n%s", text.String())
	}
	var raw bytes.Buffer
	if err := WriteJSON(&raw, r); err != nil {
		t.Fatal(err)
	}
	var back Report
	if err := json.Unmarshal(raw.Bytes(), &back); err != nil || back.Totals.TruePositives != 1 {
		t.Errorf("json: %v %+v", err, back)
	}
}
