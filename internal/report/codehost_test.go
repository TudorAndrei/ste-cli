package report

import (
	"bytes"
	"encoding/json"
	"strings"
	"testing"

	"github.com/TudorAndrei/ste-cli/internal/checker"
)

// sample gives a report of one file with two findings. The second line
// starts with a character of two bytes.
func sample() Report {
	source := "It isn't open.\nÉtat; now.\n"
	diags := []checker.Diagnostic{
		{RuleID: "STE-4.2", Message: "A contraction.", Suggestion: "Write \"is not\".",
			Severity: checker.SeverityWarning, Confidence: 0.98, Start: 3, End: 8},
		{RuleID: "STE-8.1", Message: "A semicolon, 100%: no.", Severity: checker.SeverityInfo,
			Confidence: 1, Start: 20, End: 21},
	}
	res := FileResult{Path: "docs/a.md", Words: 5}
	for _, d := range diags {
		res.Findings = append(res.Findings, MakeFinding(res.Path, source, d))
	}
	return New("flavored", []FileResult{res}, 0)
}

func TestTheRegionCountsCharacters(t *testing.T) {
	f := sample().Files[0].Findings[1]
	if f.Column != 6 {
		t.Errorf("byte column %d, want 6", f.Column)
	}
	want := region{StartLine: 2, StartColumn: 5, EndLine: 2, EndColumn: 6}
	if f.region != want {
		t.Errorf("region %+v, want %+v", f.region, want)
	}
}

func TestSARIF(t *testing.T) {
	var buf bytes.Buffer
	opts := Options{Format: FormatSARIF, ToolVersion: "1.2.3",
		Rules: []Rule{{ID: "STE-4.2", Name: "Contraction", DefaultSeverity: "warning"}}}
	if err := Write(&buf, sample(), opts); err != nil {
		t.Fatal(err)
	}
	var doc struct {
		Version string `json:"version"`
		Runs    []struct {
			Tool struct {
				Driver struct {
					Name    string           `json:"name"`
					Version string           `json:"version"`
					Rules   []map[string]any `json:"rules"`
				} `json:"driver"`
			} `json:"tool"`
			Results []struct {
				RuleID    string `json:"ruleId"`
				RuleIndex *int   `json:"ruleIndex"`
				Level     string `json:"level"`
				Message   struct {
					Text string `json:"text"`
				} `json:"message"`
				Locations []struct {
					PhysicalLocation struct {
						ArtifactLocation struct {
							URI string `json:"uri"`
						} `json:"artifactLocation"`
						Region region `json:"region"`
					} `json:"physicalLocation"`
				} `json:"locations"`
			} `json:"results"`
		} `json:"runs"`
	}
	if err := json.Unmarshal(buf.Bytes(), &doc); err != nil {
		t.Fatalf("not JSON: %v\n%s", err, buf.String())
	}
	if doc.Version != "2.1.0" || len(doc.Runs) != 1 {
		t.Fatalf("version %q, %d runs", doc.Version, len(doc.Runs))
	}
	run := doc.Runs[0]
	if run.Tool.Driver.Name != "ste" || run.Tool.Driver.Version != "1.2.3" || len(run.Tool.Driver.Rules) != 1 {
		t.Errorf("driver %+v", run.Tool.Driver)
	}
	if len(run.Results) != 2 {
		t.Fatalf("%d results, want 2", len(run.Results))
	}
	first, second := run.Results[0], run.Results[1]
	if first.RuleIndex == nil || *first.RuleIndex != 0 || first.Level != "warning" {
		t.Errorf("first result %+v", first)
	}
	if !strings.Contains(first.Message.Text, "Write \"is not\".") {
		t.Errorf("the message has no suggestion: %q", first.Message.Text)
	}
	if second.RuleIndex != nil || second.Level != "note" {
		t.Errorf("second result: index %v, level %q", second.RuleIndex, second.Level)
	}
	loc := first.Locations[0].PhysicalLocation
	if loc.ArtifactLocation.URI != "docs/a.md" || loc.Region.StartColumn != 4 || loc.Region.EndColumn != 9 {
		t.Errorf("location %+v", loc)
	}
}

func TestSARIFObeysTheLimit(t *testing.T) {
	var buf bytes.Buffer
	if err := Write(&buf, sample(), Options{Format: FormatSARIF, Limit: 1}); err != nil {
		t.Fatal(err)
	}
	if n := strings.Count(buf.String(), "\"ruleId\""); n != 1 {
		t.Errorf("%d results, want 1", n)
	}
}

func TestGitHubCommands(t *testing.T) {
	var buf bytes.Buffer
	if err := Write(&buf, sample(), Options{Format: FormatGitHub}); err != nil {
		t.Fatal(err)
	}
	lines := strings.Split(buf.String(), "\n")
	want := `::warning file=docs/a.md,line=1,col=4,endLine=1,endColumn=9,title=STE-4.2::A contraction. Write "is not".`
	if lines[0] != want {
		t.Errorf("line 1:\n got %s\nwant %s", lines[0], want)
	}
	// The message escapes "%", and an info finding is a notice.
	want = `::notice file=docs/a.md,line=2,col=5,endLine=2,endColumn=6,title=STE-8.1::A semicolon, 100%25: no.`
	if lines[1] != want {
		t.Errorf("line 2:\n got %s\nwant %s", lines[1], want)
	}
	if !strings.Contains(buf.String(), "2 findings in 5 words of 1 file") {
		t.Errorf("no summary line:\n%s", buf.String())
	}
}

func TestEscapeProperty(t *testing.T) {
	if got := escapeProperty("a,b:c%\n"); got != "a%2Cb%3Ac%25%0A" {
		t.Errorf("got %q", got)
	}
}

func TestFileURI(t *testing.T) {
	if got := fileURI("docs/a.md"); got != "docs/a.md" {
		t.Errorf("relative: %q", got)
	}
	if got := fileURI("/tmp/a.md"); got != "file:///tmp/a.md" {
		t.Errorf("absolute: %q", got)
	}
}
