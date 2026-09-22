package main

import (
	"fmt"
	"io"
	"os"

	"github.com/spf13/pflag"

	"github.com/TudorAndrei/ste-cli/internal/config"
)

// starterConfig is the config that "ste init" writes. Each key has the
// value that the tool uses without the key, thus the file changes nothing
// until a person edits it.
const starterConfig = `# The config of ste. Each key is optional. Run "ste schema" for all keys.

mode: flavored          # or strict: also report the low-confidence findings

rules: {}               # a severity for each rule: off, info, warning, or error
#  STE-3.6: info        # advice today, and a rule later

exclude: []             # path patterns from this directory
#  - "**/fixtures/**"

allow:                  # the technical words of this project (rule 1.6)
  nouns: []
  verbs: []

prefer: {}              # rule STE-1.11: one name for each item
#  "config file": ["settings file", "configuration file"]

presets: []             # software: the technical nouns of software

# min_confidence: 0.7   # remove each finding below this value
# fail_over: 2.5        # exit 1 when the score for each 100 words is higher
# warnings_as_errors: false
# baseline: .ste-baseline.json
`

func runInit(args []string, stdout, stderr io.Writer) int {
	fs := pflag.NewFlagSet("init", pflag.ContinueOnError)
	fs.SetOutput(stderr)
	format := fs.String("format", "text", "text or json")
	dryRun := fs.Bool("dry-run", false, "show the plan and write nothing")
	force := fs.Bool("force", false, "write the file also when a config exists")
	if err := fs.Parse(args); err != nil {
		fmt.Fprintf(stderr, "ste: %v\n", err)
		return exitError
	}
	if !validFormat(stderr, *format, "text", "json") || !noArgs(stderr, "init", fs.Args()) {
		return exitError
	}

	path := config.DefaultNames[0]
	existing, exists := config.Find(".")
	if exists && !*force {
		fmt.Fprintf(stderr, "ste: %s exists. Give --force to write %s all the same.\n", existing, path)
		return exitError
	}
	plan := map[string]any{"action": "init", "dry_run": *dryRun, "path": path, "exists": fileExists(path)}
	if *dryRun {
		return writeJSONOrText(stdout, *format, plan, fmt.Sprintf("A real run writes %s.\n", path))
	}
	if err := os.WriteFile(path, []byte(starterConfig), 0o644); err != nil {
		fmt.Fprintf(stderr, "ste: %v\n", err)
		return exitError
	}
	return writeJSONOrText(stdout, *format, plan,
		fmt.Sprintf("%s holds the start config. Run \"ste lint --summary .\" to see the size of the problem.\n", path))
}
