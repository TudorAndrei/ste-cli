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
	if got[0].RuleID != "STE-3.1" {
		t.Fatalf("rule %s, want STE-3.1", got[0].RuleID)
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
	src := "| " + cell + " | " + cell + " |\n"
	doc := checker.Parse(src)
	if len(doc.Sentences) != 2 {
		t.Fatalf("got %d sentences, want 2: %+v", len(doc.Sentences), doc.Sentences)
	}
	if got := checker.Lint(src, checker.Options{}); len(got) != 0 {
		t.Fatalf("got %d findings for a table row, want 0: %+v", len(got), got)
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

func TestWordCount(t *testing.T) {
	doc := checker.Parse("Open the valve. Start the pump.\n")
	if doc.WordCount() != 6 {
		t.Fatalf("word count %d, want 6", doc.WordCount())
	}
}
