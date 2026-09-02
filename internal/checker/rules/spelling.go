package rules

import "unicode"

// Identifiers of the word-level rules that come from Issue 9.
const (
	// RuleSpelling is rule 1.14: use American English spelling.
	RuleSpelling = "STE-1.14"
	// RuleNominalization is rule 3.7: use an approved verb to describe an
	// action, and not a noun.
	RuleNominalization = "STE-3.7"
	// RuleLatinAbbreviation is general recommendation GR-6. A general
	// recommendation is advice, and it is not a rule of the standard, thus
	// this check has the info severity and the GR prefix.
	RuleLatinAbbreviation = "STE-GR-6"
)

// britishSpellings maps a British spelling to its American spelling. The
// list holds only the pairs where the American form is the only correct form
// in American technical English. Pairs that need a part of speech, such as
// "licence" and "practise", are not in the list.
var britishSpellings = map[string]string{
	"colour": "color", "colours": "colors", "coloured": "colored",
	"favour": "favor", "favours": "favors", "favourite": "favorite",
	"honour": "honor", "labour": "labor", "neighbour": "neighbor",
	"behaviour": "behavior", "behaviours": "behaviors",
	"centre": "center", "centres": "centers", "centred": "centered",
	"fibre": "fiber", "fibres": "fibers", "litre": "liter",
	"litres": "liters", "metre": "meter", "metres": "meters",
	"theatre": "theater",
	"tyre":    "tire", "tyres": "tires", "aluminium": "aluminum",
	"sulphur": "sulfur", "kerb": "curb", "defence": "defense",
	"offence": "offense", "grey": "gray", "mould": "mold",
	"storey": "story", "jewellery": "jewelry",
	"travelled": "traveled", "travelling": "traveling",
	"cancelled": "canceled", "cancelling": "canceling",
	"modelled": "modeled", "modelling": "modeling",
	"signalled": "signaled", "labelled": "labeled",
	"analyse": "analyze", "analysed": "analyzed", "analyses": "analyzes",
	"organise": "organize", "organised": "organized",
	"recognise": "recognize", "recognised": "recognized",
	"initialise": "initialize", "initialised": "initialized",
	"customise": "customize", "customised": "customized",
	"catalogue": "catalog", "dialogue": "dialog", "programme": "program",
}

// Spelling reports a British spelling. Rule 1.14 tells you to use American
// English spelling unless a different official directive applies.
func Spelling(doc Document, opts Options) []Diagnostic {
	out := []Diagnostic{}
	for _, s := range doc.Sentences {
		for i, t := range s.Tokens {
			american, found := britishSpellings[t.Lower]
			if !found || opts.Allowed(t.Lower) {
				continue
			}
			// A capitalized word that does not start the sentence is
			// usually a name, as in "the Defence Industries Association".
			// A name keeps its spelling. Rule 8.6 also makes a proper noun
			// one unit.
			if i > 0 && isCapitalized(t.Text) {
				continue
			}
			out = append(out, Diagnostic{
				RuleID:     RuleSpelling,
				Message:    "\"" + t.Text + "\" is a British spelling.",
				Severity:   SeverityWarning,
				Confidence: 0.9,
				Start:      t.Start,
				End:        t.End,
				Suggestion: "Write \"" + american + "\".",
			})
		}
	}
	return out
}

// nominalizations are the word groups that use a noun for an action. Rule
// 3.7 tells you to use the verb. The list is literal and narrow on purpose.
var nominalizations = []struct {
	Words       []string
	Replacement string
}{
	{[]string{"do", "a", "check", "of"}, "check"},
	{[]string{"do", "an", "inspection", "of"}, "inspect"},
	{[]string{"do", "a", "calculation", "of"}, "calculate"},
	{[]string{"do", "an", "analysis", "of"}, "analyze"},
	{[]string{"make", "an", "adjustment", "of"}, "adjust"},
	{[]string{"make", "an", "adjustment", "to"}, "adjust"},
	{[]string{"make", "a", "comparison", "of"}, "compare"},
	{[]string{"make", "a", "decision", "about"}, "decide"},
	{[]string{"make", "a", "selection", "of"}, "select"},
	{[]string{"make", "an", "examination", "of"}, "examine"},
	{[]string{"make", "use", "of"}, "use"},
	{[]string{"give", "an", "indication", "of"}, "show"},
	{[]string{"give", "an", "explanation", "of"}, "explain"},
	{[]string{"give", "a", "description", "of"}, "describe"},
	{[]string{"perform", "a", "test", "of"}, "test"},
	{[]string{"perform", "an", "installation", "of"}, "install"},
	{[]string{"is", "in", "operation"}, "operates"},
}

// Nominalizations reports a noun that must be a verb. Rule 3.7.
func Nominalizations(doc Document, opts Options) []Diagnostic {
	out := []Diagnostic{}
	for _, s := range doc.Sentences {
		for i := 0; i < len(s.Tokens); i++ {
			for _, n := range nominalizations {
				if !tokensMatch(s, i, n.Words) {
					continue
				}
				end := i + len(n.Words) - 1
				out = append(out, Diagnostic{
					RuleID:     RuleNominalization,
					Message:    "\"" + span(s, i, end) + "\" uses a noun for an action.",
					Severity:   SeverityWarning,
					Confidence: 0.9,
					Start:      s.Tokens[i].Start,
					End:        s.Tokens[end].End,
					Suggestion: "Write \"" + n.Replacement + "\".",
				})
				i = end
				break
			}
		}
	}
	return out
}

// latinAbbreviations maps a Latin abbreviation to its replacement. The
// tokenizer keeps the internal period, thus "e.g." gives the token "e.g".
var latinAbbreviations = map[string]string{
	"e.g":   "for example",
	"i.e":   "that is",
	"etc":   "and so on, or the full list",
	"viz":   "namely",
	"cf":    "compare",
	"n.b":   "note",
	"vs":    "compared to",
	"et.al": "and others",
}

// LatinAbbreviations reports a Latin abbreviation. GR-6 is a general
// recommendation and not a rule, thus the severity is info.
func LatinAbbreviations(doc Document, opts Options) []Diagnostic {
	out := []Diagnostic{}
	for _, s := range doc.Sentences {
		for _, t := range s.Tokens {
			replacement, found := latinAbbreviations[t.Lower]
			if !found || opts.Allowed(t.Lower) {
				continue
			}
			// A Latin abbreviation is lower-case and it ends with a
			// period: "e.g.", "vs.". "VS Code" is a name, and "Etc" at
			// the start of a sentence is rare. This test removes the
			// large majority of the wrong findings.
			if t.Text != t.Lower || !followedByPeriod(doc.Source, t.End) {
				continue
			}
			out = append(out, Diagnostic{
				RuleID:     RuleLatinAbbreviation,
				Message:    "\"" + t.Text + "\" is a Latin abbreviation.",
				Severity:   SeverityInfo,
				Confidence: 0.9,
				Start:      t.Start,
				End:        t.End,
				Suggestion: "Write \"" + replacement + "\".",
			})
		}
	}
	return out
}

// followedByPeriod tells if a period comes immediately after the offset.
func followedByPeriod(source string, end int) bool {
	return end < len(source) && source[end] == '.'
}

// isCapitalized tells if the word starts with a capital letter.
func isCapitalized(word string) bool {
	if word == "" {
		return false
	}
	r := []rune(word)[0]
	return unicode.IsUpper(r)
}

// tokensMatch tells if the tokens at i are the given words.
func tokensMatch(s Sentence, i int, words []string) bool {
	if i+len(words) > len(s.Tokens) {
		return false
	}
	for n, w := range words {
		if s.Tokens[i+n].Lower != w {
			return false
		}
	}
	return true
}
