package main

import (
	"encoding/json"
	"fmt"
	"io"
	"os"
	"path/filepath"
	"strings"

	"github.com/spf13/pflag"

	"github.com/TudorAndrei/ste-cli/internal/dict"
)

const dictUsage = `ste dict makes a local index of the ASD-STE100 dictionary.

This tool does not ship the dictionary. The specification is the property of
ASD, and its terms do not permit redistribution. ASD gives the specification
free of charge to each writer and user at https://asd-ste100.org, thus you
can make the index from your own copy.

One import is sufficient for each machine. The index is global: each
project reads it, and no run reads the specification again.

Usage:
  ste dict import <file>   Read the dictionary and write the index
  ste dict info            Show the index of this user
  ste dict path            Print the path of the index
  ste dict remove          Delete the index

The file must be the specification in Markdown or in plain text. To make
that file from the PDF:

  npx -y @firecrawl/anydoc ASD-STE100_ISSUE9.pdf -o ste100.md
  ste dict import ste100.md

The index goes in the data directory of the user:

  $STE_DICT                            an explicit path
  $XDG_DATA_HOME/ste/dictionary.json   when the variable is set
  ~/.local/share/ste/dictionary.json   Linux and BSD
  ~/Library/Application Support/...    macOS

Flags:
  --out       Path of the index
  --format    "text" (default) or "json"
  --dry-run   Show the plan and write nothing
`

func runDict(args []string, stdout, stderr io.Writer) int {
	fs := pflag.NewFlagSet("dict", pflag.ContinueOnError)
	fs.SetOutput(stderr)
	out := fs.String("out", "", "path of the index")
	format := fs.String("format", "text", "text or json")
	dryRun := fs.Bool("dry-run", false, "show the plan and write nothing")
	if err := fs.Parse(args); err != nil {
		fmt.Fprintf(stderr, "ste: %v\n", err)
		return exitError
	}
	path := *out
	if path == "" {
		path = dict.DefaultPath()
	}

	command := ""
	if fs.NArg() > 0 {
		command = fs.Arg(0)
	}
	switch command {
	case "import":
		if fs.NArg() < 2 {
			fmt.Fprint(stderr, dictUsage)
			return exitError
		}
		return dictImport(fs.Arg(1), path, *format, *dryRun, stdout, stderr)
	case "info":
		return dictInfo(path, *format, stdout, stderr)
	case "path":
		if *format == "json" {
			return writeJSONLine(stdout, map[string]any{"path": path})
		}
		fmt.Fprintln(stdout, path)
		return exitOK
	case "remove":
		exists := fileExists(path)
		if *dryRun {
			return writeJSONOrText(stdout, *format,
				map[string]any{"action": "dict remove", "dry_run": true, "path": path, "exists": exists},
				fmt.Sprintf("A real run deletes %s.\n", path))
		}
		if err := os.Remove(path); err != nil && !os.IsNotExist(err) {
			fmt.Fprintf(stderr, "ste: %v\n", err)
			return exitError
		}
		return writeJSONOrText(stdout, *format,
			map[string]any{"action": "dict remove", "dry_run": false, "path": path, "removed": exists},
			"The index is removed. The term rule now uses only its hand-written list.\n")
	default:
		fmt.Fprint(stderr, dictUsage)
		return exitError
	}
}

func dictImport(source, path, format string, dryRun bool, stdout, stderr io.Writer) int {
	if strings.EqualFold(filepath.Ext(source), ".pdf") {
		fmt.Fprintf(stderr, "ste: %s is a PDF. This tool reads text, thus make the Markdown first:\n", source)
		fmt.Fprintf(stderr, "  npx -y @firecrawl/anydoc %s -o ste100.md\n", source)
		fmt.Fprintf(stderr, "  ste dict import ste100.md\n")
		return exitError
	}
	raw, err := os.ReadFile(source)
	if err != nil {
		fmt.Fprintf(stderr, "ste: %v\n", err)
		return exitError
	}
	index, err := dict.Parse(string(raw), filepath.Base(source))
	if err != nil {
		fmt.Fprintf(stderr, "ste: %v\n", err)
		return exitError
	}
	s := index.Stats()
	if dryRun {
		return writeJSONOrText(stdout, format, map[string]any{
			"action": "dict import", "dry_run": true, "source": source, "path": path,
			"words": s.Words, "approved": s.Approved, "unapproved": s.Unapproved,
			"alternatives": s.Alternatives, "exists": fileExists(path),
		}, fmt.Sprintf("A real run writes %s with %d words.\n", path, s.Words))
	}
	if err := index.Save(path); err != nil {
		fmt.Fprintf(stderr, "ste: %v\n", err)
		return exitError
	}
	if format == "json" {
		return writeJSONLine(stdout, map[string]any{
			"action": "dict import", "dry_run": false, "source": source, "path": path,
			"words": s.Words, "approved": s.Approved, "unapproved": s.Unapproved,
			"alternatives": s.Alternatives,
		})
	}
	fmt.Fprintf(stdout, "%s holds %d words: %d approved and %d not approved, with %d alternatives.\n",
		path, s.Words, s.Approved, s.Unapproved, s.Alternatives)
	fmt.Fprintf(stdout, "\nThe index is for you only: do not commit it.\n")
	fmt.Fprintf(stdout, "The dictionary is off by default. Give --use-dict, or put \"dictionary: true\"\nin your config, to make rule STE-1.1 use it.\n")
	fmt.Fprintf(stdout, "\nASD-STE100 approves about %d words for aircraft maintenance. On general\nsoftware documentation, the rule reports about 1 word in 10. Start\nwith \"ste baseline .\", or with \"min_confidence: 0.7\" to remove the findings\nthat need a part of speech.\n", s.Approved)
	return exitOK
}

func dictInfo(path, format string, stdout, stderr io.Writer) int {
	index, err := dict.Load(path)
	if err != nil {
		fmt.Fprintf(stderr, "ste: %v\n", err)
		return exitError
	}
	if index == nil {
		if format == "json" {
			return writeJSONLine(stdout, map[string]any{"path": path, "present": false})
		}
		fmt.Fprintf(stdout, "There is no index at %s.\n", path)
		fmt.Fprintf(stdout, "Rule STE-1.1 uses its hand-written list of 27 words and 11 word groups.\n")
		fmt.Fprintf(stdout, "Run \"ste dict import <file>\" to make the index.\n")
		return exitOK
	}
	s := index.Stats()
	if format == "json" {
		return writeJSONLine(stdout, map[string]any{
			"path": path, "present": true, "source": index.Source,
			"words": s.Words, "approved": s.Approved, "unapproved": s.Unapproved,
			"alternatives": s.Alternatives,
		})
	}
	fmt.Fprintf(stdout, "index:        %s\n", path)
	fmt.Fprintf(stdout, "source:       %s\n", index.Source)
	fmt.Fprintf(stdout, "words:        %d\n", s.Words)
	fmt.Fprintf(stdout, "approved:     %d\n", s.Approved)
	fmt.Fprintf(stdout, "not approved: %d\n", s.Unapproved)
	fmt.Fprintf(stdout, "alternatives: %d\n", s.Alternatives)
	return exitOK
}

// writeJSONLine gives one JSON object.
func writeJSONLine(stdout io.Writer, data map[string]any) int {
	enc := json.NewEncoder(stdout)
	enc.SetIndent("", "  ")
	if err := enc.Encode(data); err != nil {
		return exitError
	}
	return exitOK
}

// writeJSONOrText gives JSON to an agent and a line to a person.
func writeJSONOrText(stdout io.Writer, format string, data map[string]any, text string) int {
	if format == "json" {
		return writeJSONLine(stdout, data)
	}
	fmt.Fprint(stdout, text)
	return exitOK
}

// loadDictionary gives the index of the user, or nil. An error in the index
// must not stop a lint run, thus the caller only shows a warning.
func loadDictionary(path string) (*dict.Index, error) {
	if path == "" {
		path = dict.DefaultPath()
	}
	return dict.Load(path)
}
