package rules_test

import (
	"strings"
	"testing"

	"github.com/TudorAndrei/ste-cli/internal/checker"
)

func TestSemicolonRule(t *testing.T) {
	text := "Open the valve; then start the pump."
	got := checker.Lint(text, checker.Options{})
	if len(got) != 1 {
		t.Fatalf("got %d findings, want 1: %s", len(got), format(text, got))
	}
	if got[0].RuleID != "STE-8.1" {
		t.Errorf("rule %s, want STE-8.1", got[0].RuleID)
	}
	if got[0].Start != 14 || got[0].End != 15 {
		t.Errorf("span %d-%d, want 14-15", got[0].Start, got[0].End)
	}
	if text[got[0].Start:got[0].End] != ";" {
		t.Errorf("span text %q, want %q", text[got[0].Start:got[0].End], ";")
	}
}

func TestSemicolonRuleKeepsHTMLEntities(t *testing.T) {
	got := checker.Lint("The gap is 10&nbsp;mm.", checker.Options{})
	if len(got) != 0 {
		t.Fatalf("got %d findings, want 0", len(got))
	}
}

func TestContractionRule(t *testing.T) {
	text := "Do not use the pump if it isn't full."
	got := checker.Lint(text, checker.Options{})
	if len(got) != 1 {
		t.Fatalf("got %d findings, want 1: %s", len(got), format(text, got))
	}
	if got[0].RuleID != "STE-4.2" {
		t.Errorf("rule %s, want STE-4.2", got[0].RuleID)
	}
	if span := text[got[0].Start:got[0].End]; span != "isn't" {
		t.Errorf("span %q, want %q", span, "isn't")
	}
	if got[0].Suggestion != "Write \"is not\"." {
		t.Errorf("suggestion %q", got[0].Suggestion)
	}
}

func TestContractionRuleKeepsPossessives(t *testing.T) {
	got := checker.Lint("The parser's output is correct.", checker.Options{})
	if len(got) != 0 {
		t.Fatalf("got %d findings, want 0", len(got))
	}
}

func TestSentenceLengthRule(t *testing.T) {
	// The sentence has 26 words, thus the flavored limit of 25 fails.
	text := "one two three four five six seven eight nine ten one two three four five six seven eight nine ten one two three four five six."
	got := checker.Lint(text, checker.Options{})
	if len(got) != 1 {
		t.Fatalf("got %d findings, want 1: %s", len(got), format(text, got))
	}
	if got[0].RuleID != "STE-5.1" {
		t.Errorf("rule %s, want STE-5.1", got[0].RuleID)
	}
	if got[0].Start != 0 || got[0].End != len(text) {
		t.Errorf("span %d-%d, want 0-%d", got[0].Start, got[0].End, len(text))
	}
}

// The 22-word sentence is correct as descriptive text (limit 25), but it is
// too long as an instruction in a procedure (limit 20). ASD-STE100 selects
// the limit from the type of the sentence, and not from the mode.
const words22 = "one two three four five six seven eight nine ten one two three four five six seven eight nine ten one two."

func TestDescriptiveSentenceKeepsThe25WordLimit(t *testing.T) {
	if got := checker.Lint(words22, checker.Options{}); len(got) != 0 {
		t.Fatalf("got %d findings, want 0: %s", len(got), format(words22, got))
	}
	if got := checker.Lint(words22, checker.Options{Mode: checker.ModeStrict}); len(got) != 0 {
		t.Fatalf("strict mode gave %d findings, want 0: the mode must not change the limit", len(got))
	}
}

func TestNumberedStepUsesThe20WordLimit(t *testing.T) {
	text := "1. " + words22
	got := checker.Lint(text, checker.Options{})
	if len(got) != 1 {
		t.Fatalf("got %d findings, want 1: %s", len(got), format(text, got))
	}
	if got[0].RuleID != "STE-5.1" {
		t.Errorf("rule %s, want STE-5.1", got[0].RuleID)
	}
	if !strings.Contains(got[0].Message, "instruction") || !strings.Contains(got[0].Message, "limit is 20") {
		t.Errorf("message %q", got[0].Message)
	}
}

func TestNoteKeepsTheLongerLimitInAProcedure(t *testing.T) {
	// Rule 5.5: a note gives information only, thus it keeps 25 words.
	text := "1. NOTE: " + words22
	if got := checker.Lint(text, checker.Options{}); len(got) != 0 {
		t.Fatalf("got %d findings, want 0: %s", len(got), format(text, got))
	}
}

func TestMaxWordsReplacesBothLimits(t *testing.T) {
	opts := checker.Options{MaxWords: 10}
	got := checker.Lint(words22, opts)
	if len(got) != 1 {
		t.Fatalf("got %d findings, want 1", len(got))
	}
	if !strings.Contains(got[0].Message, "limit is 10") {
		t.Errorf("message %q", got[0].Message)
	}
}

func TestStrictModeRaisesTheSeverity(t *testing.T) {
	text := "1. " + words22
	got := checker.Lint(text, checker.Options{Mode: checker.ModeStrict})
	if len(got) != 1 {
		t.Fatalf("got %d findings, want 1", len(got))
	}
	if got[0].Severity != checker.SeverityError {
		t.Errorf("severity %q, want %q", got[0].Severity, checker.SeverityError)
	}
}

func TestTermRule(t *testing.T) {
	text := "Utilize the tool in order to start the pump."
	got := checker.Lint(text, checker.Options{})
	if len(got) != 2 {
		t.Fatalf("got %d findings, want 2: %s", len(got), format(text, got))
	}
	if span := text[got[0].Start:got[0].End]; span != "Utilize" {
		t.Errorf("span %q, want %q", span, "Utilize")
	}
	if span := text[got[1].Start:got[1].End]; span != "in order to" {
		t.Errorf("span %q, want %q", span, "in order to")
	}
	for _, d := range got {
		if d.RuleID != "STE-1.1" {
			t.Errorf("rule %s, want STE-1.1", d.RuleID)
		}
	}
}

func TestGlossaryPermitsProjectTerm(t *testing.T) {
	text := "Leverage the webhook."
	if got := checker.Lint(text, checker.Options{}); len(got) != 1 {
		t.Fatalf("got %d findings, want 1: %s", len(got), format(text, got))
	}
	opts := checker.Options{AllowVerbs: []string{"leverage"}}
	if got := checker.Lint(text, opts); len(got) != 0 {
		t.Fatalf("the glossary did not permit the term: %s", format(text, got))
	}
}

func TestDisableRules(t *testing.T) {
	text := "Open the valve; then start the pump."
	opts := checker.Options{DisableRules: []string{"STE-8.1"}}
	if got := checker.Lint(text, opts); len(got) != 0 {
		t.Fatalf("got %d findings, want 0", len(got))
	}
}
