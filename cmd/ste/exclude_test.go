package main

import "testing"

func TestMatchesAny(t *testing.T) {
	cases := []struct {
		pattern string
		path    string
		want    bool
	}{
		{"docs/legacy/**", "root/docs/legacy/a.md", true},
		{"docs/legacy/**", "root/docs/legacy/deep/a.md", true},
		{"docs/legacy/**", "root/docs/current/a.md", false},
		{"**/fixtures/**", "root/tests/fixtures/a.md", true},
		{"**/fixtures/**", "root/a/b/fixtures/c/d.md", true},
		{"**/fixtures/**", "root/tests/other/a.md", false},
		{"*.generated.md", "root/docs/api.generated.md", true},
		{"*.generated.md", "root/docs/api.md", false},
		{"CHANGELOG.md", "root/CHANGELOG.md", true},
		{"CHANGELOG.md", "root/docs/CHANGELOG.md", true},
		{"docs/*.md", "root/docs/a.md", true},
		{"docs/*.md", "root/docs/deep/a.md", false},
	}
	for _, tc := range cases {
		got := matchesAny(tc.path, "root", []string{tc.pattern})
		if got != tc.want {
			t.Errorf("pattern %q against %q: got %v, want %v", tc.pattern, tc.path, got, tc.want)
		}
	}
	if matchesAny("root/a.md", "root", nil) {
		t.Error("an empty list must match nothing")
	}
}
