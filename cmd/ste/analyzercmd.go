package main

import (
	"encoding/json"
	"fmt"
	"io"

	"github.com/spf13/pflag"

	"github.com/TudorAndrei/ste-cli/internal/analyzer"
)

// runAnalyzer tells the user if the analyzer can run, and what to install
// when it cannot. The tool holds the analyzer in the binary, thus the user
// needs no file from the repository.
func runAnalyzer(args []string, stdout, stderr io.Writer) int {
	fs := pflag.NewFlagSet("analyzer", pflag.ContinueOnError)
	fs.SetOutput(stderr)
	format := fs.String("format", "text", "text or json")
	if err := fs.Parse(args); err != nil {
		fmt.Fprintf(stderr, "ste: %v\n", err)
		return exitError
	}

	s := analyzer.Check()
	if *format == "json" {
		enc := json.NewEncoder(stdout)
		enc.SetIndent("", "  ")
		_ = enc.Encode(map[string]any{
			"ready":   s.Ready(),
			"python":  s.Python,
			"script":  s.Script,
			"spacy":   s.SpaCy,
			"problem": s.Problem,
			"fix":     s.Fix,
		})
		if s.Ready() {
			return exitOK
		}
		return exitOK
	}

	if s.Ready() {
		fmt.Fprintf(stdout, "The analyzer is ready.\n")
		fmt.Fprintf(stdout, "  python: %s\n", s.Python)
		fmt.Fprintf(stdout, "  script: %s\n", s.Script)
		fmt.Fprintf(stdout, "\nRun \"ste lint --analyze docs/\" to use it.\n")
		fmt.Fprintf(stdout, "It makes rule STE-3.6 more exact, and it is never necessary.\n")
		return exitOK
	}

	fmt.Fprintf(stdout, "The analyzer cannot run: %s\n", s.Problem)
	if len(s.Fix) > 0 {
		fmt.Fprintf(stdout, "\nTo make it work:\n")
		for _, fix := range s.Fix {
			fmt.Fprintf(stdout, "  %s\n", fix)
		}
	}
	fmt.Fprintf(stdout, "\nThe analyzer is optional. Each rule works without it.\n")
	return exitOK
}
