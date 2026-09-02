package rules

import "strings"

// RuleUnapprovedTerm is the identifier of the term rule.
const RuleUnapprovedTerm = "STE-1.1"

// TermDataVersion identifies the term list.
const TermDataVersion = "1.0.0"

// bannedWords is a short list of words that have a shorter and more common
// replacement. The list is written by hand for this project. It is NOT the
// ASD-STE100 approved-word dictionary, and it is not derived from it. See
// docs/upstream-audit.md.
var bannedWords = map[string]string{
	"utilize":        "use",
	"utilise":        "use",
	"utilizes":       "uses",
	"utilization":    "use",
	"commence":       "start",
	"commences":      "starts",
	"terminate":      "stop",
	"terminates":     "stops",
	"initiate":       "start",
	"initiates":      "starts",
	"ascertain":      "find",
	"endeavor":       "try",
	"endeavour":      "try",
	"facilitate":     "help",
	"leverage":       "use",
	"assist":         "help",
	"possess":        "have",
	"purchase":       "buy",
	"obtain":         "get",
	"additional":     "more",
	"approximately":  "about",
	"sufficient":     "enough",
	"numerous":       "many",
	"demonstrate":    "show",
	"attempt":        "try",
	"comprise":       "have",
	"aforementioned": "the (name the item again)",
}

// bannedPhrases is the same idea for word groups.
var bannedPhrases = []struct {
	Words       []string
	Replacement string
}{
	{[]string{"in", "order", "to"}, "to"},
	{[]string{"prior", "to"}, "before"},
	{[]string{"subsequent", "to"}, "after"},
	{[]string{"due", "to", "the", "fact", "that"}, "because"},
	{[]string{"at", "this", "point", "in", "time"}, "now"},
	{[]string{"in", "the", "event", "that"}, "if"},
	{[]string{"with", "regard", "to"}, "about"},
	{[]string{"in", "conjunction", "with"}, "with"},
	{[]string{"a", "number", "of"}, "some, or the exact number"},
	{[]string{"is", "able", "to"}, "can"},
	{[]string{"are", "able", "to"}, "can"},
}

// Terms reports the words and the word groups that have a simpler
// replacement. The glossary can permit a term for one project.
func Terms(doc Document, opts Options) []Diagnostic {
	out := []Diagnostic{}
	for _, s := range doc.Sentences {
		for i := 0; i < len(s.Tokens); i++ {
			if d, n, ok := matchPhrase(s, i, opts); ok {
				out = append(out, d)
				i += n - 1
				continue
			}
			t := s.Tokens[i]
			if opts.Allowed(t.Lower) {
				continue
			}
			// The dictionary of the user is the authority. The
			// hand-written list applies only to a word that the
			// dictionary does not have.
			if d, ok := lookupDictionary(opts, s, i); ok {
				d.Start, d.End = t.Start, t.End
				d.Message = "\"" + t.Text + "\" is not an approved word."
				out = append(out, d)
				continue
			}
			replacement, banned := bannedWords[t.Lower]
			if !banned {
				continue
			}
			out = append(out, Diagnostic{
				RuleID:     RuleUnapprovedTerm,
				Message:    "\"" + t.Text + "\" is not an approved word.",
				Severity:   SeverityWarning,
				Confidence: 0.9,
				Start:      t.Start,
				End:        t.End,
				Suggestion: "Write \"" + replacement + "\".",
			})
		}
	}
	return out
}

// lookupDictionary asks the dictionary about a word. The second value is
// false when there is no dictionary, or when the dictionary approves the
// word, or when the dictionary does not have the word.
func lookupDictionary(opts Options, s Sentence, i int) (Diagnostic, bool) {
	if opts.Dictionary == nil {
		return Diagnostic{}, false
	}
	word := s.Tokens[i].Lower
	result, unapproved := opts.Dictionary.Unapproved(word)
	if !unapproved {
		return Diagnostic{}, false
	}
	onlyVerb := result.OnlyVerb
	// The dictionary can hold a word only as a verb, as with "graph",
	// "hook", and "pump". English uses each of them as a noun too, and
	// rule 1.6 permits a technical noun. This tool has no part-of-speech
	// tagger, but it does not need one for the common case: a determiner
	// or a possessive before the word makes it a noun. "the dependency
	// graph" is a noun, and "Graph the results" is a verb.
	if onlyVerb && precededByDeterminer(s, i) {
		return Diagnostic{}, false
	}
	// The dictionary is the authority of rule 1.1, thus the confidence is
	// higher than the confidence of the hand list. But a word that the
	// dictionary has only as a verb is often a technical noun in the same
	// text, and this tool cannot see the difference.
	confidence := 0.95
	if onlyVerb {
		confidence = 0.6
	}
	suggestion := "The dictionary gives no alternative. Write the idea in approved words."
	switch {
	case len(result.Alternatives) > 0:
		suggestion = "Write \"" + strings.Join(result.Alternatives, "\", or \"") + "\"."
	case result.TechnicalNoun:
		// The dictionary approves the word as a technical noun, and not
		// as a verb. This tool has no part-of-speech tagger, thus it
		// cannot know which one this sentence uses. The message states
		// what the dictionary says, and it does not state a fault.
		suggestion = "The dictionary approves \"" + word + "\" as a technical noun only. If this sentence uses it as a verb, write a different verb."
	}
	return Diagnostic{
		RuleID:     RuleUnapprovedTerm,
		Severity:   SeverityWarning,
		Confidence: confidence,
		Suggestion: suggestion,
	}, true
}

// determiners are the words that make the word after them a noun.
var determiners = map[string]bool{
	"a": true, "an": true, "the": true, "this": true, "that": true,
	"these": true, "those": true, "its": true, "their": true, "our": true,
	"your": true, "my": true, "his": true, "her": true, "no": true,
	"each": true, "every": true, "any": true, "some": true, "one": true,
	"another": true, "both": true, "all": true, "which": true, "what": true,
	"same": true, "other": true, "first": true, "last": true, "next": true,
	"new": true, "old": true, "full": true, "empty": true, "current": true,
}

// phraseStoppers end a noun phrase. A determiner before one of these words
// does not make the word after them a noun: in "the tool can graph the
// results", "graph" is a verb.
var phraseStoppers = map[string]bool{
	"to": true, "not": true, "can": true, "could": true, "must": true,
	"will": true, "would": true, "shall": true, "should": true,
	"may": true, "might": true, "do": true, "does": true, "did": true,
	"and": true, "or": true, "but": true, "if": true, "when": true,
	"then": true, "also": true, "please": true, "always": true,
	"never": true, "is": true, "are": true, "was": true, "were": true,
	"be": true, "been": true, "being": true, "cannot": true,
}

// precededByDeterminer tells if a determiner or a possessive comes before
// the token, in the same noun phrase. It looks back over the words that can
// modify a noun, as in "the dependency graph", and it stops at a word that
// ends the phrase.
func precededByDeterminer(s Sentence, i int) bool {
	for back := 1; back <= 3 && i-back >= 0; back++ {
		previous := s.Tokens[i-back].Lower
		if determiners[previous] || strings.HasSuffix(previous, "'s") {
			return true
		}
		if phraseStoppers[previous] {
			return false
		}
	}
	return false
}

func matchPhrase(s Sentence, i int, opts Options) (Diagnostic, int, bool) {
	for _, p := range bannedPhrases {
		if i+len(p.Words) > len(s.Tokens) {
			continue
		}
		ok := true
		for n, w := range p.Words {
			if s.Tokens[i+n].Lower != w {
				ok = false
				break
			}
		}
		if !ok {
			continue
		}
		end := i + len(p.Words) - 1
		phrase := span(s, i, end)
		if opts.Allowed(phrase) {
			continue
		}
		return Diagnostic{
			RuleID:     RuleUnapprovedTerm,
			Message:    "\"" + phrase + "\" is not an approved word group.",
			Severity:   SeverityWarning,
			Confidence: 0.9,
			Start:      s.Tokens[i].Start,
			End:        s.Tokens[end].End,
			Suggestion: "Write \"" + p.Replacement + "\".",
		}, len(p.Words), true
	}
	return Diagnostic{}, 0, false
}
