package checker_test

import (
	"strings"
	"testing"

	"github.com/TudorAndrei/ste-cli/internal/checker"
)

func TestMaskKeepsTheLength(t *testing.T) {
	src := "Text `code` and [link](http://example.com/a;b).\n\n```go\nx := 1;\n```\n"
	doc := checker.Parse(src)
	if len(doc.Masked) != len(doc.Source) {
		t.Fatalf("masked length %d, source length %d", len(doc.Masked), len(doc.Source))
	}
}

func TestFencedCodeGivesNoFindings(t *testing.T) {
	src := "```\nThe file has been sent to the server.\n```\n"
	if got := checker.Lint(src, checker.Options{}); len(got) != 0 {
		t.Fatalf("got %d findings in a code fence, want 0: %+v", len(got), got)
	}
}

func TestTildeFencedCodeGivesNoFindings(t *testing.T) {
	src := "~~~\nThe file has been sent to the server.\n~~~\n"
	if got := checker.Lint(src, checker.Options{}); len(got) != 0 {
		t.Fatalf("got %d findings in a code fence, want 0: %+v", len(got), got)
	}
}

func TestTheSameTextInProseGivesAFinding(t *testing.T) {
	src := "The file has been sent to the server.\n"
	got := checker.Lint(src, checker.Options{})
	if len(got) != 1 {
		t.Fatalf("got %d findings, want 1: %+v", len(got), got)
	}
	if got[0].RuleID != "STE-3.4" {
		t.Fatalf("rule %s, want STE-3.4", got[0].RuleID)
	}
}

func TestInlineCodeIsExcluded(t *testing.T) {
	src := "Run `git commit -m \"it's done\"; make` and then stop.\n"
	if got := checker.Lint(src, checker.Options{}); len(got) != 0 {
		t.Fatalf("got %d findings in inline code, want 0: %+v", len(got), got)
	}
}

func TestLinkTargetIsExcludedButLinkTextIsNot(t *testing.T) {
	src := "See [the report isn't ready](http://example.com/a;b) for the data.\n"
	got := checker.Lint(src, checker.Options{})
	if len(got) != 1 {
		t.Fatalf("got %d findings, want 1: %+v", len(got), got)
	}
	if got[0].RuleID != "STE-4.2" {
		t.Fatalf("rule %s, want STE-4.2", got[0].RuleID)
	}
}

func TestOffsetsStayValidAfterMasking(t *testing.T) {
	src := "Some `code` here. The valve isn't open.\n"
	got := checker.Lint(src, checker.Options{})
	if len(got) != 1 {
		t.Fatalf("got %d findings, want 1: %+v", len(got), got)
	}
	if span := src[got[0].Start:got[0].End]; span != "isn't" {
		t.Fatalf("span %q, want %q", span, "isn't")
	}
}

func TestHeadingIsItsOwnSentence(t *testing.T) {
	src := "# Installation\n\nStart the pump.\n"
	doc := checker.Parse(src)
	if len(doc.Sentences) != 2 {
		t.Fatalf("got %d sentences, want 2: %+v", len(doc.Sentences), doc.Sentences)
	}
	if doc.Sentences[0].Text != "Installation" {
		t.Errorf("first sentence %q, want %q", doc.Sentences[0].Text, "Installation")
	}
}

func TestListItemsAreSeparateSentences(t *testing.T) {
	src := "- Open the valve\n- Start the pump\n"
	doc := checker.Parse(src)
	if len(doc.Sentences) != 2 {
		t.Fatalf("got %d sentences, want 2: %+v", len(doc.Sentences), doc.Sentences)
	}
}

func TestAbbreviationDoesNotEndASentence(t *testing.T) {
	src := "Use the correct tool, e.g. the torque wrench, for this task.\n"
	doc := checker.Parse(src)
	if len(doc.Sentences) != 1 {
		t.Fatalf("got %d sentences, want 1: %+v", len(doc.Sentences), doc.Sentences)
	}
}

func TestWrappedLinesStayOneSentence(t *testing.T) {
	src := "The pump gives pressure to the system\nand the valve controls the flow.\n"
	doc := checker.Parse(src)
	if len(doc.Sentences) != 1 {
		t.Fatalf("got %d sentences, want 1: %+v", len(doc.Sentences), doc.Sentences)
	}
	if !strings.Contains(doc.Sentences[0].Text, "valve") {
		t.Errorf("the sentence lost its second line: %q", doc.Sentences[0].Text)
	}
}

func TestIndentedCodeBlockIsExcluded(t *testing.T) {
	src := "Example structure:\n\n    docs/   # Additional documentation\n    tools/  # It isn't ready\n\nStart the pump.\n"
	if got := checker.Lint(src, checker.Options{}); len(got) != 0 {
		t.Fatalf("got %d findings in an indented code block, want 0: %+v", len(got), got)
	}
}

func TestIndentedListContinuationIsNotCode(t *testing.T) {
	src := "- The first step:\n\n    The valve isn't open.\n"
	got := checker.Lint(src, checker.Options{})
	if len(got) != 1 {
		t.Fatalf("got %d findings, want 1: %+v", len(got), got)
	}
	if got[0].RuleID != "STE-4.2" {
		t.Fatalf("rule %s, want STE-4.2", got[0].RuleID)
	}
}

func TestTableCellsAreSeparateSentences(t *testing.T) {
	// Each cell has 15 words. One row is not a 30-word sentence.
	cell := "one two three four five six seven eight nine ten one two three four five"
	src := "| A | B |\n|---|---|\n| " + cell + " | " + cell + " |\n"
	doc := checker.Parse(src)
	// Two header cells and two body cells.
	if len(doc.Sentences) != 4 {
		t.Fatalf("got %d sentences, want 4: %+v", len(doc.Sentences), doc.Sentences)
	}
	if got := checker.Lint(src, checker.Options{}); len(got) != 0 {
		t.Fatalf("got %d findings for a table row, want 0: %+v", len(got), got)
	}
}

func TestAListItemKeepsItsWrappedLines(t *testing.T) {
	// A step that continues on the next line is one instruction, thus its
	// full length is checked against the 20-word limit.
	src := "1. Open the valve one two three four five six seven eight nine ten and\n   then start the pump one two three four five six seven.\n"
	doc := checker.Parse(src)
	if len(doc.Sentences) != 1 {
		t.Fatalf("got %d sentences, want 1: %+v", len(doc.Sentences), doc.Sentences)
	}
	got := checker.Lint(src, checker.Options{})
	if len(got) != 1 || got[0].RuleID != "STE-5.1" {
		t.Fatalf("got %+v, want one STE-5.1 finding", got)
	}
}

func TestTwoListItemsStaySeparate(t *testing.T) {
	src := "1. Open the valve.\n2. Start the pump.\n"
	doc := checker.Parse(src)
	if len(doc.Sentences) != 2 {
		t.Fatalf("got %d sentences, want 2: %+v", len(doc.Sentences), doc.Sentences)
	}
}

func TestInlineCodeDoesNotHideASentenceStart(t *testing.T) {
	// The masked inline code must not join the two sentences.
	src := "The tool checks the text. `ste` gives a report of the findings.\n"
	doc := checker.Parse(src)
	if len(doc.Sentences) != 2 {
		t.Fatalf("got %d sentences, want 2: %+v", len(doc.Sentences), doc.Sentences)
	}
}

func TestADigitBeforeAPeriodEndsASentence(t *testing.T) {
	// "Issue 9." is the end of a sentence. A single letter, as in an
	// initial, is not.
	doc := checker.Parse("The tool obeys Issue 9. The rules agree with it.\n")
	if len(doc.Sentences) != 2 {
		t.Fatalf("got %d sentences, want 2: %+v", len(doc.Sentences), doc.Sentences)
	}
	doc = checker.Parse("The author is J. Smith of the group.\n")
	if len(doc.Sentences) != 1 {
		t.Fatalf("got %d sentences, want 1: %+v", len(doc.Sentences), doc.Sentences)
	}
}

func TestAClosingMarkDoesNotStopASentenceEnd(t *testing.T) {
	// The bold mark after the period must not join the two sentences.
	doc := checker.Parse("**Open the valve.** Then start the pump.\n")
	if len(doc.Sentences) != 2 {
		t.Fatalf("got %d sentences, want 2: %+v", len(doc.Sentences), doc.Sentences)
	}
}

// The CommonMark parser gives constructs that the first hand-written reader
// did not know.
func TestCommonMarkConstructs(t *testing.T) {
	cases := []struct {
		name string
		src  string
		want int // findings
	}{
		{"reference link keeps the label, not the target",
			"See [the report isn't ready][ref] here.\n\n[ref]: http://example.com/a;b\n", 1},
		{"setext heading is prose",
			"The valve isn't open\n====================\n", 1},
		{"HTML block is not prose",
			"<div class=\"note\">The report isn't ready.</div>\n", 0},
		{"an inline HTML tag is not prose",
			"The valve <b>isn't</b> open.\n", 1},
		{"a nested list item is its own sentence",
			"- Open the valve\n  - Start the pump\n", 0},
		{"an image title is not prose",
			"![the report isn't ready](a.png)\n", 0},
		{"a blockquote holds prose",
			"> The valve isn't open.\n", 1},
		{"a code fence with a language is not prose",
			"```go\nx := \"it isn't code prose\"\n```\n", 0},
	}
	for _, tc := range cases {
		t.Run(tc.name, func(t *testing.T) {
			got := checker.Lint(tc.src, checker.Options{})
			if len(got) != tc.want {
				t.Errorf("got %d findings, want %d: %+v", len(got), tc.want, got)
			}
		})
	}
}

func TestWordCount(t *testing.T) {
	doc := checker.Parse("Open the valve. Start the pump.\n")
	if doc.WordCount() != 6 {
		t.Fatalf("word count %d, want 6", doc.WordCount())
	}
}

// Section 8 gives the count rules. A quantity with its unit, a quoted
// string, and text in parentheses each count as one word.
func TestWordCountFollowsTheCountRules(t *testing.T) {
	cases := []struct {
		name string
		text string
		want int
	}{
		{"plain", "Set the pressure of the pump.", 6},
		{"quantity and unit", "Set the pressure to 30 psi.", 5},
		{"quantity and unit in a longer sentence",
			"Set the pressure to 30 psi before you start the test.", 10},
		{"quoted string is one word", "Push the \"EMER PWR\" switch.", 4},
		{"parentheses are one word", "Start the pump (the second pump on the left).", 4},
		{"hyphenated word is one word", "Install the quick-release fastener.", 4},
		{"a number alone is one word", "Remove the 4 bolts.", 4},
	}
	for _, tc := range cases {
		t.Run(tc.name, func(t *testing.T) {
			doc := checker.Parse(tc.text)
			if got := doc.WordCount(); got != tc.want {
				t.Errorf("word count %d, want %d for %q", got, tc.want, tc.text)
			}
		})
	}
}

func TestSentenceTypeAnnotation(t *testing.T) {
	src := "Start the pump.\n\n1. Open the valve.\n2. NOTE: The pump needs pressure.\n\n- Open the valve.\n"
	doc := checker.Parse(src)
	if len(doc.Sentences) != 4 {
		t.Fatalf("got %d sentences, want 4: %+v", len(doc.Sentences), doc.Sentences)
	}
	want := []struct {
		procedural bool
		note       bool
		limit      int
	}{
		{false, false, 25}, // plain prose
		{true, false, 20},  // a numbered step is an instruction
		{true, true, 25},   // a note keeps the longer limit
		{false, false, 25}, // a bulleted item is not a step
	}
	for i, w := range want {
		s := doc.Sentences[i]
		if s.Procedural != w.procedural || s.Note != w.note || s.Limit() != w.limit {
			t.Errorf("sentence %d (%q): procedural=%v note=%v limit=%d, want %v/%v/%d",
				i, s.Text, s.Procedural, s.Note, s.Limit(), w.procedural, w.note, w.limit)
		}
	}
}

// Rule 8.4: in a vertical list, a colon ends a sentence and the word count
// starts again.
func TestColonEndsSentenceInAList(t *testing.T) {
	cases := []struct {
		name string
		src  string
		want int
	}{
		{"a colon divides a list item", "- The flag: it starts the pump.\n", 2},
		{"a colon in a paragraph does not divide", "The flag: it starts the pump.\n", 1},
		{"a colon with no space is not punctuation", "- The run starts at 12:30 each day.\n", 1},
		{"the label of a note stays with its sentence",
			"- **NOTE:** The pump needs pressure.\n", 1},
		{"a colon at the end of the item", "- The flag does this:\n", 1},
	}
	for _, tc := range cases {
		t.Run(tc.name, func(t *testing.T) {
			doc := checker.Parse(tc.src)
			if got := len(doc.Sentences); got != tc.want {
				t.Errorf("got %d sentences, want %d: %+v", got, tc.want, doc.Sentences)
			}
		})
	}
}
