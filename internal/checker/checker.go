// Package checker finds high-confidence ASD-STE100 violations in Markdown and
// plain text. Lint is the only entry point that the CLI needs.
package checker

import (
	"sort"

	"github.com/TudorAndrei/ste-cli/internal/checker/rules"
)

// Lint returns the findings for the text. The result is never nil, thus it
// serializes to "[]" and not to "null".
func Lint(text string, options Options) []Diagnostic {
	return LintDocument(Parse(text), options)
}

// LintDocument runs the rules against an already parsed document. The CLI uses
// it when it must also know the word count of the document.
func LintDocument(doc Document, options Options) []Diagnostic {
	opts := options.Normalized()
	found := []Diagnostic{}
	for _, rule := range rules.All() {
		found = append(found, rule(doc, opts)...)
	}

	out := make([]Diagnostic, 0, len(found))
	for _, d := range found {
		if isDisabled(d.RuleID, opts.DisableRules) {
			continue
		}
		if opts.Mode == ModeFlavored && d.Confidence < rules.MinConfidenceFlavored {
			continue
		}
		if opts.Mode == ModeStrict {
			d.Severity = strictSeverity(d.Severity)
		}
		out = append(out, d)
	}

	sort.SliceStable(out, func(i, j int) bool {
		if out[i].Start != out[j].Start {
			return out[i].Start < out[j].Start
		}
		if out[i].End != out[j].End {
			return out[i].End < out[j].End
		}
		return out[i].RuleID < out[j].RuleID
	})
	return out
}

// strictSeverity makes every finding one step stronger in strict mode.
func strictSeverity(s Severity) Severity {
	switch s {
	case SeverityInfo:
		return SeverityWarning
	default:
		return SeverityError
	}
}

func isDisabled(ruleID string, disabled []string) bool {
	for _, id := range disabled {
		if id == ruleID {
			return true
		}
	}
	return false
}
