// Command ste finds high-confidence ASD-STE100 violations in Markdown and
// plain text.
package main

import (
	"errors"
	"fmt"
	"io"
	"os"
	"os/exec"
	"path/filepath"
	"sort"
	"strings"
	"time"

	"github.com/spf13/pflag"

	"github.com/TudorAndrei/ste-cli/internal/baseline"
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

The tool is an aid, and not a gate. It exits with code 0 even when it finds
something, until you ask for a gate with --fail-over or --fail-on-new.

Usage:
  ste lint [flags] [path ...]   Check files, directories, or standard input
  ste baseline [flags] [path]   Accept the findings of today, and report only
                                the new ones from now
  ste dict <command>            Make a local index of the ASD-STE100
                                dictionary from your own copy
  ste eval [flags] <dir>        Measure the rules against a labeled corpus
  ste version                   Print the version

Lint flags:
  --mode          "flavored" (default) or "strict"
  --format        "text" (default) or "json"
  --config        Path of the config file. The default is the first of
                  .ste.yml, .ste.yaml, glossary.yml, or docs/glossary.yml.
  --no-config     Do not read a config file
  --baseline      Path of the file of accepted findings
  --no-baseline   Report every finding, and not only the new ones
  --fail-on-new   Exit with code 1 when a finding is not in the baseline
  --warnings-as-errors
                  Make each warning an error, and exit with code 1. An info
                  finding stays advice.
  --fail-over     Exit with code 1 when the score for each 100 words is
                  more than this value
  --max-words     Replace the sentence limit
  --use-dict      Use the imported ASD-STE100 dictionary for rule STE-1.1
  --dict          Path of the dictionary index
  --all           Read every file, and not only the files that git shows

Examples:
  ste lint README.md
  ste baseline .                          # accept what exists today
  ste lint --fail-on-new docs/            # block only a new violation
  ste lint --mode strict --format json docs/
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
		return runLint(args[1:], stdin, stdout, stderr, false)
	case "baseline":
		return runLint(args[1:], stdin, stdout, stderr, true)
	case "dict":
		return runDict(args[1:], stdout, stderr)
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

func runLint(args []string, stdin io.Reader, stdout, stderr io.Writer, write bool) int {
	fs := pflag.NewFlagSet("lint", pflag.ContinueOnError)
	fs.SetOutput(stderr)
	mode := fs.String("mode", "", "flavored or strict")
	format := fs.String("format", "text", "text or json")
	failOver := fs.Float64("fail-over", -1, "maximum score for each 100 words")
	maxWords := fs.Int("max-words", 0, "sentence limit in words")
	cfgPath := fs.String("config", "", "path of the glossary file")
	noConfig := fs.Bool("no-config", false, "do not read a glossary file")
	all := fs.Bool("all", false, "read every file, and not only the files that git shows")
	baselinePath := fs.String("baseline", "", "path of the file of accepted findings")
	noBaseline := fs.Bool("no-baseline", false, "report every finding, and not only the new ones")
	failOnNew := fs.Bool("fail-on-new", false, "exit with code 1 when a finding is not in the baseline")
	warnAsError := fs.Bool("warnings-as-errors", false, "make each warning an error, and exit with code 1")
	dictPath := fs.String("dict", "", "path of the dictionary index")
	useDict := fs.Bool("use-dict", false, "use the imported ASD-STE100 dictionary for rule STE-1.1")
	if err := fs.Parse(args); err != nil {
		return exitError
	}
	if *format != "text" && *format != "json" {
		fmt.Fprintf(stderr, "ste: the format %q is not \"text\" or \"json\"\n", *format)
		return exitError
	}

	cfg, err := loadConfig(*cfgPath, *noConfig)
	if err != nil {
		fmt.Fprintf(stderr, "ste: %v\n", err)
		return exitError
	}
	opts, err := options(cfg, *mode, *maxWords)
	if err != nil {
		fmt.Fprintf(stderr, "ste: %v\n", err)
		return exitError
	}
	if *failOver < 0 {
		*failOver = cfg.FailOver
	}
	if *warnAsError {
		opts.WarningsAsErrors = true
	}
	// The dictionary is off by default. It approves about 900 words for
	// aircraft maintenance, thus it reports a large part of ordinary
	// software documentation.
	if *useDict || cfg.Dictionary {
		index, err := loadDictionary(*dictPath)
		if err != nil {
			fmt.Fprintf(stderr, "ste: %v\n", err)
			return exitError
		}
		if index == nil {
			fmt.Fprintf(stderr, "ste: there is no dictionary index. Run \"ste dict import <file>\" first.\n")
			return exitError
		}
		opts.Dictionary = index
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
		files, err := textFiles(p, *all, cfg.Exclude)
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

	// The baseline holds the findings that the project accepts today, thus
	// the report shows only the new ones.
	basePath := *baselinePath
	if basePath == "" {
		basePath = cfg.Baseline
	}
	if basePath == "" {
		if _, err := os.Stat(baseline.DefaultName); err == nil {
			basePath = baseline.DefaultName
		}
	}
	if write {
		if basePath == "" {
			basePath = baseline.DefaultName
		}
		if err := saveBaseline(basePath, results); err != nil {
			fmt.Fprintf(stderr, "ste: %v\n", err)
			return exitError
		}
		total := 0
		for _, r := range results {
			total += len(r.Findings)
		}
		fmt.Fprintf(stdout, "%s holds %d findings of %d files.\n", basePath, total, len(results))
		fmt.Fprintf(stdout, "The tool now reports only a new finding. Remove the file to report all.\n")
		return exitOK
	}

	accepted := 0
	if basePath != "" && !*noBaseline {
		set, err := baseline.Load(basePath)
		if err != nil {
			fmt.Fprintf(stderr, "ste: %v\n", err)
			return exitError
		}
		results, accepted = applyBaseline(set, results)
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
	if accepted > 0 && *format == "text" {
		fmt.Fprintf(stdout, "%d findings are in the baseline %s, thus this report does not show them.\n", accepted, basePath)
	}
	if errors := countErrors(rep); opts.WarningsAsErrors && errors > 0 {
		fmt.Fprintf(stderr, "ste: %d findings have the error severity\n", errors)
		return exitThreshold
	}
	if *failOnNew && rep.Summary.Findings > 0 {
		fmt.Fprintf(stderr, "ste: %d findings are not in the baseline\n", rep.Summary.Findings)
		return exitThreshold
	}
	if *failOver >= 0 && rep.Summary.Score > *failOver {
		fmt.Fprintf(stderr, "ste: the score %.2f is more than the limit %.2f\n", rep.Summary.Score, *failOver)
		return exitThreshold
	}
	return exitOK
}

// countErrors gives the number of findings with the error severity.
func countErrors(rep report.Report) int {
	n := 0
	for _, f := range rep.Files {
		for _, d := range f.Findings {
			if d.Severity == checker.SeverityError {
				n++
			}
		}
	}
	return n
}

// applyBaseline removes the findings that the project accepted before. It
// gives the new results and the number of accepted findings.
func applyBaseline(set *baseline.Set, results []report.FileResult) ([]report.FileResult, int) {
	accepted := 0
	out := make([]report.FileResult, 0, len(results))
	for _, r := range results {
		kept := make([]report.Finding, 0, len(r.Findings))
		for _, f := range r.Findings {
			if set.Take(r.Path, f.RuleID, f.Text) {
				accepted++
				continue
			}
			kept = append(kept, f)
		}
		r.Findings = kept
		out = append(out, r)
	}
	return out, accepted
}

// saveBaseline writes the findings of this run as the accepted findings.
func saveBaseline(path string, results []report.FileResult) error {
	entries := make([]baseline.Result, 0, len(results))
	for _, r := range results {
		findings := make([]baseline.Finding, 0, len(r.Findings))
		for _, f := range r.Findings {
			findings = append(findings, baseline.Finding{RuleID: f.RuleID, Text: f.Text})
		}
		entries = append(entries, baseline.Result{Path: r.Path, Findings: findings})
	}
	return baseline.Save(path, entries, time.Now().UTC().Format(time.RFC3339))
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

// loadConfig reads the config file, or gives an empty config.
func loadConfig(cfgPath string, noConfig bool) (config.Config, error) {
	cfg := config.Config{FailOver: -1}
	if noConfig {
		return cfg, nil
	}
	path := cfgPath
	if path == "" {
		found, ok := config.Find(".")
		if !ok {
			return cfg, nil
		}
		path = found
	}
	return config.Load(path)
}

// options merges the config file and the command flags. A flag always wins.
func options(cfg config.Config, mode string, maxWords int) (checker.Options, error) {
	opts := cfg.Options()
	if mode != "" {
		if mode != string(checker.ModeFlavored) && mode != string(checker.ModeStrict) {
			return opts, fmt.Errorf("the mode %q is not \"flavored\" or \"strict\"", mode)
		}
		opts.Mode = checker.Mode(mode)
	}
	if maxWords > 0 {
		opts.MaxWords = maxWords
	}
	return opts, nil
}

// gitVisible gives the files below dir that git does not ignore. It asks
// git, because git is the only correct reader of a .gitignore file: the
// syntax has negation, anchors, and one file for each directory.
//
// The result is nil when dir is not in a git work tree, or when git is not
// on the system. Then no filter applies.
func gitVisible(dir string) map[string]bool {
	if _, err := exec.LookPath("git"); err != nil {
		return nil
	}
	// --cached gives the tracked files, and --others gives the untracked
	// files. --exclude-standard removes the ignored files from --others.
	cmd := exec.Command("git", "-C", dir, "ls-files", "--cached", "--others", "--exclude-standard", "-z")
	out, err := cmd.Output()
	if err != nil {
		return nil
	}
	visible := map[string]bool{}
	for _, rel := range strings.Split(string(out), "\x00") {
		if rel == "" {
			continue
		}
		if abs, err := filepath.Abs(filepath.Join(dir, rel)); err == nil {
			visible[abs] = true
		}
	}
	return visible
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
// text files below it. A file that git ignores does not come from a
// directory, but a file that you give by its path is always read.
func textFiles(path string, all bool, exclude []string) ([]string, error) {
	info, err := os.Stat(path)
	if err != nil {
		return nil, err
	}
	if !info.IsDir() {
		return []string{path}, nil
	}
	root := filepath.Clean(path)
	var visible map[string]bool
	if !all {
		visible = gitVisible(path)
	}
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
			if !all && (strings.HasPrefix(name, ".") || skippedDirs[name]) {
				return filepath.SkipDir
			}
			return nil
		}
		switch filepath.Ext(p) {
		case ".md", ".markdown", ".txt":
		default:
			return nil
		}
		if visible != nil {
			abs, err := filepath.Abs(p)
			if err != nil || !visible[abs] {
				return nil
			}
		}
		if matchesAny(p, root, exclude) {
			return nil
		}
		out = append(out, p)
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
	fs := pflag.NewFlagSet("eval", pflag.ContinueOnError)
	fs.SetOutput(stderr)
	format := fs.String("format", "text", "text or json")
	if err := fs.Parse(args); err != nil {
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
