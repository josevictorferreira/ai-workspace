package main

import (
	"bytes"
	"os"
	"path/filepath"
	"testing"
)

func entries() []Entry {
	return []Entry{{ID: "ux-01", Participant: "one"}, {ID: "ux-02", Participant: "two"}}
}

func TestGenerationPromptPrependsPersona(t *testing.T) {
	persona := "You are a designer."
	generate := "Create {{OUTPUT}} from {{FEATURES}}."
	prompt := persona + "\n\n" + generate
	if got, want := prompt, "You are a designer.\n\nCreate {{OUTPUT}} from {{FEATURES}}."; got != want {
		t.Fatalf("prompt = %q, want %q", got, want)
	}
}

func TestParseScorecard(t *testing.T) {
	dir := t.TempDir()
	path := filepath.Join(dir, "UX_SCORECARD.md")
	valid := `# review
| UX File | Cat. 1 | Cat. 2 | Cat. 3 | Cat. 4 | Cat. 5 | Cat. 6 | Cat. 7 | Cat. 8 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| ux-01 | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 |
| ux-02 | 10 | 9 | 8 | 7 | 6 | 5 | 4 | 3 |
`
	if err := os.WriteFile(path, []byte(valid), 0644); err != nil {
		t.Fatal(err)
	}
	scores, err := parseScorecard(path, "judge", entries())
	if err != nil {
		t.Fatal(err)
	}
	if len(scores) != 2 || scores[0].Points[7] != 8 || scores[1].Points[0] != 10 {
		t.Fatalf("unexpected scores: %#v", scores)
	}
	if err := os.WriteFile(path, []byte(stringsReplace(valid, "| ux-01 |", "| ux-01.html |")), 0644); err != nil {
		t.Fatal(err)
	}
	if _, err := parseScorecard(path, "judge", entries()); err != nil {
		t.Fatalf("expected .html entry name to work: %v", err)
	}

	for _, content := range []string{
		stringsReplace(valid, "| ux-02 |", "| ux-01 |"),
		stringsReplace(valid, "| ux-02 |", "| ux-03 |"),
		stringsReplace(valid, "| 1 | 2", "| 0 | 2"),
	} {
		if err := os.WriteFile(path, []byte(content), 0644); err != nil {
			t.Fatal(err)
		}
		if _, err := parseScorecard(path, "judge", entries()); err == nil {
			t.Fatalf("expected invalid scorecard error for:\n%s", content)
		}
	}
}

func TestStageGeneratedHTMLAcceptsOneRenamedFile(t *testing.T) {
	work := t.TempDir()
	generated := filepath.Join(work, "index.html")
	destination := filepath.Join(work, "staged.html")
	if err := os.WriteFile(generated, []byte("<html></html>"), 0644); err != nil {
		t.Fatal(err)
	}
	if err := stageGeneratedHTML(work, filepath.Join(work, "ux-01.html"), destination); err != nil {
		t.Fatal(err)
	}
	if _, err := os.Stat(destination); err != nil {
		t.Fatal(err)
	}
}

func TestPrintReportIncludesEntryFile(t *testing.T) {
	var output bytes.Buffer
	printReport(&output, Report{Results: []Result{{
		Rank:  1,
		Entry: Entry{ID: "ux-01", Participant: "model-a", Model: "a"},
		Final: 8.5,
	}}}, "runs/20260805-120000")
	if got, want := output.String(), "ux-01.html"; !stringsContains(got, want) {
		t.Fatalf("report output %q does not include %q", got, want)
	}
}

func TestAggregateUsesWeights(t *testing.T) {
	c := Config{CategoryWeights: []float64{2, 1, 1, 1, 1, 1, 1, 1}}
	c.Judges = []Person{{ID: "a", Weight: 1}, {ID: "b", Weight: 3}}
	var low, high [categories]int
	for i := range low {
		low[i], high[i] = 2, 10
	}
	report := aggregate("test", c, []Entry{{ID: "ux-01", Participant: "one"}}, []Score{{Judge: "a", Entry: "ux-01", Points: low}, {Judge: "b", Entry: "ux-01", Points: high}}, map[string]bool{}, nil)
	if got, want := report.Results[0].Categories[0], 8.0; got != want {
		t.Fatalf("category mean = %v, want %v", got, want)
	}
	if got, want := report.Results[0].Final, 8.0; got != want {
		t.Fatalf("final = %v, want %v", got, want)
	}
}

func TestLoadConfigAllowsZeroCategoryWeightAndDotsInID(t *testing.T) {
	path := filepath.Join(t.TempDir(), "config.yaml")
	config := `pi: {command: pi, args: [--print]}
run: {max_parallel: 1}
participants: [{id: model-3.7, model: a}]
judges: [{id: b, model: b}]
category_weights: [1, 1, 1, 1, 1, 1, 1, 0]
`
	if err := os.WriteFile(path, []byte(config), 0644); err != nil {
		t.Fatal(err)
	}
	if _, err := loadConfig(path); err != nil {
		t.Fatalf("expected valid config: %v", err)
	}
}

func TestLoadConfigRejectsBadWeights(t *testing.T) {
	path := filepath.Join(t.TempDir(), "config.yaml")
	bad := `pi: {command: pi, args: [--print]}
run: {max_parallel: 1}
participants: [{id: a, model: a}]
judges: [{id: b, model: b}]
category_weights: [1, 1]
`
	if err := os.WriteFile(path, []byte(bad), 0644); err != nil {
		t.Fatal(err)
	}
	if _, err := loadConfig(path); err == nil {
		t.Fatal("expected validation error")
	}
}

func stringsContains(s, substr string) bool {
	for i := 0; i+len(substr) <= len(s); i++ {
		if s[i:i+len(substr)] == substr {
			return true
		}
	}
	return false
}

func stringsReplace(s, old, new string) string {
	for i := 0; i+len(old) <= len(s); i++ {
		if s[i:i+len(old)] == old {
			return s[:i] + new + s[i+len(old):]
		}
	}
	return s
}
