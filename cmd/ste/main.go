// Command ste finds high-confidence ASD-STE100 violations in Markdown and
// plain text.
package main

import (
	"errors"
	"flag"
	"fmt"
	"io"
	"os"
	"path/filepath"
	"sort"
	"strings"

	"github.com/TudorAndrei/ste-cli/internal/checker"
	"github.com/TudorAndrei/ste-cli/internal/config"
	"github.com/TudorAndrei/ste-cli/internal/eval"
	"github.com/TudorAndrei/ste-cli/internal/report"
)

// Version is the version of the tool. The release build replaces it with
// the tag name: go build -ldflags "-X main.Version=0.1.0".
var Version = "dev"

// Exit codes.
const (
	exitOK        = 0
	exitThreshold = 1
	exitError     = 2
)

const usage = `ste finds ASD-STE100 violations in Markdown and plain text.

Usage:
  ste lint [flags] [path ...]   Check files, directories, or standard input
  ste eval [flags] <dir>        Measure the rules against a labeled corpus
  ste version                   Print the version

Lint flags:
  --mode         "flavored" (default) or "strict"
  --format       "text" (default) or "json"
  --fail-over    Exit with code 1 when the score for each 100 words is
                 more than this value
  --max-words    Replace the sentence limit of the mode
  --config       Path of the glossary file. The default is the first of
                 .ste.yml, .ste.yaml, glossary.yml, or docs/glossary.yml in
                 the current directory.
  --no-config    Do not read a glossary file

Examples:
  ste lint README.md
  ste lint --mode strict --format json docs/
  ste lint --fail-over 2.5 draft.md
  cat draft.md | ste lint -
`

func main() {
	os.Exit(run(os.Args[1:], os.Stdin, os.Stdout, os.Stderr))
}

func run(args []string, stdin io.Reader, stdout, stderr io.Writer) int {
	if len(args) == 0 {
		fmt.Fprint(stderr, usage)
		return exitError
	}
	switch args[0] {
	case "lint":
		return runLint(args[1:], stdin, stdout, stderr)
	case "eval":
		return runEval(args[1:], stdout, stderr)
	case "version", "--version", "-v":
		fmt.Fprintf(stdout, "ste %s\n", Version)
		return exitOK
	case "help", "--help", "-h":
		fmt.Fprint(stdout, usage)
		return exitOK
	default:
		fmt.Fprintf(stderr, "ste: %q is not a command\n\n%s", args[0], usage)
		return exitError
	}
}

// The flags that take a value. reorder needs them to know if the next
// argument is a value or a path.
var (
	lintValueFlags = map[string]bool{
		"mode": true, "format": true, "fail-over": true,
		"max-words": true, "config": true,
	}
	evalValueFlags = map[string]bool{"format": true}
)

// reorder moves the flags in front of the paths. The flag package stops at
// the first argument that is not a flag, but "ste lint docs/ --format json"
// must also work.
func reorder(args []string, valueFlags map[string]bool) []string {
	flags := []string{}
	paths := []string{}
	for i := 0; i < len(args); i++ {
		arg := args[i]
		if arg == "--" {
			paths = append(paths, args[i+1:]...)
			break
		}
		if arg == "-" || !strings.HasPrefix(arg, "-") {
			paths = append(paths, arg)
			continue
		}
		flags = append(flags, arg)
		name := strings.TrimLeft(arg, "-")
		if strings.Contains(name, "=") {
			continue
		}
		if valueFlags[name] && i+1 < len(args) {
			i++
			flags = append(flags, args[i])
		}
	}
	return append(flags, paths...)
}

func runLint(args []string, stdin io.Reader, stdout, stderr io.Writer) int {
	fs := flag.NewFlagSet("lint", flag.ContinueOnError)
	fs.SetOutput(stderr)
	mode := fs.String("mode", "", "flavored or strict")
	format := fs.String("format", "text", "text or json")
	failOver := fs.Float64("fail-over", -1, "maximum score for each 100 words")
	maxWords := fs.Int("max-words", 0, "sentence limit in words")
	cfgPath := fs.String("config", "", "path of the glossary file")
	noConfig := fs.Bool("no-config", false, "do not read a glossary file")
	if err := fs.Parse(reorder(args, lintValueFlags)); err != nil {
		return exitError
	}
	if *format != "text" && *format != "json" {
		fmt.Fprintf(stderr, "ste: the format %q is not \"text\" or \"json\"\n", *format)
		return exitError
	}

	opts, err := options(*cfgPath, *noConfig, *mode, *maxWords)
	if err != nil {
		fmt.Fprintf(stderr, "ste: %v\n", err)
		return exitError
	}

	results := []report.FileResult{}
	paths := fs.Args()
	if len(paths) == 0 {
		paths = []string{"-"}
	}
	for _, p := range paths {
		if p == "-" {
			raw, err := io.ReadAll(stdin)
			if err != nil {
				fmt.Fprintf(stderr, "ste: standard input: %v\n", err)
				return exitError
			}
			results = append(results, lintOne("(standard input)", string(raw), opts))
			continue
		}
		files, err := textFiles(p)
		if err != nil {
			fmt.Fprintf(stderr, "ste: %v\n", err)
			return exitError
		}
		for _, f := range files {
			raw, err := os.ReadFile(f)
			if err != nil {
				fmt.Fprintf(stderr, "ste: %v\n", err)
				return exitError
			}
			results = append(results, lintOne(f, string(raw), opts))
		}
	}

	rep := report.New(string(opts.Normalized().Mode), results)
	if *format == "json" {
		err = report.WriteJSON(stdout, rep)
	} else {
		err = report.WriteText(stdout, rep)
	}
	if err != nil {
		fmt.Fprintf(stderr, "ste: %v\n", err)
		return exitError
	}
	if *failOver >= 0 && rep.Summary.Score > *failOver {
		fmt.Fprintf(stderr, "ste: the score %.2f is more than the limit %.2f\n", rep.Summary.Score, *failOver)
		return exitThreshold
	}
	return exitOK
}

func lintOne(path, source string, opts checker.Options) report.FileResult {
	doc := checker.Parse(source)
	diags := checker.LintDocument(doc, opts)
	out := report.FileResult{Path: path, Words: doc.WordCount(), Findings: []report.Finding{}}
	for _, d := range diags {
		out.Findings = append(out.Findings, report.MakeFinding(path, source, d))
	}
	return out
}

// options merges the glossary file and the command flags. A flag always wins.
func options(cfgPath string, noConfig bool, mode string, maxWords int) (checker.Options, error) {
	opts := checker.Options{}
	if !noConfig {
		path := cfgPath
		if path == "" {
			if found, ok := config.Find("."); ok {
				path = found
			}
		}
		if path != "" {
			cfg, err := config.Load(path)
			if err != nil {
				return opts, err
			}
			opts = cfg.Options()
		}
	}
	if mode != "" {
		if mode != string(checker.ModeFlavored) && mode != string(checker.ModeStrict) {
			return opts, fmt.Errorf("the mode %q is not \"flavored\" or \"strict\"", mode)
		}
		opts.Mode = checker.Mode(mode)
		// The mode default for the sentence limit must win over the
		// limit of the other mode.
		if maxWords == 0 {
			opts.MaxWords = 0
		}
	}
	if maxWords > 0 {
		opts.MaxWords = maxWords
	}
	return opts, nil
}

// skippedDirs are the directories that hold build output or dependencies.
// A walk does not go into them, because their text is not your prose. A
// directory that starts with "." is also skipped. To check one of these
// directories, give its path to the command.
var skippedDirs = map[string]bool{
	"node_modules": true,
	"vendor":       true,
	"dist":         true,
	"build":        true,
	"target":       true,
	"bin":          true,
	"obj":          true,
	"out":          true,
	"coverage":     true,
	"__pycache__":  true,
}

// textFiles gives the files to check. A directory gives all Markdown and
// text files below it.
func textFiles(path string) ([]string, error) {
	info, err := os.Stat(path)
	if err != nil {
		return nil, err
	}
	if !info.IsDir() {
		return []string{path}, nil
	}
	root := filepath.Clean(path)
	out := []string{}
	err = filepath.WalkDir(path, func(p string, d os.DirEntry, err error) error {
		if err != nil {
			return err
		}
		if d.IsDir() {
			// The directory that you give is always read. Only a
			// directory below it can be skipped.
			if filepath.Clean(p) == root {
				return nil
			}
			name := d.Name()
			if strings.HasPrefix(name, ".") || skippedDirs[name] {
				return filepath.SkipDir
			}
			return nil
		}
		switch filepath.Ext(p) {
		case ".md", ".markdown", ".txt":
			out = append(out, p)
		}
		return nil
	})
	if err != nil {
		return nil, err
	}
	sort.Strings(out)
	if len(out) == 0 {
		return nil, errors.New(path + ": the directory has no Markdown or text files")
	}
	return out, nil
}

func runEval(args []string, stdout, stderr io.Writer) int {
	fs := flag.NewFlagSet("eval", flag.ContinueOnError)
	fs.SetOutput(stderr)
	format := fs.String("format", "text", "text or json")
	if err := fs.Parse(reorder(args, evalValueFlags)); err != nil {
		return exitError
	}
	dir := "testdata"
	if fs.NArg() > 0 {
		dir = fs.Arg(0)
	}
	rep, err := eval.Run(dir)
	if err != nil {
		fmt.Fprintf(stderr, "ste: %v\n", err)
		return exitError
	}
	if *format == "json" {
		err = eval.WriteJSON(stdout, rep)
	} else {
		err = eval.WriteText(stdout, rep)
	}
	if err != nil {
		fmt.Fprintf(stderr, "ste: %v\n", err)
		return exitError
	}
	return exitOK
}
