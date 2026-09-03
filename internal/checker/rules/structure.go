package rules

import (
	"fmt"
	"strings"
)

// The rules of the structure of a text. Each one uses the blocks that the
// parser gives, thus none of them needs a part-of-speech tagger.
const (
	// RuleVerticalList is rule 4.3: use a vertical list for complex text.
	RuleVerticalList = "STE-4.3"
	// RuleNoteInstruction is rule 5.5: write a note to give information,
	// and not an instruction.
	RuleNoteInstruction = "STE-5.5"
	// RuleParagraphLength is rule 6.6: a paragraph has 6 sentences maximum.
	RuleParagraphLength = "STE-6.6"
	// RuleSafetyWord is rule 7.1: start a safety instruction with a word
	// that identifies the level of the risk.
	RuleSafetyWord = "STE-7.1"
	// RuleSafetyExplanation is rule 7.3: give the risk or the possible
	// result.
	RuleSafetyExplanation = "STE-7.3"
)

// MaxSentencesInParagraph is the limit of rule 6.6.
const MaxSentencesInParagraph = 6

// ParagraphLength reports a paragraph of more than 6 sentences. Rule 6.6.
//
// A heading, a list item, and a cell of a table are not paragraphs, thus
// this rule does not count them.
func ParagraphLength(doc Document, opts Options) []Diagnostic {
	out := []Diagnostic{}
	for _, group := range paragraphs(doc) {
		if len(group) <= MaxSentencesInParagraph {
			continue
		}
		first, last := group[0], group[len(group)-1]
		out = append(out, Diagnostic{
			RuleID:     RuleParagraphLength,
			Message:    fmt.Sprintf("The paragraph has %d sentences. The limit is %d sentences.", len(group), MaxSentencesInParagraph),
			Severity:   SeverityWarning,
			Confidence: 1.0,
			Start:      first.Start,
			End:        last.End,
			Suggestion: "Divide the paragraph.",
		})
	}
	return out
}

// paragraphs groups the sentences of each paragraph.
func paragraphs(doc Document) [][]Sentence {
	groups := [][]Sentence{}
	current := []Sentence{}
	block := -1
	for _, s := range doc.Sentences {
		if s.Kind != BlockParagraph {
			continue
		}
		if s.Block != block {
			if len(current) > 0 {
				groups = append(groups, current)
			}
			current = []Sentence{}
			block = s.Block
		}
		current = append(current, s)
	}
	if len(current) > 0 {
		groups = append(groups, current)
	}
	return groups
}

// instructionWords are the words that make a sentence an instruction.
var instructionWords = map[string]bool{
	"must": true, "shall": true, "do": true, "always": true, "never": true,
}

// NoteInstruction reports an instruction in a note. Rule 5.5 says that a
// note gives information only.
func NoteInstruction(doc Document, opts Options) []Diagnostic {
	out := []Diagnostic{}
	for _, s := range doc.Sentences {
		if s.Admonition != "note" && s.Admonition != "notes" {
			continue
		}
		for i, t := range s.Tokens {
			if !instructionWords[t.Lower] {
				continue
			}
			// "do" is an instruction only with "not": "Do not touch".
			if t.Lower == "do" && (i+1 >= len(s.Tokens) || s.Tokens[i+1].Lower != "not") {
				continue
			}
			out = append(out, Diagnostic{
				RuleID:     RuleNoteInstruction,
				Message:    "The note has an instruction: \"" + t.Text + "\".",
				Severity:   SeverityWarning,
				Confidence: 0.8,
				Start:      t.Start,
				End:        t.End,
				Suggestion: "A note gives information only. Move the instruction to a step of the procedure.",
			})
			break
		}
	}
	return out
}

// safetyWords identify the level of a risk. Rule 7.1.
var safetyWords = map[string]bool{"warning": true, "caution": true, "danger": true}

// SafetyInstruction reports a safety instruction with no explanation of the
// risk. Rule 7.3 says that the reader must know the possible result.
//
// The rule does not report a note or a tip, because those are not safety
// instructions.
func SafetyInstruction(doc Document, opts Options) []Diagnostic {
	out := []Diagnostic{}
	byBlock := map[int][]Sentence{}
	order := []int{}
	for _, s := range doc.Sentences {
		if !safetyWords[s.Admonition] {
			continue
		}
		if _, seen := byBlock[s.Block]; !seen {
			order = append(order, s.Block)
		}
		byBlock[s.Block] = append(byBlock[s.Block], s)
	}
	for _, block := range order {
		group := byBlock[block]
		// The first sentence gives the command. A second sentence gives
		// the risk. One sentence alone gives no explanation.
		if len(group) > 1 || words(group) > 12 {
			continue
		}
		first, last := group[0], group[len(group)-1]
		out = append(out, Diagnostic{
			RuleID:     RuleSafetyExplanation,
			Message:    "The " + first.Admonition + " gives no explanation of the risk.",
			Severity:   SeverityWarning,
			Confidence: 0.7,
			Start:      first.Start,
			End:        last.End,
			Suggestion: "Add a sentence that gives the risk or the possible result.",
		})
	}
	return out
}

func words(group []Sentence) int {
	n := 0
	for _, s := range group {
		n += s.Words
	}
	return n
}

// VerticalList reports a list that starts some items with a capital letter
// and other items with a small letter. Rule 4.3 gives the construction of a
// vertical list.
//
// A list that starts each item with a small letter is a decision of style,
// and this rule does not report it. A list that changes in the middle is a
// defect, and a reader sees it.
func VerticalList(doc Document, opts Options) []Diagnostic {
	out := []Diagnostic{}
	for _, group := range lists(doc) {
		upper, lower := 0, 0
		for _, s := range group {
			if isLowerRune(firstRune(s.Text)) {
				lower++
			} else {
				upper++
			}
		}
		if upper == 0 || lower == 0 || len(group) < 2 {
			continue
		}
		// Report the smaller group: it is the exception in this list.
		reportLower := lower <= upper
		for _, s := range group {
			r := firstRune(s.Text)
			if isLowerRune(r) != reportLower {
				continue
			}
			shape := "a small letter"
			if !reportLower {
				shape = "a capital letter"
			}
			out = append(out, Diagnostic{
				RuleID:     RuleVerticalList,
				Message:    "The item of the list starts with " + shape + ", and the other items do not.",
				Severity:   SeverityInfo,
				Confidence: 0.8,
				Start:      s.Start,
				End:        s.Start + len(string(r)),
				Suggestion: "Use the same construction for each item of a vertical list.",
			})
		}
	}
	return out
}

// lists groups the items of each vertical list. Two items are in the same
// list when their blocks follow each other.
func lists(doc Document) [][]Sentence {
	groups := [][]Sentence{}
	current := []Sentence{}
	previous := -2
	for _, s := range doc.Sentences {
		if s.Kind != BlockListItem || !s.First {
			continue
		}
		// An item of a list must hold a sentence, and not one word.
		if len(s.Tokens) < 3 {
			continue
		}
		// An item that starts with code, a link, or an image gives no
		// letter to compare: the parser replaced that part with spaces,
		// thus the first letter of the prose is not the first letter of
		// the item.
		if hiddenStart(doc.Source, s.Start) {
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

// hiddenStart tells if the parser removed something at the start of the
// item, before the first word of the prose.
func hiddenStart(source string, start int) bool {
	if start > len(source) {
		return false
	}
	lineStart := strings.LastIndexByte(source[:start], '\n') + 1
	prefix := source[lineStart:start]
	// The markers of a list item and the space after them are not hidden
	// content.
	prefix = strings.TrimLeft(prefix, " \t-*+>0123456789.)")
	return strings.TrimSpace(prefix) != ""
}

func firstRune(s string) rune {
	for _, r := range s {
		return r
	}
	return 0
}

func isLowerRune(r rune) bool { return r >= 'a' && r <= 'z' }
