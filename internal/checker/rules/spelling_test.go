package rules_test

import (
	"testing"

	"github.com/TudorAndrei/ste-cli/internal/checker"
)

func TestSpellingRule(t *testing.T) {
	text := "The colour of the centre indicator changed."
	got := checker.Lint(text, checker.Options{})
	if len(got) != 2 {
		t.Fatalf("got %d findings, want 2: %s", len(got), format(text, got))
	}
	for _, d := range got {
		if d.RuleID != "STE-1.14" {
			t.Errorf("rule %s, want STE-1.14", d.RuleID)
		}
	}
	if span := text[got[0].Start:got[0].End]; span != "colour" {
		t.Errorf("span %q, want %q", span, "colour")
	}
	if got[0].Suggestion != "Write \"color\"." {
		t.Errorf("suggestion %q", got[0].Suggestion)
	}
}

func TestSpellingRuleKeepsAmericanForms(t *testing.T) {
	text := "The color of the center indicator is correct."
	if got := checker.Lint(text, checker.Options{}); len(got) != 0 {
		t.Fatalf("got %d findings, want 0: %s", len(got), format(text, got))
	}
}

func TestSpellingRuleObeysTheGlossary(t *testing.T) {
	// A project can use a British spelling in its own product name.
	text := "Open the Colour Manager."
	opts := checker.Options{AllowNouns: []string{"colour"}}
	if got := checker.Lint(text, opts); len(got) != 0 {
		t.Fatalf("the glossary did not permit the term: %s", format(text, got))
	}
}

func TestSpellingRuleKeepsAName(t *testing.T) {
	// "Defence" is part of the name of an organization. A name keeps its
	// spelling.
	text := "The AeroSpace and Defence Industries Association makes the standard."
	if got := checker.Lint(text, checker.Options{}); len(got) != 0 {
		t.Fatalf("got %d findings, want 0: %s", len(got), format(text, got))
	}
}

func TestSpellingRuleStillReportsTheFirstWord(t *testing.T) {
	// A capital letter at the start of a sentence is not a name.
	text := "Colour is not correct here."
	got := checker.Lint(text, checker.Options{})
	if len(got) != 1 {
		t.Fatalf("got %d findings, want 1: %s", len(got), format(text, got))
	}
	if got[0].RuleID != "STE-1.14" {
		t.Errorf("rule %s, want STE-1.14", got[0].RuleID)
	}
}

func TestNominalizationRule(t *testing.T) {
	text := "Do a check of the pressure."
	got := checker.Lint(text, checker.Options{})
	if len(got) != 1 {
		t.Fatalf("got %d findings, want 1: %s", len(got), format(text, got))
	}
	if got[0].RuleID != "STE-3.7" {
		t.Errorf("rule %s, want STE-3.7", got[0].RuleID)
	}
	if span := text[got[0].Start:got[0].End]; span != "Do a check of" {
		t.Errorf("span %q, want %q", span, "Do a check of")
	}
	if got[0].Suggestion != "Write \"check\"." {
		t.Errorf("suggestion %q", got[0].Suggestion)
	}
}

func TestNominalizationRuleKeepsTheVerb(t *testing.T) {
	if got := checker.Lint("Check the pressure.", checker.Options{}); len(got) != 0 {
		t.Fatalf("got %d findings, want 0", len(got))
	}
}

func TestLatinAbbreviationRule(t *testing.T) {
	text := "Use the correct tool, e.g. the torque wrench."
	got := checker.Lint(text, checker.Options{})
	if len(got) != 1 {
		t.Fatalf("got %d findings, want 1: %s", len(got), format(text, got))
	}
	if got[0].RuleID != "STE-GR-6" {
		t.Errorf("rule %s, want STE-GR-6", got[0].RuleID)
	}
	// A general recommendation is advice, not a rule of the standard.
	if got[0].Severity != checker.SeverityInfo {
		t.Errorf("severity %q, want %q", got[0].Severity, checker.SeverityInfo)
	}
	if span := text[got[0].Start:got[0].End]; span != "e.g" {
		t.Errorf("span %q, want %q", span, "e.g")
	}
}

func TestGeneralRecommendationStaysBelowARule(t *testing.T) {
	// Strict mode makes a rule an error. A general recommendation is
	// advice and not a rule, thus it keeps the info severity.
	got := checker.Lint("Use the tool, e.g. the wrench.", checker.Options{Mode: checker.ModeStrict})
	if len(got) != 1 {
		t.Fatalf("got %d findings, want 1", len(got))
	}
	if got[0].Severity != checker.SeverityInfo {
		t.Errorf("severity %q, want %q", got[0].Severity, checker.SeverityInfo)
	}
}

func TestLatinAbbreviationNeedsThePeriodAndLowerCase(t *testing.T) {
	// "VS Code" is a name, and "vs" without a period is not the Latin
	// abbreviation.
	for _, text := range []string{
		"Install the VS Code extension.",
		"Compare the vs value of the two files.",
	} {
		if got := checker.Lint(text, checker.Options{}); len(got) != 0 {
			t.Errorf("got %d findings for %q, want 0: %s", len(got), text, format(text, got))
		}
	}
	if got := checker.Lint("Use a tool, e.g. the wrench.", checker.Options{}); len(got) != 1 {
		t.Errorf("got %d findings for \"e.g.\", want 1", len(got))
	}
}
