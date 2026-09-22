package main

import (
	"encoding/json"
	"os"
	"strings"
	"testing"

	"github.com/TudorAndrei/ste-cli/internal/config"
)

func TestTheStarterConfigIsValidAndChangesNothing(t *testing.T) {
	cfg, err := config.Parse(starterConfig)
	if err != nil {
		t.Fatalf("the start config does not parse: %v", err)
	}
	if cfg.Mode != "flavored" || len(cfg.Rules) != 0 || len(cfg.Exclude) != 0 || len(cfg.AllowNouns) != 0 {
		t.Errorf("the start config changes the defaults: %+v", cfg)
	}
}

func TestInit(t *testing.T) {
	t.Chdir(t.TempDir())

	code, stdout, stderr := runCLI(t, "", "init", "--dry-run", "--format", "json")
	if code != 0 {
		t.Fatalf("dry run: exit %d: %s", code, stderr)
	}
	var plan map[string]any
	if err := json.Unmarshal([]byte(stdout), &plan); err != nil {
		t.Fatalf("not JSON: %v", err)
	}
	if plan["dry_run"] != true || plan["path"] != ".ste.yml" {
		t.Errorf("plan %v", plan)
	}
	if _, err := os.Stat(".ste.yml"); !os.IsNotExist(err) {
		t.Fatal("--dry-run wrote the file")
	}

	if code, _, stderr := runCLI(t, "", "init"); code != 0 {
		t.Fatalf("exit %d: %s", code, stderr)
	}
	raw, err := os.ReadFile(".ste.yml")
	if err != nil || string(raw) != starterConfig {
		t.Fatalf("the file is not the start config: %v", err)
	}

	// A second run does not replace a config, and it names the file.
	if err := os.WriteFile(".ste.yml", []byte("mode: strict\n"), 0o644); err != nil {
		t.Fatal(err)
	}
	code, _, stderr = runCLI(t, "", "init")
	if code != 2 || !strings.Contains(stderr, ".ste.yml exists") {
		t.Fatalf("exit %d, stderr %q", code, stderr)
	}
	if raw, _ := os.ReadFile(".ste.yml"); string(raw) != "mode: strict\n" {
		t.Fatal("init replaced the config")
	}
	if code, _, _ := runCLI(t, "", "init", "--force"); code != 0 {
		t.Fatalf("--force: exit %d", code)
	}
}
