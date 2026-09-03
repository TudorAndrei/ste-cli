package rules

import "strings"

// RuleOneName is rule 1.11: do not use different technical nouns for the
// same item.
const RuleOneName = "STE-1.11"

// Preferred is one item of the project with the names to not use for it.
// The config file gives these, because only the project knows which names
// mean the same item.
type Preferred struct {
	// Name is the technical noun to use.
	Name string
	// Instead holds the other names of the same item.
	Instead []string
}

// OneName reports a name that the project replaced with a different name for
// the same item. Rule 1.11 tells you to select one technical noun and to use
// it in each place.
//
// The rule reports nothing when the config gives no "prefer" key: no tool can
// know that two nouns mean the same item, and only the project can say so.
func OneName(doc Document, opts Options) []Diagnostic {
	if len(opts.Prefer) == 0 {
		return nil
	}
	out := []Diagnostic{}
	for _, s := range doc.Sentences {
		for _, p := range opts.Prefer {
			for _, old := range p.Instead {
				out = append(out, matchName(s, old, p.Name)...)
			}
		}
	}
	return out
}

// matchName finds each use of one name in a sentence. The name can hold more
// than one word.
func matchName(s Sentence, old, want string) []Diagnostic {
	words := strings.Fields(strings.ToLower(old))
	if len(words) == 0 {
		return nil
	}
	out := []Diagnostic{}
	for i := 0; i+len(words) <= len(s.Tokens); i++ {
		match := true
		for n, w := range words {
			if s.Tokens[i+n].Lower != w {
				match = false
				break
			}
		}
		if !match {
			continue
		}
		end := i + len(words) - 1
		out = append(out, Diagnostic{
			RuleID:     RuleOneName,
			Message:    "The text uses \"" + span(s, i, end) + "\" and \"" + want + "\" for the same item.",
			Severity:   SeverityWarning,
			Confidence: 0.95,
			Start:      s.Tokens[i].Start,
			End:        s.Tokens[end].End,
			Suggestion: "Write \"" + want + "\".",
		})
	}
	return out
}
