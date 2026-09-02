package checker

import (
	"strings"
)

// A writer can silence a finding in the text itself. This is necessary
// because no rule set is correct for every sentence, and a wrong finding
// must not stop the work.
//
//	<!-- ste-disable -->              from here to the end of the file
//	<!-- ste-disable STE-3.6 -->      only that rule
//	<!-- ste-enable STE-3.6 -->       start the rule again
//	<!-- ste-disable-next-line -->    the line that follows
//	<!-- ste-disable-line -->         the same line
//
// A comment with no rule ID applies to every rule. The tool reads these
// comments in an HTML comment, thus Markdown does not show them.
const (
	directiveDisable     = "ste-disable"
	directiveEnable      = "ste-enable"
	directiveNextLine    = "ste-disable-next-line"
	directiveSameLine    = "ste-disable-line"
	directiveCommentOpen = "<!--"
)

// suppression is one region of the source in which a rule gives no finding.
type suppression struct {
	start int
	end   int // len(source) for "to the end of the file"
	rules []string
}

type suppressionList []suppression

// covers tells if a finding is inside a suppressed region.
func (list suppressionList) covers(source string, d Diagnostic) bool {
	for _, s := range list {
		if d.Start < s.start || d.Start >= s.end {
			continue
		}
		if len(s.rules) == 0 {
			return true
		}
		for _, id := range s.rules {
			if id == d.RuleID {
				return true
			}
		}
	}
	return false
}

// suppressions reads the directives of a document.
func suppressions(source string) suppressionList {
	if !strings.Contains(source, directiveDisable) {
		return nil
	}
	list := suppressionList{}
	open := map[string]int{} // rule ID to start offset
	openAll := -1            // start offset of a disable with no rule ID
	lineStart := 0
	for lineStart <= len(source) {
		lineEnd := len(source)
		if i := strings.IndexByte(source[lineStart:], '\n'); i >= 0 {
			lineEnd = lineStart + i
		}
		nextLineStart := lineEnd + 1
		line := source[lineStart:lineEnd]

		if directive, ids, ok := parseDirective(line); ok {
			switch directive {
			case directiveNextLine:
				end := nextLineStart
				if i := strings.IndexByte(source[nextLineStart:], '\n'); i >= 0 && nextLineStart <= len(source) {
					end = nextLineStart + i + 1
				} else {
					end = len(source)
				}
				list = append(list, suppression{start: nextLineStart, end: end, rules: ids})
			case directiveSameLine:
				list = append(list, suppression{start: lineStart, end: lineEnd, rules: ids})
			case directiveDisable:
				if len(ids) == 0 {
					if openAll < 0 {
						openAll = lineStart
					}
					break
				}
				for _, id := range ids {
					if _, already := open[id]; !already {
						open[id] = lineStart
					}
				}
			case directiveEnable:
				if len(ids) == 0 {
					if openAll >= 0 {
						list = append(list, suppression{start: openAll, end: lineEnd})
						openAll = -1
					}
					for id, start := range open {
						list = append(list, suppression{start: start, end: lineEnd, rules: []string{id}})
						delete(open, id)
					}
					break
				}
				for _, id := range ids {
					if start, found := open[id]; found {
						list = append(list, suppression{start: start, end: lineEnd, rules: []string{id}})
						delete(open, id)
					}
				}
			}
		}

		if lineEnd >= len(source) {
			break
		}
		lineStart = nextLineStart
	}

	if openAll >= 0 {
		list = append(list, suppression{start: openAll, end: len(source)})
	}
	for id, start := range open {
		list = append(list, suppression{start: start, end: len(source), rules: []string{id}})
	}
	return list
}

// parseDirective reads a directive from one line. The line must hold an HTML
// comment that starts with a known directive word.
func parseDirective(line string) (string, []string, bool) {
	i := strings.Index(line, directiveCommentOpen)
	if i < 0 {
		return "", nil, false
	}
	body := line[i+len(directiveCommentOpen):]
	if j := strings.Index(body, "-->"); j >= 0 {
		body = body[:j]
	}
	fields := strings.Fields(body)
	if len(fields) == 0 {
		return "", nil, false
	}
	// The longer directives must come first.
	for _, directive := range []string{directiveNextLine, directiveSameLine, directiveEnable, directiveDisable} {
		if fields[0] != directive {
			continue
		}
		ids := []string{}
		for _, id := range fields[1:] {
			ids = append(ids, strings.TrimSuffix(id, ","))
		}
		return directive, ids, true
	}
	return "", nil, false
}
