package rules

import "fmt"

// RuleSentenceLength is the identifier of the sentence-length rule.
const RuleSentenceLength = "STE-5.1"

// SentenceLength reports a sentence that is longer than the configured limit.
// The limit is 25 words in flavored mode and 20 words in strict mode.
func SentenceLength(doc Document, opts Options) []Diagnostic {
	limit := opts.MaxWords
	out := []Diagnostic{}
	for _, s := range doc.Sentences {
		n := len(s.Tokens)
		if n <= limit {
			continue
		}
		out = append(out, Diagnostic{
			RuleID:     RuleSentenceLength,
			Message:    fmt.Sprintf("The sentence has %d words. The limit is %d words.", n, limit),
			Severity:   SeverityWarning,
			Confidence: 1.0,
			Start:      s.Start,
			End:        s.End,
			Suggestion: "Divide the sentence into two or more sentences.",
		})
	}
	return out
}
