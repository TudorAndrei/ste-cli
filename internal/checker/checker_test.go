package checker_test

import (
	"encoding/json"
	"testing"

	"github.com/TudorAndrei/ste-cli/internal/checker"
)

func TestLintCleanTextGivesNoFindings(t *testing.T) {
	got := checker.Lint("Start the pump. Then open the valve.", checker.Options{})
	if len(got) != 0 {
		t.Fatalf("got %d findings, want 0: %+v", len(got), got)
	}
}

func TestLintResultSerializesToEmptyJSONArray(t *testing.T) {
	got := checker.Lint("Open the valve.", checker.Options{})
	raw, err := json.Marshal(got)
	if err != nil {
		t.Fatalf("marshal: %v", err)
	}
	if string(raw) != "[]" {
		t.Fatalf("json %s, want []", raw)
	}
}

func TestDiagnosticSerializesAllFields(t *testing.T) {
	got := checker.Lint("Open the valve; start the pump.", checker.Options{})
	if len(got) != 1 {
		t.Fatalf("got %d findings, want 1", len(got))
	}
	raw, err := json.Marshal(got[0])
	if err != nil {
		t.Fatalf("marshal: %v", err)
	}
	var back map[string]any
	if err := json.Unmarshal(raw, &back); err != nil {
		t.Fatalf("unmarshal: %v", err)
	}
	for _, field := range []string{"rule_id", "message", "severity", "confidence", "start", "end", "suggestion"} {
		if _, ok := back[field]; !ok {
			t.Errorf("the JSON has no %q field: %s", field, raw)
		}
	}
}

func TestFindingsAreSortedByPosition(t *testing.T) {
	text := "The pump isn't full; the valve is running."
	got := checker.Lint(text, checker.Options{})
	if len(got) < 3 {
		t.Fatalf("got %d findings, want 3 or more", len(got))
	}
	for i := 1; i < len(got); i++ {
		if got[i].Start < got[i-1].Start {
			t.Fatalf("finding %d starts before finding %d", i, i-1)
		}
	}
}
