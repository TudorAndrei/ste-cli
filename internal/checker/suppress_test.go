package checker_test

import (
	"testing"

	"github.com/TudorAndrei/ste-cli/internal/checker"
)

func TestSuppressionDirectives(t *testing.T) {
	cases := []struct {
		name string
		src  string
		want int
	}{
		{"no directive", "The valve isn't open.\n", 1},
		{"disable the next line",
			"<!-- ste-disable-next-line -->\nThe valve isn't open.\n", 0},
		{"disable the next line, one rule",
			"<!-- ste-disable-next-line STE-4.2 -->\nThe valve isn't open.\n", 0},
		{"disable the next line, a different rule",
			"<!-- ste-disable-next-line STE-8.1 -->\nThe valve isn't open.\n", 1},
		{"disable the same line",
			"The valve isn't open. <!-- ste-disable-line -->\n", 0},
		{"disable to the end of the file",
			"<!-- ste-disable -->\nThe valve isn't open.\nThe pump isn't on.\n", 0},
		{"disable and enable again",
			"<!-- ste-disable STE-4.2 -->\nThe valve isn't open.\n<!-- ste-enable STE-4.2 -->\nThe pump isn't on.\n", 1},
		{"a directive for one rule does not hide another rule",
			"<!-- ste-disable STE-8.1 -->\nThe valve isn't open.\n", 1},
	}
	for _, tc := range cases {
		t.Run(tc.name, func(t *testing.T) {
			got := checker.Lint(tc.src, checker.Options{})
			if len(got) != tc.want {
				t.Errorf("got %d findings, want %d: %+v", len(got), tc.want, got)
			}
		})
	}
}

func TestPerRuleSeverity(t *testing.T) {
	text := "Open the valve; the report isn't ready.\n"

	opts := checker.Options{RuleSeverity: map[string]checker.Severity{
		"STE-8.1": checker.SeverityError,
		"STE-4.2": "off",
	}}
	got := checker.Lint(text, opts)
	if len(got) != 1 {
		t.Fatalf("got %d findings, want 1: %+v", len(got), got)
	}
	if got[0].RuleID != "STE-8.1" || got[0].Severity != checker.SeverityError {
		t.Errorf("finding %s %s, want STE-8.1 error", got[0].RuleID, got[0].Severity)
	}
}

func TestMinConfidence(t *testing.T) {
	// The passive voice of a regular participle has confidence 0.70.
	text := "The report was approved.\n"
	if got := checker.Lint(text, checker.Options{}); len(got) != 1 {
		t.Fatalf("got %d findings, want 1", len(got))
	}
	if got := checker.Lint(text, checker.Options{MinConfidence: 0.8}); len(got) != 0 {
		t.Fatalf("got %d findings with a limit of 0.80, want 0", len(got))
	}
}

func TestFrontMatterIsNotProse(t *testing.T) {
	src := "---\nid: ADR-0035\ntitle: VS Code-compatible companion extension\nstatus: it isn't ready\n---\n\nThe valve is open.\n"
	got := checker.Lint(src, checker.Options{})
	if len(got) != 0 {
		t.Fatalf("got %d findings in the front matter, want 0: %+v", len(got), got)
	}
	// The prose below the front matter is still checked.
	src2 := "---\nid: ADR-0035\n---\n\nThe report isn't ready.\n"
	if got := checker.Lint(src2, checker.Options{}); len(got) != 1 {
		t.Fatalf("got %d findings after the front matter, want 1: %+v", len(got), got)
	}
}

func TestAHorizontalRuleIsNotFrontMatter(t *testing.T) {
	// The document does not start with the fence, thus the text is prose.
	src := "The report isn't ready.\n\n---\n\nThe valve isn't open.\n"
	if got := checker.Lint(src, checker.Options{}); len(got) != 2 {
		t.Fatalf("got %d findings, want 2: %+v", len(got), got)
	}
}
