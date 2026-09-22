package main

import (
	"os"
	"path/filepath"
	"strings"

	"github.com/TudorAndrei/ste-cli/internal/config"
	"github.com/TudorAndrei/ste-cli/internal/report"
)

// project is the directory that the config applies to. A relative path in
// the config, a pattern of exclude, and the default baseline all start from
// it. Thus the result of a run does not change when you run the command
// from a subdirectory, or when you give an absolute path.
type project struct {
	// Dir is the absolute path of the project directory.
	Dir string
	// Config is the path of the config file, or "" when there is none.
	Config string
}

// findProject gives the project of the current directory.
//
// An explicit config file makes its own directory the project. Otherwise
// the search goes up from the current directory. It stops at the first
// directory that holds a config file, or at the top of the git work tree.
// With no config file and no git work tree, the current directory is the
// project.
func findProject(cfgPath string, noConfig bool) (project, error) {
	cwd, err := os.Getwd()
	if err != nil {
		return project{}, err
	}
	if cfgPath != "" && !noConfig {
		abs, err := filepath.Abs(cfgPath)
		if err != nil {
			return project{}, err
		}
		return project{Dir: filepath.Dir(abs), Config: cfgPath}, nil
	}
	for dir := cwd; ; {
		if !noConfig {
			if found, ok := config.Find(dir); ok {
				return project{Dir: dir, Config: found}, nil
			}
		}
		if _, err := os.Stat(filepath.Join(dir, ".git")); err == nil {
			return project{Dir: dir}, nil
		}
		parent := filepath.Dir(dir)
		if parent == dir {
			return project{Dir: cwd}, nil
		}
		dir = parent
	}
}

// resolve gives a path of the config as a path from the project directory.
// An absolute path does not change.
func (p project) resolve(path string) string {
	if path == "" || filepath.IsAbs(path) {
		return path
	}
	return filepath.Join(p.Dir, path)
}

// repoRoot gives the top of the git work tree that holds dir, or dir when
// there is no work tree.
func repoRoot(dir string) string {
	for d := dir; ; {
		if _, err := os.Stat(filepath.Join(d, ".git")); err == nil {
			return d
		}
		parent := filepath.Dir(d)
		if parent == d {
			return dir
		}
		d = parent
	}
}

// pathsFrom gives each file of the results as a path from dir. A file that
// is not below dir keeps its path.
func pathsFrom(dir string, results []report.FileResult) []report.FileResult {
	out := make([]report.FileResult, 0, len(results))
	for _, r := range results {
		if r.Path == stdinName {
			out = append(out, r)
			continue
		}
		rel := relativeTo(dir, r.Path)
		if strings.HasPrefix(rel, "../") || filepath.IsAbs(rel) {
			out = append(out, r)
			continue
		}
		findings := make([]report.Finding, len(r.Findings))
		for i, f := range r.Findings {
			f.File = rel
			findings[i] = f
		}
		r.Path, r.Findings = rel, findings
		out = append(out, r)
	}
	return out
}

// relativeTo gives path relative to dir, with forward slashes. A path that
// has no relative form stays absolute.
func relativeTo(dir, path string) string {
	abs, err := filepath.Abs(path)
	if err != nil {
		return filepath.ToSlash(filepath.Clean(path))
	}
	absDir, err := filepath.Abs(dir)
	if err != nil {
		return filepath.ToSlash(abs)
	}
	rel, err := filepath.Rel(absDir, abs)
	if err != nil {
		return filepath.ToSlash(abs)
	}
	return filepath.ToSlash(rel)
}
