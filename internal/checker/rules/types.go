// Package rules contains the ASD-STE100 checks and the data types that they
// operate on. The types stay in this package to prevent an import cycle: the
// parent checker package builds a Document, then calls each rule here.
package rules

// Severity tells how strongly the tool objects to a span of text.
type Severity string

const (
	// SeverityError marks a finding that a strict review must correct.
	SeverityError Severity = "error"
	// SeverityWarning marks a finding that usually needs a correction.
	SeverityWarning Severity = "warning"
	// SeverityInfo marks a finding that is only advice.
	SeverityInfo Severity = "info"
)

// Mode selects how strict the checker is.
type Mode string

const (
	// ModeFlavored keeps only the high-confidence findings.
	ModeFlavored Mode = "flavored"
	// ModeStrict also reports the low-confidence findings and uses the
	// shorter sentence limit for procedures.
	ModeStrict Mode = "strict"
)

// Sentence limits, in words. ASD-STE100 selects the limit by the type of
// sentence, and not by a mode: rule 5.1 gives 20 words for an instruction in
// a procedure, and rules 5.5 and 6.3 give 25 words for a note and for
// descriptive text.
const (
	MaxWordsProcedural  = 20
	MaxWordsDescriptive = 25
)

// MinConfidenceFlavored is the confidence limit below which the flavored mode
// discards a finding.
const MinConfidenceFlavored = 0.6

// Diagnostic is one finding. Start and End are byte offsets into the source
// text. The offsets always point into the original document, not into the
// masked copy.
type Diagnostic struct {
	RuleID     string   `json:"rule_id"`
	Message    string   `json:"message"`
	Severity   Severity `json:"severity"`
	Confidence float64  `json:"confidence"`
	Start      int      `json:"start"`
	End        int      `json:"end"`
	Suggestion string   `json:"suggestion,omitempty"`
}

// Options controls the rules. The config package fills this structure from
// glossary.yml, and the CLI flags can replace single fields.
type Options struct {
	Mode Mode
	// MaxWords is the sentence limit in words. A value of 0 selects the
	// default for the mode.
	MaxWords int
	// AllowNouns and AllowVerbs are the project terms that the term rule
	// must not report.
	AllowNouns []string
	AllowVerbs []string
	// DisableRules holds the rule IDs to remove from the result.
	DisableRules []string
}

// Normalized returns a copy of the options with all defaults applied. It
// does not give MaxWords a value: a value of 0 tells the length rule to
// select the limit from the type of each sentence.
func (o Options) Normalized() Options {
	out := o
	if out.Mode != ModeStrict {
		out.Mode = ModeFlavored
	}
	return out
}

// Allowed tells if the word is a project term from the glossary.
func (o Options) Allowed(word string) bool {
	for _, w := range o.AllowNouns {
		if equalFold(w, word) {
			return true
		}
	}
	for _, w := range o.AllowVerbs {
		if equalFold(w, word) {
			return true
		}
	}
	return false
}

// Token is one word of a sentence with its position in the source text.
type Token struct {
	Text  string
	Lower string
	Start int
	End   int
}

// Sentence is one segment of prose with its position in the source text.
type Sentence struct {
	Text   string
	Start  int
	End    int
	Tokens []Token
	// Words is the number of words by the count rules of section 8. It is
	// not always len(Tokens): a quantity with its unit, a quoted string,
	// and text in parentheses each count as one word.
	Words int
	// Procedural is true when the sentence is an instruction in a
	// procedure. A numbered list item is the signal that this tool uses.
	Procedural bool
	// Note is true when the sentence is in a note. A note gives
	// information only, thus it keeps the longer limit.
	Note bool
}

// Limit gives the word limit for this sentence.
func (s Sentence) Limit() int {
	if s.Procedural && !s.Note {
		return MaxWordsProcedural
	}
	return MaxWordsDescriptive
}

// Document is the input for all rules.
type Document struct {
	// Source is the original text.
	Source string
	// Masked is the source with all excluded spans (code fences, inline
	// code, link targets) replaced by spaces. It has the same length as
	// Source, thus all offsets agree.
	Masked string
	// Sentences holds the prose segments in document order.
	Sentences []Sentence
}

// WordCount gives the number of words in the document. The CLI uses it for
// the findings-per-100-words score.
func (d Document) WordCount() int {
	n := 0
	for _, s := range d.Sentences {
		n += s.Words
	}
	return n
}

// Rule is one check.
type Rule func(doc Document, opts Options) []Diagnostic

// All returns the rules in the order in which the checker runs them.
func All() []Rule {
	return []Rule{
		SentenceLength,
		Semicolons,
		Contractions,
		Verbs,
		Terms,
		Spelling,
		Nominalizations,
		LatinAbbreviations,
	}
}

func equalFold(a, b string) bool {
	if len(a) != len(b) {
		return false
	}
	for i := 0; i < len(a); i++ {
		if lowerByte(a[i]) != lowerByte(b[i]) {
			return false
		}
	}
	return true
}

func lowerByte(c byte) byte {
	if c >= 'A' && c <= 'Z' {
		return c + 32
	}
	return c
}
