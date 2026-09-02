package checker

import "github.com/TudorAndrei/ste-cli/internal/checker/rules"

// The public result types are aliases of the types in the rules package. The
// rules package holds the definitions because the rules must not import this
// package.
type (
	// Diagnostic is one finding.
	Diagnostic = rules.Diagnostic
	// Options controls the rules.
	Options = rules.Options
	// Severity tells how strongly the tool objects to a span of text.
	Severity = rules.Severity
	// Mode selects how strict the checker is.
	Mode = rules.Mode
	// Document is the parsed input.
	Document = rules.Document
	// Sentence is one prose segment.
	Sentence = rules.Sentence
	// Token is one word.
	Token = rules.Token
	// Dictionary is the ASD-STE100 dictionary of the user.
	Dictionary = rules.Dictionary
	// DictionaryResult is what the dictionary says about a word.
	DictionaryResult = rules.DictionaryResult
)

// Severity values.
const (
	SeverityError   = rules.SeverityError
	SeverityWarning = rules.SeverityWarning
	SeverityInfo    = rules.SeverityInfo
)

// Mode values.
const (
	ModeFlavored = rules.ModeFlavored
	ModeStrict   = rules.ModeStrict
)
