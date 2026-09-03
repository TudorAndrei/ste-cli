package checker

import (
	"strings"
	"unicode"
	"unicode/utf8"

	"github.com/yuin/goldmark"
	"github.com/yuin/goldmark/ast"
	"github.com/yuin/goldmark/extension"
	east "github.com/yuin/goldmark/extension/ast"
	"github.com/yuin/goldmark/text"

	"github.com/TudorAndrei/ste-cli/internal/checker/rules"
)

// markdown is the parser. goldmark follows CommonMark, thus this tool does
// not need its own reader for code fences, lists, links, and HTML. The
// table extension is necessary because a table cell holds prose.
var markdown = goldmark.New(goldmark.WithExtensions(extension.Table, extension.Strikethrough))

// Parse builds a Document from Markdown or plain text.
//
// goldmark gives an AST in which each text node keeps its byte offsets in
// the source. The parser copies only the prose bytes into Masked and leaves
// a space at each other byte, thus:
//   - Code, link targets, and HTML are not prose, and no rule sees them.
//   - Masked has the length of Source, and each offset of a finding is an
//     offset in the original text.
func Parse(src string) Document {
	source := []byte(src)
	root := markdown.Parser().Parse(text.NewReader(source))

	buf := blankCopy(source)
	blocks := collectBlocks(root, source)
	if end := frontMatterEnd(src); end > 0 {
		blocks = dropBefore(blocks, end)
	}
	for _, b := range blocks {
		for _, seg := range b.segments {
			copy(buf[seg.Start:seg.Stop], source[seg.Start:seg.Stop])
		}
	}
	masked := string(buf)

	doc := Document{Source: src, Masked: masked}
	for i, b := range blocks {
		doc.Sentences = append(doc.Sentences, b.sentences(src, masked, i)...)
	}
	return doc
}

// frontMatterEnd gives the offset after the front matter of a document, or
// 0 when the document has none. Front matter is data for a tool, and it is
// not prose. CommonMark has no front matter, thus a Markdown parser reads
// the "---" as a horizontal rule and the keys as a paragraph.
func frontMatterEnd(src string) int {
	var fence string
	switch {
	case strings.HasPrefix(src, "---\n"), strings.HasPrefix(src, "---\r\n"):
		fence = "---"
	case strings.HasPrefix(src, "+++\n"), strings.HasPrefix(src, "+++\r\n"):
		fence = "+++"
	default:
		return 0
	}
	for i := strings.IndexByte(src, '\n') + 1; i < len(src); {
		lineEnd := strings.IndexByte(src[i:], '\n')
		line := src[i:]
		next := len(src)
		if lineEnd >= 0 {
			line = src[i : i+lineEnd]
			next = i + lineEnd + 1
		}
		switch strings.TrimRight(line, " \t\r") {
		case fence, "...":
			return next
		}
		i = next
	}
	// No closing fence: the document is not front matter.
	return 0
}

// dropBefore removes each block that starts before the offset.
func dropBefore(blocks []block, offset int) []block {
	out := blocks[:0]
	for _, b := range blocks {
		if b.segments[0].Start >= offset {
			out = append(out, b)
		}
	}
	return out
}

// blankCopy gives a buffer of the same length with a space at each byte. It
// keeps each line break, thus a line number stays correct.
func blankCopy(source []byte) []byte {
	buf := make([]byte, len(source))
	for i, c := range source {
		if c == '\n' || c == '\r' {
			buf[i] = c
			continue
		}
		buf[i] = ' '
	}
	return buf
}

// block is one leaf block of the document: a paragraph, a heading, a step of
// a list, or a cell of a table. A sentence never crosses a block.
type block struct {
	segments   []text.Segment
	procedural bool
	note       bool
	kind       Kind
	admonition string
	// paragraph is the number of the group of blocks that a rule counts
	// as one paragraph. A list gives one number to each of its items.
	paragraph int
}

// Kind is the type of a leaf block.
type Kind = rules.BlockKind

// collectBlocks walks the AST and gives one block for each leaf block, with
// the text segments of its prose.
func collectBlocks(root ast.Node, source []byte) []block {
	blocks := []block{}
	_ = ast.Walk(root, func(n ast.Node, entering bool) (ast.WalkStatus, error) {
		if !entering || !isLeafBlock(n) {
			return ast.WalkContinue, nil
		}
		segments := proseSegments(n)
		if len(segments) == 0 {
			return ast.WalkSkipChildren, nil
		}
		// The label of an admonition can be more than one text node:
		// goldmark reads "[!WARNING]" as three nodes. Thus the detector
		// reads the raw source at the start of the block.
		first := leadingSource(source, segments[0].Start)
		b := block{
			segments:   segments,
			procedural: inOrderedListItem(n),
			kind:       blockKind(n),
			admonition: admonitionWord(first),
		}
		b.note = b.admonition == "note" || b.admonition == "notes"
		blocks = append(blocks, b)
		// The children are inline nodes, and proseSegments read them.
		return ast.WalkSkipChildren, nil
	})
	return blocks
}

// blockKind gives the type of a leaf block.
func blockKind(n ast.Node) Kind {
	switch n.Kind() {
	case ast.KindHeading:
		return rules.BlockHeading
	case east.KindTableCell:
		return rules.BlockTableCell
	}
	// A paragraph or a text block inside a list item is a list item.
	for p := n.Parent(); p != nil; p = p.Parent() {
		if p.Kind() == ast.KindListItem {
			return rules.BlockListItem
		}
	}
	return rules.BlockParagraph
}

// leadingSource gives the first bytes of the block, for a label.
func leadingSource(source []byte, start int) string {
	end := start + 48
	if end > len(source) {
		end = len(source)
	}
	return string(source[start:end])
}

// admonitions are the words that start a note or a safety instruction.
// Rule 7.1 tells you to identify the level of a safety instruction with a
// word such as "warning" or "caution".
var admonitions = map[string]bool{
	"warning": true, "caution": true, "danger": true, "note": true,
	"notes": true, "important": true, "attention": true, "tip": true,
	"info": true,
}

// admonitionWord gives the word that starts a block, when that word
// identifies a note or a safety instruction. It reads the forms of Markdown
// that a writer uses: "WARNING:", "**Warning:**", "> [!WARNING]", and
// ":::warning".
func admonitionWord(text string) string {
	trimmed := strings.TrimLeft(text, " \t*_>:!-[")
	end := 0
	for end < len(trimmed) && isLetterByte(trimmed[end]) {
		end++
	}
	word := strings.ToLower(trimmed[:end])
	if !admonitions[word] {
		return ""
	}
	// The word must be a label, thus a mark must follow it.
	rest := strings.TrimLeft(trimmed[end:], " \t")
	switch {
	case strings.HasPrefix(rest, ":"), strings.HasPrefix(rest, "]"),
		strings.HasPrefix(rest, "*"), strings.HasPrefix(rest, "!"), rest == "":
		return word
	}
	return ""
}

func isLetterByte(c byte) bool {
	return c >= 'a' && c <= 'z' || c >= 'A' && c <= 'Z'
}

// isLeafBlock tells if the node is a block that holds prose. A list item
// holds a paragraph or a text block, thus it is not in this list.
func isLeafBlock(n ast.Node) bool {
	switch n.Kind() {
	case ast.KindParagraph, ast.KindHeading, ast.KindTextBlock, east.KindTableCell:
		return true
	}
	return false
}

// proseSegments gives the text segments below a block. It does not go into a
// code span, an autolink, or raw HTML, because those are not prose. The
// destination of a link is not a text node, thus it never appears here.
func proseSegments(block ast.Node) []text.Segment {
	segments := []text.Segment{}
	_ = ast.Walk(block, func(n ast.Node, entering bool) (ast.WalkStatus, error) {
		if !entering {
			return ast.WalkContinue, nil
		}
		switch n.Kind() {
		case ast.KindCodeSpan, ast.KindAutoLink, ast.KindRawHTML, ast.KindHTMLBlock,
			ast.KindCodeBlock, ast.KindFencedCodeBlock, ast.KindImage:
			return ast.WalkSkipChildren, nil
		case ast.KindText:
			t := n.(*ast.Text)
			if seg := t.Segment; seg.Stop > seg.Start {
				segments = append(segments, seg)
			}
		}
		return ast.WalkContinue, nil
	})
	return segments
}

// inOrderedListItem tells if the block is a step of a numbered list.
// ASD-STE100 rule 5.1 gives 20 words to an instruction in a procedure, and
// a numbered list is the signal that this tool uses. A bulleted list is
// usually a list of items and not a sequence of steps.
func inOrderedListItem(n ast.Node) bool {
	for p := n.Parent(); p != nil; p = p.Parent() {
		if p.Kind() != ast.KindListItem {
			continue
		}
		if list, ok := p.Parent().(*ast.List); ok && list.IsOrdered() {
			return true
		}
	}
	return false
}

// sentences cuts one block into sentences.
func (b block) sentences(src, masked string, number int) []Sentence {
	out := []Sentence{}
	start := b.segments[0].Start
	end := b.segments[len(b.segments)-1].Stop

	segStart := start
	flush := func(to int) {
		if s, ok := makeSentence(src, masked, segStart, to); ok {
			s.Procedural = b.procedural
			s.Note = b.note
			s.Block = number
			s.Kind = b.kind
			s.Admonition = b.admonition
			out = append(out, s)
		}
		segStart = to
	}

	for i := start; i < end; i++ {
		c := masked[i]
		// Rule 8.4: in a vertical list, a colon has the same effect as a
		// period. It ends a sentence, and the word count starts again.
		// A colon with no space after it is not a mark of punctuation:
		// "12:30" and "http:" are examples.
		if c == ':' && b.kind == rules.BlockListItem {
			k := i + 1
			for k < end && isClosingMark(masked[k]) {
				k++
			}
			if k < end && !isSpaceByte(masked[k]) {
				continue
			}
			// The colon of an admonition label is a part of the label,
			// and not the end of a sentence. "NOTE: The pump needs
			// pressure" is one sentence with a label.
			if b.admonition != "" && isLabelOnly(masked[segStart:i], b.admonition) {
				continue
			}
			flush(k)
			i = k - 1
			continue
		}
		if c != '.' && c != '!' && c != '?' {
			continue
		}
		// Keep a run of end punctuation together, as in "What?!".
		j := i
		for j < end && (masked[j] == '.' || masked[j] == '!' || masked[j] == '?') {
			j++
		}
		// A closing mark can follow, as in the bold text "**Do this.**".
		k := j
		for k < end && isClosingMark(masked[k]) {
			k++
		}
		if k < end && !isSpaceByte(masked[k]) {
			i = j - 1
			continue
		}
		if c == '.' && !endsSentence(src, masked, i) {
			i = j - 1
			continue
		}
		flush(k)
		i = k - 1
	}
	if segStart < end {
		flush(end)
	}
	if len(out) > 0 {
		out[0].First = true
		out[len(out)-1].Last = true
	}
	return out
}

// isLabelOnly tells if the text before a colon is only the admonition word.
// The marks of the label, such as the asterisks of "**NOTE:**", are not a
// part of the word.
func isLabelOnly(text, admonition string) bool {
	trimmed := strings.TrimFunc(text, func(r rune) bool {
		return !unicode.IsLetter(r)
	})
	return strings.EqualFold(trimmed, admonition)
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
	if len(word) == 1 && word[0] >= 'a' && word[0] <= 'z' {
		// A single letter is an initial, as in "J. Smith". A single digit
		// is not: "Issue 9." is the end of a sentence.
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
	s.Words = countWords(masked, start, end)
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
		i = endOfWord(masked, i, end)
		txt := masked[wordStart:i]
		tokens = append(tokens, Token{
			Text:  txt,
			Lower: strings.ToLower(normalizeApostrophes(txt)),
			Start: wordStart,
			End:   i,
		})
	}
	return tokens
}

// units are the measurement units that make one word with the number before
// them. Rule 8.6 counts a quantity and its unit as one word.
var units = map[string]bool{
	"mm": true, "cm": true, "m": true, "km": true, "in": true, "ft": true,
	"mg": true, "g": true, "kg": true, "lb": true, "lbs": true,
	"ml": true, "l": true, "gal": true,
	"ms": true, "s": true, "sec": true, "min": true, "h": true, "hr": true,
	"hrs": true, "day": true, "days": true, "week": true, "weeks": true,
	"month": true, "months": true, "year": true, "years": true,
	"hz": true, "khz": true, "mhz": true, "ghz": true,
	"b": true, "kb": true, "mb": true, "gb": true, "tb": true,
	"kib": true, "mib": true, "gib": true, "tib": true,
	"bit": true, "bits": true, "byte": true, "bytes": true,
	"v": true, "a": true, "ma": true, "w": true, "kw": true,
	"psi": true, "bar": true, "kpa": true, "mpa": true, "n": true, "nm": true,
	"px": true, "pt": true, "em": true, "rem": true, "dpi": true,
	"rpm": true, "c": true, "f": true, "k": true, "%": true,
}

// countWords counts the words of a span with the count rules of section 8.
// A quantity with its unit, a quoted string, and text in parentheses each
// count as one word. Rule 8.6 also makes a multi-word title or a multi-word
// proper noun one word; this tool cannot find those without a dictionary,
// thus it counts them as separate words. See docs/rules.md.
func countWords(masked string, start, end int) int {
	n := 0
	i := start
	for i < end {
		r, size := utf8.DecodeRuneInString(masked[i:])
		if unicode.IsSpace(r) {
			i += size
			continue
		}
		// Text in parentheses counts as one word.
		if r == '(' {
			if close := matchDelimiter(masked, i, end, '(', ')'); close > i {
				n++
				i = close
				continue
			}
		}
		// A quoted string counts as one word.
		if isOpenQuote(r) {
			if close := matchQuote(masked, i, end, r); close > i {
				n++
				i = close
				continue
			}
		}
		if !isWordRune(r) {
			i += size
			continue
		}
		wordStart := i
		i = endOfWord(masked, i, end)
		n++
		// A quantity and its unit make one word.
		if isAllDigits(masked[wordStart:i]) {
			if next := skipSpaces(masked, i, end); next > i && next < end {
				unitEnd := endOfWord(masked, next, end)
				if unitEnd > next && units[strings.ToLower(masked[next:unitEnd])] {
					i = unitEnd
				}
			}
		}
	}
	return n
}

func endOfWord(masked string, i, end int) int {
	for i < end {
		r, size := utf8.DecodeRuneInString(masked[i:])
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
	return i
}

func skipSpaces(masked string, i, end int) int {
	for i < end && isSpaceByte(masked[i]) {
		i++
	}
	return i
}

func isAllDigits(s string) bool {
	if s == "" {
		return false
	}
	for i := 0; i < len(s); i++ {
		if (s[i] < '0' || s[i] > '9') && s[i] != '.' && s[i] != ',' {
			return false
		}
	}
	return true
}

// matchDelimiter gives the offset after the closing delimiter.
func matchDelimiter(masked string, i, end int, open, close byte) int {
	depth := 0
	for j := i; j < end; j++ {
		switch masked[j] {
		case open:
			depth++
		case close:
			depth--
			if depth == 0 {
				return j + 1
			}
		}
	}
	return i
}

func isOpenQuote(r rune) bool {
	return r == '"' || r == '“'
}

// matchQuote gives the offset after the closing quotation mark.
func matchQuote(masked string, i, end int, open rune) int {
	closeRune := '"'
	if open == '“' {
		closeRune = '”'
	}
	_, size := utf8.DecodeRuneInString(masked[i:])
	for j := i + size; j < end; {
		r, s := utf8.DecodeRuneInString(masked[j:])
		if r == closeRune {
			return j + s
		}
		j += s
	}
	return i
}

func normalizeApostrophes(s string) string {
	if !strings.ContainsAny(s, "’ʼ") {
		return s
	}
	return strings.NewReplacer("’", "'", "ʼ", "'").Replace(s)
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

// isClosingMark tells if the byte is a mark that can follow the end
// punctuation of a sentence.
func isClosingMark(c byte) bool {
	switch c {
	case '*', '_', ')', ']', '"', '\'', '`':
		return true
	}
	return false
}

func isSpaceByte(c byte) bool {
	return c == ' ' || c == '\t' || c == '\n' || c == '\r'
}
