package analyzer_test

import (
	"os/exec"
	"path/filepath"
	"testing"

	"github.com/TudorAndrei/ste-cli/internal/analyzer"
)

func stub(t *testing.T) *analyzer.Client {
	t.Helper()
	python, err := exec.LookPath("python3")
	if err != nil {
		t.Skip("python3 is not on this system")
	}
	path, err := filepath.Abs(filepath.Join("testdata", "stub_analyzer.py"))
	if err != nil {
		t.Fatal(err)
	}
	client, err := analyzer.Start(python + " " + path)
	if err != nil {
		t.Fatalf("start: %v", err)
	}
	t.Cleanup(func() { _ = client.Close() })
	return client
}

func TestStartAndAnalyze(t *testing.T) {
	client := stub(t)
	if client.Model() != "stub" {
		t.Errorf("model %q, want stub", client.Model())
	}
	tokens, err := client.Analyze("The report was signed by the team.")
	if err != nil {
		t.Fatalf("analyze: %v", err)
	}
	if len(tokens) == 0 {
		t.Fatal("the analyzer gave no token")
	}
}

func TestPassiveAt(t *testing.T) {
	client := stub(t)
	sentence := "The report was signed by the team."
	offset := 15 // "signed"
	if sentence[offset:offset+6] != "signed" {
		t.Fatalf("the offset is wrong: %q", sentence[offset:])
	}
	passive, known := client.PassiveAt(sentence, offset)
	if !known || !passive {
		t.Errorf("passive=%v known=%v, want true and true", passive, known)
	}

	// A word that the analyzer does not call passive.
	passive, known = client.PassiveAt(sentence, 4) // "report"
	if !known || passive {
		t.Errorf("passive=%v known=%v, want false and true", passive, known)
	}

	// An offset with no token gives no answer, thus the rule keeps its
	// own result.
	if _, known := client.PassiveAt(sentence, 999); known {
		t.Error("an unknown offset must give known=false")
	}
}

func TestAMissingCommandIsAnError(t *testing.T) {
	if _, err := analyzer.Start("this-command-does-not-exist-1234"); err == nil {
		t.Fatal("Start accepted a command that does not exist")
	}
	if _, err := analyzer.Start(""); err == nil {
		t.Fatal("Start accepted an empty command")
	}
}
