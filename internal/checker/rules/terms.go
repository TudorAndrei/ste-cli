package rules

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
			replacement, banned := bannedWords[t.Lower]
			if !banned || opts.Allowed(t.Lower) {
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
