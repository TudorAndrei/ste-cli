// The test uses the external test package because the fixtures go through
// checker.Parse, and the checker package imports the rules package.
package rules_test

import (
	"encoding/json"
	"os"
	"testing"

	"github.com/TudorAndrei/ste-cli/internal/checker"
	"github.com/TudorAndrei/ste-cli/internal/checker/rules"
)

type verbCase struct {
	Name   string `json:"name"`
	Text   string `json:"text"`
	Mode   string `json:"mode"`
	Expect []struct {
		RuleID string `json:"rule_id"`
		Text   string `json:"text"`
	} `json:"expect"`
}

type verbFixture struct {
	DataVersion string     `json:"data_version"`
	Cases       []verbCase `json:"cases"`
}

func loadVerbFixture(t *testing.T) verbFixture {
	t.Helper()
	raw, err := os.ReadFile("testdata/verbs.json")
	if err != nil {
		t.Fatalf("read fixture: %v", err)
	}
	var fx verbFixture
	if err := json.Unmarshal(raw, &fx); err != nil {
		t.Fatalf("parse fixture: %v", err)
	}
	if len(fx.Cases) == 0 {
		t.Fatal("the fixture has no cases")
	}
	return fx
}

func TestVerbFixtureDataVersion(t *testing.T) {
	fx := loadVerbFixture(t)
	if fx.DataVersion != rules.VerbDataVersion {
		t.Fatalf("fixture data version %q, verb data version %q", fx.DataVersion, rules.VerbDataVersion)
	}
}

func TestVerbRules(t *testing.T) {
	fx := loadVerbFixture(t)
	for _, tc := range fx.Cases {
		t.Run(tc.Name, func(t *testing.T) {
			opts := checker.Options{Mode: checker.ModeFlavored}
			if tc.Mode == string(checker.ModeStrict) {
				opts.Mode = checker.ModeStrict
			}
			got := checker.Lint(tc.Text, opts)
			if len(got) != len(tc.Expect) {
				t.Fatalf("got %d findings, want %d: %s", len(got), len(tc.Expect), format(tc.Text, got))
			}
			for i, want := range tc.Expect {
				if got[i].RuleID != want.RuleID {
					t.Errorf("finding %d: rule %s, want %s", i, got[i].RuleID, want.RuleID)
				}
				if span := tc.Text[got[i].Start:got[i].End]; span != want.Text {
					t.Errorf("finding %d: span %q, want %q", i, span, want.Text)
				}
			}
		})
	}
}

func format(text string, ds []checker.Diagnostic) string {
	out := ""
	for _, d := range ds {
		out += "\n  " + d.RuleID + " " + text[d.Start:d.End]
	}
	if out == "" {
		return "(no findings)"
	}
	return out
}
