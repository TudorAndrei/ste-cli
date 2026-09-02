// Package config reads the project glossary. The file gives the mode, the
// project terms, and the disabled rules.
package config

import (
	"fmt"
	"os"
	"path/filepath"
	"strings"

	"github.com/goccy/go-yaml"

	"github.com/TudorAndrei/ste-cli/internal/checker/rules"
)

// DefaultNames are the file names that Find looks for, in order.
var DefaultNames = []string{".ste.yml", ".ste.yaml", "glossary.yml", "docs/glossary.yml"}

// file is the shape of the glossary file. A pointer for Mode separates "the
// key is not in the file" from "the key has no value".
type file struct {
	Mode     *string `yaml:"mode"`
	MaxWords *int    `yaml:"max_words"`
	Allow    struct {
		Nouns []string `yaml:"nouns"`
		Verbs []string `yaml:"verbs"`
	} `yaml:"allow"`
	DisableRules     []string          `yaml:"disable_rules"`
	Rules            map[string]string `yaml:"rules"`
	Exclude          []string          `yaml:"exclude"`
	MinConfidence    *float64          `yaml:"min_confidence"`
	FailOver         *float64          `yaml:"fail_over"`
	WarningsAsErrors *bool             `yaml:"warnings_as_errors"`
	Baseline         *string           `yaml:"baseline"`
}

// Config is the content of the config file.
type Config struct {
	Mode         string
	MaxWords     int
	AllowNouns   []string
	AllowVerbs   []string
	DisableRules []string
	// Rules gives a severity to one rule: "off", "info", "warning", or
	// "error". A project uses it to accept a rule slowly.
	Rules map[string]rules.Severity
	// Exclude holds the path patterns that the tool does not read.
	Exclude []string
	// MinConfidence removes each finding below this value.
	MinConfidence float64
	// FailOver gives the score that makes the command exit with code 1. A
	// negative value never fails.
	FailOver float64
	// Baseline is the path of the file of accepted findings.
	Baseline string
	// WarningsAsErrors makes each warning an error, and the command then
	// exits with code 1.
	WarningsAsErrors bool
}

// Options makes the checker options from the config.
func (c Config) Options() rules.Options {
	opts := rules.Options{
		MaxWords:         c.MaxWords,
		AllowNouns:       c.AllowNouns,
		AllowVerbs:       c.AllowVerbs,
		DisableRules:     c.DisableRules,
		RuleSeverity:     c.Rules,
		MinConfidence:    c.MinConfidence,
		WarningsAsErrors: c.WarningsAsErrors,
	}
	if c.Mode != "" {
		opts.Mode = rules.Mode(c.Mode)
	}
	return opts
}

// Find looks for a glossary file in dir. It returns the path and true when it
// finds one.
func Find(dir string) (string, bool) {
	for _, name := range DefaultNames {
		path := filepath.Join(dir, name)
		if info, err := os.Stat(path); err == nil && !info.IsDir() {
			return path, true
		}
	}
	return "", false
}

// Load reads and parses a glossary file.
func Load(path string) (Config, error) {
	raw, err := os.ReadFile(path)
	if err != nil {
		return Config{}, err
	}
	cfg, err := Parse(string(raw))
	if err != nil {
		return Config{}, fmt.Errorf("%s: %w", path, err)
	}
	return cfg, nil
}

// Parse reads the glossary from text. An unknown key is an error, thus a
// spelling mistake in the file does not stay hidden.
func Parse(text string) (Config, error) {
	var f file
	keys := map[string]any{}
	if strings.TrimSpace(text) != "" {
		if err := yaml.UnmarshalWithOptions([]byte(text), &f, yaml.DisallowUnknownField()); err != nil {
			return Config{}, cleanError(err)
		}
		// A key with no value gives a null, which the struct cannot
		// separate from a key that is not in the file.
		if err := yaml.Unmarshal([]byte(text), &keys); err != nil {
			return Config{}, cleanError(err)
		}
	}
	for name, target := range map[string]bool{"mode": f.Mode == nil, "max_words": f.MaxWords == nil} {
		if _, present := keys[name]; present && target {
			return Config{}, fmt.Errorf("the key %q has no value", name)
		}
	}

	cfg := Config{
		AllowNouns:   f.Allow.Nouns,
		AllowVerbs:   f.Allow.Verbs,
		DisableRules: f.DisableRules,
		Exclude:      f.Exclude,
		FailOver:     -1,
	}
	if f.Baseline != nil {
		cfg.Baseline = *f.Baseline
	}
	if f.FailOver != nil {
		cfg.FailOver = *f.FailOver
	}
	if f.WarningsAsErrors != nil {
		cfg.WarningsAsErrors = *f.WarningsAsErrors
	}
	if f.MinConfidence != nil {
		if *f.MinConfidence < 0 || *f.MinConfidence > 1 {
			return Config{}, fmt.Errorf("min_confidence must be between 0 and 1")
		}
		cfg.MinConfidence = *f.MinConfidence
	}
	if len(f.Rules) > 0 {
		cfg.Rules = map[string]rules.Severity{}
		for id, severity := range f.Rules {
			switch rules.Severity(severity) {
			case rules.SeverityOff, rules.SeverityInfo, rules.SeverityWarning, rules.SeverityError:
				cfg.Rules[id] = rules.Severity(severity)
			default:
				return Config{}, fmt.Errorf("the severity %q of rule %q is not \"off\", \"info\", \"warning\", or \"error\"", severity, id)
			}
		}
	}
	if f.Mode != nil {
		mode := *f.Mode
		if mode != string(rules.ModeFlavored) && mode != string(rules.ModeStrict) {
			return Config{}, fmt.Errorf("the mode %q is not \"flavored\" or \"strict\"", mode)
		}
		cfg.Mode = mode
	}
	if f.MaxWords != nil {
		if *f.MaxWords <= 0 {
			return Config{}, fmt.Errorf("max_words must be a positive number")
		}
		cfg.MaxWords = *f.MaxWords
	}
	return cfg, nil
}

// cleanError keeps the message of the YAML reader on one line, because the
// reader adds the source text below its message.
func cleanError(err error) error {
	msg := err.Error()
	if i := strings.IndexByte(msg, '\n'); i > 0 {
		msg = msg[:i]
	}
	return fmt.Errorf("%s", strings.TrimSpace(msg))
}
