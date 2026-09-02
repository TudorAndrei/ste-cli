// Package report turns the checker findings into text, JSON, or NDJSON.
//
// An agent is a first-class reader of this output. Thus the JSON is stable,
// each field has a name that does not change, and the caller can limit the
// size of the result before the command runs.
package report

import (
	"encoding/json"
	"fmt"
	"io"
	"sort"
	"strings"

	"github.com/TudorAndrei/ste-cli/internal/checker"
)

// Format is an output format.
type Format string

const (
	// FormatText is for a person.
	FormatText Format = "text"
	// FormatJSON is one object for the full run.
	FormatJSON Format = "json"
	// FormatNDJSON is one object for each line. A reader can stop at any
	// line, thus a large result does not need memory for all of it.
	FormatNDJSON Format = "ndjson"
)

// Formats gives the names of the formats.
func Formats() []string { return []string{"text", "json", "ndjson"} }

// ValidFormat tells if the name is a format.
func ValidFormat(name string) bool {
	for _, f := range Formats() {
		if f == name {
			return true
		}
	}
	return false
}

// Finding is one diagnostic with its file and its position in lines and
// columns.
type Finding struct {
	checker.Diagnostic
	File   string `json:"file"`
	Line   int    `json:"line"`
	Column int    `json:"column"`
	Text   string `json:"text"`
}

// Fields gives the names of the fields of a finding, for --fields.
func Fields() []string {
	return []string{
		"rule_id", "message", "severity", "confidence",
		"start", "end", "suggestion", "file", "line", "column", "text",
	}
}

// ValidFields tells which of the given names are not fields.
func ValidFields(names []string) []string {
	known := map[string]bool{}
	for _, f := range Fields() {
		known[f] = true
	}
	unknown := []string{}
	for _, n := range names {
		if !known[n] {
			unknown = append(unknown, n)
		}
	}
	return unknown
}

// project gives the finding with only the named fields. An empty list gives
// each field.
func (f Finding) project(fields []string) map[string]any {
	all := map[string]any{
		"rule_id":    f.RuleID,
		"message":    f.Message,
		"severity":   string(f.Severity),
		"confidence": f.Confidence,
		"start":      f.Start,
		"end":        f.End,
		"suggestion": f.Suggestion,
		"file":       f.File,
		"line":       f.Line,
		"column":     f.Column,
		"text":       f.Text,
	}
	if len(fields) == 0 {
		if f.Suggestion == "" {
			delete(all, "suggestion")
		}
		return all
	}
	out := map[string]any{}
	for _, name := range fields {
		if v, ok := all[name]; ok {
			out[name] = v
		}
	}
	return out
}

// FileResult holds the findings of one file.
type FileResult struct {
	Path     string    `json:"path"`
	Words    int       `json:"words"`
	Findings []Finding `json:"findings"`
}

// Summary gives the totals of a run.
type Summary struct {
	Files    int     `json:"files"`
	Words    int     `json:"words"`
	Findings int     `json:"findings"`
	Score    float64 `json:"score"`
	// Shown is the number of findings in this output. It is less than
	// Findings when --limit applies.
	Shown int `json:"shown"`
	// Truncated tells a reader that the output has fewer findings than the
	// run found.
	Truncated bool `json:"truncated"`
	// Accepted is the number of findings that the baseline holds.
	Accepted int `json:"accepted,omitempty"`
	// Errors is the number of findings with the error severity.
	Errors int `json:"errors"`
}

// Report is the full result of a run.
type Report struct {
	Version int          `json:"version"`
	Tool    string       `json:"tool"`
	Mode    string       `json:"mode"`
	Files   []FileResult `json:"files"`
	Summary Summary      `json:"summary"`
}

// Options control the shape of the output.
type Options struct {
	Format Format
	// Limit is the maximum number of findings in the output. A value of 0
	// gives every finding.
	Limit int
	// Fields are the fields of a finding to give. An empty list gives
	// every field.
	Fields []string
	// SummaryOnly removes the findings from the output.
	SummaryOnly bool
}

// New makes a report from the per-file results.
func New(mode string, files []FileResult, accepted int) Report {
	r := Report{Version: 1, Tool: "ste", Mode: mode, Files: files}
	for _, f := range files {
		r.Summary.Words += f.Words
		r.Summary.Findings += len(f.Findings)
		for _, d := range f.Findings {
			if d.Severity == checker.SeverityError {
				r.Summary.Errors++
			}
		}
	}
	r.Summary.Files = len(files)
	r.Summary.Shown = r.Summary.Findings
	r.Summary.Accepted = accepted
	r.Summary.Score = Score(r.Summary.Findings, r.Summary.Words)
	return r
}

// Score gives the number of findings for each 100 words.
func Score(findings, words int) float64 {
	if words == 0 {
		return 0
	}
	return float64(findings) * 100 / float64(words)
}

// MakeFinding adds the file name and the position to a diagnostic.
func MakeFinding(path, source string, d checker.Diagnostic) Finding {
	line, column := position(source, d.Start)
	text := ""
	if d.Start >= 0 && d.End <= len(source) && d.Start < d.End {
		text = source[d.Start:d.End]
	}
	return Finding{Diagnostic: d, File: path, Line: line, Column: column, Text: oneLine(text)}
}

func position(source string, offset int) (int, int) {
	if offset > len(source) {
		offset = len(source)
	}
	line, column := 1, 1
	for i := 0; i < offset; i++ {
		if source[i] == '\n' {
			line++
			column = 1
			continue
		}
		column++
	}
	return line, column
}

func oneLine(s string) string {
	return strings.Join(strings.Fields(s), " ")
}

// limited gives the findings of the report in one list, with the limit
// applied. It also gives the number of findings that the run found.
func (r Report) limited(limit int) ([]Finding, bool) {
	all := []Finding{}
	for _, f := range r.Files {
		all = append(all, f.Findings...)
	}
	sort.SliceStable(all, func(i, j int) bool {
		if all[i].File != all[j].File {
			return all[i].File < all[j].File
		}
		return all[i].Start < all[j].Start
	})
	if limit > 0 && len(all) > limit {
		return all[:limit], true
	}
	return all, false
}

// fileRows gives one compact row for each file of the given findings.
func (r Report) fileRows(shown []Finding) []map[string]any {
	words := map[string]int{}
	total := map[string]int{}
	order := []string{}
	for _, f := range r.Files {
		words[f.Path] = f.Words
		total[f.Path] = len(f.Findings)
	}
	seen := map[string]bool{}
	for _, f := range shown {
		if seen[f.File] {
			continue
		}
		seen[f.File] = true
		order = append(order, f.File)
	}
	rows := make([]map[string]any, 0, len(order))
	for _, path := range order {
		rows = append(rows, map[string]any{"path": path, "words": words[path], "count": total[path]})
	}
	return rows
}

// Write prints the report in the given format.
func Write(w io.Writer, r Report, opts Options) error {
	switch opts.Format {
	case FormatNDJSON:
		return writeNDJSON(w, r, opts)
	case FormatJSON:
		return writeJSON(w, r, opts)
	default:
		return WriteText(w, r, opts)
	}
}

// writeJSON gives one object for the run.
func writeJSON(w io.Writer, r Report, opts Options) error {
	out := map[string]any{
		"version": r.Version,
		"tool":    r.Tool,
		"mode":    r.Mode,
	}
	findings, truncated := r.limited(opts.Limit)
	r.Summary.Shown = len(findings)
	r.Summary.Truncated = truncated
	if opts.SummaryOnly {
		r.Summary.Shown = 0
	}
	out["summary"] = r.Summary
	if !opts.SummaryOnly {
		// A compact row for each file gives a per-file score without a
		// second copy of each finding. The list names only the files of
		// the findings in this output, thus --limit makes the full
		// result smaller and not only the list of findings.
		out["files"] = r.fileRows(findings)
	}

	if !opts.SummaryOnly {
		// The findings come as one list, and not one list for each
		// file. Each finding names its file, thus a reader needs no
		// second loop.
		items := make([]map[string]any, 0, len(findings))
		for _, f := range findings {
			items = append(items, f.project(opts.Fields))
		}
		out["findings"] = items
	}
	enc := json.NewEncoder(w)
	enc.SetIndent("", "  ")
	return enc.Encode(out)
}

// writeNDJSON gives one object for each line: each finding, and then the
// summary. A reader can stop at any line.
func writeNDJSON(w io.Writer, r Report, opts Options) error {
	enc := json.NewEncoder(w)
	findings, truncated := r.limited(opts.Limit)
	if !opts.SummaryOnly {
		for _, f := range findings {
			item := f.project(opts.Fields)
			item["type"] = "finding"
			if err := enc.Encode(item); err != nil {
				return err
			}
		}
	}
	r.Summary.Shown = len(findings)
	if opts.SummaryOnly {
		r.Summary.Shown = 0
	}
	r.Summary.Truncated = truncated
	return enc.Encode(map[string]any{
		"type":    "summary",
		"version": r.Version,
		"tool":    r.Tool,
		"mode":    r.Mode,
		"summary": r.Summary,
	})
}

// WriteText prints the report for a person.
func WriteText(w io.Writer, r Report, opts Options) error {
	findings, truncated := r.limited(opts.Limit)
	if !opts.SummaryOnly {
		for _, d := range findings {
			if _, err := fmt.Fprintf(w, "%s:%d:%d: %s [%s] %s\n",
				d.File, d.Line, d.Column, d.Severity, d.RuleID, d.Message); err != nil {
				return err
			}
			if d.Suggestion != "" {
				if _, err := fmt.Fprintf(w, "    %s\n", d.Suggestion); err != nil {
					return err
				}
			}
		}
	}
	if truncated {
		if _, err := fmt.Fprintf(w, "\n%s of %s are in this report. Give a higher --limit for more.\n",
			count(len(findings), "finding"), count(r.Summary.Findings, "finding")); err != nil {
			return err
		}
	}
	_, err := fmt.Fprintf(w, "\n%s in %s of %s (%.2f for each 100 words)\n",
		count(r.Summary.Findings, "finding"),
		count(r.Summary.Words, "word"),
		count(r.Summary.Files, "file"),
		r.Summary.Score)
	return err
}

// count gives "1 file" or "2 files".
func count(n int, noun string) string {
	if n == 1 {
		return fmt.Sprintf("%d %s", n, noun)
	}
	return fmt.Sprintf("%d %ss", n, noun)
}
