// Package dict reads the ASD-STE100 dictionary from a copy that the user
// supplies, and it keeps the result in a local file.
//
// This tool does not ship the dictionary. The specification is the property
// of ASD, and its terms do not permit redistribution without written
// permission. But ASD gives the specification free of charge to each writer
// and user through asd-ste100.org, thus each user can make this index from
// their own copy. See docs/upstream-audit.md.
package dict

import (
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"regexp"
	"sort"
	"strings"
)

// Version is the format version of the index file.
const Version = 1

// Entry is one word of the dictionary.
type Entry struct {
	Word string `json:"word"`
	// POS is the part of speech: n, v, adj, adv, prep, and more.
	POS string `json:"pos,omitempty"`
	// Approved tells if the dictionary approves the word. The dictionary
	// writes an approved word in capital letters.
	Approved bool `json:"approved"`
	// Alternatives are the approved words to use in place of an
	// unapproved word.
	Alternatives []string `json:"alternatives,omitempty"`
}

// Index is the dictionary in memory.
type Index struct {
	Version int     `json:"version"`
	Source  string  `json:"source"`
	Words   []Entry `json:"words"`

	byWord map[string][]Entry
}

// Stats gives the size of an index.
type Stats struct {
	Words        int
	Approved     int
	Unapproved   int
	Alternatives int
}

// Stats counts the entries.
func (ix *Index) Stats() Stats {
	s := Stats{Words: len(ix.Words)}
	for _, e := range ix.Words {
		if e.Approved {
			s.Approved++
		} else {
			s.Unapproved++
		}
		s.Alternatives += len(e.Alternatives)
	}
	return s
}

// Lookup gives the entries for a word.
func (ix *Index) Lookup(word string) []Entry {
	if ix == nil {
		return nil
	}
	if ix.byWord == nil {
		ix.build()
	}
	return ix.byWord[strings.ToLower(word)]
}

// Unapproved tells if the dictionary marks the word as not approved, and it
// gives the approved alternatives. A word that is not in the dictionary
// gives false, because rule 1.6 permits a technical noun that the dictionary
// does not have.
func (ix *Index) Unapproved(word string) ([]string, bool, bool) {
	entries := ix.Lookup(word)
	if len(entries) == 0 {
		return nil, false, false
	}
	alternatives := []string{}
	onlyVerb := true
	for _, e := range entries {
		// One word can be approved as one part of speech and not
		// approved as a different one. This tool has no part-of-speech
		// tagger, thus one approved entry makes the word approved.
		if e.Approved {
			return nil, false, false
		}
		if e.POS != "v" {
			onlyVerb = false
		}
		alternatives = append(alternatives, e.Alternatives...)
	}
	return merge(nil, alternatives), onlyVerb, true
}

func (ix *Index) build() {
	ix.byWord = map[string][]Entry{}
	for _, e := range ix.Words {
		key := strings.ToLower(e.Word)
		ix.byWord[key] = append(ix.byWord[key], e)
	}
}

// The dictionary of part 2 is a table of four columns. Column 1 holds the
// word and its part of speech. The dictionary writes an approved word in
// capital letters and an unapproved word in small letters.
var (
	headword = regexp.MustCompile(`([A-Za-z][A-Za-z'’\-]*(?:\s+[A-Za-z][A-Za-z'’\-]*)*)\s*\(([a-z]+)\)`)
	// An alternative can be a word group, as in "MAKE A LIST". A single
	// capital letter can be part of it, thus the group repeats with "*".
	alternative = regexp.MustCompile(`\b([A-Z][A-Z'’\-]+(?:\s+[A-Z][A-Z'’\-]*)*)\b`)
	partTwo     = regexp.MustCompile(`(?i)part\s*2\s*[–-]\s*dictionary`)
)

// Parse reads the dictionary from the Markdown conversion of the
// specification. It reads only part 2.
func Parse(markdown, source string) (*Index, error) {
	lines := strings.Split(markdown, "\n")
	start := -1
	for i, line := range lines {
		if strings.HasPrefix(line, "#") && partTwo.MatchString(line) {
			start = i
			break
		}
	}
	if start < 0 {
		return nil, fmt.Errorf("the text has no part 2, thus it is not the dictionary of ASD-STE100")
	}

	ix := &Index{Version: Version, Source: source}
	seen := map[string]int{} // word+pos to position in ix.Words
	last := -1               // the last unapproved entry, for a row that continues it

	for _, line := range lines[start:] {
		cells, ok := tableRow(line)
		if !ok {
			continue
		}
		word, meaning := cells[0], cells[1]

		// A row with no word continues the row above it.
		if strings.TrimSpace(word) == "" {
			if last >= 0 {
				ix.Words[last].Alternatives = merge(ix.Words[last].Alternatives, alternatives(meaning))
			}
			continue
		}

		matches := headword.FindAllStringSubmatch(word, -1)
		if len(matches) == 0 {
			continue
		}
		last = -1
		for n, m := range matches {
			text, pos := strings.TrimSpace(m[1]), m[2]
			if text == "" || strings.EqualFold(text, "Word") {
				continue
			}
			entry := Entry{Word: strings.ToLower(text), POS: pos, Approved: isUpper(text)}
			// The conversion of the PDF sometimes joins two entries in
			// one cell. Only the first entry of the cell can take the
			// alternatives of the meaning column.
			if !entry.Approved && n == 0 {
				entry.Alternatives = alternatives(meaning)
			}
			key := entry.Word + "\x00" + entry.POS
			if at, found := seen[key]; found {
				ix.Words[at].Alternatives = merge(ix.Words[at].Alternatives, entry.Alternatives)
				if entry.Approved {
					ix.Words[at].Approved = true
				}
				if !entry.Approved && n == 0 {
					last = at
				}
				continue
			}
			seen[key] = len(ix.Words)
			ix.Words = append(ix.Words, entry)
			if !entry.Approved && n == 0 {
				last = len(ix.Words) - 1
			}
		}
	}
	if len(ix.Words) == 0 {
		return nil, fmt.Errorf("the text has no dictionary entry")
	}
	sort.Slice(ix.Words, func(i, j int) bool {
		if ix.Words[i].Word != ix.Words[j].Word {
			return ix.Words[i].Word < ix.Words[j].Word
		}
		return ix.Words[i].POS < ix.Words[j].POS
	})
	return ix, nil
}

// tableRow gives the cells of a Markdown table row.
func tableRow(line string) ([]string, bool) {
	line = strings.TrimSpace(line)
	if !strings.HasPrefix(line, "|") || strings.HasPrefix(line, "|---") {
		return nil, false
	}
	// TrimPrefix removes one mark. strings.Trim would remove each mark,
	// and a row that continues the row above it starts with two marks and
	// an empty cell.
	line = strings.TrimSuffix(strings.TrimPrefix(line, "|"), "|")
	cells := strings.Split(line, "|")
	if len(cells) < 2 {
		return nil, false
	}
	return cells, true
}

// markers are the labels of the dictionary, and not alternatives. "TN" is a
// technical noun and "TV" is a technical verb.
var markers = map[string]bool{"tn": true, "tv": true, "ste": true, "asd": true}

// alternatives reads the approved words from the meaning column.
func alternatives(meaning string) []string {
	out := []string{}
	for _, m := range alternative.FindAllStringSubmatch(meaning, -1) {
		word := strings.ToLower(strings.TrimSpace(m[1]))
		if word == "" || len(word) < 2 || markers[word] {
			continue
		}
		out = append(out, word)
	}
	return merge(nil, out)
}

func merge(into, more []string) []string {
	seen := map[string]bool{}
	out := []string{}
	for _, list := range [][]string{into, more} {
		for _, w := range list {
			if seen[w] {
				continue
			}
			seen[w] = true
			out = append(out, w)
		}
	}
	if len(out) == 0 {
		return nil
	}
	return out
}

func isUpper(s string) bool {
	letters := 0
	for _, r := range s {
		if r >= 'a' && r <= 'z' {
			return false
		}
		if r >= 'A' && r <= 'Z' {
			letters++
		}
	}
	return letters > 0
}

// DefaultPath gives the path of the index for this user. The index stays out
// of a project directory, because git must never see it.
func DefaultPath() string {
	if dir := os.Getenv("STE_DICT"); dir != "" {
		return dir
	}
	base, err := os.UserCacheDir()
	if err != nil {
		return ".ste-dictionary.json"
	}
	return filepath.Join(base, "ste", "dictionary.json")
}

// Save writes the index.
func (ix *Index) Save(path string) error {
	if err := os.MkdirAll(filepath.Dir(path), 0o755); err != nil {
		return err
	}
	raw, err := json.Marshal(ix)
	if err != nil {
		return err
	}
	return os.WriteFile(path, append(raw, '\n'), 0o600)
}

// Load reads an index. A file that does not exist gives nil and no error,
// because the dictionary rule is optional.
func Load(path string) (*Index, error) {
	raw, err := os.ReadFile(path)
	if os.IsNotExist(err) {
		return nil, nil
	}
	if err != nil {
		return nil, err
	}
	var ix Index
	if err := json.Unmarshal(raw, &ix); err != nil {
		return nil, fmt.Errorf("%s: %w", path, err)
	}
	if ix.Version != Version {
		return nil, fmt.Errorf("%s: the index has version %d, and this tool makes version %d. Import the dictionary again", path, ix.Version, Version)
	}
	ix.build()
	return &ix, nil
}
