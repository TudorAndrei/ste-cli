package rules

import (
	"fmt"
	"strings"
)

// The rules of this file need the grammar of a sentence, which an external
// analyzer gives. Each one reports nothing when there is no analyzer: a
// guess about a part of speech is worse than silence, and the command must
// stay one binary with no runtime.
const (
	// RuleImperative is rule 5.3: write instructions in the imperative.
	RuleImperative = "STE-5.3"
	// RuleNounCluster is rule 2.1: write multi-word nouns of no more than
	// three words.
	RuleNounCluster = "STE-2.1"
	// RuleGerund is the part of rule 3.5 that needs the grammar: an "-ing"
	// form that is a verb, and not a technical noun or a modifier.
	RuleGerund = "STE-3.5"
)

// MaxNounWords is the limit of rule 2.1.
const MaxNounWords = 3

// Imperative reports an instruction that does not start with a command verb.
// Rule 5.3 tells you to write an instruction in the imperative form, so the
// reader knows that the sentence is an action and not a description.
// A numbered list does not always hold a procedure. A design record uses one
// for its requirements, and those sentences are descriptions. The rule reads
// a list only when most of its items are commands: a list of steps with one
// description is a defect, and a list with no command at all is not a
// procedure.
func Imperative(doc Document, opts Options) []Diagnostic {
	out := []Diagnostic{}
	for _, group := range procedures(doc) {
		type item struct {
			s       Sentence
			grammar []SyntaxToken
			command bool
		}
		items := []item{}
		commands := 0
		for _, s := range group {
			grammar := grammarOf(opts, s)
			if len(grammar) == 0 {
				continue
			}
			_, bad := notImperative(s, grammar, opts)
			items = append(items, item{s, grammar, !bad})
			if !bad {
				commands++
			}
		}
		// One item gives no majority, and a list with half or fewer
		// commands is not a sequence of steps.
		if len(items) < 2 || commands*2 <= len(items) {
			continue
		}
		for _, it := range items {
			if it.command {
				continue
			}
			if d, ok := notImperative(it.s, it.grammar, opts); ok {
				out = append(out, d)
			}
		}
	}
	return out
}

// procedures groups the first sentence of each item of each numbered list.
// Two items are in the same list when their blocks follow each other.
func procedures(doc Document) [][]Sentence {
	groups := [][]Sentence{}
	current := []Sentence{}
	previous := -2
	for _, s := range doc.Sentences {
		if !s.Procedural || s.Note || !s.First || s.Kind != BlockListItem || len(s.Tokens) == 0 {
			continue
		}
		if s.Block != previous+1 && len(current) > 0 {
			groups = append(groups, current)
			current = []Sentence{}
		}
		current = append(current, s)
		previous = s.Block
	}
	if len(current) > 0 {
		groups = append(groups, current)
	}
	return groups
}

// notImperative tests the first word of the command. A condition can come
// first, as rule 5.4 asks, and then the command starts after the comma.
func notImperative(s Sentence, grammar []SyntaxToken, opts Options) (Diagnostic, bool) {
	first := commandStart(s, grammar)
	if first < 0 || first >= len(grammar) {
		return Diagnostic{}, false
	}
	// An adverb can come before the verb: "Atomically replace the file".
	for first < len(grammar) && grammar[first].POS == "ADV" {
		first++
	}
	if first >= len(grammar) {
		return Diagnostic{}, false
	}
	t := grammar[first]
	// VB is the base form, which is the imperative. "Do not touch" starts
	// with "Do", and that is also VB.
	if t.Tag == "VB" {
		return Diagnostic{}, false
	}
	// The analyzer gives a wrong tag for a short sentence with no context.
	// A word that is the root of the sentence and a verb is a command.
	if t.POS == "VERB" && t.Dep == "ROOT" {
		return Diagnostic{}, false
	}
	// "Do not touch the surface" is a command in the negative form, and the
	// standard writes its safety instructions that way. The first word is
	// an auxiliary, and the command verb follows it.
	if t.POS == "AUX" && t.Dep == "aux" && headIsBaseVerb(grammar, t) {
		return Diagnostic{}, false
	}
	// A command at the start of a short sentence looks like an adjective or
	// a noun to the analyzer: "Delete quarantined files" and "Complete
	// preflight" are examples. The word "Please" makes the sentence a
	// command with no doubt, thus the analyzer reads the same word again
	// with that context.
	if ambiguousCommand(t) && readsAsCommandWithPlease(s, opts, first) {
		return Diagnostic{}, false
	}
	start, end := spanOfSyntax(s, t)
	return Diagnostic{
		RuleID:     RuleImperative,
		Message:    "The instruction starts with \"" + t.Text + "\", which is not a command verb.",
		Severity:   SeverityWarning,
		Confidence: 0.75,
		Start:      start,
		End:        end,
		Suggestion: "Start the instruction with the command form of the verb.",
	}, true
}

// commandStart gives the index of the first word of the command. It steps
// over a condition clause and its comma.
func commandStart(s Sentence, grammar []SyntaxToken) int {
	if len(grammar) == 0 {
		return -1
	}
	// A sentence can start with a condition ("When the light comes on, set
	// the switch") or with a phrase that gives the place ("In the pull
	// request, give the date"). Rule 5.4 asks for the condition first, and
	// the command then starts after the comma.
	first := grammar[0]
	if !conditionWords[strings.ToLower(first.Text)] && first.POS != "ADP" && first.POS != "SCONJ" {
		return 0
	}
	// The phrase ends at the first comma of the sentence.
	comma := strings.IndexByte(s.Text, ',')
	if comma < 0 {
		return -1
	}
	for i, t := range grammar {
		if t.Start > comma {
			return i
		}
	}
	return -1
}

// NounCluster reports a noun of more than three words. Rule 2.1 gives that
// limit, because a long noun cluster has more than one meaning.
func NounCluster(doc Document, opts Options) []Diagnostic {
	out := []Diagnostic{}
	for _, s := range doc.Sentences {
		grammar := grammarOf(opts, s)
		if len(grammar) == 0 {
			continue
		}
		out = append(out, clusters(s, grammar, opts)...)
	}
	return out
}

func clusters(s Sentence, grammar []SyntaxToken, opts Options) []Diagnostic {
	out := []Diagnostic{}
	for i := 0; i < len(grammar); {
		if !isNounWord(grammar[i]) {
			i++
			continue
		}
		j := i
		for j+1 < len(grammar) && isNounWord(grammar[j+1]) {
			j++
		}
		n := j - i + 1
		if n <= MaxNounWords || allProper(grammar[i:j+1]) {
			i = j + 1
			continue
		}
		phrase := phraseOf(grammar[i : j+1])
		if opts.Allowed(phrase) {
			i = j + 1
			continue
		}
		start, _ := spanOfSyntax(s, grammar[i])
		_, end := spanOfSyntax(s, grammar[j])
		out = append(out, Diagnostic{
			RuleID:     RuleNounCluster,
			Message:    fmt.Sprintf("The noun \"%s\" has %d words. The limit is %d words.", phrase, n, MaxNounWords),
			Severity:   SeverityWarning,
			Confidence: 0.8,
			Start:      start,
			End:        end,
			Suggestion: "Divide the noun, or write it with a preposition.",
		})
		i = j + 1
	}
	return out
}

// isNounWord tells if the word is a part of a noun cluster. A noun and a
// name are, and a word that modifies a noun with the "compound" relation is.
func isNounWord(t SyntaxToken) bool {
	return t.POS == "NOUN" || t.POS == "PROPN"
}

// allProper tells if each word of the cluster is a name. Rule 8.6 makes a
// multi-word name one unit, thus rule 2.1 does not read it.
func allProper(tokens []SyntaxToken) bool {
	for _, t := range tokens {
		if t.POS != "PROPN" {
			return false
		}
	}
	return true
}

func phraseOf(tokens []SyntaxToken) string {
	words := make([]string, 0, len(tokens))
	for _, t := range tokens {
		words = append(words, t.Text)
	}
	return strings.Join(words, " ")
}

// gerundDeps are the relations of an "-ing" word that is a verb. A word with
// the relation "amod" or "compound" modifies a noun, and rule 3.5 permits
// that.
var gerundDeps = map[string]bool{
	"advcl": true, "xcomp": true, "pcomp": true, "ccomp": true,
}

// Gerund reports an "-ing" form that is a verb. Rule 3.5 permits the "-ing"
// form only as a technical noun, or as a modifier in a technical noun.
//
// The Verbs rule finds "is running" with no analyzer. This rule finds the
// other positions, such as "Before starting the pump".
func Gerund(doc Document, opts Options) []Diagnostic {
	out := []Diagnostic{}
	for _, s := range doc.Sentences {
		grammar := grammarOf(opts, s)
		if len(grammar) == 0 {
			continue
		}
		for _, t := range grammar {
			if t.Tag != "VBG" || t.POS != "VERB" || !gerundDeps[t.Dep] {
				continue
			}
			word := strings.ToLower(t.Text)
			if opts.Allowed(word) || adjectivalIng[word] {
				continue
			}
			// "is running" is a progressive form, and the Verbs rule
			// reports it. A second finding for the same word is noise.
			if precededByBe(grammar, t) {
				continue
			}
			start, end := spanOfSyntax(s, t)
			out = append(out, Diagnostic{
				RuleID:     RuleGerund,
				Message:    "\"" + t.Text + "\" is an \"-ing\" form of a verb.",
				Severity:   SeverityWarning,
				Confidence: 0.8,
				Start:      start,
				End:        end,
				Suggestion: "Write a sentence with a verb in the simple present or the simple past.",
			})
		}
	}
	return out
}

// precededByBe tells if a form of "be" governs the word.
func precededByBe(grammar []SyntaxToken, t SyntaxToken) bool {
	for _, other := range grammar {
		if other.Head != t.Index {
			continue
		}
		if other.Dep == "aux" || other.Dep == "auxpass" {
			if beForms[strings.ToLower(other.Text)] {
				return true
			}
		}
	}
	return false
}

// spanOfSyntax gives the offsets of a word in the source text. The analyzer
// gives an offset in the sentence, and a finding needs an offset in the
// document.
func spanOfSyntax(s Sentence, t SyntaxToken) (int, int) {
	start := s.Start + t.Start
	end := start + len(t.Text)
	if start < s.Start || end > s.End {
		return s.Start, s.End
	}
	return start, end
}

// ambiguousCommand tells if a word can be a command that the analyzer read
// as something else. An adjective, a noun, and a name are the forms that a
// command verb takes at the start of a short sentence.
func ambiguousCommand(t SyntaxToken) bool {
	switch t.POS {
	case "ADJ", "NOUN", "PROPN":
		return true
	}
	return false
}

// readsAsCommandWithPlease asks the analyzer to read the sentence again with
// "Please " at its start. That word makes a command with no doubt, and the
// answer then gives the true part of speech of the word at index.
func readsAsCommandWithPlease(s Sentence, opts Options, index int) bool {
	if opts.Syntax == nil {
		return false
	}
	// The word keeps its capital letter at the start of a sentence, and the
	// analyzer then reads it as a name. A small letter after "please" gives
	// the true part of speech.
	grammar, ok := opts.Syntax.Grammar("please " + smallFirst(s.Text))
	if !ok {
		return false
	}
	// "Please" is one more word at the start of the sentence.
	if index+1 >= len(grammar) {
		return false
	}
	return grammar[index+1].Tag == "VB"
}

// smallFirst gives the text with a small first letter.
func smallFirst(text string) string {
	for i, r := range text {
		if r >= 'A' && r <= 'Z' {
			return string(r+32) + text[i+1:]
		}
		return text
	}
	return text
}

// headIsBaseVerb tells if the word that governs this auxiliary is a verb in
// the base form. "Do not touch" gives "touch", which is that form.
func headIsBaseVerb(grammar []SyntaxToken, t SyntaxToken) bool {
	if t.Head < 0 || t.Head >= len(grammar) {
		return false
	}
	return grammar[t.Head].Tag == "VB"
}
