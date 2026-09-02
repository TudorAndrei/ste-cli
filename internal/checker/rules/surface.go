package rules

import "strings"

// Identifiers of the surface rules.
const (
	RuleSemicolon   = "STE-8.1"
	RuleContraction = "STE-4.2"
)

// Semicolons reports each semicolon in prose. ASD-STE100 permits only the
// comma, the period, the colon, the hyphen, the parentheses, and the slash.
func Semicolons(doc Document, opts Options) []Diagnostic {
	out := []Diagnostic{}
	for _, s := range doc.Sentences {
		for i := s.Start; i < s.End; i++ {
			if doc.Masked[i] != ';' {
				continue
			}
			if isHTMLEntity(doc.Masked, s.Start, i) {
				continue
			}
			out = append(out, Diagnostic{
				RuleID:     RuleSemicolon,
				Message:    "The semicolon is not an approved punctuation mark.",
				Severity:   SeverityWarning,
				Confidence: 1.0,
				Start:      i,
				End:        i + 1,
				Suggestion: "Write two sentences, or use a list.",
			})
		}
	}
	return out
}

// isHTMLEntity tells if the semicolon at pos closes an HTML entity, such as
// "&nbsp;".
func isHTMLEntity(masked string, lineStart, pos int) bool {
	j := pos - 1
	for j >= lineStart && j > pos-12 {
		c := masked[j]
		if c == '&' {
			return j < pos-1
		}
		if !isEntityByte(c) {
			return false
		}
		j--
	}
	return false
}

func isEntityByte(c byte) bool {
	return c >= 'a' && c <= 'z' || c >= 'A' && c <= 'Z' || c >= '0' && c <= '9' || c == '#'
}

// contractionSuffixes are the endings that always make a contraction.
var contractionSuffixes = []string{"n't", "'re", "'ve", "'ll", "'m", "'d"}

// sContractions are the words in which "'s" is a contraction and not a
// possessive form.
var sContractions = map[string]bool{
	"it's": true, "let's": true, "that's": true, "there's": true,
	"here's": true, "what's": true, "who's": true, "he's": true,
	"she's": true, "where's": true, "how's": true,
}

// Contractions reports the contracted forms. ASD-STE100 tells writers to use
// the full form of a verb and its negation.
func Contractions(doc Document, opts Options) []Diagnostic {
	out := []Diagnostic{}
	for _, s := range doc.Sentences {
		for _, t := range s.Tokens {
			if !strings.Contains(t.Lower, "'") {
				continue
			}
			if !isContraction(t.Lower) {
				continue
			}
			out = append(out, Diagnostic{
				RuleID:     RuleContraction,
				Message:    "The contraction \"" + t.Text + "\" is not approved.",
				Severity:   SeverityWarning,
				Confidence: 0.98,
				Start:      t.Start,
				End:        t.End,
				Suggestion: expandContraction(t.Lower),
			})
		}
	}
	return out
}

func isContraction(lower string) bool {
	if sContractions[lower] {
		return true
	}
	for _, suffix := range contractionSuffixes {
		if strings.HasSuffix(lower, suffix) && len(lower) > len(suffix) {
			return true
		}
	}
	return false
}

var contractionExpansions = map[string]string{
	"don't": "do not", "doesn't": "does not", "didn't": "did not",
	"can't": "cannot", "won't": "will not", "isn't": "is not",
	"aren't": "are not", "wasn't": "was not", "weren't": "were not",
	"hasn't": "has not", "haven't": "have not", "hadn't": "had not",
	"shouldn't": "should not", "wouldn't": "would not",
	"couldn't": "could not", "mustn't": "must not",
	"it's": "it is", "that's": "that is", "there's": "there is",
	"here's": "here is", "what's": "what is", "let's": "let us",
	"you're": "you are", "we're": "we are", "they're": "they are",
	"i'm": "I am", "i've": "I have", "you've": "you have",
	"we've": "we have", "they've": "they have", "you'll": "you will",
	"we'll": "we will", "it'll": "it will", "they'll": "they will",
}

func expandContraction(lower string) string {
	if full, ok := contractionExpansions[lower]; ok {
		return "Write \"" + full + "\"."
	}
	return "Write the full form."
}
