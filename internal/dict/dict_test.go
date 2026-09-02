package dict

import (
	"path/filepath"
	"strings"
	"testing"
)

// The fixture is not the ASD-STE100 dictionary. It has the shape of the
// table of part 2, with invented words, because the specification must not
// enter this repository. See docs/upstream-audit.md.
const fixture = `
# Part 1 - Writing rules

|Rule 1.1|Use approved words|

## Part 2 – Dictionary

|Word (part of speech)|Approved meaning/ ALTERNATIVES|STE EXAMPLE|Non-STE example|
|---|---|---|---|
|FRAMMIS (n)|A part of the machine|INSTALL THE FRAMMIS.||
|GRIBBLE (v), GRIBBLES, GRIBBLED|To make a hole|GRIBBLE THE PLATE.||
|wibble (adj)|GRIBBLE (adj)|THE GRIBBLE PLATE IS CLEAN.|The wibble plate is clean.|
||FRAMMIS (n)|INSTALL THE FRAMMIS.|Install the wibble.|
|snarf (v)|MAKE A LIST|MAKE A LIST OF THE PARTS.|Snarf the parts.|
|zorble (n)|No alternative is possible|||
|GRIBBLE (n)|A hole in a plate|EXAMINE THE GRIBBLE.||
`

func parseFixture(t *testing.T) *Index {
	t.Helper()
	ix, err := Parse(fixture, "fixture")
	if err != nil {
		t.Fatalf("parse: %v", err)
	}
	return ix
}

func TestParseReadsOnlyPartTwo(t *testing.T) {
	ix := parseFixture(t)
	// "Rule" is in part 1, thus it must not be a word of the dictionary.
	if len(ix.Lookup("rule")) != 0 {
		t.Errorf("the parser read part 1")
	}
	if got := ix.Stats().Words; got != 6 {
		t.Errorf("words %d, want 6: %+v", got, ix.Words)
	}
}

func TestApprovedAndUnapproved(t *testing.T) {
	ix := parseFixture(t)
	cases := []struct {
		word       string
		unapproved bool
		onlyVerb   bool
		alts       []string
	}{
		{"frammis", false, false, nil},
		{"gribble", false, false, nil},
		{"wibble", true, false, []string{"gribble", "frammis"}},
		{"snarf", true, true, []string{"make a list"}},
		{"zorble", true, false, nil},
		{"unknown-word", false, false, nil},
	}
	for _, tc := range cases {
		alts, onlyVerb, unapproved := ix.Unapproved(tc.word)
		if unapproved != tc.unapproved {
			t.Errorf("%s: unapproved %v, want %v", tc.word, unapproved, tc.unapproved)
			continue
		}
		if !unapproved {
			continue
		}
		if onlyVerb != tc.onlyVerb {
			t.Errorf("%s: onlyVerb %v, want %v", tc.word, onlyVerb, tc.onlyVerb)
		}
		if len(alts) != len(tc.alts) {
			t.Errorf("%s: alternatives %v, want %v", tc.word, alts, tc.alts)
			continue
		}
		for i := range alts {
			if alts[i] != tc.alts[i] {
				t.Errorf("%s: alternatives %v, want %v", tc.word, alts, tc.alts)
				break
			}
		}
	}
}

func TestAWordApprovedAsOnePartOfSpeech(t *testing.T) {
	// The fixture gives GRIBBLE as a verb and as a noun, and both are
	// approved. A word with one approved entry is approved, because this
	// tool has no part-of-speech tagger.
	ix := parseFixture(t)
	if entries := ix.Lookup("gribble"); len(entries) != 2 {
		t.Fatalf("entries %+v, want 2", entries)
	}
	if _, _, unapproved := ix.Unapproved("gribble"); unapproved {
		t.Error("gribble is approved")
	}
}

func TestParseRejectsATextWithNoDictionary(t *testing.T) {
	if _, err := Parse("# Some other document\n\nNo table here.\n", "x"); err == nil {
		t.Fatal("the parser accepted a text that is not the specification")
	}
}

func TestSaveAndLoad(t *testing.T) {
	ix := parseFixture(t)
	path := filepath.Join(t.TempDir(), "sub", "dictionary.json")
	if err := ix.Save(path); err != nil {
		t.Fatalf("save: %v", err)
	}
	back, err := Load(path)
	if err != nil {
		t.Fatalf("load: %v", err)
	}
	if back.Stats() != ix.Stats() {
		t.Errorf("stats %+v, want %+v", back.Stats(), ix.Stats())
	}
	if _, _, unapproved := back.Unapproved("wibble"); !unapproved {
		t.Error("the index lost its entries")
	}
}

func TestLoadOfAMissingFileIsNotAnError(t *testing.T) {
	ix, err := Load(filepath.Join(t.TempDir(), "none.json"))
	if err != nil || ix != nil {
		t.Fatalf("index %v, error %v, want nil and nil", ix, err)
	}
}

func TestDefaultPathIsGlobalAndFollowsXDG(t *testing.T) {
	// The index is data, and not a cache: this tool cannot make it again
	// without the copy of the user.
	t.Setenv("STE_DICT", "")
	t.Setenv("XDG_DATA_HOME", "/data")
	if got := DefaultPath(); got != filepath.Join("/data", "ste", "dictionary.json") {
		t.Errorf("path %q, want the XDG data directory", got)
	}

	t.Setenv("STE_DICT", "/explicit/index.json")
	if got := DefaultPath(); got != "/explicit/index.json" {
		t.Errorf("path %q, want the explicit path", got)
	}
}

func TestDefaultPathWithNoEnvironment(t *testing.T) {
	t.Setenv("STE_DICT", "")
	t.Setenv("XDG_DATA_HOME", "")
	got := DefaultPath()
	if !filepath.IsAbs(got) {
		t.Fatalf("path %q is not absolute", got)
	}
	// The path must not be in a cache directory, and it must not be in
	// the working directory of a project.
	if strings.Contains(strings.ToLower(got), "cache") {
		t.Errorf("path %q is in a cache directory", got)
	}
	if filepath.Base(filepath.Dir(got)) != "ste" {
		t.Errorf("path %q is not in a directory of this tool", got)
	}
}
