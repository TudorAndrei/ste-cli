// Package report turns the checker findings into text or JSON.
package report

import (
	"encoding/json"
	"fmt"
	"io"
	"strings"

	"github.com/TudorAndrei/ste-cli/internal/checker"
)

// Finding is one diagnostic with its file and its position in lines and
// columns. The CLI adds these fields for the reader.
type Finding struct {
	checker.Diagnostic
	File   string `json:"file"`
	Line   int    `json:"line"`
	Column int    `json:"column"`
	Text   string `json:"text"`
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
}

// Report is the full result of a run.
type Report struct {
	Version int          `json:"version"`
	Mode    string       `json:"mode"`
	Files   []FileResult `json:"files"`
	Summary Summary      `json:"summary"`
}

// New makes a report from the per-file results.
func New(mode string, files []FileResult) Report {
	r := Report{Version: 1, Mode: mode, Files: files}
	for _, f := range files {
		r.Summary.Words += f.Words
		r.Summary.Findings += len(f.Findings)
	}
	r.Summary.Files = len(files)
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

// WriteJSON prints the report as JSON.
func WriteJSON(w io.Writer, r Report) error {
	enc := json.NewEncoder(w)
	enc.SetIndent("", "  ")
	return enc.Encode(r)
}

// WriteText prints the report for a human reader.
func WriteText(w io.Writer, r Report) error {
	for _, f := range r.Files {
		for _, d := range f.Findings {
			if _, err := fmt.Fprintf(w, "%s:%d:%d: %s [%s] %s\n",
				f.Path, d.Line, d.Column, d.Severity, d.RuleID, d.Message); err != nil {
				return err
			}
			if d.Suggestion != "" {
				if _, err := fmt.Fprintf(w, "    %s\n", d.Suggestion); err != nil {
					return err
				}
			}
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
