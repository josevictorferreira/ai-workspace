package main

import (
	"context"
	"encoding/json"
	"errors"
	"flag"
	"fmt"
	"io"
	"math/rand/v2"
	"os"
	"os/exec"
	"path/filepath"
	"regexp"
	"sort"
	"strconv"
	"strings"
	"sync"
	"time"

	"gopkg.in/yaml.v3"
)

const categories = 8

type Config struct {
	Pi struct {
		Command string   `yaml:"command"`
		Args    []string `yaml:"args"`
	} `yaml:"pi"`
	Run struct {
		MaxParallel int `yaml:"max_parallel"`
	} `yaml:"run"`
	Participants    []Person  `yaml:"participants"`
	Judges          []Person  `yaml:"judges"`
	CategoryWeights []float64 `yaml:"category_weights"`
}

type Person struct {
	ID     string  `yaml:"id"`
	Model  string  `yaml:"model"`
	Weight float64 `yaml:"weight"`
}

type Entry struct {
	ID          string `json:"id"`
	Participant string `json:"participant"`
	Model       string `json:"model"`
}

type Score struct {
	Judge  string          `json:"judge"`
	Entry  string          `json:"entry"`
	Points [categories]int `json:"points"`
}

type Result struct {
	Rank       int                 `json:"rank"`
	Entry      Entry               `json:"entry"`
	Categories [categories]float64 `json:"categories"`
	Final      float64             `json:"final"`
}

type Report struct {
	RunID         string   `json:"run_id"`
	ValidJudges   []string `json:"valid_judges"`
	InvalidJudges []string `json:"invalid_judges"`
	FailedEntries []string `json:"failed_entries"`
	Results       []Result `json:"results"`
}

func main() {
	if len(os.Args) < 2 {
		usage(os.Stderr)
		os.Exit(2)
	}
	switch os.Args[1] {
	case "init":
		if err := initProject("."); err != nil {
			fatal(err)
		}
	case "run":
		if err := run(os.Args[2:]); err != nil {
			fatal(err)
		}
	case "help", "--help", "-h":
		usage(os.Stdout)
	default:
		usage(os.Stderr)
		os.Exit(2)
	}
}

func usage(w io.Writer) {
	fmt.Fprintln(w, "Usage:\n  design-poc-page init\n  design-poc-page run [--config tournament.yaml] [--features FEATURES.md] [--scorecard SCORECARD.md] [--output runs] [--max-parallel N]")
}

func fatal(err error) { fmt.Fprintln(os.Stderr, "error:", err); os.Exit(1) }

func initProject(root string) error {
	files := map[string]string{
		"FEATURES.md":              "# Feature brief\n\nDescribe the page, its users, primary workflow, and important states here.\n",
		"SCORECARD.md":             scorecard,
		"tournament.yaml":          sampleConfig,
		"prompts/persona.md.tmpl":  personaPrompt,
		"prompts/generate.md.tmpl": generatePrompt,
		"prompts/judge.md.tmpl":    judgePrompt,
		".gitignore":               "runs/\n",
	}
	for path, content := range files {
		path = filepath.Join(root, path)
		if _, err := os.Stat(path); err == nil {
			continue
		}
		if err := os.MkdirAll(filepath.Dir(path), 0755); err != nil {
			return err
		}
		if err := os.WriteFile(path, []byte(content), 0644); err != nil {
			return err
		}
		fmt.Println("created", path)
	}
	return nil
}

func run(args []string) error {
	fs := flag.NewFlagSet("run", flag.ContinueOnError)
	configPath := fs.String("config", "tournament.yaml", "configuration file")
	featuresPath := fs.String("features", "FEATURES.md", "feature brief")
	scorecardPath := fs.String("scorecard", "SCORECARD.md", "scorecard")
	outputDir := fs.String("output", "runs", "run artifact directory")
	parallel := fs.Int("max-parallel", 0, "maximum concurrent Pi jobs")
	if err := fs.Parse(args); err != nil {
		return err
	}

	config, err := loadConfig(*configPath)
	if err != nil {
		return err
	}
	if *parallel > 0 {
		config.Run.MaxParallel = *parallel
	}
	features, err := os.ReadFile(*featuresPath)
	if err != nil {
		return err
	}
	rubric, err := os.ReadFile(*scorecardPath)
	if err != nil {
		return err
	}
	personaTemplate, err := os.ReadFile("prompts/persona.md.tmpl")
	if err != nil {
		return err
	}
	generateTemplate, err := os.ReadFile("prompts/generate.md.tmpl")
	if err != nil {
		return err
	}
	judgeTemplate, err := os.ReadFile("prompts/judge.md.tmpl")
	if err != nil {
		return err
	}

	runID := time.Now().Format("20060102-150405")
	root := filepath.Join(*outputDir, runID)
	for _, dir := range []string{"input", "entries", "generation", "judges", "work"} {
		if err := os.MkdirAll(filepath.Join(root, dir), 0755); err != nil {
			return err
		}
	}
	copyInput := func(name string, data []byte) error {
		return os.WriteFile(filepath.Join(root, "input", name), data, 0644)
	}
	if err := copyInput("FEATURES.md", features); err != nil {
		return err
	}
	if err := copyInput("SCORECARD.md", rubric); err != nil {
		return err
	}
	configData, _ := os.ReadFile(*configPath)
	if err := copyInput("tournament.yaml", configData); err != nil {
		return err
	}

	entries := make([]Entry, len(config.Participants))
	indices := rand.Perm(len(entries))
	for i, person := range config.Participants {
		entries[i] = Entry{ID: fmt.Sprintf("ux-%02d", indices[i]+1), Participant: person.ID, Model: person.Model}
	}
	mapping, _ := json.MarshalIndent(entries, "", "  ")
	if err := os.WriteFile(filepath.Join(root, "entry-map.private.json"), mapping, 0600); err != nil {
		return err
	}

	fmt.Printf("Run %s: generating %d entries with up to %d jobs\n", runID, len(entries), config.Run.MaxParallel)
	failed := runGeneration(context.Background(), config, root, entries, string(personaTemplate)+"\n\n"+string(generateTemplate))
	validEntries := make([]Entry, 0, len(entries))
	for _, entry := range entries {
		if !failed[entry.ID] {
			validEntries = append(validEntries, entry)
		}
	}
	if len(validEntries) == 0 {
		return errors.New("all generation jobs failed; see generation logs")
	}

	fmt.Printf("Judging %d anonymous entries with %d judges\n", len(validEntries), len(config.Judges))
	scores, invalid := runJudges(context.Background(), config, root, validEntries, string(judgeTemplate))
	if len(scores) == 0 {
		return errors.New("no valid judge scorecards; see judge logs")
	}
	report := aggregate(runID, config, validEntries, scores, failed, invalid)
	if err := writeReport(root, report); err != nil {
		return err
	}
	printReport(os.Stdout, report, root)
	fmt.Println("Artifacts:", root)
	return nil
}

func loadConfig(path string) (Config, error) {
	var c Config
	data, err := os.ReadFile(path)
	if err != nil {
		return c, err
	}
	if err := yaml.Unmarshal(data, &c); err != nil {
		return c, err
	}
	if c.Pi.Command == "" {
		return c, errors.New("pi.command is required")
	}
	if len(c.Pi.Args) == 0 {
		return c, errors.New("pi.args is required")
	}
	if c.Run.MaxParallel < 1 {
		return c, errors.New("run.max_parallel must be at least 1")
	}
	if len(c.Participants) == 0 || len(c.Judges) == 0 {
		return c, errors.New("at least one participant and judge are required")
	}
	if len(c.CategoryWeights) == 0 {
		c.CategoryWeights = make([]float64, categories)
		for i := range c.CategoryWeights {
			c.CategoryWeights[i] = 1
		}
	}
	if len(c.CategoryWeights) != categories {
		return c, fmt.Errorf("category_weights must contain %d values", categories)
	}
	seen := map[string]bool{}
	for _, group := range [][]Person{c.Participants, c.Judges} {
		seen = map[string]bool{}
		for _, p := range group {
			if !safeID(p.ID) || p.Model == "" {
				return c, errors.New("every id must contain only letters, numbers, ., _ or -, and models are required")
			}
			if seen[p.ID] {
				return c, fmt.Errorf("duplicate id: %s", p.ID)
			}
			seen[p.ID] = true
			if p.Weight < 0 {
				return c, fmt.Errorf("negative weight for %s", p.ID)
			}
		}
	}
	categoryWeightTotal := 0.0
	for _, w := range c.CategoryWeights {
		if w < 0 {
			return c, errors.New("category weights cannot be negative")
		}
		categoryWeightTotal += w
	}
	if categoryWeightTotal == 0 {
		return c, errors.New("at least one category weight must be positive")
	}
	for i := range c.Judges {
		if c.Judges[i].Weight == 0 {
			c.Judges[i].Weight = 1
		}
	}
	return c, nil
}

var idRE = regexp.MustCompile(`^[A-Za-z0-9_.-]+$`)

func safeID(id string) bool { return idRE.MatchString(id) }

func runGeneration(ctx context.Context, c Config, root string, entries []Entry, tmpl string) map[string]bool {
	failed := make(map[string]bool)
	var mu sync.Mutex
	runParallel(ctx, c.Run.MaxParallel, len(entries), func(i int) {
		entry, person := entries[i], c.Participants[i]
		work := filepath.Join(root, "work", "generate-"+entry.ID)
		_ = os.MkdirAll(work, 0755)
		_ = os.WriteFile(filepath.Join(work, "FEATURES.md"), mustRead(filepath.Join(root, "input", "FEATURES.md")), 0644)
		output := filepath.Join(work, entry.ID+".html")
		prompt := strings.ReplaceAll(tmpl, "{{OUTPUT}}", output)
		prompt = strings.ReplaceAll(prompt, "{{FEATURES}}", filepath.Join(work, "FEATURES.md"))
		err := invoke(ctx, c, person.Model, prompt, work, filepath.Join(root, "generation", person.ID+".log"))
		if err == nil {
			err = stageGeneratedHTML(work, output, filepath.Join(root, "entries", entry.ID+".html"))
		}
		mu.Lock()
		defer mu.Unlock()
		if err != nil {
			failed[entry.ID] = true
			fmt.Printf("  generation %-12s failed: %v\n", entry.ID, err)
		} else {
			fmt.Printf("  generation %-12s complete\n", entry.ID)
		}
	})
	return failed
}

func runJudges(ctx context.Context, c Config, root string, entries []Entry, tmpl string) ([]Score, []string) {
	all := []Score{}
	invalid := []string{}
	var mu sync.Mutex
	runParallel(ctx, c.Run.MaxParallel, len(c.Judges), func(i int) {
		judge := c.Judges[i]
		work := filepath.Join(root, "judges", judge.ID)
		_ = os.MkdirAll(filepath.Join(work, "entries"), 0755)
		_ = os.WriteFile(filepath.Join(work, "FEATURES.md"), mustRead(filepath.Join(root, "input", "FEATURES.md")), 0644)
		_ = os.WriteFile(filepath.Join(work, "SCORECARD.md"), mustRead(filepath.Join(root, "input", "SCORECARD.md")), 0644)
		for _, e := range entries {
			_ = copyFile(filepath.Join(root, "entries", e.ID+".html"), filepath.Join(work, "entries", e.ID+".html"))
		}
		prompt := strings.ReplaceAll(tmpl, "{{WORKSPACE}}", work)
		err := invoke(ctx, c, judge.Model, prompt, work, filepath.Join(work, "pi.log"))
		var parsed []Score
		if err == nil {
			parsed, err = parseScorecard(filepath.Join(work, "UX_SCORECARD.md"), judge.ID, entries)
		}
		mu.Lock()
		defer mu.Unlock()
		if err != nil {
			invalid = append(invalid, judge.ID)
			fmt.Printf("  judge %-17s invalid: %v\n", judge.ID, err)
		} else {
			all = append(all, parsed...)
			fmt.Printf("  judge %-17s complete\n", judge.ID)
		}
	})
	return all, invalid
}

func runParallel(ctx context.Context, n, count int, job func(int)) {
	jobs := make(chan int)
	var wg sync.WaitGroup
	for range n {
		wg.Add(1)
		go func() {
			defer wg.Done()
			for i := range jobs {
				job(i)
			}
		}()
	}
	for i := range count {
		jobs <- i
	}
	close(jobs)
	wg.Wait()
}

func invoke(ctx context.Context, c Config, model, prompt, work, logPath string) error {
	args := make([]string, len(c.Pi.Args))
	for i, arg := range c.Pi.Args {
		args[i] = strings.ReplaceAll(strings.ReplaceAll(arg, "{model}", model), "{prompt}", prompt)
	}
	var lastErr error
	for attempt := 1; attempt <= 3; attempt++ {
		log, err := os.OpenFile(logPath, os.O_CREATE|os.O_WRONLY|os.O_APPEND, 0644)
		if err != nil {
			return err
		}
		fmt.Fprintf(log, "\n--- Pi attempt %d of 3 ---\n", attempt)
		cmd := exec.CommandContext(ctx, c.Pi.Command, args...)
		cmd.Dir = work
		cmd.Stdout, cmd.Stderr = log, log
		lastErr = cmd.Run()
		log.Close()
		if lastErr == nil {
			return nil
		}
		if ctx.Err() != nil || attempt == 3 {
			break
		}
		time.Sleep(time.Duration(attempt) * 2 * time.Second)
	}
	return lastErr
}

func stageGeneratedHTML(work, assigned, destination string) error {
	if info, err := os.Stat(assigned); err == nil && info.Size() > 0 {
		return copyFile(assigned, destination)
	}
	matches, err := filepath.Glob(filepath.Join(work, "*.html"))
	if err != nil {
		return err
	}
	if len(matches) != 1 {
		return fmt.Errorf("expected assigned HTML file or exactly one HTML file in workspace; found %d", len(matches))
	}
	info, err := os.Stat(matches[0])
	if err != nil || info.Size() == 0 {
		return errors.New("generated HTML is empty")
	}
	return copyFile(matches[0], destination)
}
func copyFile(source, destination string) error {
	data, err := os.ReadFile(source)
	if err != nil {
		return err
	}
	return os.WriteFile(destination, data, 0644)
}
func mustRead(path string) []byte { data, _ := os.ReadFile(path); return data }

func parseScorecard(path, judge string, entries []Entry) ([]Score, error) {
	data, err := os.ReadFile(path)
	if err != nil {
		return nil, err
	}
	wanted := map[string]bool{}
	for _, e := range entries {
		wanted[e.ID] = true
	}
	found := map[string]bool{}
	var result []Score
	for _, line := range strings.Split(string(data), "\n") {
		cells := splitTable(line)
		if len(cells) != 9 || cells[0] == "UX File" || strings.HasPrefix(cells[0], "-") {
			continue
		}
		entryID := strings.TrimSuffix(cells[0], ".html")
		if !wanted[entryID] {
			if strings.HasPrefix(entryID, "ux-") {
				return nil, fmt.Errorf("unknown entry row: %s", cells[0])
			}
			continue
		}
		if found[entryID] {
			return nil, fmt.Errorf("duplicate row for %s", entryID)
		}
		var points [categories]int
		for i := range points {
			n, err := strconv.Atoi(cells[i+1])
			if err != nil || n < 1 || n > 10 {
				return nil, fmt.Errorf("invalid score for %s category %d", entryID, i+1)
			}
			points[i] = n
		}
		found[entryID] = true
		result = append(result, Score{Judge: judge, Entry: entryID, Points: points})
	}
	if len(found) != len(wanted) {
		return nil, fmt.Errorf("scorecard has %d of %d required entry rows", len(found), len(wanted))
	}
	return result, nil
}
func splitTable(line string) []string {
	line = strings.TrimSpace(line)
	if !strings.HasPrefix(line, "|") {
		return nil
	}
	raw := strings.Split(strings.Trim(line, "|"), "|")
	for i := range raw {
		raw[i] = strings.TrimSpace(raw[i])
	}
	return raw
}

func aggregate(runID string, c Config, entries []Entry, scores []Score, failed map[string]bool, invalid []string) Report {
	byEntry := map[string][]Score{}
	judgeOK := map[string]bool{}
	for _, score := range scores {
		byEntry[score.Entry] = append(byEntry[score.Entry], score)
		judgeOK[score.Judge] = true
	}
	judgeWeight := map[string]float64{}
	for _, j := range c.Judges {
		judgeWeight[j.ID] = j.Weight
	}
	report := Report{RunID: runID, InvalidJudges: invalid}
	for _, j := range c.Judges {
		if judgeOK[j.ID] {
			report.ValidJudges = append(report.ValidJudges, j.ID)
		}
	}
	for id := range failed {
		report.FailedEntries = append(report.FailedEntries, id)
	}
	sort.Strings(report.FailedEntries)
	for _, entry := range entries {
		var means [categories]float64
		totalJudgeWeight := 0.0
		for _, score := range byEntry[entry.ID] {
			totalJudgeWeight += judgeWeight[score.Judge]
			for i, point := range score.Points {
				means[i] += float64(point) * judgeWeight[score.Judge]
			}
		}
		for i := range means {
			means[i] /= totalJudgeWeight
		}
		final, weightTotal := 0.0, 0.0
		for i, mean := range means {
			final += mean * c.CategoryWeights[i]
			weightTotal += c.CategoryWeights[i]
		}
		report.Results = append(report.Results, Result{Entry: entry, Categories: means, Final: final / weightTotal})
	}
	sort.Slice(report.Results, func(i, j int) bool {
		if report.Results[i].Final == report.Results[j].Final {
			return report.Results[i].Entry.ID < report.Results[j].Entry.ID
		}
		return report.Results[i].Final > report.Results[j].Final
	})
	for i := range report.Results {
		report.Results[i].Rank = i + 1
	}
	return report
}

func writeReport(root string, report Report) error {
	data, err := json.MarshalIndent(report, "", "  ")
	if err != nil {
		return err
	}
	if err := os.WriteFile(filepath.Join(root, "results.json"), data, 0644); err != nil {
		return err
	}
	var b strings.Builder
	b.WriteString("# Design POC Tournament Results\n\n")
	b.WriteString("| Rank | Entry | Participant | Model | C1 | C2 | C3 | C4 | C5 | C6 | C7 | C8 | Final |\n| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |\n")
	for _, r := range report.Results {
		fmt.Fprintf(&b, "| %d | %s | %s | %s", r.Rank, r.Entry.ID, r.Entry.Participant, r.Entry.Model)
		for _, score := range r.Categories {
			fmt.Fprintf(&b, " | %.2f", score)
		}
		fmt.Fprintf(&b, " | **%.2f** |\n", r.Final)
	}
	if len(report.InvalidJudges) > 0 {
		fmt.Fprintf(&b, "\nInvalid judges excluded: %s.\n", strings.Join(report.InvalidJudges, ", "))
	}
	if len(report.FailedEntries) > 0 {
		fmt.Fprintf(&b, "\nFailed entries excluded: %s.\n", strings.Join(report.FailedEntries, ", "))
	}
	return os.WriteFile(filepath.Join(root, "RESULTS.md"), []byte(b.String()), 0644)
}
func printReport(w io.Writer, report Report, root string) {
	fmt.Fprintln(w, "\nFinal ranking:")
	for _, r := range report.Results {
		fmt.Fprintf(w, "%d. %-14s %-20s %.2f  %s.html\n", r.Rank, r.Entry.Participant, r.Entry.Model, r.Final, r.Entry.ID)
	}
}

const sampleConfig = `pi:
  command: pi
  args: ["--model", "omniroute/{model}", "--print", "--no-session", "--approve", "{prompt}"]
run:
  max_parallel: 2
participants:
  - id: mimo-v2-5-pro
    model: mimo-v2.5-pro
  - id: glm-5-2
    model: glm-5.2
judges:
  - id: kimi-k3
    model: kimi-k3
    weight: 1.0
  - id: radagast
    model: radagast
    weight: 1.0
category_weights: [1, 1, 1, 1, 1, 1, 1, 1]
`

const personaPrompt = `You are a senior product designer specializing in polished, intuitive web experiences. Prioritize clear user flows, visual hierarchy, accessibility, and realistic interface states.`

const generatePrompt = `Read {{FEATURES}} and design a polished UI/UX proof of concept for the described web page. Consider the complete user workflow and use mocked data only; do not implement data integrations or authentication. Create exactly one self-contained HTML file at {{OUTPUT}}. You may use inline CSS and JavaScript. Do not modify any other file.\n`
const judgePrompt = `You are conducting a blind UI/UX review. In {{WORKSPACE}}, read FEATURES.md, SCORECARD.md, and every anonymous HTML file in entries/. Evaluate only against the feature brief and rubric. Create exactly one file at UX_SCORECARD.md using the table template from SCORECARD.md. Score every entry with an integer from 1 to 10 in each category. Do not change entry IDs, add model identity guesses, or modify any other files.\n`
const scorecard = `# UX/UI Evaluation Scorecard

Read FEATURES.md for the application requirements. Evaluate every anonymous HTML file in entries/.

Rate each category from 1 to 10:

1. **User Goal Fit** — Does the screen help the user do the thing they came to do?
2. **Clarity & Information Hierarchy** — Is the purpose and priority clear in 3–5 seconds?
3. **Interaction & Flow** — Is the path smooth, with clear states and feedback?
4. **Visual Design Quality** — Typography, spacing, contrast, balance, and polish.
5. **Consistency & System Thinking** — Are patterns, language, and components consistent?
6. **Accessibility & Inclusiveness** — Contrast, font size, targets, keyboard and screen reader friendliness.
7. **Emotional Quality & Brand Fit** — Does the design fit the product’s intended feeling?
8. **Edge Cases & Error Handling** — Empty, loading, error, long-text, and destructive states.

Write a file named UX_SCORECARD.md. Use this exact header and score each entry with integer values from 1 to 10:

| UX File | Cat. 1 | Cat. 2 | Cat. 3 | Cat. 4 | Cat. 5 | Cat. 6 | Cat. 7 | Cat. 8 |
| ------- | ------ | ------ | ------ | ------ | ------ | ------ | ------ | ------ |
`
