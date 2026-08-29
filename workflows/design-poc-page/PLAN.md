# Implementation Plan: Design POC Tournament CLI

## 1. Purpose

Build a local Go CLI that runs a repeatable UI/UX design tournament from a feature brief:

1. Multiple Pi coding agents, each using a configured model, independently create one self-contained HTML UI/UX proof of concept.
2. Multiple Pi judge agents score the generated HTML files against a common scorecard in a blind review.
3. The CLI validates the scorecards, applies configured category and judge weights, and prints and saves a ranked results table.

The product is a workflow runner, not a web application. HTML output is mocked, static demonstration material; it has no data integration requirement.

## 2. Decisions and Assumptions

### In scope

- A Go command-line application in this directory.
- Calling the locally installed `pi` executable as subprocesses.
- Parallel generation and parallel judging with bounded concurrency.
- Per-run directories holding every input, prompt, output, scorecard, log, and result needed to audit a tournament.
- A text TUI/progress display while commands run, plus Markdown/JSON result files.
- Configurable participant models, judges, weights, and prompt templates.

### Out of scope for the first version

- A browser UI.
- API/provider integrations inside this program. Pi owns authentication, provider selection, and model access.
- Rendering or automatically visually inspecting HTML with a browser/screenshot pipeline.
- Retrying failed agents automatically, resume support, historical analytics, or cross-run comparisons.
- Data integrations or production-ready application code in generated HTML.

### Choices requiring confirmation during implementation

1. **Pi non-interactive model syntax:** the implementation must use the actual installed Pi CLI flags/options for supplying a prompt and selecting a model. This plan represents it as an adapter command, rather than assuming a particular `pi` flag syntax.
2. **Weights:** default category and judge weights are all `1.0`. Configuration will allow changing them. A model’s final score is the weighted mean of its category scores across judges.
3. **Judges:** by default, judges are independent model configurations. A judge must not be the same *configured participant identity* as the entry it is evaluating if strict independence is required; the CLI will warn about overlaps but will not infer provider/model equivalence.

## 3. Success Criteria

A successful run can be reproduced and audited from its run directory and meets all of the following:

- Given `FEATURES.md` and a config with N participants, it produces exactly N entries named with anonymous IDs such as `ux-01.html` through `ux-NN.html`.
- Generation prompts instruct each agent to create only its assigned file.
- Every judge receives the same feature brief, scorecard rubric, and anonymous entries, without participant model names in its judging workspace or prompt.
- The CLI rejects malformed, missing, duplicate, non-numeric, or out-of-range (1–10) scores before aggregation.
- The final report maps anonymous entries back to configured participant labels only after all scorecards have been parsed.
- The terminal and saved final report show per-category totals, weighted scores, ranking, and any failed/skipped work.
- `go test ./...` validates parsing, validation, weighting, anonymity mapping, and command construction without invoking real models.

## 4. Repository Layout

Keep the implementation small and conventional:

```text
.
├── FEATURES.md                 # User-supplied product/feature brief
├── SCORECARD.md                # User-supplied evaluation rubric/template
├── tournament.yaml             # User-edited participants, judges, weights
├── prompts/
│   ├── generate.md.tmpl        # Prompt template for design agents
│   └── judge.md.tmpl           # Prompt template for judge agents
├── cmd/design-poc-page/
│   └── main.go
├── internal/
│   ├── config/                 # YAML loading and config validation
│   ├── runner/                 # Pi subprocess execution and concurrency
│   ├── workspace/              # Run directory creation/staging
│   ├── scoring/                # Scorecard parser, validation, aggregation
│   └── report/                 # Terminal, Markdown, and JSON reports
├── testdata/                   # Valid/invalid scorecard fixtures
├── runs/                       # Git-ignored tournament artifacts
├── go.mod
├── go.sum
└── PLAN.md
```

`runs/` must be added to `.gitignore`. `FEATURES.md`, `SCORECARD.md`, prompt templates, and sample configuration should be committed because they define a reproducible tournament.

The existing `flake.nix` should be extended only as needed to provide Go and the normal formatting/lint/test tools. No root-level workspace dependency files should be added.

## 5. Configuration

Use one declarative YAML configuration file. Keep it intentionally narrow:

```yaml
pi:
  command: pi
  # Exact Pi invocation is centralized here. Example placeholders only:
  prompt_args: ["--prompt", "{prompt}"]
  model_args: ["--model", "{model}"]

run:
  max_parallel: 4

participants:
  - id: claude
    model: provider/model-a
  - id: qwen
    model: provider/model-b

judges:
  - id: gandalf
    model: provider/judge-a
    weight: 1.0
  - id: fusion
    model: provider/judge-b
    weight: 1.0

category_weights:
  user_goal_fit: 1.0
  clarity_information_hierarchy: 1.0
  interaction_flow: 1.0
  visual_design_quality: 1.0
  consistency_system_thinking: 1.0
  accessibility_inclusiveness: 1.0
  emotional_quality_brand_fit: 1.0
  edge_cases_error_handling: 1.0
```

Validation rules:

- Participant and judge IDs are unique within their own lists and safe to use in filenames.
- At least one participant and one judge exist.
- Model strings and Pi command configuration are non-empty.
- All weights are positive numbers.
- `max_parallel` is at least one.
- Exactly the eight scorecard categories are configured; this prevents silently evaluating a changed rubric with stale aggregation logic.

The Pi command needs a configuration-driven argument template because Pi installations may differ. The runner replaces `{prompt}` and `{model}` with values and executes the resulting argument list directly (not through a shell), avoiding quoting and injection problems.

## 6. Run Workspace and Audit Trail

Each invocation creates a timestamped directory such as `runs/20260716-153045/`:

```text
runs/<run-id>/
├── input/
│   ├── FEATURES.md             # Immutable copy used by all agents
│   ├── SCORECARD.md            # Immutable rubric copy
│   └── tournament.yaml         # Immutable config copy
├── prompts/
│   ├── generate-claude.md
│   └── judge-gandalf.md
├── generation/
│   ├── claude.log
│   └── qwen.log
├── entries/                    # Blind-review source directory
│   ├── ux-01.html
│   └── ux-02.html
├── judges/
│   ├── gandalf/
│   │   ├── SCORECARD.md
│   │   └── pi.log
│   └── fusion/
│       ├── SCORECARD.md
│       └── pi.log
├── entry-map.private.json      # ux-01 -> participant ID/model; never staged to judges
├── results.json
├── RESULTS.md
└── manifest.json               # timestamps, statuses, commands with prompts redacted
```

Use a private mapping file rather than naming entries after models. The runner must never copy or symlink `entry-map.private.json`, generation logs, original output filenames, or participant configuration into a judge workspace.

The user can retain the run directory for auditability or remove it manually. The program should not delete past runs.

## 7. Generation Workflow

### 7.1 Prompt contract

`prompts/generate.md.tmpl` should be close to the supplied example, but standardized:

- Direct the agent to read the run-local `FEATURES.md`.
- Ask it to design the whole relevant user workflow with sound UI/UX patterns.
- Explicitly permit mocked data and JavaScript for interaction demonstrations.
- Explicitly exclude authentication and real integrations.
- Require one self-contained HTML document only, written to its assigned anonymous path (for example `entries/ux-03.html`).
- Prohibit edits outside that assigned output file.
- Require no external asset dependency where practical, so results can be opened locally.

The CLI writes each participant’s exact rendered prompt into `prompts/` before invoking Pi.

### 7.2 Execution

For each participant:

1. Assign a randomized, zero-padded anonymous entry ID after loading configuration. Do not base it on list order if avoiding predictable mapping matters; persist the mapping privately.
2. Create an isolated generation workspace containing only the copied feature brief and the assigned output location.
3. Render the generation template with the local feature path and assigned HTML path.
4. Invoke Pi with that participant’s configured model.
5. Capture stdout/stderr to a participant-specific log.
6. Verify that the assigned HTML file exists, is non-empty, and is the only intended generated deliverable.
7. Copy the verified file into `entries/<anonymous-id>.html`.

Run these jobs concurrently up to `run.max_parallel`. Show live statuses (`queued`, `running`, `succeeded`, `failed`) and elapsed time. A failed generation is recorded and excluded from judging; remaining entries continue.

A deliberately simple first implementation can use a separate working directory per participant. This avoids agents modifying each other’s work and makes the “only one HTML file” constraint enforceable through filesystem inspection.

## 8. Blind Judging Workflow

### 8.1 Judge workspace

After generation finishes, construct a fresh workspace for every judge containing only:

```text
FEATURES.md
SCORECARD.md
entries/
  ux-01.html
  ux-02.html
  ...
```

The copied rubric should tell the judge to write `UX_SCORECARD.md` in its own workspace. It must list only anonymous entry IDs. It must not include model identifiers, participant prompt files, logs, original workspaces, or any mapping file.

### 8.2 Judge prompt

`prompts/judge.md.tmpl` should:

- State that entries are anonymous and must be evaluated only against `FEATURES.md` and the rubric.
- Require all listed entries to be scored.
- Require exactly one Markdown file, `UX_SCORECARD.md`.
- Require integer scores from 1 through 10 for each of the eight categories.
- Instruct the judge not to add identity guesses or alter entry names.
- Include the scorecard template by reference or as a copied file, not dynamic model information.

The supplied scorecard example is appropriate as the initial `SCORECARD.md`, but correct its `FEATURES.md` path to match this project and keep its requested output filename consistent with the parser.

### 8.3 Execution

Run each judge subprocess in parallel with the same concurrency limit. Capture its output to `judges/<judge-id>/pi.log`, verify `UX_SCORECARD.md` exists, then parse it. Judge failures or invalid scorecards are reported and excluded from the aggregate, rather than producing guessed values.

If no valid judge scorecards remain, mark the run unsuccessful and do not declare a winner.

## 9. Scorecard Parsing and Aggregation

### 9.1 Strict scorecard format

The parser must locate the Markdown table with the required columns:

```text
| UX File | Cat. 1 | Cat. 2 | Cat. 3 | Cat. 4 | Cat. 5 | Cat. 6 | Cat. 7 | Cat. 8 |
```

Accept harmless Markdown formatting differences such as alignment separators and surrounding whitespace, but reject ambiguous output. For every generated entry, require exactly one row and exactly eight integer scores, each in the inclusive range 1–10. Reject unknown/missing/duplicate entry rows.

The judge can include notes outside the score table. The first version does not attempt to score or summarize free-text notes.

### 9.2 Formula

For entry `e`, category `c`, and valid judge `j`:

```text
category_mean(e, c) = sum(score(j, e, c) * judge_weight(j)) / sum(judge_weight(j))
final_score(e) = sum(category_mean(e, c) * category_weight(c)) / sum(category_weight(c))
```

This retains a 1.00–10.00 final-score scale. Save raw per-judge scores as well as computed category means and final scores.

Rank descending by final score. Break exact ties deterministically by:

1. Higher unweighted total across all raw category scores;
2. Higher User Goal Fit category mean;
3. Anonymous entry ID.

The report must state this tie-break policy.

## 10. CLI Interface

Keep the first release to two commands plus help:

```bash
# Create sample config, prompts, FEATURES.md, and SCORECARD.md if absent.
design-poc-page init

# Execute generation, judging, validation, and reporting.
design-poc-page run --config tournament.yaml
```

Useful minimal options for `run`:

```text
--config <path>       configuration file (default: tournament.yaml)
--features <path>     feature brief (default: FEATURES.md)
--scorecard <path>    rubric (default: SCORECARD.md)
--output <directory>  base run directory (default: runs)
--max-parallel <n>    override configured concurrency
```

Do not add flags for individual phases initially. The complete pipeline is the requested workflow, and fewer states reduce implementation and support complexity. If a run fails, its retained artifacts make manual diagnosis possible.

Terminal output should be concise: run ID, live job state transitions, valid/invalid judge count, and final ranking. `RESULTS.md` is the human-readable saved result; `results.json` is the machine-readable equivalent.

## 11. Implementation Phases

### Phase 1 — Project skeleton and static inputs

1. Initialize the Go module and add the CLI entry point.  
   **Verify:** `go run ./cmd/design-poc-page --help` succeeds.
2. Add `init`, sample `tournament.yaml`, prompt templates, a starter `FEATURES.md`, and the provided scorecard adapted to project-local paths.  
   **Verify:** `design-poc-page init` is idempotent and does not overwrite existing user files.
3. Add `.gitignore` coverage for `runs/`.  
   **Verify:** a created run directory does not appear in `git status`.

### Phase 2 — Configuration and run workspace

1. Implement typed config loading and validation.  
   **Verify:** table-driven tests accept a valid config and reject each invalid rule listed above.
2. Implement timestamped workspace creation, immutable input copies, random anonymous IDs, and the private mapping file.  
   **Verify:** a unit/integration test checks mapping is absent from a constructed judge workspace.
3. Write a manifest with version, timestamps, statuses, and redacted command metadata.  
   **Verify:** a failed test run still produces a readable manifest.

### Phase 3 — Pi generation runner

1. Implement one subprocess adapter with argument-template expansion, working directory assignment, output capture, context cancellation, and exit-status reporting.  
   **Verify:** unit tests use a fake executable/script and assert exact argument and working-directory handling.
2. Implement bounded concurrent participant execution and HTML output validation.  
   **Verify:** a fake run demonstrates no more than configured jobs running concurrently and correctly identifies missing output.
3. Stage successful output under anonymous names in `entries/`.  
   **Verify:** generated filenames/model labels do not appear in the staged entry HTML paths.

### Phase 4 — Blind judges and scorecard parser

1. Build isolated judge workspaces from anonymous entries and common inputs only.  
   **Verify:** fixture test confirms neither model labels nor `entry-map.private.json` is accessible from judge directories.
2. Run configured judges concurrently using their model settings and collect `UX_SCORECARD.md`.  
   **Verify:** fake judge commands write fixture scorecards that are collected into the correct judge directories.
3. Implement strict Markdown table parsing and validation.  
   **Verify:** tests cover valid rows, whitespace variations, missing rows, duplicate rows, unknown IDs, malformed columns, decimals, and scores outside 1–10.

### Phase 5 — Scoring and reports

1. Implement the weighted formulas, deterministic ranking, and handling of invalid/failed judges.  
   **Verify:** unit tests assert known example totals, unequal weights, ties, and all-judges-invalid failure.
2. Produce terminal output, `RESULTS.md`, and `results.json`.  
   **Verify:** golden-file tests check that reports include raw scores, category means, final score, rank, winner, participants revealed only here, and excluded judges.
3. Run `gofmt`, `go vet ./...`, and `go test ./...`.  
   **Verify:** all pass in the subproject’s Nix development shell.

### Phase 6 — Real smoke test and documentation

1. Configure two inexpensive participant models and one judge model using the actual local Pi CLI syntax.  
   **Verify:** a real run creates two HTML files, a valid scorecard, and a final result.
2. Manually inspect the judge workspace during/after the run.  
   **Verify:** no participant identity is exposed before the final report.
3. Add a concise `README.md` with prerequisites, Pi setup expectation, config example, command usage, artifact locations, and limitations.  
   **Verify:** a new user can run `init`, edit `FEATURES.md`/config, and execute a tournament using only the README.

## 12. Risks and Mitigations

| Risk | Mitigation |
| --- | --- |
| Pi CLI invocation differs by installed version | Keep Pi argument construction in config and validate it first with a fake executable plus a documented smoke test. |
| A generation agent writes files outside its designated target | Use separate generation workspaces; only copy the assigned verified HTML into `entries/`. |
| Judges infer authorship from filenames or metadata | Use randomized anonymous IDs, fresh judge workspaces, and exclude all identity-bearing files. Generated HTML itself may contain stylistic clues; this cannot be fully eliminated. |
| LLM judge output drifts from the table format | Use a strict prompt/template, retain raw output, validate it, and exclude invalid scorecards instead of silently repairing scores. |
| One high-weight judge dominates results unintentionally | Default every weight to `1.0`, show all weights in final reports, and require explicit config edits to change them. |
| Concurrent Pi jobs exhaust local/API capacity | Provide a conservative bounded `max_parallel` setting, defaulting to 4. |

## 13. Definition of Done

The work is complete when the Go binary can be built in this project’s Nix shell; `init` produces editable starter inputs; `run` orchestrates independent anonymous HTML generation and blind judging; score validation and weighted aggregation are covered by automated tests; and a real two-participant/one-judge smoke test produces an auditable ranked report without exposing participant identities to the judge.
