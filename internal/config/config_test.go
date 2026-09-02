package config_test

import (
	"os"
	"path/filepath"
	"testing"

	"github.com/TudorAndrei/ste-cli/internal/checker"
	"github.com/TudorAndrei/ste-cli/internal/config"
)

const sample = `# Project glossary
mode: flavored
allow:
  nouns: [parser, webhook]
  verbs:
    - provision
    - leverage
disable_rules: []
`

func TestParse(t *testing.T) {
	cfg, err := config.Parse(sample)
	if err != nil {
		t.Fatalf("parse: %v", err)
	}
	if cfg.Mode != "flavored" {
		t.Errorf("mode %q, want %q", cfg.Mode, "flavored")
	}
	if len(cfg.AllowNouns) != 2 || cfg.AllowNouns[0] != "parser" || cfg.AllowNouns[1] != "webhook" {
		t.Errorf("nouns %v", cfg.AllowNouns)
	}
	if len(cfg.AllowVerbs) != 2 || cfg.AllowVerbs[0] != "provision" || cfg.AllowVerbs[1] != "leverage" {
		t.Errorf("verbs %v", cfg.AllowVerbs)
	}
	if len(cfg.DisableRules) != 0 {
		t.Errorf("disable_rules %v", cfg.DisableRules)
	}
}

func TestParseStrictMode(t *testing.T) {
	cfg, err := config.Parse("mode: strict\nmax_words: 18\n")
	if err != nil {
		t.Fatalf("parse: %v", err)
	}
	opts := cfg.Options()
	if opts.Mode != checker.ModeStrict {
		t.Errorf("mode %q, want strict", opts.Mode)
	}
	if opts.MaxWords != 18 {
		t.Errorf("max_words %d, want 18", opts.MaxWords)
	}
}

func TestParseRejectsBadInput(t *testing.T) {
	cases := map[string]string{
		"unknown key":  "modes: strict\n",
		"bad mode":     "mode: pedantic\n",
		"bad number":   "max_words: many\n",
		"not a key":    "just text\n",
		"orphan item":  "- parser\n",
		"missing list": "mode:\n",
	}
	for name, text := range cases {
		t.Run(name, func(t *testing.T) {
			if _, err := config.Parse(text); err == nil {
				t.Fatalf("the parser accepted %q", text)
			}
		})
	}
}

func TestCommentsAndQuotes(t *testing.T) {
	cfg, err := config.Parse("mode: \"strict\" # the mode\nallow:\n  nouns: ['web#hook']\n")
	if err != nil {
		t.Fatalf("parse: %v", err)
	}
	if cfg.Mode != "strict" {
		t.Errorf("mode %q", cfg.Mode)
	}
	if len(cfg.AllowNouns) != 1 || cfg.AllowNouns[0] != "web#hook" {
		t.Errorf("nouns %v", cfg.AllowNouns)
	}
}

func TestGlossaryStopsATermFinding(t *testing.T) {
	cfg, err := config.Parse("allow:\n  verbs: [provision, leverage]\n")
	if err != nil {
		t.Fatalf("parse: %v", err)
	}
	text := "Leverage the parser."
	if got := checker.Lint(text, checker.Options{}); len(got) != 1 {
		t.Fatalf("without the glossary: got %d findings, want 1", len(got))
	}
	if got := checker.Lint(text, cfg.Options()); len(got) != 0 {
		t.Fatalf("with the glossary: got %d findings, want 0: %+v", len(got), got)
	}
}

// The reader is now a full YAML reader, thus a file can use the parts of
// YAML that the first hand-written reader did not accept.
func TestFullYAMLSyntax(t *testing.T) {
	const text = `
mode: strict
allow:
  nouns: &shared
    - parser
    - webhook
  verbs: *shared
disable_rules: [
  "STE-1.1",
  'STE-8.1',
]
`
	cfg, err := config.Parse(text)
	if err != nil {
		t.Fatalf("parse: %v", err)
	}
	if cfg.Mode != "strict" {
		t.Errorf("mode %q", cfg.Mode)
	}
	if len(cfg.AllowNouns) != 2 || len(cfg.AllowVerbs) != 2 {
		t.Errorf("the anchor did not work: nouns %v verbs %v", cfg.AllowNouns, cfg.AllowVerbs)
	}
	if len(cfg.DisableRules) != 2 || cfg.DisableRules[0] != "STE-1.1" {
		t.Errorf("disable_rules %v", cfg.DisableRules)
	}
}

func TestEmptyFileIsValid(t *testing.T) {
	cfg, err := config.Parse("# only a comment\n")
	if err != nil {
		t.Fatalf("parse: %v", err)
	}
	if cfg.Mode != "" || cfg.MaxWords != 0 {
		t.Errorf("config %+v, want the defaults", cfg)
	}
}

func TestLoadAndFind(t *testing.T) {
	dir := t.TempDir()
	path := filepath.Join(dir, ".ste.yml")
	if err := os.WriteFile(path, []byte(sample), 0o644); err != nil {
		t.Fatalf("write: %v", err)
	}
	found, ok := config.Find(dir)
	if !ok || found != path {
		t.Fatalf("find gave %q, %v", found, ok)
	}
	cfg, err := config.Load(found)
	if err != nil {
		t.Fatalf("load: %v", err)
	}
	if len(cfg.AllowNouns) != 2 {
		t.Errorf("nouns %v", cfg.AllowNouns)
	}
	if _, ok := config.Find(t.TempDir()); ok {
		t.Error("find gave a file in an empty directory")
	}
}

func TestShippedGlossaryParses(t *testing.T) {
	cfg, err := config.Load(filepath.Join("..", "..", "docs", "glossary.yml"))
	if err != nil {
		t.Fatalf("load docs/glossary.yml: %v", err)
	}
	if cfg.Mode == "" {
		t.Error("docs/glossary.yml gives no mode")
	}
}
