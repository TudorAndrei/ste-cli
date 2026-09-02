package checker

import (
	"strings"
	"unicode"
	"unicode/utf8"
)

// Parse builds a Document from Markdown or plain text. It masks the spans
// that are not prose, then splits the remaining text into sentences. All
// offsets stay valid for the original text.
func Parse(src string) Document {
	masked, blockLines, blankLines, lineStarts := mask(src)
	doc := Document{Source: src, Masked: masked}
	doc.Sentences = split(src, masked, blockLines, blankLines, lineStarts)
	return doc
}

// mask replaces every non-prose span with spaces. It returns the masked text,
// one flag per line that tells if the line is a Markdown block line (heading,
// list item, quote, or table row), one flag per line that tells if the masked
// line is empty, and the byte offset of each line.
func mask(src string) (string, []bool, []bool, []int) {
	buf := []byte(src)
	lineStarts := []int{}
	blockLines := []bool{}
	blankLines := []bool{}

	inFence := false
	fenceChar := byte(0)
	fenceLen := 0
	inIndentedCode := false
	listActive := false
	prevBlank := true

	for pos := 0; pos <= len(src); {
		if pos == len(src) && pos > 0 && src[pos-1] == '\n' {
			break
		}
		lineStart := pos
		lineEnd := strings.IndexByte(src[pos:], '\n')
		if lineEnd < 0 {
			lineEnd = len(src)
		} else {
			lineEnd += pos
		}
		line := src[lineStart:lineEnd]
		lineStarts = append(lineStarts, lineStart)

		if char, n, ok := fenceMarker(line); ok && (!inFence || (char == fenceChar && n >= fenceLen)) {
			if inFence {
				inFence = false
			} else {
				inFence = true
				fenceChar = char
				fenceLen = n
			}
			blank(buf, lineStart, lineEnd)
			blockLines = append(blockLines, false)
			blankLines = append(blankLines, true)
			pos = lineEnd + 1
			continue
		}
		if inFence {
			blank(buf, lineStart, lineEnd)
			blockLines = append(blockLines, false)
			blankLines = append(blankLines, true)
			pos = lineEnd + 1
			continue
		}

		// An indented block of 4 or more spaces is code, but only when a
		// list does not continue on that line.
		lineBlank := isBlank([]byte(line))
		indent := indentWidth(line)
		if !lineBlank {
			switch {
			case inIndentedCode && indent < 4:
				inIndentedCode = false
			case !inIndentedCode && indent >= 4 && prevBlank && !listActive:
				inIndentedCode = true
			}
		}
		if inIndentedCode && !lineBlank {
			blank(buf, lineStart, lineEnd)
			blockLines = append(blockLines, false)
			blankLines = append(blankLines, true)
			prevBlank = false
			pos = lineEnd + 1
			continue
		}
		if !lineBlank && indent < 4 {
			listActive = startsListItem(line)
		}
		prevBlank = lineBlank

		isBlock := maskLineMarkers(buf, src, lineStart, lineEnd)
		maskInlineCode(buf, src, lineStart, lineEnd)
		maskLinksAndURLs(buf, src, lineStart, lineEnd)

		blockLines = append(blockLines, isBlock)
		blankLines = append(blankLines, isBlank(buf[lineStart:lineEnd]))
		pos = lineEnd + 1
	}
	return string(buf), blockLines, blankLines, lineStarts
}

// fenceMarker reports whether the line opens or closes a code fence.
func fenceMarker(line string) (byte, int, bool) {
	i := 0
	for i < len(line) && line[i] == ' ' && i < 3 {
		i++
	}
	if i >= len(line) {
		return 0, 0, false
	}
	c := line[i]
	if c != '`' && c != '~' {
		return 0, 0, false
	}
	n := 0
	for i+n < len(line) && line[i+n] == c {
		n++
	}
	if n < 3 {
		return 0, 0, false
	}
	return c, n, true
}

// indentWidth gives the indent of a line in spaces. A tab counts as 4.
func indentWidth(line string) int {
	n := 0
	for i := 0; i < len(line); i++ {
		switch line[i] {
		case ' ':
			n++
		case '\t':
			n += 4
		default:
			return n
		}
	}
	return n
}

// startsListItem tells if the line starts a list item or a quote.
func startsListItem(line string) bool {
	i := 0
	for i < len(line) && (line[i] == ' ' || line[i] == '\t') {
		i++
	}
	if i >= len(line) {
		return false
	}
	if line[i] == '>' {
		return true
	}
	if (line[i] == '-' || line[i] == '*' || line[i] == '+') && i+1 < len(line) && line[i+1] == ' ' {
		return true
	}
	n := 0
	for i+n < len(line) && line[i+n] >= '0' && line[i+n] <= '9' {
		n++
	}
	return n > 0 && i+n+1 < len(line) && (line[i+n] == '.' || line[i+n] == ')') && line[i+n+1] == ' '
}

// maskLineMarkers removes the Markdown block markers at the start of a line
// and the cell separators of a table row. It reports whether the line is a
// block line.
func maskLineMarkers(buf []byte, src string, start, end int) bool {
	i := start
	for i < end && (src[i] == ' ' || src[i] == '\t') {
		i++
	}
	isBlock := false
	// Quote and list markers can repeat, as in "> - item".
	for i < end {
		switch {
		case src[i] == '>':
			buf[i] = ' '
			i++
			isBlock = true
		case (src[i] == '-' || src[i] == '*' || src[i] == '+') && i+1 < end && (src[i+1] == ' ' || src[i+1] == '\t'):
			buf[i] = ' '
			i++
			isBlock = true
		case src[i] == '#':
			n := 0
			for i+n < end && src[i+n] == '#' {
				n++
			}
			if n <= 6 && i+n < end && (src[i+n] == ' ' || src[i+n] == '\t') {
				blank(buf, i, i+n)
				i += n
				isBlock = true
			} else {
				return isBlock
			}
		case src[i] >= '0' && src[i] <= '9':
			n := 0
			for i+n < end && src[i+n] >= '0' && src[i+n] <= '9' {
				n++
			}
			if i+n < end && (src[i+n] == '.' || src[i+n] == ')') && i+n+1 < end && src[i+n+1] == ' ' {
				blank(buf, i, i+n+1)
				i += n + 1
				isBlock = true
			} else {
				return isBlock
			}
		default:
			// A table row keeps its text and its separators. The
			// separators become sentence boundaries in split, because
			// each cell is a different item.
			if strings.Count(src[start:end], "|") >= 2 {
				isBlock = true
			}
			return isBlock
		}
		for i < end && (src[i] == ' ' || src[i] == '\t') {
			i++
		}
	}
	return isBlock
}

// maskInlineCode blanks every inline code span of the line.
func maskInlineCode(buf []byte, src string, start, end int) {
	i := start
	for i < end {
		if src[i] != '`' {
			i++
			continue
		}
		n := 0
		for i+n < end && src[i+n] == '`' {
			n++
		}
		closeAt := -1
		for j := i + n; j < end; j++ {
			if src[j] != '`' {
				continue
			}
			m := 0
			for j+m < end && src[j+m] == '`' {
				m++
			}
			if m == n {
				closeAt = j + m
				break
			}
			j += m - 1
		}
		if closeAt < 0 {
			// An unbalanced backtick is not a code span.
			i += n
			continue
		}
		blank(buf, i, closeAt)
		i = closeAt
	}
}

// maskLinksAndURLs blanks link targets and bare URLs. The link text stays,
// because it is prose.
func maskLinksAndURLs(buf []byte, src string, start, end int) {
	for i := start; i < end; i++ {
		if src[i] == '(' && i > start && src[i-1] == ']' {
			depth := 0
			for j := i; j < end; j++ {
				if src[j] == '(' {
					depth++
				} else if src[j] == ')' {
					depth--
					if depth == 0 {
						blank(buf, i, j+1)
						i = j
						break
					}
				}
			}
			continue
		}
		if src[i] == '<' {
			for j := i + 1; j < end; j++ {
				if src[j] == '>' {
					blank(buf, i, j+1)
					i = j
					break
				}
				if src[j] == ' ' {
					break
				}
			}
			continue
		}
		if strings.HasPrefix(src[i:end], "http://") || strings.HasPrefix(src[i:end], "https://") {
			j := i
			for j < end && src[j] != ' ' && src[j] != '\t' {
				j++
			}
			blank(buf, i, j)
			i = j
		}
	}
}

func blank(buf []byte, start, end int) {
	for i := start; i < end && i < len(buf); i++ {
		if buf[i] != '\n' {
			buf[i] = ' '
		}
	}
}

func isBlank(b []byte) bool {
	for _, c := range b {
		if c != ' ' && c != '\t' && c != '\r' {
			return false
		}
	}
	return true
}

// split cuts the masked text into sentences. A blank line, the end of a block
// line, and the end punctuation of a sentence are all boundaries.
func split(src, masked string, blockLines, blankLines []bool, lineStarts []int) []Sentence {
	boundary := make([]bool, len(masked)+1)
	for i, ls := range lineStarts {
		lineEnd := len(masked)
		if i+1 < len(lineStarts) {
			lineEnd = lineStarts[i+1] - 1
		}
		if blankLines[i] || blockLines[i] {
			boundary[ls] = true
			if lineEnd <= len(masked) {
				boundary[lineEnd] = true
			}
		}
	}

	sentences := []Sentence{}
	segStart := 0
	flush := func(end int) {
		s, ok := makeSentence(src, masked, segStart, end)
		if ok {
			sentences = append(sentences, s)
		}
		segStart = end
	}

	for i := 0; i < len(masked); i++ {
		if boundary[i] && i > segStart {
			flush(i)
		}
		c := masked[i]
		if c == '|' {
			// Each cell of a table row is a different item.
			flush(i)
			continue
		}
		if c != '.' && c != '!' && c != '?' {
			continue
		}
		// Keep a run of end punctuation together, as in "What?!".
		j := i
		for j < len(masked) && (masked[j] == '.' || masked[j] == '!' || masked[j] == '?') {
			j++
		}
		if j < len(masked) && !isSpaceByte(masked[j]) {
			i = j - 1
			continue
		}
		if c == '.' && !endsSentence(src, masked, i) {
			i = j - 1
			continue
		}
		flush(j)
		i = j - 1
	}
	if segStart < len(masked) {
		flush(len(masked))
	}
	return sentences
}

// endsSentence tells if the period at pos closes a sentence. It rejects the
// known abbreviations, the decimal separators, and the single initials. The
// look-ahead uses the source text, because a masked span, such as inline
// code, can hide the start of the next sentence.
func endsSentence(src, masked string, pos int) bool {
	// The next word starts with a lower-case letter: probably an
	// abbreviation, such as "e.g. the parser".
	for j := pos + 1; j < len(src); j++ {
		if src[j] == ' ' || src[j] == '\t' {
			continue
		}
		if src[j] == '\n' || src[j] == '\r' {
			break
		}
		r, _ := utf8.DecodeRuneInString(src[j:])
		if unicode.IsLower(r) {
			return false
		}
		break
	}
	start := pos
	for start > 0 && isWordByte(masked[start-1]) {
		start--
	}
	word := strings.ToLower(masked[start:pos])
	if word == "" {
		return true
	}
	if len(word) == 1 {
		// A single letter is an initial; a single digit is a list number.
		return false
	}
	return !abbreviations[word]
}

var abbreviations = map[string]bool{
	"e.g": true, "i.e": true, "etc": true, "vs": true, "fig": true,
	"no": true, "ref": true, "approx": true, "min": true, "max": true,
	"sec": true, "para": true, "ch": true, "al": true, "inc": true,
	"ltd": true, "dr": true, "mr": true, "mrs": true, "ms": true,
	"st": true, "vol": true, "cf": true, "ca": true, "dept": true,
}

func makeSentence(src, masked string, start, end int) (Sentence, bool) {
	for start < end && isSpaceByte(masked[start]) {
		start++
	}
	for end > start && isSpaceByte(masked[end-1]) {
		end--
	}
	if start >= end {
		return Sentence{}, false
	}
	s := Sentence{
		Text:   src[start:end],
		Start:  start,
		End:    end,
		Tokens: tokenize(masked, start, end),
	}
	if len(s.Tokens) == 0 {
		return Sentence{}, false
	}
	return s, true
}

// tokenize returns the words of a span. A word can hold an internal
// apostrophe, hyphen, or period, which keeps "don't", "shut-down", and "e.g."
// as single tokens.
func tokenize(masked string, start, end int) []Token {
	tokens := []Token{}
	i := start
	for i < end {
		r, size := utf8.DecodeRuneInString(masked[i:])
		if !isWordRune(r) {
			i += size
			continue
		}
		wordStart := i
		for i < end {
			r, size = utf8.DecodeRuneInString(masked[i:])
			if isWordRune(r) {
				i += size
				continue
			}
			if isJoinRune(r) && i+size < end {
				next, _ := utf8.DecodeRuneInString(masked[i+size:])
				if isWordRune(next) {
					i += size
					continue
				}
			}
			break
		}
		text := masked[wordStart:i]
		tokens = append(tokens, Token{
			Text:  text,
			Lower: strings.ToLower(normalizeApostrophes(text)),
			Start: wordStart,
			End:   i,
		})
	}
	return tokens
}

func normalizeApostrophes(s string) string {
	if !strings.ContainsAny(s, "’ʼ") {
		return s
	}
	r := strings.NewReplacer("’", "'", "ʼ", "'")
	return r.Replace(s)
}

func isWordRune(r rune) bool {
	return unicode.IsLetter(r) || unicode.IsDigit(r)
}

func isJoinRune(r rune) bool {
	return r == '\'' || r == '’' || r == 'ʼ' || r == '-' || r == '.' || r == '_'
}

func isWordByte(c byte) bool {
	return c >= 'a' && c <= 'z' || c >= 'A' && c <= 'Z' || c >= '0' && c <= '9' || c == '.' || c == '_'
}

func isSpaceByte(c byte) bool {
	return c == ' ' || c == '\t' || c == '\n' || c == '\r'
}
