package report

import (
	"encoding/json"
	"fmt"
	"io"
	"path/filepath"
	"strings"

	"github.com/TudorAndrei/ste-cli/internal/checker"
)

// helpURI is the page that documents each rule.
const helpURI = "https://tudorandrei.github.io/ste-cli/rules.html"

// sarifLevel gives the SARIF level of a severity.
func sarifLevel(s checker.Severity) string {
	switch s {
	case checker.SeverityError:
		return "error"
	case checker.SeverityInfo:
		return "note"
	default:
		return "warning"
	}
}

// fileURI gives the URI of a file for SARIF. A relative path stays
// relative, thus a code host finds the file in its own copy of the
// repository.
func fileURI(path string) string {
	slash := filepath.ToSlash(path)
	if filepath.IsAbs(path) {
		if !strings.HasPrefix(slash, "/") {
			slash = "/" + slash
		}
		return "file://" + slash
	}
	return slash
}

// message gives the message of a finding with its suggestion.
func (f Finding) fullMessage() string {
	if f.Suggestion == "" {
		return f.Message
	}
	return f.Message + " " + f.Suggestion
}

// writeSARIF gives SARIF 2.1.0. GitHub code scanning and many editors read
// it.
func writeSARIF(w io.Writer, r Report, opts Options) error {
	findings, _ := r.limited(opts.Limit)
	if opts.SummaryOnly {
		findings = nil
	}

	rules := make([]map[string]any, 0, len(opts.Rules))
	index := map[string]int{}
	for _, rule := range opts.Rules {
		index[rule.ID] = len(rules)
		rules = append(rules, map[string]any{
			"id":                   rule.ID,
			"name":                 rule.Name,
			"shortDescription":     map[string]any{"text": rule.Name},
			"helpUri":              helpURI,
			"defaultConfiguration": map[string]any{"level": sarifLevel(checker.Severity(rule.DefaultSeverity))},
		})
	}

	results := make([]map[string]any, 0, len(findings))
	for _, f := range findings {
		result := map[string]any{
			"ruleId":  f.RuleID,
			"level":   sarifLevel(f.Severity),
			"message": map[string]any{"text": f.fullMessage()},
			"locations": []any{map[string]any{
				"physicalLocation": map[string]any{
					"artifactLocation": map[string]any{"uri": fileURI(f.File)},
					"region":           f.region,
				},
			}},
			"properties": map[string]any{"confidence": f.Confidence},
		}
		if i, ok := index[f.RuleID]; ok {
			result["ruleIndex"] = i
		}
		results = append(results, result)
	}

	driver := map[string]any{
		"name":           "ste",
		"informationUri": "https://tudorandrei.github.io/ste-cli/",
		"rules":          rules,
	}
	if opts.ToolVersion != "" {
		driver["version"] = opts.ToolVersion
	}
	out := map[string]any{
		"$schema": "https://json.schemastore.org/sarif-2.1.0.json",
		"version": "2.1.0",
		"runs": []any{map[string]any{
			"tool":       map[string]any{"driver": driver},
			"columnKind": "unicodeCodePoints",
			"results":    results,
		}},
	}
	enc := json.NewEncoder(w)
	enc.SetIndent("", "  ")
	return enc.Encode(out)
}

// githubLevel gives the workflow command of a severity.
func githubLevel(s checker.Severity) string {
	switch s {
	case checker.SeverityError:
		return "error"
	case checker.SeverityInfo:
		return "notice"
	default:
		return "warning"
	}
}

// escapeData escapes the message of a workflow command.
func escapeData(s string) string {
	return strings.NewReplacer("%", "%25", "\r", "%0D", "\n", "%0A").Replace(s)
}

// escapeProperty escapes a property of a workflow command.
func escapeProperty(s string) string {
	return strings.NewReplacer("%", "%25", "\r", "%0D", "\n", "%0A", ":", "%3A", ",", "%2C").Replace(s)
}

// writeGitHub gives one workflow command of GitHub Actions for each
// finding, and then the summary line of the text format.
func writeGitHub(w io.Writer, r Report, opts Options) error {
	findings, _ := r.limited(opts.Limit)
	if !opts.SummaryOnly {
		for _, f := range findings {
			if _, err := fmt.Fprintf(w, "::%s file=%s,line=%d,col=%d,endLine=%d,endColumn=%d,title=%s::%s\n",
				githubLevel(f.Severity), escapeProperty(filepath.ToSlash(f.File)),
				f.region.StartLine, f.region.StartColumn, f.region.EndLine, f.region.EndColumn,
				escapeProperty(f.RuleID), escapeData(f.fullMessage())); err != nil {
				return err
			}
		}
	}
	return WriteText(w, r, Options{SummaryOnly: true, Limit: opts.Limit})
}
