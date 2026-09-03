package rules_test

import (
	"strings"
	"testing"

	"github.com/TudorAndrei/ste-cli/internal/checker"
	"github.com/TudorAndrei/ste-cli/internal/checker/rules"
)

// fakeSyntax gives a grammar that a test writes by hand. It keeps the tests
// away from Python and from the model, and the rule logic is what the test
// measures.
type fakeSyntax struct {
	// grammar holds the words of each sentence, in the order of the
	// sentence. Each word is "text/POS/TAG/DEP/HEAD".
	grammar map[string][]string
}

func (f fakeSyntax) PassiveAt(string, int) (bool, bool) { return false, false }

func (f fakeSyntax) Grammar(sentence string) ([]rules.SyntaxToken, bool) {
	spec, found := f.grammar[strings.TrimSpace(sentence)]
	if !found {
		return nil, false
	}
	out := []rules.SyntaxToken{}
	offset := 0
	for i, item := range spec {
		parts := strings.Split(item, "/")
		if len(parts) != 5 {
			panic("a word of the fake grammar needs 5 parts: " + item)
		}
		text := parts[0]
		head := i
		if parts[4] != "" {
			head = 0
			for _, c := range parts[4] {
				head = head*10 + int(c-'0')
			}
		}
		start := strings.Index(sentence[offset:], text)
		if start < 0 {
			panic("the word " + text + " is not in the sentence")
		}
		start += offset
		offset = start + len(text)
		out = append(out, rules.SyntaxToken{
			Index: i, Text: text, POS: parts[1], Tag: parts[2], Dep: parts[3],
			Head: head, Start: start,
		})
	}
	return out, true
}

func syntaxFindings(t *testing.T, src, ruleID string, grammar map[string][]string) []checker.Diagnostic {
	t.Helper()
	opts := rules.Options{Syntax: fakeSyntax{grammar: grammar}}
	out := []checker.Diagnostic{}
	for _, d := range checker.Lint(src, opts) {
		if d.RuleID == ruleID {
			out = append(out, d)
		}
	}
	return out
}

func TestImperative(t *testing.T) {
	cases := []struct {
		name    string
		src     string
		grammar map[string][]string
		want    int
	}{
		{"a command verb starts the step",
			"1. Open the valve.\n",
			map[string][]string{"Open the valve.": {"Open/VERB/VB/ROOT/0", "the/DET/DT/det/2", "valve/NOUN/NN/dobj/0"}},
			0},
		{"one description in a list of steps",
			"1. Open the valve.\n2. Start the pump.\n3. Installation of the pump is necessary.\n",
			map[string][]string{
				"Open the valve.": {"Open/VERB/VB/ROOT/0", "the/DET/DT/det/2", "valve/NOUN/NN/dobj/0"},
				"Start the pump.": {"Start/VERB/VB/ROOT/0", "the/DET/DT/det/2", "pump/NOUN/NN/dobj/0"},
				"Installation of the pump is necessary.": {
					"Installation/NOUN/NN/nsubj/4", "of/ADP/IN/prep/0", "the/DET/DT/det/3",
					"pump/NOUN/NN/pobj/1", "is/AUX/VBZ/ROOT/4", "necessary/ADJ/JJ/acomp/4"}},
			1},
		{"a numbered list of requirements is not a procedure",
			"1. Installation of the pump is necessary.\n2. Removal of the valve is necessary.\n",
			map[string][]string{
				"Installation of the pump is necessary.": {
					"Installation/NOUN/NN/nsubj/4", "of/ADP/IN/prep/0", "the/DET/DT/det/3",
					"pump/NOUN/NN/pobj/1", "is/AUX/VBZ/ROOT/4", "necessary/ADJ/JJ/acomp/4"},
				"Removal of the valve is necessary.": {
					"Removal/NOUN/NN/nsubj/4", "of/ADP/IN/prep/0", "the/DET/DT/det/3",
					"valve/NOUN/NN/pobj/1", "is/AUX/VBZ/ROOT/4", "necessary/ADJ/JJ/acomp/4"}},
			0},
		{"one item alone gives no majority",
			"1. Installation of the pump is necessary.\n",
			map[string][]string{"Installation of the pump is necessary.": {
				"Installation/NOUN/NN/nsubj/4", "of/ADP/IN/prep/0", "the/DET/DT/det/3",
				"pump/NOUN/NN/pobj/1", "is/AUX/VBZ/ROOT/4", "necessary/ADJ/JJ/acomp/4"}},
			0},
		{"a condition comes first, and the command follows",
			"1. When the light comes on, set the switch.\n",
			map[string][]string{"When the light comes on, set the switch.": {
				"When/SCONJ/WRB/advmod/3", "the/DET/DT/det/2", "light/NOUN/NN/nsubj/3",
				"comes/VERB/VBZ/advcl/5", "on/ADP/RP/prt/3", "set/VERB/VB/ROOT/5",
				"the/DET/DT/det/7", "switch/NOUN/NN/dobj/5"}},
			0},
		{"descriptive text is not an instruction",
			"The operator opens the valve.\n",
			map[string][]string{"The operator opens the valve.": {
				"The/DET/DT/det/1", "operator/NOUN/NN/nsubj/2", "opens/VERB/VBZ/ROOT/2",
				"the/DET/DT/det/4", "valve/NOUN/NN/dobj/2"}},
			0},
		{"no analyzer gives no finding",
			"1. Installation of the pump is necessary.\n",
			map[string][]string{},
			0},
	}
	for _, tc := range cases {
		t.Run(tc.name, func(t *testing.T) {
			if got := syntaxFindings(t, tc.src, "STE-5.3", tc.grammar); len(got) != tc.want {
				t.Errorf("got %d findings, want %d: %+v", len(got), tc.want, got)
			}
		})
	}
}

func TestNounCluster(t *testing.T) {
	cases := []struct {
		name    string
		src     string
		grammar map[string][]string
		want    int
	}{
		{"three words are inside the limit",
			"The pump control unit is on the left.\n",
			map[string][]string{"The pump control unit is on the left.": {
				"The/DET/DT/det/3", "pump/NOUN/NN/compound/3", "control/NOUN/NN/compound/3",
				"unit/NOUN/NN/nsubj/4", "is/AUX/VBZ/ROOT/4", "on/ADP/IN/prep/4",
				"the/DET/DT/det/7", "left/NOUN/NN/pobj/5"}},
			0},
		{"five words are more than the limit",
			"The engine fuel pump control unit is here.\n",
			map[string][]string{"The engine fuel pump control unit is here.": {
				"The/DET/DT/det/5", "engine/NOUN/NN/compound/5", "fuel/NOUN/NN/compound/5",
				"pump/NOUN/NN/compound/5", "control/NOUN/NN/compound/5", "unit/NOUN/NN/nsubj/6",
				"is/AUX/VBZ/ROOT/6", "here/ADV/RB/advmod/6"}},
			1},
		{"a name of many words is one unit",
			"The Aerospace Security Defence Industries Association is here.\n",
			map[string][]string{"The Aerospace Security Defence Industries Association is here.": {
				"The/DET/DT/det/5", "Aerospace/PROPN/NNP/compound/5", "Security/PROPN/NNP/compound/5",
				"Defence/PROPN/NNP/compound/5", "Industries/PROPN/NNP/compound/5",
				"Association/PROPN/NNP/nsubj/6", "is/AUX/VBZ/ROOT/6", "here/ADV/RB/advmod/6"}},
			0},
	}
	for _, tc := range cases {
		t.Run(tc.name, func(t *testing.T) {
			if got := syntaxFindings(t, tc.src, "STE-2.1", tc.grammar); len(got) != tc.want {
				t.Errorf("got %d findings, want %d: %+v", len(got), tc.want, got)
			}
		})
	}
}

func TestGerund(t *testing.T) {
	cases := []struct {
		name    string
		src     string
		grammar map[string][]string
		want    int
	}{
		{"an \"-ing\" verb in a clause",
			"Before starting the pump, open the valve.\n",
			map[string][]string{"Before starting the pump, open the valve.": {
				"Before/ADP/IN/prep/1", "starting/VERB/VBG/pcomp/0", "the/DET/DT/det/3",
				"pump/NOUN/NN/dobj/1", "open/VERB/VB/ROOT/4", "the/DET/DT/det/6",
				"valve/NOUN/NN/dobj/4"}},
			1},
		{"an \"-ing\" word that modifies a noun",
			"The operating manual is here.\n",
			map[string][]string{"The operating manual is here.": {
				"The/DET/DT/det/2", "operating/VERB/VBG/amod/2", "manual/NOUN/NN/nsubj/3",
				"is/AUX/VBZ/ROOT/3", "here/ADV/RB/advmod/3"}},
			0},
		{"a progressive form belongs to the verb rule",
			"The pump is running.\n",
			map[string][]string{"The pump is running.": {
				"The/DET/DT/det/1", "pump/NOUN/NN/nsubj/3", "is/AUX/VBZ/aux/3",
				"running/VERB/VBG/ROOT/3"}},
			1},
	}
	for _, tc := range cases {
		t.Run(tc.name, func(t *testing.T) {
			if got := syntaxFindings(t, tc.src, "STE-3.5", tc.grammar); len(got) != tc.want {
				t.Errorf("got %d findings, want %d: %+v", len(got), tc.want, got)
			}
		})
	}
}
