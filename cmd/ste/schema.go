package main

import (
	"encoding/json"
	"io"

	"github.com/TudorAndrei/ste-cli/internal/checker/rules"
	"github.com/TudorAndrei/ste-cli/internal/report"
)

// runSchema prints the interface of this tool as JSON. An agent reads it in
// place of the documentation, thus it never has to guess a rule identifier,
// a config key, a field name, or an exit code.
func runSchema(args []string, stdout, stderr io.Writer) int {
	enc := json.NewEncoder(stdout)
	enc.SetIndent("", "  ")
	if err := enc.Encode(schema()); err != nil {
		return exitError
	}
	return exitOK
}

type ruleDoc struct {
	ID              string    `json:"id"`
	Name            string    `json:"name"`
	Standard        string    `json:"standard_rule"`
	DefaultSeverity string    `json:"default_severity"`
	Confidence      []float64 `json:"confidence"`
	Note            string    `json:"note,omitempty"`
}

func schema() map[string]any {
	return map[string]any{
		"tool":           "ste",
		"version":        Version,
		"schema_version": 1,
		"description":    "A deterministic ASD-STE100 checker for Markdown and plain text.",
		"standard":       "ASD-STE100 Issue 9",

		"exit_codes": map[string]any{
			"0": "The tool ran. Findings alone do not change this code.",
			"1": "A gate failed: --fail-on-new, --warnings-as-errors, or --fail-over.",
			"2": "A flag, a file, or the config has an error.",
		},

		"commands": map[string]any{
			"lint":     "Check files, directories, or standard input.",
			"baseline": "Accept the findings of today, and report only the new ones after that.",
			"dict":     "Make a local index of the ASD-STE100 dictionary from your own copy.",
			"eval":     "Measure the rules against a labeled corpus.",
			"analyzer": "Show the analyzer of the grammar and what it needs.",
			"schema":   "Print this document.",
			"version":  "Print the version.",
		},

		"lint_flags": map[string]any{
			"--format":             map[string]any{"type": "string", "values": report.Formats(), "default": "text"},
			"--limit":              map[string]any{"type": "integer", "default": 0, "note": "0 gives every finding"},
			"--fields":             map[string]any{"type": "string", "values": report.Fields(), "note": "separated by a comma"},
			"--summary":            map[string]any{"type": "boolean", "note": "give only the summary"},
			"--mode":               map[string]any{"type": "string", "values": []string{"flavored", "strict"}, "default": "flavored"},
			"--max-words":          map[string]any{"type": "integer", "note": "replaces the limit of the standard"},
			"--config":             map[string]any{"type": "path"},
			"--no-config":          map[string]any{"type": "boolean"},
			"--baseline":           map[string]any{"type": "path"},
			"--no-baseline":        map[string]any{"type": "boolean"},
			"--fail-on-new":        map[string]any{"type": "boolean", "note": "exit 1 when a finding is not in the baseline"},
			"--warnings-as-errors": map[string]any{"type": "boolean", "note": "exit 1 when a warning exists; info stays advice"},
			"--fail-over":          map[string]any{"type": "number", "note": "exit 1 when the score for each 100 words is higher"},
			"--use-dict":           map[string]any{"type": "boolean", "note": "use the imported dictionary for STE-1.1"},
			"--dict":               map[string]any{"type": "path"},
			"--all":                map[string]any{"type": "boolean", "note": "read every file, including the files that git ignores"},
			"--dry-run":            map[string]any{"type": "boolean", "note": "for the baseline command: show the plan and write nothing"},
			"--preset":             map[string]any{"type": "string", "values": []string{"software"}, "note": "add the technical nouns of a subject field"},
			"--analyze":            map[string]any{"type": "boolean", "note": "use the analyzer of the grammar; it makes rule 3.6 more exact. Run \"ste analyzer\" to see what it needs."},
			"--analyzer":           map[string]any{"type": "string", "note": "command of a different analyzer"},
		},

		"config_keys": map[string]any{
			"mode":               map[string]any{"type": "string", "values": []string{"flavored", "strict"}},
			"rules":              map[string]any{"type": "map", "values": []string{"off", "info", "warning", "error"}},
			"exclude":            map[string]any{"type": "list of path patterns"},
			"allow.nouns":        map[string]any{"type": "list of strings"},
			"allow.verbs":        map[string]any{"type": "list of strings"},
			"prefer":             map[string]any{"type": "map", "note": "the key is the name to use, and the list holds the other names of the same item. Rule STE-1.11 reads it."},
			"min_confidence":     map[string]any{"type": "number", "range": []float64{0, 1}},
			"max_words":          map[string]any{"type": "integer"},
			"baseline":           map[string]any{"type": "path"},
			"fail_over":          map[string]any{"type": "number"},
			"warnings_as_errors": map[string]any{"type": "boolean"},
			"dictionary":         map[string]any{"type": "boolean"},
			"disable_rules":      map[string]any{"type": "list of rule identifiers"},
			"presets":            map[string]any{"type": "list", "values": []string{"software"}},
			"analyzer":           map[string]any{"type": "boolean", "note": "start the analyzer of the grammar for each run"},
		},
		"config_files": []string{".ste.yml", ".ste.yaml", "glossary.yml", "docs/glossary.yml"},

		"severities": []string{"off", "info", "warning", "error"},
		"rules":      ruleCatalog(),

		"suppression": map[string]any{
			"syntax": []string{
				"<!-- ste-disable -->",
				"<!-- ste-disable STE-3.6 -->",
				"<!-- ste-enable STE-3.6 -->",
				"<!-- ste-disable-next-line -->",
				"<!-- ste-disable-line -->",
			},
			"note": "A directive with no rule identifier applies to every rule.",
		},

		"output": map[string]any{
			"finding_fields": report.Fields(),
			"summary_fields": []string{"files", "words", "findings", "score", "shown", "truncated", "accepted", "errors"},
			"note":           "json gives one object with a flat findings list. ndjson gives one object for each line, each with a type of finding or summary.",
		},

		"agent_notes": []string{
			"The output can be large: a repository of 180 files gave 4 MB of JSON with the dictionary. Give --limit, --fields, or --summary first.",
			"Findings alone never change the exit code. Ask for a gate when you want one.",
			"A rule identifier is stable. Read it from this document, and not from the text of a message.",
			"The dictionary is off by default, because it reports about 1 word in 10 of general software documentation.",
		},
	}
}

// ruleCatalog gives each rule with its number in the standard.
func ruleCatalog() []ruleDoc {
	return []ruleDoc{
		{rules.RuleUnapprovedTerm, "Unapproved word or word group", "1.1", "warning", []float64{0.9, 0.95, 0.6}, "0.95 and 0.6 come from the dictionary. 0.6 means that the dictionary has the word only as a verb, and the tool has no part-of-speech tagger."},
		{rules.RuleSpelling, "British spelling", "1.14", "warning", []float64{0.9}, "A capitalized word that does not start a sentence is a name, thus the rule does not report it."},
		{rules.RulePerfectTense, "Complex verb construction", "3.4", "warning", []float64{0.9, 0.55}, ""},
		{rules.RuleProgressive, "Progressive -ing form", "3.5", "warning", []float64{0.9}, ""},
		{rules.RulePassiveVoice, "Passive voice", "3.6", "warning", []float64{0.95, 0.85, 0.7}, "0.95 with a by-agent, 0.85 for an irregular participle, 0.7 for a participle that ends with ed."},
		{rules.RuleNominalization, "A noun for an action", "3.7", "warning", []float64{0.9}, ""},
		{rules.RuleContraction, "Contraction", "4.2", "warning", []float64{0.98}, "The tool checks only the contraction part of rule 4.2."},
		{rules.RuleSentenceLength, "Sentence too long", "5.1", "warning", []float64{0.9}, "20 words for a numbered step, and 25 for other text."},
		{rules.RuleSemicolon, "Semicolon", "8.1", "warning", []float64{1.0}, ""},
		{rules.RulePhrasalVerb, "Phrasal verb", "9.3", "warning", []float64{0.85}, ""},
		{rules.RuleLatinAbbreviation, "Latin abbreviation", "GR-6", "info", []float64{0.9}, "A general recommendation is advice and not a rule, thus no mode and no flag makes it an error."},
		{rules.RuleVerticalList, "A list with two constructions", "4.3", "info", []float64{0.8}, "The rule reports a list that starts some items with a capital letter and other items with a small letter."},
		{rules.RuleNoteInstruction, "An instruction in a note", "5.5", "warning", []float64{0.8}, ""},
		{rules.RuleParagraphLength, "Paragraph too long", "6.6", "warning", []float64{1.0}, "6 sentences maximum."},
		{rules.RuleSafetyExplanation, "A safety instruction with no explanation", "7.3", "warning", []float64{0.7}, "The rule reads a warning, a caution, and a danger block."},
		{rules.RuleConditionOrder, "A condition after the command", "5.4", "info", []float64{0.7}, "The rule reads a numbered step only. A condition that follows an infinitive belongs to the infinitive, and the rule does not report it."},
		{rules.RuleOneName, "Two names for the same item", "1.11", "warning", []float64{0.95}, "The rule reports nothing until the prefer key of the config gives the names. No tool can know that two nouns mean the same item."},
		{rules.RuleImperative, "An instruction that is not a command", "5.3", "warning", []float64{0.75}, "The rule needs the analyzer. It reads a numbered step, and it steps over a condition clause."},
		{rules.RuleNounCluster, "A noun of more than three words", "2.1", "warning", []float64{0.8}, "The rule needs the analyzer. A name of many words is one unit by rule 8.6, thus the rule does not report it."},
	}
}
