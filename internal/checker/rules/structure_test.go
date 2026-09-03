package rules_test

import (
	"strings"
	"testing"

	"github.com/TudorAndrei/ste-cli/internal/checker"
)

func findingsOf(t *testing.T, src, ruleID string) []checker.Diagnostic {
	t.Helper()
	out := []checker.Diagnostic{}
	for _, d := range checker.Lint(src, checker.Options{}) {
		if d.RuleID == ruleID {
			out = append(out, d)
		}
	}
	return out
}

func TestParagraphLength(t *testing.T) {
	six := "One. Two. Three. Four. Five. Six.\n"
	if got := findingsOf(t, six, "STE-6.6"); len(got) != 0 {
		t.Errorf("6 sentences gave %d findings, want 0", len(got))
	}
	seven := "One. Two. Three. Four. Five. Six. Seven.\n"
	got := findingsOf(t, seven, "STE-6.6")
	if len(got) != 1 {
		t.Fatalf("7 sentences gave %d findings, want 1", len(got))
	}
	if !strings.Contains(got[0].Message, "7 sentences") {
		t.Errorf("message %q", got[0].Message)
	}

	// A list is not a paragraph, thus the rule does not count its items.
	list := "- One.\n- Two.\n- Three.\n- Four.\n- Five.\n- Six.\n- Seven.\n"
	if got := findingsOf(t, list, "STE-6.6"); len(got) != 0 {
		t.Errorf("a list gave %d findings, want 0", len(got))
	}
	// Two paragraphs of 4 sentences are not one paragraph of 8.
	two := "One. Two. Three. Four.\n\nFive. Six. Seven. Eight.\n"
	if got := findingsOf(t, two, "STE-6.6"); len(got) != 0 {
		t.Errorf("two paragraphs gave %d findings, want 0", len(got))
	}
}

func TestNoteInstruction(t *testing.T) {
	cases := []struct {
		name string
		src  string
		want int
	}{
		{"a note with an instruction", "**NOTE:** You must disconnect the power.\n", 1},
		{"a note with information", "**NOTE:** The capacitor keeps a charge.\n", 0},
		{"a note with a negative command", "**NOTE:** Do not touch the surface.\n", 1},
		{"an instruction outside a note", "You must disconnect the power.\n", 0},
		{"a warning can hold an instruction", "**WARNING:** You must disconnect the power. It holds a charge.\n", 0},
	}
	for _, tc := range cases {
		t.Run(tc.name, func(t *testing.T) {
			if got := findingsOf(t, tc.src, "STE-5.5"); len(got) != tc.want {
				t.Errorf("got %d findings, want %d", len(got), tc.want)
			}
		})
	}
}

func TestSafetyExplanation(t *testing.T) {
	cases := []struct {
		name string
		src  string
		want int
	}{
		{"a warning with no explanation", "**WARNING:** Do not touch the surface.\n", 1},
		{"a warning with an explanation",
			"**WARNING:** Do not touch the surface. The surface is hot and it can burn your skin.\n", 0},
		{"a note is not a safety instruction", "**NOTE:** The surface is hot.\n", 0},
		{"a tip is not a safety instruction", "**TIP:** Use the other tool.\n", 0},
	}
	for _, tc := range cases {
		t.Run(tc.name, func(t *testing.T) {
			if got := findingsOf(t, tc.src, "STE-7.3"); len(got) != tc.want {
				t.Errorf("got %d findings, want %d", len(got), tc.want)
			}
		})
	}
}

func TestVerticalList(t *testing.T) {
	cases := []struct {
		name string
		src  string
		want int
	}{
		{"each item starts with a small letter",
			"- open the valve of the pump\n- start the pump of the system\n", 0},
		{"each item starts with a capital letter",
			"- Open the valve of the pump\n- Start the pump of the system\n", 0},
		{"one item of three is different",
			"- Open the valve of the pump\n- Start the pump of the system\n- close the valve of the tank\n", 1},
		{"a short item is not a sentence", "- go\n- stop\n", 0},
		{"a paragraph is not a list", "open the valve of the pump\n", 0},
		{"two lists do not join",
			"- Open the valve of the pump\n\nSome text between them here.\n\n- close the valve of the tank\n", 0},
	}
	for _, tc := range cases {
		t.Run(tc.name, func(t *testing.T) {
			if got := findingsOf(t, tc.src, "STE-4.3"); len(got) != tc.want {
				t.Errorf("got %d findings, want %d", len(got), tc.want)
			}
		})
	}
}

func TestAdmonitionForms(t *testing.T) {
	// A writer marks a note or a warning in more than one way.
	forms := []string{
		"**WARNING:** Do not touch it.\n",
		"WARNING: Do not touch it.\n",
		"> [!WARNING]\n> Do not touch it.\n",
		"> **Warning:** Do not touch it.\n",
	}
	for _, src := range forms {
		if got := findingsOf(t, src, "STE-7.3"); len(got) != 1 {
			t.Errorf("%q gave %d findings, want 1", src, len(got))
		}
	}
}

func TestMaskedCodeDoesNotJoinTwoWords(t *testing.T) {
	// The parser replaces code with spaces. Two words that the code
	// separates are not one verb construction.
	cases := []struct {
		name string
		src  string
		want int
	}{
		{"code between the two words",
			"The command is `scripts/release.sh`, exposed through the API.\n", 0},
		{"a link between the two words",
			"The result is [the report](http://example.com), signed by the team.\n", 0},
		{"nothing between the two words",
			"The report is signed by the team.\n", 1},
		{"an adverb between the two words",
			"The report is carefully signed by the team.\n", 1},
	}
	for _, tc := range cases {
		t.Run(tc.name, func(t *testing.T) {
			if got := findingsOf(t, tc.src, "STE-3.6"); len(got) != tc.want {
				t.Errorf("got %d findings, want %d: %+v", len(got), tc.want, got)
			}
		})
	}
}

func TestVerticalListIgnoresANonLetterStart(t *testing.T) {
	// A changelog starts each item with a version number or a mark. Those
	// items give no proof of the construction, thus the rule ignores them.
	cases := []struct {
		name string
		src  string
		want int
	}{
		{"each item starts with a digit",
			"- 0.4.0 gives the new parser\n- 0.3.0 gives the first rules\n- fix the count of words\n", 0},
		{"each item starts with a mark",
			"- (a) open the valve of the pump\n- (b) start the pump of the system\n", 0},
		{"a digit item does not change the letter items",
			"- 3 of the tests are new\n- Open the valve of the pump\n- Start the pump of the system\n", 0},
	}
	for _, tc := range cases {
		t.Run(tc.name, func(t *testing.T) {
			if got := findingsOf(t, tc.src, "STE-4.3"); len(got) != tc.want {
				t.Errorf("got %d findings, want %d: %+v", len(got), tc.want, got)
			}
		})
	}
}
