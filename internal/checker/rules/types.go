// Package rules contains the ASD-STE100 checks and the data types that they
// operate on. The types stay in this package to prevent an import cycle: the
// parent checker package builds a Document, then calls each rule here.
package rules

import "strings"

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

// SeverityOff removes a rule from the result. It is a severity value in the
// config file, and it never appears in a finding.
const SeverityOff Severity = "off"

// Options controls the rules. The config package fills this structure from
// the config file, and the CLI flags can replace single fields.
type Options struct {
	Mode Mode
	// MaxWords is the sentence limit in words. A value of 0 selects the
	// limit from the type of each sentence.
	MaxWords int
	// AllowNouns and AllowVerbs are the project terms that the term rule
	// must not report.
	AllowNouns []string
	AllowVerbs []string
	// Prefer holds one name for each item, with the other names of that
	// item. Rule 1.11 uses it. Only the project knows that two nouns mean
	// the same item, thus the config gives them.
	Prefer []Preferred
	// DisableRules holds the rule IDs to remove from the result. The
	// RuleSeverity map with the value "off" does the same.
	DisableRules []string
	// RuleSeverity replaces the severity of one rule. The value "off"
	// removes the rule. A project uses this to make a rule advice today
	// and an error later.
	RuleSeverity map[string]Severity
	// MinConfidence removes each finding below this value. A value of 0
	// selects the default of the mode.
	MinConfidence float64
	// WarningsAsErrors makes each warning an error. It does not change an
	// info finding, because a general recommendation is advice and not a
	// rule of the standard.
	WarningsAsErrors bool
	// Dictionary is the ASD-STE100 dictionary that the user imported from
	// their own copy. It is nil when there is no import, and then the term
	// rule uses only its short hand-written list.
	Dictionary Dictionary
	// Syntax gives the grammar of a sentence. It is nil when the user
	// starts no analyzer, and then each rule uses its own test. A rule
	// must work without it.
	Syntax Syntax
}

// Syntax answers a question about the grammar of one sentence. An external
// program gives the answer, because Go has no library that gives the
// grammar of English with a trained model.
type Syntax interface {
	// PassiveAt tells if the word at the offset is the verb of a passive
	// construction. The second value is false when the analyzer gives no
	// answer, and the rule then keeps its own result.
	PassiveAt(sentence string, offset int) (passive bool, known bool)
	// Grammar gives one item for each word of the sentence. The second
	// value is false when the analyzer gives no answer.
	Grammar(sentence string) ([]SyntaxToken, bool)
}

// SyntaxToken is one word with its grammar. An external program gives it,
// and the fields are the fields of that program.
type SyntaxToken struct {
	// Index is the position of the word in the sentence.
	Index int
	Text  string
	// POS is the coarse part of speech: NOUN, VERB, ADJ, and more.
	POS string
	// Tag is the fine part of speech: NN, VB, VBG, VBN, and more.
	Tag string
	// Dep is the relation of the word to its head: nsubj, amod, compound,
	// advcl, and more.
	Dep string
	// Head is the index of the word that this word depends on.
	Head int
	// Start is the offset of the word in the sentence.
	Start int
}

// grammarOf gives the grammar of a sentence, or nil when there is no
// analyzer. A rule of the syntax group reports nothing when it gets nil,
// because a guess is worse than silence.
func grammarOf(opts Options, s Sentence) []SyntaxToken {
	if opts.Syntax == nil {
		return nil
	}
	tokens, ok := opts.Syntax.Grammar(s.Text)
	if !ok {
		return nil
	}
	return tokens
}

// DictionaryResult is what the dictionary says about a word that it does
// not approve.
type DictionaryResult struct {
	// Alternatives are the approved words to write in its place. The word
	// itself is never in this list.
	Alternatives []string
	// OnlyVerb is true when the dictionary has the word only as a verb.
	// English uses many of those words as a noun too, as in "pump", and
	// this tool has no part-of-speech tagger. The term rule gives a lower
	// confidence to that finding.
	OnlyVerb bool
	// TechnicalNoun is true when the dictionary approves the word as a
	// technical noun, and not as the part of speech of this entry. The
	// dictionary writes "(TN)" for that. "graph" is an example: you can
	// write "a graph", but not "to graph the results".
	TechnicalNoun bool
}

// Dictionary answers the one question that rule 1.1 asks about a word.
type Dictionary interface {
	// Unapproved gives the result for a word that the dictionary does not
	// approve. A word that the dictionary does not have gives false,
	// because rule 1.6 permits a technical noun that is not in the
	// dictionary.
	Unapproved(word string) (DictionaryResult, bool)
}

// Confidence gives the lowest confidence that the mode accepts.
func (o Options) Confidence() float64 {
	if o.MinConfidence > 0 {
		return o.MinConfidence
	}
	if o.Mode == ModeStrict {
		return 0
	}
	return MinConfidenceFlavored
}

// Severity gives the severity of a finding after the config applies.
func (o Options) Severity(ruleID string, given Severity) Severity {
	return o.promote(o.severity(ruleID, given))
}

// promote makes a warning an error when the config asks for it.
func (o Options) promote(s Severity) Severity {
	if o.WarningsAsErrors && s == SeverityWarning {
		return SeverityError
	}
	return s
}

func (o Options) severity(ruleID string, given Severity) Severity {
	if s, ok := o.RuleSeverity[ruleID]; ok {
		return s
	}
	if o.Mode == ModeStrict {
		// A general recommendation is advice, and not a rule of the
		// standard. Strict mode does not make it an error.
		if strings.HasPrefix(ruleID, "STE-GR-") {
			return given
		}
		switch given {
		case SeverityInfo:
			return SeverityWarning
		default:
			return SeverityError
		}
	}
	return given
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
	// Block is the number of the leaf block that holds the sentence. Each
	// paragraph, heading, list item, and table cell has its own number,
	// thus a rule can group the sentences of a paragraph.
	Block int
	// Kind is the type of that block.
	Kind BlockKind
	// Admonition is the word that starts a safety instruction or a note,
	// in small letters: "warning", "caution", "note", and more. It is
	// empty when the block is not one of those.
	Admonition string
	// First is true for the first sentence of its block.
	First bool
	// Last is true for the last sentence of its block.
	Last bool
}

// BlockKind is the type of a leaf block.
type BlockKind string

const (
	BlockParagraph BlockKind = "paragraph"
	BlockHeading   BlockKind = "heading"
	BlockListItem  BlockKind = "list-item"
	BlockTableCell BlockKind = "table-cell"
)

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
		ParagraphLength,
		NoteInstruction,
		SafetyInstruction,
		VerticalList,
		ConditionOrder,
		OneName,
		Imperative,
		NounCluster,
		Gerund,
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
