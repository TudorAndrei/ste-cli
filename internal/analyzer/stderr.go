package analyzer

import (
	"io"
	"os"
)

// stderrOf gives the writer for the messages of the analyzer. A message of
// the analyzer, such as "the model is not installed", must reach the user.
func stderrOf() io.Writer { return os.Stderr }
