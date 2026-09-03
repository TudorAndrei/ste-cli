package rules

import "strings"

// RuleConditionOrder is rule 5.4: when a condition applies to an
// instruction, write the condition first.
const RuleConditionOrder = "STE-5.4"

// conditionWords start a condition clause. The standard gives "when" and
// "if" in its examples, and these other words make the same clause.
var conditionWords = map[string]bool{
	"when": true, "if": true, "before": true, "after": true,
	"until": true, "unless": true, "while": true,
}

// clauseVerbs take a clause as their object, and not as a condition. "Make
// sure that the valve is open before you start" has a condition, but "Check
// if the valve is open" has none: the "if" clause is what you check.
var clauseVerbs = map[string]bool{
	"check": true, "verify": true, "see": true, "test": true, "know": true,
	"determine": true, "ask": true, "confirm": true, "examine": true,
	"decide": true, "tell": true, "find": true, "identify": true,
}

// ConditionOrder reports an instruction that gives its condition after the
// command. Rule 5.4 tells you to write the condition first, so the reader
// knows the condition before they do the work.
//
// The rule reads an instruction only. A descriptive sentence can give a
// condition in any position.
func ConditionOrder(doc Document, opts Options) []Diagnostic {
	out := []Diagnostic{}
	for _, s := range doc.Sentences {
		if !s.Procedural || s.Note {
			continue
		}
		if d, ok := lateCondition(s); ok {
			out = append(out, d)
		}
	}
	return out
}

// minWordsBeforeCondition is the number of words that must come before the
// condition word. A command needs a verb and an object, and a condition
// that follows fewer words is usually a part of the first phrase.
const minWordsBeforeCondition = 3

func lateCondition(s Sentence) (Diagnostic, bool) {
	for i, t := range s.Tokens {
		if !conditionWords[t.Lower] {
			continue
		}
		// A sentence that starts with its condition already obeys the
		// rule. The first word decides, and a later condition word in
		// that sentence belongs to the clause that is already first.
		if i == 0 {
			return Diagnostic{}, false
		}
		if i < minWordsBeforeCondition {
			continue
		}
		// "Check if the valve is open" gives no condition.
		if clauseVerbs[s.Tokens[i-1].Lower] {
			continue
		}
		// A condition that follows an infinitive belongs to the
		// infinitive, and not to the command. "Use the flag to stop when
		// you have enough" does not become "When you have enough, use
		// the flag". A name in capital letters is a value and not a
		// verb: "Set the switch to NORMAL when the light comes on" keeps
		// its finding.
		if i >= 2 && s.Tokens[i-2].Lower == "to" && isSmallWord(s.Tokens[i-1].Text) {
			continue
		}
		// The condition must hold a verb of its own. "Close the valve
		// after the test" names a time and not a condition, and the
		// standard gives no correction for it.
		if !hasVerbAfter(s, i) {
			continue
		}
		return Diagnostic{
			RuleID:     RuleConditionOrder,
			Message:    "The instruction gives its condition (\"" + t.Text + "\") after the command.",
			Severity:   SeverityInfo,
			Confidence: 0.7,
			Start:      t.Start,
			End:        s.Tokens[len(s.Tokens)-1].End,
			Suggestion: "Write the condition first, then a comma, then the command.",
		}, true
	}
	return Diagnostic{}, false
}

// isSmallWord tells if the word starts with a small letter. A word in
// capital letters is the name of a setting or a value.
func isSmallWord(word string) bool {
	if word == "" {
		return false
	}
	return word[0] >= 'a' && word[0] <= 'z'
}

// hasVerbAfter tells if a clause that starts at index i holds a verb. The
// tool has no part-of-speech tagger, thus it looks for the words that make
// a clause: a pronoun or an auxiliary, or a word that ends in "s" or "ed".
func hasVerbAfter(s Sentence, i int) bool {
	for j := i + 1; j < len(s.Tokens); j++ {
		w := s.Tokens[j].Lower
		if clauseMarkers[w] {
			return true
		}
		if len(w) > 3 && (strings.HasSuffix(w, "ed") || strings.HasSuffix(w, "es")) {
			return true
		}
	}
	return false
}

// clauseMarkers are the words that show a clause with its own verb.
var clauseMarkers = map[string]bool{
	"is": true, "are": true, "was": true, "were": true, "be": true,
	"has": true, "have": true, "had": true, "does": true, "do": true,
	"did": true, "can": true, "will": true, "must": true, "comes": true,
	"you": true, "it": true, "they": true,
}
