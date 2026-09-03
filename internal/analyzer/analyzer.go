// Package analyzer speaks to an external program that gives the syntax of a
// sentence.
//
// Some rules of ASD-STE100 need a part of speech and a relation between two
// words. Go has no library that gives those with a trained model for
// English, and spaCy does. Thus the syntax comes from a program that the
// user starts, and not from this binary.
//
// The analyzer is optional. Each rule that uses it must also work without
// it, because the default command must stay one binary with no runtime.
package analyzer

import (
	"bufio"
	"encoding/json"
	"fmt"
	"io"
	"os/exec"
	"strings"
	"sync"
	"time"
)

// Token is one word with its syntax.
type Token struct {
	Index int    `json:"i"`
	Text  string `json:"text"`
	// POS is the coarse part of speech: NOUN, VERB, ADJ, and more.
	POS string `json:"pos"`
	// Tag is the fine part of speech: NN, VBZ, VBN, and more.
	Tag string `json:"tag"`
	// Dep is the relation of the token to its head: nsubjpass, auxpass,
	// amod, and more.
	Dep string `json:"dep"`
	// Head is the index of the token that this token depends on.
	Head int `json:"head"`
	// Start is the offset of the token in the sentence.
	Start int `json:"start"`
}

type request struct {
	ID   int    `json:"id"`
	Text string `json:"text"`
	Stop bool   `json:"stop,omitempty"`
}

type response struct {
	ID     int     `json:"id"`
	Tokens []Token `json:"tokens"`
	Error  string  `json:"error"`
	Ready  bool    `json:"ready"`
	Model  string  `json:"model"`
}

// Client is a running analyzer.
type Client struct {
	cmd    *exec.Cmd
	stdin  io.WriteCloser
	reader *bufio.Reader
	model  string

	mu   sync.Mutex
	next int
	// cache keeps the answer for each sentence. One document repeats a
	// sentence often, and a repeat must not pay for the model again.
	cache map[string][]Token
}

// StartTimeout is the time to wait for the model of the analyzer.
var StartTimeout = 60 * time.Second

// Start runs a command and waits for its ready line. The command is a word
// list, such as "python3 ste_analyzer.py". A path with a space in it needs
// StartArgv.
func Start(command string) (*Client, error) {
	fields := strings.Fields(command)
	if len(fields) == 0 {
		return nil, fmt.Errorf("the analyzer command is empty")
	}
	return StartArgv(fields[0], fields[1:]...)
}

// StartArgv runs the program with its arguments, and it waits for the ready
// line. Each argument stays one argument, thus a path with a space works.
func StartArgv(name string, args ...string) (*Client, error) {
	if name == "" {
		return nil, fmt.Errorf("the analyzer command is empty")
	}
	cmd := exec.Command(name, args...)
	stdin, err := cmd.StdinPipe()
	if err != nil {
		return nil, err
	}
	stdout, err := cmd.StdoutPipe()
	if err != nil {
		return nil, err
	}
	// The messages of the analyzer go to the terminal of the user, thus a
	// missing model gives a message that names the command to run.
	cmd.Stderr = stderrOf()
	if err := cmd.Start(); err != nil {
		return nil, fmt.Errorf("%s: %w", name, err)
	}

	c := &Client{cmd: cmd, stdin: stdin, reader: bufio.NewReader(stdout), cache: map[string][]Token{}}

	ready := make(chan error, 1)
	go func() {
		line, err := c.reader.ReadString('\n')
		if err != nil {
			ready <- fmt.Errorf("the analyzer stopped before it was ready")
			return
		}
		var r response
		if err := json.Unmarshal([]byte(line), &r); err != nil || !r.Ready {
			ready <- fmt.Errorf("the analyzer did not give a ready line")
			return
		}
		c.model = r.Model
		ready <- nil
	}()

	select {
	case err := <-ready:
		if err != nil {
			_ = cmd.Process.Kill()
			return nil, err
		}
	case <-time.After(StartTimeout):
		_ = cmd.Process.Kill()
		return nil, fmt.Errorf("the analyzer did not start in %s", StartTimeout)
	}
	return c, nil
}

// Model gives the name of the model of the analyzer.
func (c *Client) Model() string { return c.model }

// Analyze gives the tokens of one sentence. An error gives no tokens, and
// the caller then uses the rules that need no syntax.
func (c *Client) Analyze(text string) ([]Token, error) {
	if c == nil {
		return nil, nil
	}
	c.mu.Lock()
	defer c.mu.Unlock()
	if tokens, found := c.cache[text]; found {
		return tokens, nil
	}

	c.next++
	req, err := json.Marshal(request{ID: c.next, Text: text})
	if err != nil {
		return nil, err
	}
	if _, err := c.stdin.Write(append(req, '\n')); err != nil {
		return nil, err
	}
	line, err := c.reader.ReadString('\n')
	if err != nil {
		return nil, err
	}
	var r response
	if err := json.Unmarshal([]byte(line), &r); err != nil {
		return nil, err
	}
	if r.Error != "" {
		return nil, fmt.Errorf("%s", r.Error)
	}
	c.cache[text] = r.Tokens
	return r.Tokens, nil
}

// Close stops the analyzer.
func (c *Client) Close() error {
	if c == nil {
		return nil
	}
	req, _ := json.Marshal(request{Stop: true})
	_, _ = c.stdin.Write(append(req, '\n'))
	_ = c.stdin.Close()
	done := make(chan error, 1)
	go func() { done <- c.cmd.Wait() }()
	select {
	case <-done:
	case <-time.After(5 * time.Second):
		_ = c.cmd.Process.Kill()
	}
	return nil
}
