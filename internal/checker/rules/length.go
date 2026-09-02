package rules

import "fmt"

// RuleSentenceLength is the identifier of the sentence-length rule. Rule 5.1
// gives the 20-word limit for an instruction in a procedure. Rules 5.5 and
// 6.3 give the 25-word limit for a note and for descriptive text.
const RuleSentenceLength = "STE-5.1"

// SentenceLength reports a sentence that is longer than its limit. The limit
// comes from the type of the sentence, and not from the mode: a numbered
// list item is an instruction and gets 20 words, and all other text gets 25
// words. The max_words option replaces both limits.
func SentenceLength(doc Document, opts Options) []Diagnostic {
	out := []Diagnostic{}
	for _, s := range doc.Sentences {
		limit := s.Limit()
		kind := "sentence"
		if s.Procedural && !s.Note {
			kind = "instruction"
		}
		if opts.MaxWords > 0 {
			limit = opts.MaxWords
		}
		if s.Words <= limit {
			continue
		}
		out = append(out, Diagnostic{
			RuleID:     RuleSentenceLength,
			Message:    fmt.Sprintf("The %s has %d words. The limit is %d words.", kind, s.Words, limit),
			Severity:   SeverityWarning,
			Confidence: 0.9,
			Start:      s.Start,
			End:        s.End,
			Suggestion: "Divide the sentence into two or more sentences.",
		})
	}
	return out
}
