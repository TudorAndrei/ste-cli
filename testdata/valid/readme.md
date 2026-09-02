# ste

The ste tool is a linter for ASD-STE100 Simplified Technical English.

## Installation

Use `go install ./cmd/ste` to build the binary. Then run `ste lint README.md`.

## Rules

The tool reports a small set of rules. Each rule has an identifier, a
message, and a confidence value.

The tool is an aid for a writer. It is not an ASD-certified checker.
