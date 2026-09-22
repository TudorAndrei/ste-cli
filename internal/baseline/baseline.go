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
	"path"
	"path/filepath"
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

// Stale gives the number of accepted findings of the given files that no
// finding of this run took. A value of more than 0 means that the text
// improved, thus you can write the baseline again. Call it after each Take
// of the run. A file that the run did not read does not count, because its
// findings are not known.
func (s *Set) Stale(files map[string]bool) int {
	n := 0
	for k, c := range s.counts {
		if files[strings.SplitN(k, "\x00", 2)[0]] {
			n += c
		}
	}
	return n
}

// Load reads a baseline file. A file that does not exist gives an empty set
// and no error, thus the first run needs no file.
func Load(path string) (*Set, error) {
	f, err := read(path)
	if err != nil {
		return nil, err
	}
	set := New()
	for _, e := range f.Entries {
		set.counts[key(e.File, e.RuleID, e.Text)] += e.Count
	}
	return set, nil
}

// read gives the entries of a baseline file, with a clean file name and a
// count of 1 or more. A file that does not exist gives no entries.
func read(path string) (File, error) {
	raw, err := os.ReadFile(path)
	if os.IsNotExist(err) {
		return File{}, nil
	}
	if err != nil {
		return File{}, err
	}
	var f File
	if err := json.Unmarshal(raw, &f); err != nil {
		return File{}, fmt.Errorf("%s: %w", path, err)
	}
	for i := range f.Entries {
		f.Entries[i].File = Clean(f.Entries[i].File)
		if f.Entries[i].Count <= 0 {
			f.Entries[i].Count = 1
		}
	}
	return f, nil
}

// Clean gives the form of a file name that a key uses: forward slashes and
// no "./" or "..". A baseline of Windows and a baseline of Linux thus agree.
func Clean(file string) string {
	return path.Clean(filepath.ToSlash(file))
}

// Save writes the findings of a run as the new baseline. The paths of the
// results must be relative to the directory of the baseline file.
//
// The entries of a file that the run did not read stay in the baseline,
// thus a run on one directory does not remove the findings of a different
// directory. An entry of a file that no longer exists goes.
func Save(file string, results []Result, created string) error {
	plan, err := Plan(file, results)
	if err != nil {
		return err
	}
	set := New()
	for _, r := range results {
		for _, d := range r.Findings {
			set.Add(Clean(r.Path), d.RuleID, d.Text)
		}
	}
	for _, e := range plan.kept {
		set.counts[key(e.File, e.RuleID, e.Text)] += e.Count
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
	return os.WriteFile(file, append(raw, '\n'), 0o644)
}

// Merge tells what Save does to the entries that exist in the file.
type Merge struct {
	// Kept is the number of accepted findings of the files that the run
	// did not read. Save keeps them.
	Kept int
	// Removed is the number of accepted findings of the files that no
	// longer exist. Save removes them.
	Removed int
	kept    []Entry
}

// Plan gives the result of Save and changes nothing.
func Plan(file string, results []Result) (Merge, error) {
	old, err := read(file)
	if err != nil {
		return Merge{}, err
	}
	run := map[string]bool{}
	for _, r := range results {
		run[Clean(r.Path)] = true
	}
	dir := filepath.Dir(file)
	m := Merge{}
	for _, e := range old.Entries {
		if run[e.File] {
			continue
		}
		if _, err := os.Stat(filepath.Join(dir, filepath.FromSlash(e.File))); err != nil {
			m.Removed += e.Count
			continue
		}
		m.Kept += e.Count
		m.kept = append(m.kept, e)
	}
	return m, nil
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
