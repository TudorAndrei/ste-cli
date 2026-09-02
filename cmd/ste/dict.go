package main

import (
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
  --out    Path of the index
`

func runDict(args []string, stdout, stderr io.Writer) int {
	fs := pflag.NewFlagSet("dict", pflag.ContinueOnError)
	fs.SetOutput(stderr)
	out := fs.String("out", "", "path of the index")
	if err := fs.Parse(args); err != nil {
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
		return dictImport(fs.Arg(1), path, stdout, stderr)
	case "info":
		return dictInfo(path, stdout, stderr)
	case "path":
		fmt.Fprintln(stdout, path)
		return exitOK
	case "remove":
		if err := os.Remove(path); err != nil && !os.IsNotExist(err) {
			fmt.Fprintf(stderr, "ste: %v\n", err)
			return exitError
		}
		fmt.Fprintf(stdout, "The index is removed. The term rule now uses only its hand-written list.\n")
		return exitOK
	default:
		fmt.Fprint(stderr, dictUsage)
		return exitError
	}
}

func dictImport(source, path string, stdout, stderr io.Writer) int {
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
	if err := index.Save(path); err != nil {
		fmt.Fprintf(stderr, "ste: %v\n", err)
		return exitError
	}
	s := index.Stats()
	fmt.Fprintf(stdout, "%s holds %d words: %d approved and %d not approved, with %d alternatives.\n",
		path, s.Words, s.Approved, s.Unapproved, s.Alternatives)
	fmt.Fprintf(stdout, "\nThe index is for you only: do not commit it.\n")
	fmt.Fprintf(stdout, "The dictionary is off by default. Give --use-dict, or put \"dictionary: true\"\nin your config, to make rule STE-1.1 use it.\n")
	fmt.Fprintf(stdout, "\nASD-STE100 approves about %d words for aircraft maintenance. On general\nsoftware documentation, the rule reports about 1 word in 10. Start\nwith \"ste baseline .\", or with \"min_confidence: 0.7\" to remove the findings\nthat need a part of speech.\n", s.Approved)
	return exitOK
}

func dictInfo(path string, stdout, stderr io.Writer) int {
	index, err := dict.Load(path)
	if err != nil {
		fmt.Fprintf(stderr, "ste: %v\n", err)
		return exitError
	}
	if index == nil {
		fmt.Fprintf(stdout, "There is no index at %s.\n", path)
		fmt.Fprintf(stdout, "Rule STE-1.1 uses its hand-written list of 27 words and 11 word groups.\n")
		fmt.Fprintf(stdout, "Run \"ste dict import <file>\" to make the index.\n")
		return exitOK
	}
	s := index.Stats()
	fmt.Fprintf(stdout, "index:        %s\n", path)
	fmt.Fprintf(stdout, "source:       %s\n", index.Source)
	fmt.Fprintf(stdout, "words:        %d\n", s.Words)
	fmt.Fprintf(stdout, "approved:     %d\n", s.Approved)
	fmt.Fprintf(stdout, "not approved: %d\n", s.Unapproved)
	fmt.Fprintf(stdout, "alternatives: %d\n", s.Alternatives)
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
