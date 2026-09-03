package analyzer

import "github.com/TudorAndrei/ste-cli/internal/checker/rules"

// PassiveAt tells if the word at the offset is the verb of a passive
// construction. It gives false for the second value when the analyzer gives
// no answer, and the rule then keeps its own result.
//
// The test is the relation of the dependency tree: a passive verb has a
// child with the relation "auxpass" ("is closed") or "nsubjpass" ("the
// valve is closed").
func (c *Client) PassiveAt(sentence string, offset int) (bool, bool) {
	tokens, err := c.Analyze(sentence)
	if err != nil || len(tokens) == 0 {
		return false, false
	}
	verb := -1
	for _, t := range tokens {
		if t.Start == offset {
			verb = t.Index
			break
		}
	}
	if verb < 0 {
		return false, false
	}
	for _, t := range tokens {
		if t.Head != verb {
			continue
		}
		if t.Dep == "auxpass" || t.Dep == "nsubjpass" || t.Dep == "csubjpass" {
			return true, true
		}
	}
	return false, true
}

// Grammar gives the grammar of each word of the sentence. It answers false
// when the analyzer gives no answer, and each rule of the syntax group then
// reports nothing for that sentence.
func (c *Client) Grammar(sentence string) ([]rules.SyntaxToken, bool) {
	tokens, err := c.Analyze(sentence)
	if err != nil || len(tokens) == 0 {
		return nil, false
	}
	out := make([]rules.SyntaxToken, 0, len(tokens))
	for _, t := range tokens {
		out = append(out, rules.SyntaxToken{
			Index: t.Index,
			Text:  t.Text,
			POS:   t.POS,
			Tag:   t.Tag,
			Dep:   t.Dep,
			Head:  t.Head,
			Start: t.Start,
		})
	}
	return out, true
}
