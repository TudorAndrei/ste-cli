package rules_test

import (
	"strings"
	"testing"

	"github.com/TudorAndrei/ste-cli/internal/checker"
	"github.com/TudorAndrei/ste-cli/internal/checker/rules"
)

func oneNameOpts() rules.Options {
	return rules.Options{Prefer: []rules.Preferred{
		{Name: "config file", Instead: []string{"settings file", "configuration file"}},
		{Name: "pump", Instead: []string{"frammis"}},
	}}
}

func TestOneName(t *testing.T) {
	cases := []struct {
		name string
		src  string
		want int
	}{
		{"the name to use gives no finding", "Open the config file.\n", 0},
		{"a second name for the same item", "Open the settings file.\n", 1},
		{"a third name for the same item", "Open the configuration file.\n", 1},
		{"two names in one document",
			"Open the settings file. Then read the configuration file.\n", 2},
		{"a name of one word", "Start the frammis.\n", 1},
		{"the letter case does not matter", "Open the Settings File.\n", 1},
		{"a name that is not in the config", "Open the report file.\n", 0},
	}
	for _, tc := range cases {
		t.Run(tc.name, func(t *testing.T) {
			got := []checker.Diagnostic{}
			for _, d := range checker.Lint(tc.src, oneNameOpts()) {
				if d.RuleID == "STE-1.11" {
					got = append(got, d)
				}
			}
			if len(got) != tc.want {
				t.Fatalf("got %d findings, want %d: %+v", len(got), tc.want, got)
			}
			if tc.want > 0 && !strings.Contains(got[0].Suggestion, "Write") {
				t.Errorf("suggestion %q gives no name to use", got[0].Suggestion)
			}
		})
	}
}

func TestOneNameNeedsTheConfig(t *testing.T) {
	// No tool can know that two nouns mean the same item. With no config,
	// the rule must report nothing.
	src := "Open the settings file. Then read the configuration file.\n"
	for _, d := range checker.Lint(src, rules.Options{}) {
		if d.RuleID == "STE-1.11" {
			t.Fatalf("the rule reported %+v with no config", d)
		}
	}
}
