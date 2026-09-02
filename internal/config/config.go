// Package config reads the project glossary. The file gives the mode, the
// project terms, and the disabled rules.
//
// The reader accepts only the subset of YAML that the glossary needs:
// scalars, block lists ("- item"), inline lists ("[a, b]"), comments, and one
// level of nested keys. It is not a full YAML parser. This keeps the tool
// free of dependencies.
package config

import (
	"fmt"
	"os"
	"path/filepath"
	"strconv"
	"strings"

	"github.com/TudorAndrei/ste-cli/internal/checker/rules"
)

// DefaultNames are the file names that Find looks for, in order.
var DefaultNames = []string{".ste.yml", ".ste.yaml", "glossary.yml", "docs/glossary.yml"}

// Config is the content of the glossary file.
type Config struct {
	Mode         string
	MaxWords     int
	AllowNouns   []string
	AllowVerbs   []string
	DisableRules []string
}

// Options makes the checker options from the config.
func (c Config) Options() rules.Options {
	opts := rules.Options{
		MaxWords:     c.MaxWords,
		AllowNouns:   c.AllowNouns,
		AllowVerbs:   c.AllowVerbs,
		DisableRules: c.DisableRules,
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

// Parse reads the glossary from text.
func Parse(text string) (Config, error) {
	cfg := Config{}
	section := ""
	listKey := ""

	for n, line := range strings.Split(text, "\n") {
		lineNo := n + 1
		content := strings.TrimRight(stripComment(line), " \t\r")
		if strings.TrimSpace(content) == "" {
			continue
		}
		indented := content[0] == ' ' || content[0] == '\t'
		trimmed := strings.TrimSpace(content)

		if strings.HasPrefix(trimmed, "- ") || trimmed == "-" {
			if listKey == "" {
				return cfg, fmt.Errorf("line %d: a list item has no key", lineNo)
			}
			item := unquote(strings.TrimSpace(strings.TrimPrefix(trimmed, "-")))
			if item != "" {
				if err := appendList(&cfg, listKey, item, lineNo); err != nil {
					return cfg, err
				}
			}
			continue
		}

		key, value, ok := strings.Cut(trimmed, ":")
		if !ok {
			return cfg, fmt.Errorf("line %d: %q is not a key", lineNo, trimmed)
		}
		key = strings.TrimSpace(key)
		value = strings.TrimSpace(value)

		full := key
		if indented {
			if section == "" {
				return cfg, fmt.Errorf("line %d: the key %q has no parent", lineNo, key)
			}
			full = section + "." + key
		} else {
			section = key
		}

		if value == "" {
			listKey = full
			if !isListKey(full) && !isSectionKey(full) {
				return cfg, fmt.Errorf("line %d: the key %q needs a value", lineNo, full)
			}
			continue
		}
		listKey = ""
		if err := setValue(&cfg, full, value, lineNo); err != nil {
			return cfg, err
		}
	}
	return cfg, nil
}

func isSectionKey(key string) bool { return key == "allow" }

func isListKey(key string) bool {
	switch key {
	case "allow.nouns", "allow.verbs", "disable_rules":
		return true
	}
	return false
}

func setValue(cfg *Config, key, value string, lineNo int) error {
	if isListKey(key) {
		items, err := parseInlineList(value, lineNo)
		if err != nil {
			return err
		}
		for _, item := range items {
			if err := appendList(cfg, key, item, lineNo); err != nil {
				return err
			}
		}
		return nil
	}
	switch key {
	case "mode":
		mode := unquote(value)
		if mode != string(rules.ModeFlavored) && mode != string(rules.ModeStrict) {
			return fmt.Errorf("line %d: the mode %q is not \"flavored\" or \"strict\"", lineNo, mode)
		}
		cfg.Mode = mode
	case "max_words":
		n, err := strconv.Atoi(unquote(value))
		if err != nil || n <= 0 {
			return fmt.Errorf("line %d: max_words must be a positive number", lineNo)
		}
		cfg.MaxWords = n
	default:
		return fmt.Errorf("line %d: the key %q is not known", lineNo, key)
	}
	return nil
}

func appendList(cfg *Config, key, item string, lineNo int) error {
	switch key {
	case "allow.nouns":
		cfg.AllowNouns = append(cfg.AllowNouns, item)
	case "allow.verbs":
		cfg.AllowVerbs = append(cfg.AllowVerbs, item)
	case "disable_rules":
		cfg.DisableRules = append(cfg.DisableRules, item)
	default:
		return fmt.Errorf("line %d: the key %q does not take a list", lineNo, key)
	}
	return nil
}

func parseInlineList(value string, lineNo int) ([]string, error) {
	if !strings.HasPrefix(value, "[") {
		return nil, fmt.Errorf("line %d: %q must be a list, as in \"[a, b]\"", lineNo, value)
	}
	if !strings.HasSuffix(value, "]") {
		return nil, fmt.Errorf("line %d: the list has no \"]\"", lineNo)
	}
	inner := strings.TrimSpace(value[1 : len(value)-1])
	if inner == "" {
		return nil, nil
	}
	parts := strings.Split(inner, ",")
	items := make([]string, 0, len(parts))
	for _, p := range parts {
		item := unquote(strings.TrimSpace(p))
		if item != "" {
			items = append(items, item)
		}
	}
	return items, nil
}

// stripComment removes a "#" comment, but not a "#" inside quotation marks.
func stripComment(line string) string {
	inQuote := byte(0)
	for i := 0; i < len(line); i++ {
		c := line[i]
		switch {
		case inQuote != 0:
			if c == inQuote {
				inQuote = 0
			}
		case c == '"' || c == '\'':
			inQuote = c
		case c == '#':
			if i == 0 || line[i-1] == ' ' || line[i-1] == '\t' {
				return line[:i]
			}
		}
	}
	return line
}

func unquote(s string) string {
	if len(s) >= 2 {
		if (s[0] == '"' && s[len(s)-1] == '"') || (s[0] == '\'' && s[len(s)-1] == '\'') {
			return s[1 : len(s)-1]
		}
	}
	return s
}
