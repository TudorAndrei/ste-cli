// Package eval measures the rule quality against the labeled fixture corpus.
// Each fixture file can have a "<name>.expected.json" file that lists the
// findings that the checker must give. A file with no expectation file must
// give no findings.
package eval

import (
	"encoding/json"
	"fmt"
	"io"
	"os"
	"path/filepath"
	"sort"
	"strings"

	"github.com/TudorAndrei/ste-cli/internal/checker"
	"github.com/TudorAndrei/ste-cli/internal/checker/rules"
)

// Expectation is one labeled finding.
type Expectation struct {
	RuleID string `json:"rule_id"`
	Text   string `json:"text"`
}

// expectedFile is the content of a "<name>.expected.json" file.
type expectedFile struct {
	Mode string `json:"mode"`
	// Prefer gives the names of rule 1.11, which reports nothing until the
	// config names them. The key is the name to use.
	Prefer map[string][]string `json:"prefer"`
	// AllowNouns gives the project terms of the fixture.
	AllowNouns []string      `json:"allow_nouns"`
	Expect     []Expectation `json:"expect"`
}

// options makes the checker options for one fixture.
func (e expectedFile) options() checker.Options {
	opts := checker.Options{Mode: checker.Mode(e.Mode), AllowNouns: e.AllowNouns}
	names := make([]string, 0, len(e.Prefer))
	for name := range e.Prefer {
		names = append(names, name)
	}
	sort.Strings(names)
	for _, name := range names {
		opts.Prefer = append(opts.Prefer, rules.Preferred{Name: name, Instead: e.Prefer[name]})
	}
	return opts
}

// RuleScore holds the counts for one rule.
type RuleScore struct {
	RuleID         string  `json:"rule_id"`
	TruePositives  int     `json:"true_positives"`
	FalsePositives int     `json:"false_positives"`
	FalseNegatives int     `json:"false_negatives"`
	Precision      float64 `json:"precision"`
	Recall         float64 `json:"recall"`
}

// Report is the result of a run.
type Report struct {
	Files  int         `json:"files"`
	Rules  []RuleScore `json:"rules"`
	Totals RuleScore   `json:"totals"`
}

// Run measures the corpus in dir.
func Run(dir string) (Report, error) {
	files, err := corpusFiles(dir)
	if err != nil {
		return Report{}, err
	}
	if len(files) == 0 {
		return Report{}, fmt.Errorf("%s: the corpus has no fixture files", dir)
	}

	counts := map[string]*RuleScore{}
	score := func(id string) *RuleScore {
		if _, ok := counts[id]; !ok {
			counts[id] = &RuleScore{RuleID: id}
		}
		return counts[id]
	}

	for _, path := range files {
		raw, err := os.ReadFile(path)
		if err != nil {
			return Report{}, err
		}
		source := string(raw)
		exp, err := loadExpected(path)
		if err != nil {
			return Report{}, err
		}
		opts := exp.options()
		got := checker.Lint(source, opts)

		want := append([]Expectation{}, exp.Expect...)
		used := make([]bool, len(want))
		for _, d := range got {
			text := strings.Join(strings.Fields(source[d.Start:d.End]), " ")
			matched := false
			for i, w := range want {
				if used[i] || w.RuleID != d.RuleID {
					continue
				}
				if w.Text != "" && w.Text != text {
					continue
				}
				used[i] = true
				matched = true
				break
			}
			if matched {
				score(d.RuleID).TruePositives++
			} else {
				score(d.RuleID).FalsePositives++
			}
		}
		for i, w := range want {
			if !used[i] {
				score(w.RuleID).FalseNegatives++
			}
		}
	}

	report := Report{Files: len(files)}
	for _, s := range counts {
		s.Precision = ratio(s.TruePositives, s.TruePositives+s.FalsePositives)
		s.Recall = ratio(s.TruePositives, s.TruePositives+s.FalseNegatives)
		report.Rules = append(report.Rules, *s)
		report.Totals.TruePositives += s.TruePositives
		report.Totals.FalsePositives += s.FalsePositives
		report.Totals.FalseNegatives += s.FalseNegatives
	}
	sort.Slice(report.Rules, func(i, j int) bool { return report.Rules[i].RuleID < report.Rules[j].RuleID })
	report.Totals.RuleID = "all"
	report.Totals.Precision = ratio(report.Totals.TruePositives, report.Totals.TruePositives+report.Totals.FalsePositives)
	report.Totals.Recall = ratio(report.Totals.TruePositives, report.Totals.TruePositives+report.Totals.FalseNegatives)
	return report, nil
}

func ratio(a, b int) float64 {
	if b == 0 {
		return 1
	}
	return float64(a) / float64(b)
}

func corpusFiles(dir string) ([]string, error) {
	out := []string{}
	err := filepath.WalkDir(dir, func(path string, d os.DirEntry, err error) error {
		if err != nil {
			return err
		}
		if d.IsDir() {
			return nil
		}
		if strings.HasSuffix(path, ".expected.json") {
			return nil
		}
		switch filepath.Ext(path) {
		case ".md", ".markdown", ".txt":
			out = append(out, path)
		}
		return nil
	})
	sort.Strings(out)
	return out, err
}

func loadExpected(path string) (expectedFile, error) {
	expPath := strings.TrimSuffix(path, filepath.Ext(path)) + ".expected.json"
	raw, err := os.ReadFile(expPath)
	if os.IsNotExist(err) {
		return expectedFile{}, nil
	}
	if err != nil {
		return expectedFile{}, err
	}
	var exp expectedFile
	if err := json.Unmarshal(raw, &exp); err != nil {
		return expectedFile{}, fmt.Errorf("%s: %w", expPath, err)
	}
	return exp, nil
}

// WriteText prints the report as a table.
func WriteText(w io.Writer, r Report) error {
	if _, err := fmt.Fprintf(w, "%-10s %5s %5s %5s %10s %8s\n", "rule", "tp", "fp", "fn", "precision", "recall"); err != nil {
		return err
	}
	for _, s := range append(append([]RuleScore{}, r.Rules...), r.Totals) {
		if _, err := fmt.Fprintf(w, "%-10s %5d %5d %5d %10.2f %8.2f\n",
			s.RuleID, s.TruePositives, s.FalsePositives, s.FalseNegatives, s.Precision, s.Recall); err != nil {
			return err
		}
	}
	_, err := fmt.Fprintf(w, "\n%d fixture files\n", r.Files)
	return err
}

// WriteJSON prints the report as JSON.
func WriteJSON(w io.Writer, r Report) error {
	enc := json.NewEncoder(w)
	enc.SetIndent("", "  ")
	return enc.Encode(r)
}
