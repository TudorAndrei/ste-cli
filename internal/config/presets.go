package config

import "sort"

// A preset is a list of technical nouns for one subject field.
//
// ASD-STE100 is a language for the maintenance of an aircraft, thus its
// dictionary does not approve "hook", "file", or "build". Rule 1.5 of the
// standard gives 22 categories of technical noun, and category 19 is
// "Computer science, information and communication technology". A writer of
// software documentation is thus permitted to use the technical nouns of
// that field, and this preset is that list.
//
// A person wrote this list for this project. It is not a list from the
// specification.
var presets = map[string][]string{
	"software": softwareNouns,
}

// Presets gives the names of the presets.
func Presets() []string {
	names := make([]string, 0, len(presets))
	for name := range presets {
		names = append(names, name)
	}
	sort.Strings(names)
	return names
}

// Preset gives the nouns of one preset.
func Preset(name string) ([]string, bool) {
	nouns, ok := presets[name]
	return nouns, ok
}

// softwareNouns are the technical nouns of software and of information
// technology. Each one is a thing that a writer of software documentation
// names, and the dictionary of ASD-STE100 does not have it or does not
// approve it.
var softwareNouns = []string{
	// Files and source control
	"backup", "branch", "changelog", "commit", "diff", "directory", "file",
	"folder", "merge", "patch", "path", "rebase", "repository", "snapshot",
	"tag", "version", "worktree",
	// The program and its parts
	"binary", "build", "class", "compiler", "component", "constant",
	"dependency", "function", "interface", "library", "linter", "method",
	"module", "package", "parser", "plugin", "pointer", "runtime", "script",
	"struct", "variable",
	// Data
	"array", "boolean", "buffer", "cache", "column", "database", "field",
	"graph", "hash", "index", "integer", "list", "map", "node", "payload",
	"query", "record", "row", "schema", "stack", "string", "table",
	"template", "transaction", "tree", "value",
	// The system
	"cluster", "container", "daemon", "disk", "environment", "host",
	"image", "instance", "memory", "namespace", "node", "partition",
	"process", "server", "service", "socket", "storage", "thread", "volume",
	// The network
	"address", "api", "client", "cookie", "domain", "endpoint", "gateway",
	"header", "packet", "port", "protocol", "proxy", "request", "response",
	"route", "router", "session", "url", "webhook",
	// The work
	"artifact", "job", "pipeline", "queue", "release", "runner", "task",
	"workflow", "worker",
	// The interface
	"button", "cursor", "editor", "form", "icon", "keyboard", "layout",
	"menu", "panel", "prompt", "screen", "shell", "tab", "terminal",
	"widget", "window",
	// The command line
	"argument", "command", "flag", "input", "option", "output", "pipe",
	"stream", "subcommand",
	// Safety and identity
	"account", "certificate", "credential", "permission", "profile", "role",
	"secret", "token", "user",
	// The work of a writer and of a tester
	"coverage", "fixture", "issue", "log", "metric", "mock", "review",
	"test", "trace",
	// The words that a tool of this field uses
	"config", "hook", "state", "link", "search", "watch", "run", "sandbox",
	"lint", "format", "parse", "deploy",
}
