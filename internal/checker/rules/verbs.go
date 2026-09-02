package rules

import "strings"

// Identifiers of the verb rules. The numbers are the rule numbers of
// ASD-STE100 Issue 9.
const (
	// RulePerfectTense is rule 3.4: do not use auxiliary verbs to make
	// complex verb constructions.
	RulePerfectTense = "STE-3.4"
	// RulePassiveVoice is rule 3.6: use the active voice.
	RulePassiveVoice = "STE-3.6"
	// RuleProgressive is rule 3.5: use the "-ing" form only as a technical
	// noun or as a modifier in a technical noun.
	RuleProgressive = "STE-3.5"
	// RulePhrasalVerb is rule 9.3: when you use two words together, do not
	// make phrasal verbs.
	RulePhrasalVerb = "STE-9.3"
)

// Verbs finds the verb forms that ASD-STE100 does not approve: the perfect
// tenses, the passive voice, the progressive "-ing" forms, and the phrasal
// verbs. The four checks stay in one function because the perfect-tense
// result can hide a passive result that says the same thing.
func Verbs(doc Document, opts Options) []Diagnostic {
	out := []Diagnostic{}
	for _, s := range doc.Sentences {
		out = append(out, sentenceVerbs(s, opts)...)
	}
	return out
}

// agentSpan marks a passive finding that has a "by" agent.
type verbFinding struct {
	diag    Diagnostic
	byAgent bool
}

func sentenceVerbs(s Sentence, opts Options) []Diagnostic {
	perfect := []Diagnostic{}
	passive := []verbFinding{}
	other := []Diagnostic{}

	for i := 0; i < len(s.Tokens); i++ {
		t := s.Tokens[i]
		if opts.Allowed(t.Lower) {
			continue
		}

		if perfectAux[t.Lower] {
			if d, ok := matchPerfect(s, i); ok {
				perfect = append(perfect, d)
			}
		}
		if beForms[t.Lower] {
			if d, ok := matchProgressive(s, i, opts); ok {
				other = append(other, d)
			}
			if d, agent, ok := matchPassive(s, i, opts); ok {
				passive = append(passive, verbFinding{d, agent})
			}
		}
		if d, ok := matchPhrasal(s, i, opts); ok {
			other = append(other, d)
		}
	}

	out := append([]Diagnostic{}, perfect...)
	for _, p := range passive {
		// "has been sent" already gives a perfect-tense finding. A second
		// finding for the same words is noise, except when a "by" agent
		// shows that the sentence also needs an active subject.
		if !p.byAgent && containedInAny(p.diag, perfect) {
			continue
		}
		out = append(out, p.diag)
	}
	return append(out, other...)
}

func containedInAny(d Diagnostic, outer []Diagnostic) bool {
	for _, o := range outer {
		if d.Start >= o.Start && d.End <= o.End {
			return true
		}
	}
	return false
}

// nextContent gives the index of the next token that is not an interrupter.
func nextContent(s Sentence, i int) int {
	j := i
	for j < len(s.Tokens) && isInterrupter(s.Tokens[j].Lower) {
		j++
	}
	return j
}

func isInterrupter(word string) bool {
	if interrupters[word] {
		return true
	}
	return len(word) > 3 && strings.HasSuffix(word, "ly")
}

// matchPerfect finds "has|have|had (been) <participle>".
func matchPerfect(s Sentence, i int) (Diagnostic, bool) {
	j := nextContent(s, i+1)
	if j >= len(s.Tokens) {
		return Diagnostic{}, false
	}
	// "have to" is an obligation, not a perfect tense.
	if s.Tokens[j].Lower == "to" {
		return Diagnostic{}, false
	}
	if s.Tokens[j].Lower == "been" {
		k := nextContent(s, j+1)
		if k < len(s.Tokens) && (isParticiple(s.Tokens[k].Lower) || isIngForm(s.Tokens[k].Lower)) {
			return perfectDiag(s, i, k, 0.9), true
		}
		// "has been available" is a perfect tense, but the word after
		// "been" gives no proof. Only strict mode reports it.
		return perfectDiag(s, i, j, 0.55), true
	}
	if isParticiple(s.Tokens[j].Lower) {
		return perfectDiag(s, i, j, 0.9), true
	}
	return Diagnostic{}, false
}

func perfectDiag(s Sentence, from, to int, confidence float64) Diagnostic {
	return Diagnostic{
		RuleID:     RulePerfectTense,
		Message:    "\"" + span(s, from, to) + "\" is a perfect tense. ASD-STE100 approves only the simple present, the simple past, and the simple future.",
		Severity:   SeverityWarning,
		Confidence: confidence,
		Start:      s.Tokens[from].Start,
		End:        s.Tokens[to].End,
		Suggestion: "Write the simple past or the simple present.",
	}
}

// matchProgressive finds "is|was|are (still) <verb>ing".
func matchProgressive(s Sentence, i int, opts Options) (Diagnostic, bool) {
	j := nextContent(s, i+1)
	if j >= len(s.Tokens) || j == i {
		return Diagnostic{}, false
	}
	w := s.Tokens[j].Lower
	if !isIngForm(w) || adjectivalIng[w] || opts.Allowed(w) {
		return Diagnostic{}, false
	}
	// "is being adjusted" is a passive construction. The passive rule
	// reports it, thus a progressive finding for "is being" is wrong.
	if w == "being" {
		return Diagnostic{}, false
	}
	return Diagnostic{
		RuleID:     RuleProgressive,
		Message:    "\"" + span(s, i, j) + "\" is a progressive form. ASD-STE100 does not approve the \"-ing\" verb forms.",
		Severity:   SeverityWarning,
		Confidence: 0.9,
		Start:      s.Tokens[i].Start,
		End:        s.Tokens[j].End,
		Suggestion: "Write the simple present or the simple past.",
	}, true
}

// matchPassive finds "is|was|been (not) <participle>". It gives a high
// confidence when a "by" agent follows.
func matchPassive(s Sentence, i int, opts Options) (Diagnostic, bool, bool) {
	j := nextContent(s, i+1)
	if j >= len(s.Tokens) || j == i {
		return Diagnostic{}, false, false
	}
	w := s.Tokens[j].Lower
	if !isParticiple(w) || opts.Allowed(w) {
		return Diagnostic{}, false, false
	}
	byAgent := j+1 < len(s.Tokens) && s.Tokens[j+1].Lower == "by"
	if adjectivalParticiples[w] && !byAgent {
		// "is enabled" is an adjective in almost all technical text.
		return Diagnostic{}, false, false
	}

	confidence := 0.7
	switch {
	case byAgent:
		confidence = 0.95
	case irregularParticiples[w]:
		confidence = 0.85
	}
	return Diagnostic{
		RuleID:     RulePassiveVoice,
		Message:    "\"" + span(s, i, j) + "\" is the passive voice.",
		Severity:   SeverityWarning,
		Confidence: confidence,
		Start:      s.Tokens[i].Start,
		End:        s.Tokens[j].End,
		Suggestion: "Write the active voice. Name the person or the part that does the task.",
	}, byAgent, true
}

// matchPhrasal finds a phrasal verb that starts at token i.
func matchPhrasal(s Sentence, i int, opts Options) (Diagnostic, bool) {
	entries := phrasalIndex[s.Tokens[i].Lower]
	if len(entries) == 0 {
		return Diagnostic{}, false
	}
	for _, pv := range entries {
		end := i
		ok := true
		for n, particle := range pv.Particle {
			k := i + 1 + n
			if k >= len(s.Tokens) || s.Tokens[k].Lower != particle {
				ok = false
				break
			}
			end = k
		}
		if !ok {
			continue
		}
		phrase := span(s, i, end)
		if opts.Allowed(phrase) || opts.Allowed(s.Tokens[i].Lower) {
			continue
		}
		return Diagnostic{
			RuleID:     RulePhrasalVerb,
			Message:    "\"" + phrase + "\" is a phrasal verb. ASD-STE100 does not approve phrasal verbs.",
			Severity:   SeverityWarning,
			Confidence: 0.85,
			Start:      s.Tokens[i].Start,
			End:        s.Tokens[end].End,
			Suggestion: pv.Suggestion,
		}, true
	}
	return Diagnostic{}, false
}

// span gives the source text between two tokens. A span that crosses a line
// break becomes one line, because the text goes into a message.
func span(s Sentence, from, to int) string {
	start := s.Tokens[from].Start - s.Start
	end := s.Tokens[to].End - s.Start
	if start < 0 || end > len(s.Text) || start > end {
		return s.Tokens[from].Text
	}
	return strings.Join(strings.Fields(s.Text[start:end]), " ")
}

func isParticiple(word string) bool {
	if isCompound(word) {
		return false
	}
	if irregularParticiples[word] {
		return true
	}
	return len(word) > 3 && strings.HasSuffix(word, "ed")
}

func isIngForm(word string) bool {
	return !isCompound(word) && len(word) > 4 && strings.HasSuffix(word, "ing")
}

// isCompound tells if the word has a hyphen. A hyphenated form, such as
// "MIT-licensed" or "self-checking", is an adjective and not a verb.
func isCompound(word string) bool {
	return strings.Contains(word, "-")
}
