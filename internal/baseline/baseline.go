// Package baseline records the findings that a project accepts today.
//
// A tool that reports 1000 findings on its first day is a tool that a team
// removes. The baseline gives a different start: you record the findings
// that exist now, and the tool then reports only the new ones. The number in
// the baseline can go down with time, but it does not stop the work today.
package baseline

import (
	"encoding/json"
	"fmt"
	"os"
	"sort"
	"strings"

	"github.com/TudorAndrei/ste-cli/internal/checker"
)

// DefaultName is the file that the tool writes and reads.
const DefaultName = ".ste-baseline.json"

// Entry is one accepted finding. It has no line number, thus a change in a
// different part of the file does not make the entry invalid.
type Entry struct {
	File   string `json:"file"`
	RuleID string `json:"rule_id"`
	Text   string `json:"text"`
	// Count is the number of times that this finding is in the file.
	Count int `json:"count"`
}

// File is the content of a baseline file.
type File struct {
	Version int     `json:"version"`
	Created string  `json:"created"`
	Entries []Entry `json:"entries"`
}

// Set is a baseline in memory.
type Set struct {
	counts map[string]int
}

// key gives the fingerprint of a finding.
func key(file, ruleID, text string) string {
	return file + "\x00" + ruleID + "\x00" + strings.Join(strings.Fields(text), " ")
}

// New makes an empty set.
func New() *Set { return &Set{counts: map[string]int{}} }

// Add records one finding.
func (s *Set) Add(file, ruleID, text string) {
	s.counts[key(file, ruleID, text)]++
}

// Take removes one finding from the set. It gives true when the set had it,
// which means that the project accepted this finding before.
func (s *Set) Take(file, ruleID, text string) bool {
	k := key(file, ruleID, text)
	if s.counts[k] <= 0 {
		return false
	}
	s.counts[k]--
	return true
}

// Remaining gives the number of accepted findings that no run matched. A
// value of more than 0 means that the text improved, thus you can write the
// baseline again.
func (s *Set) Remaining() int {
	n := 0
	for _, c := range s.counts {
		n += c
	}
	return n
}

// Load reads a baseline file. A file that does not exist gives an empty set
// and no error, thus the first run needs no file.
func Load(path string) (*Set, error) {
	raw, err := os.ReadFile(path)
	if os.IsNotExist(err) {
		return New(), nil
	}
	if err != nil {
		return nil, err
	}
	var f File
	if err := json.Unmarshal(raw, &f); err != nil {
		return nil, fmt.Errorf("%s: %w", path, err)
	}
	set := New()
	for _, e := range f.Entries {
		count := e.Count
		if count <= 0 {
			count = 1
		}
		set.counts[key(e.File, e.RuleID, e.Text)] += count
	}
	return set, nil
}

// Save writes the findings of a run as the new baseline.
func Save(path string, results []Result, created string) error {
	set := New()
	for _, r := range results {
		for _, d := range r.Findings {
			set.Add(r.Path, d.RuleID, d.Text)
		}
	}
	f := File{Version: 1, Created: created, Entries: []Entry{}}
	for k, count := range set.counts {
		parts := strings.SplitN(k, "\x00", 3)
		f.Entries = append(f.Entries, Entry{File: parts[0], RuleID: parts[1], Text: parts[2], Count: count})
	}
	sort.Slice(f.Entries, func(i, j int) bool {
		if f.Entries[i].File != f.Entries[j].File {
			return f.Entries[i].File < f.Entries[j].File
		}
		if f.Entries[i].RuleID != f.Entries[j].RuleID {
			return f.Entries[i].RuleID < f.Entries[j].RuleID
		}
		return f.Entries[i].Text < f.Entries[j].Text
	})
	raw, err := json.MarshalIndent(f, "", "  ")
	if err != nil {
		return err
	}
	return os.WriteFile(path, append(raw, '\n'), 0o644)
}

// Result is the part of a file result that the baseline needs. The report
// package holds the full type, thus this package does not import it.
type Result struct {
	Path     string
	Findings []Finding
}

// Finding is one finding with the text that makes its fingerprint.
type Finding struct {
	RuleID string
	Text   string
	Diag   checker.Diagnostic
}
