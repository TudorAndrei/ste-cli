package main

import (
	"path/filepath"
	"strings"
)

// matchesAny tells if a path matches one of the exclude patterns of the
// config. A pattern applies to the path relative to the directory that you
// give, and also to the file name.
//
//	docs/legacy/**      each file below docs/legacy
//	**/fixtures/**      each file below a directory named fixtures
//	*.generated.md      each file with that ending, in each directory
//	CHANGELOG.md        that file at the top of the directory
func matchesAny(path, root string, patterns []string) bool {
	if len(patterns) == 0 {
		return false
	}
	rel, err := filepath.Rel(root, path)
	if err != nil {
		rel = path
	}
	rel = filepath.ToSlash(rel)
	base := filepath.Base(rel)
	for _, pattern := range patterns {
		pattern = strings.TrimPrefix(filepath.ToSlash(pattern), "./")
		if matchPattern(pattern, rel) || matchPattern(pattern, base) {
			return true
		}
	}
	return false
}

// matchPattern gives a match of one pattern against one path. It knows "**"
// for "each directory below this one", which filepath.Match does not.
func matchPattern(pattern, path string) bool {
	if pattern == "" {
		return false
	}
	if !strings.Contains(pattern, "**") {
		ok, err := filepath.Match(pattern, path)
		return err == nil && ok
	}

	parts := strings.Split(pattern, "**")
	pos := 0
	for i, part := range parts {
		part = strings.Trim(part, "/")
		if part == "" {
			continue
		}
		idx := indexSegment(path[pos:], part, i == 0)
		if idx < 0 {
			return false
		}
		pos += idx + len(part)
	}
	// A pattern that ends with "**" matches each path below the prefix.
	return true
}

// indexSegment finds a part of a pattern on a segment boundary of the path.
func indexSegment(path, part string, anchored bool) int {
	for i := 0; i+len(part) <= len(path); i++ {
		if anchored && i > 0 {
			return -1
		}
		if !strings.HasPrefix(path[i:], part) {
			continue
		}
		if i > 0 && path[i-1] != '/' {
			continue
		}
		end := i + len(part)
		if end == len(path) || path[end] == '/' {
			return i
		}
		// A pattern such as "*.md" needs the glob reader.
		if strings.ContainsAny(part, "*?[") {
			if ok, err := filepath.Match(part, path[i:]); err == nil && ok {
				return i
			}
		}
	}
	return -1
}
