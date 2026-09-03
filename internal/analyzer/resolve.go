package analyzer

import (
	_ "embed"
	"errors"
	"fmt"
	"os"
	"os/exec"
	"path/filepath"

	"github.com/adrg/xdg"
)

// script is the analyzer. The binary holds it, thus a user needs no file
// from the repository and no path on the command line.
//
//go:embed ste_analyzer.py
var script string

// ScriptName is the file that the tool writes for the analyzer.
const ScriptName = "ste_analyzer.py"

// Status tells what the analyzer needs.
type Status struct {
	// Python is the interpreter that the tool found, or an empty string.
	Python string
	// Script is the path of the analyzer.
	Script string
	// SpaCy is true when the interpreter has spaCy and its model.
	SpaCy bool
	// Problem gives the reason that the analyzer cannot run.
	Problem string
	// Fix gives the commands that make the analyzer work.
	Fix []string
}

// Ready tells if the analyzer can run.
func (s Status) Ready() bool { return s.Python != "" && s.SpaCy }

// pythonNames are the interpreters to look for, in order. $STE_PYTHON
// replaces them.
var pythonNames = []string{"python3", "python"}

// FindPython gives the interpreter for the analyzer.
func FindPython() string {
	if p := os.Getenv("STE_PYTHON"); p != "" {
		return p
	}
	for _, name := range pythonNames {
		if path, err := exec.LookPath(name); err == nil {
			return path
		}
	}
	return ""
}

// ScriptPath writes the analyzer to the cache directory of the user and
// gives its path. The file is a cache: the binary can write it again.
func ScriptPath() (string, error) {
	base := filepath.Join(xdg.CacheHome, "ste")
	if err := os.MkdirAll(base, 0o755); err != nil {
		return "", err
	}
	path := filepath.Join(base, ScriptName)
	// A file of an older version must not stay.
	if current, err := os.ReadFile(path); err == nil && string(current) == script {
		return path, nil
	}
	if err := os.WriteFile(path, []byte(script), 0o644); err != nil {
		return "", err
	}
	return path, nil
}

// Check tells if the analyzer can run, and what to do when it cannot.
func Check() Status {
	s := Status{Python: FindPython()}
	if s.Python == "" {
		s.Problem = "python3 is not on this computer"
		s.Fix = []string{"Install Python 3, or give $STE_PYTHON"}
		return s
	}
	path, err := ScriptPath()
	if err != nil {
		s.Problem = fmt.Sprintf("the tool cannot write the analyzer: %v", err)
		return s
	}
	s.Script = path

	// The analyzer answers with its own message when spaCy or the model is
	// missing, thus one run gives the answer.
	cmd := exec.Command(s.Python, "-c",
		"import spacy, importlib.util as u; "+
			"raise SystemExit(0 if u.find_spec('en_core_web_sm') else 3)")
	switch err := cmd.Run(); {
	case err == nil:
		s.SpaCy = true
	case isExitCode(err, 3):
		s.Problem = "the model en_core_web_sm is not installed"
		s.Fix = []string{s.Python + " -m spacy download en_core_web_sm"}
	default:
		s.Problem = "spaCy is not installed for " + s.Python
		s.Fix = []string{
			"uv pip install spacy   (or: " + s.Python + " -m pip install spacy)",
			s.Python + " -m spacy download en_core_web_sm",
		}
	}
	return s
}

func isExitCode(err error, code int) bool {
	var exit *exec.ExitError
	if !errors.As(err, &exit) {
		return false
	}
	return exit.ExitCode() == code
}

// StartDefault runs the analyzer of this binary. It gives a message that
// names the commands to run when something is missing.
func StartDefault() (*Client, error) {
	s := Check()
	if !s.Ready() {
		msg := s.Problem
		for _, fix := range s.Fix {
			msg += "\n  " + fix
		}
		return nil, fmt.Errorf("%s", msg)
	}
	// StartArgv keeps each path in one argument, thus a directory with a
	// space in its name works.
	return StartArgv(s.Python, s.Script)
}
