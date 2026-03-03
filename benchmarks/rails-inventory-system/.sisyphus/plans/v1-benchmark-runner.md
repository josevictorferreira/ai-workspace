# v1 benchmark runner (fail→fix via opencode)

## TL;DR
Build a **one-shot, zero-manual** runner that:
1) sanity-checks `v1/working` (green rspec), then 2) for each `v1/fail/*` branch creates `v1/fix/<fail-suffix>/<model_snake>` worktree, generates/reads `PROMPT.md` (includes failing rspec output), runs `opencode run`, re-runs rspec, auto-commits if needed, and appends PASS/FAIL into `.sisyphus/benchmark-results.md` + saves logs.

Deliverables:
- `bin/benchmark-runner` (or `script/benchmark-runner`) executable
- `.sisyphus/benchmark-results.md`
- `.sisyphus/bench-logs/*` (opencode + rspec logs per branch)

Effort: Medium
Parallelism: NO (sequential by design)
Critical path: env checks → baseline rspec → per-branch loop → results

---

## Context
- Repo: Rails 8.1 API-only. RSpec.
- Branches: `v1/working` (should be green) + 7 `v1/fail/*`.
- Runner requirements (user):
  - No manual steps.
  - Git mgmt inside script.
  - For each fail branch create fix branch named:
    - `v1/fix/{fail-branch-suffix}/{model-name-in-snake-case}`
  - Use per-branch `PROMPT.md` (created as part of this work).
  - Metric: PASS/FAIL only.
  - Artifacts: always save opencode logs + rspec outputs.
  - Isolation: git worktrees.
  - Model string provided via env var `MODEL=...`.

---

## Work Objectives
- Deterministic benchmark: same steps, same env vars, same artifacts.
- Strict non-interactive behavior: never hang on prompts.
- Per-branch DB isolation to prevent cross-branch pollution.

Defaults (unless flags override):
- Sequential execution (1 branch at a time).
- Script language: bash (`set -euo pipefail`) unless repo conventions demand Ruby.
- Non-interactive env always set for subprocesses:
  - `CI=true`, `GIT_TERMINAL_PROMPT=0`, `BUNDLE_WITHOUT=development` (if applicable), `RAILS_ENV=test` for rspec/db.
- Opencode invocation must be validated at runtime via `opencode run --help` and logged.

---

## Verification Strategy
- Automated tests exist: RSpec.
- Benchmark verification is **agent-executed** via bash only.
- For each branch run, record:
  - opencode exit code
  - rspec exit code
  - git status clean/dirty
  - commit SHA (if committed)
  - log paths

Evidence paths:
- `.sisyphus/bench-logs/<ts>/<branch>/<phase>.log`
- `.sisyphus/benchmark-results.md`

PASS/FAIL rules:
- Baseline: abort run if `v1/working` rspec rc != 0.
- Per branch: PASS iff post-rspec rc == 0 (regardless of opencode rc, but opencode rc recorded).

---

## Execution Strategy (waves)

Wave 1 (foundation + plumbing)
- Task 1: runner CLI + env checks + branch discovery
- Task 2: slugify model/branch + naming + idempotency rules
- Task 3: worktree mgmt + cleanup trap

Wave 2 (DB + rspec + prompt)
- Task 4: DB isolation strategy (TEST_ENV_NUMBER) + db prepare/drop
- Task 5: rspec runner + log capture + PASS/FAIL detection
- Task 6: PROMPT.md generator (includes failing rspec output)

Wave 3 (opencode + git + reporting)
- Task 7: opencode non-interactive invocation + timeout + logs
- Task 8: git branch creation/checkout + auto-commit policy
- Task 9: results table writer + per-branch artifact indexing

Wave 4 (hardening)
- Task 10: resume/skip semantics + failure handling + keep-worktree flags
- Task 11: end-to-end dry-run mode (single branch filter)

---

## TODOs

- [x] 1. Runner entrypoint + env gating + nix re-exec

  **What to do**:
  - Add executable runner (prefer `bin/benchmark-runner`).
  - Hard requirements (fail fast):
    - `MODEL` env var set (non-empty)
    - `opencode` in PATH
    - git repo clean enough for runner (no uncommitted changes in main checkout) OR runner supports `--allow-dirty`
  - If not already inside nix dev shell (`IN_NIX_SHELL` unset), re-exec itself via:
    - `nix develop --impure --command bash -lc 'MODEL=... bin/benchmark-runner --_in_nix ...'`
  - Add CLI flags (min):
    - `--branches "v1/fail/*"` (default)
    - `--filter <regex>` (run subset)
    - `--keep-worktrees`
    - `--worktree-root .sisyphus/worktrees`
    - `--timeout-opencode-sec <n>`
    - `--timeout-rspec-sec <n>`
    - `--require-env VAR` (repeatable; if set, enforce those vars exist before starting)

  **Must NOT do**:
  - No `git push`, no remote writes.
  - No force-delete branches.

  **Recommended Agent Profile**:
  - **Category**: quick
  - **Skills**: []

  **Parallelization**:
  - Can Run In Parallel: YES (with Tasks 2-3)
  - Blocks: 4-11

  **References**:
  - `flake.nix` (devShell + db helpers; runner should be able to self-enter nix)
  - `AGENTS.md` (repo intent + test command)

  **Acceptance Criteria**:
  - [ ] `MODEL=x bin/benchmark-runner --help` exits 0 and prints flags.
  - [ ] Running without `MODEL` exits non-zero with clear message.
  - [ ] `bin/benchmark-runner --require-env FOO` exits non-zero when `FOO` unset.

  **QA Scenarios**:
  ```
  Scenario: env gating
    Tool: Bash
    Steps:
      1. unset MODEL; bin/benchmark-runner --help >.sisyphus/bench-logs/q1.log 2>&1; echo $? >.sisyphus/bench-logs/q1.rc
      2. Assert rc != 0 and log contains "MODEL"
    Evidence: .sisyphus/bench-logs/q1.log
  ```

- [x] 2. Deterministic naming: model_snake + fix branch names

  **What to do**:
  - Convert `MODEL` to snake_case for branch suffix (example rules):
    - lowercase
    - `/` and `:` and `@` and spaces → `_`
    - collapse repeats, trim `_`
  - Derive `fail_suffix` from `v1/fail/<suffix>`.
  - Fix branch name: `v1/fix/<fail_suffix>/<model_snake>`.
  - Decide idempotency:
    - if fix branch exists: default `--skip-existing` (record SKIPPED), optional `--overwrite` (delete/recreate) guarded.

  **Must NOT do**:
  - Never delete non-`v1/fix/*` branches.

  **Recommended Agent Profile**:
  - **Category**: quick
  - **Skills**: []

  **Parallelization**:
  - Can Run In Parallel: YES (with Tasks 1,3)
  - Blocks: 7-9

  **References**:
  - User requirement: `v1/fix/{fail-branch-suffix}/{model-name-in-snake-case}`.

  **Acceptance Criteria**:
  - [ ] `MODEL='anthropic/claude-sonnet-4-5'` → `model_snake='anthropic_claude_sonnet_4_5'`.

  **QA Scenarios**:
  ```
  Scenario: naming
    Tool: Bash
    Steps:
      1. MODEL='anthropic/claude-sonnet-4-5' bin/benchmark-runner --print-names v1/fail/removing-transaction >.sisyphus/bench-logs/q2.txt
      2. Assert output contains "v1/fix/removing-transaction/anthropic_claude_sonnet_4_5"
    Evidence: .sisyphus/bench-logs/q2.txt
  ```

- [x] 3. Worktree lifecycle + cleanup trap

  **What to do**:
  - Create worktree per fix branch under `.sisyphus/worktrees/<fail_suffix>/<model_snake>/`.
  - Implement `trap` cleanup:
    - on EXIT/INT/TERM: if worktree created and not `--keep-worktrees`, remove it.
    - never remove user worktrees outside `.sisyphus/worktrees`.
  - Ensure runner is re-runnable:
    - if directory exists and is a worktree, handle per `--skip-existing`.

  **Recommended Agent Profile**:
  - **Category**: quick
  - **Skills**: ["git-master"]

  **Parallelization**:
  - Can Run In Parallel: YES (with Tasks 1-2)
  - Blocks: 4-11

  **References**:
  - `git worktree` (must use add/remove, no interactive flags)

  **Acceptance Criteria**:
  - [ ] After a forced failure, `git worktree list | grep .sisyphus/worktrees` is empty (unless `--keep-worktrees`).

  **QA Scenarios**:
  ```
  Scenario: cleanup on failure
    Tool: Bash
    Steps:
      1. MODEL=x bin/benchmark-runner --filter removing-transaction --timeout-opencode-sec 1 || true
      2. Assert: git worktree list does not include .sisyphus/worktrees (unless keep flag used)
    Evidence: .sisyphus/bench-logs/q3.log
  ```

- [x] 4. DB isolation per branch run (TEST_ENV_NUMBER) + db prepare/drop

  **What to do**:
  - Use DB isolation via `TEST_ENV_NUMBER` (database.yml uses `inventory_system_test<TEST_ENV_NUMBER>` + `_queue`).
  - Per branch run, set `TEST_ENV_NUMBER=bench_<shortslug>`.
    - `shortslug` must be `[a-z0-9]+` and short (<= 12) to keep DB name < 63 chars.
  - In each worktree, before rspec:
    - run `bin/rails db:prepare` in `RAILS_ENV=test` (ensures schema up-to-date)
  - After branch run, drop isolated DBs (best-effort, never fail run on drop errors):
    - try Rails tasks for multi-db drop (prefer):
      - `RAILS_ENV=test TEST_ENV_NUMBER=... bin/rails db:drop`
      - if queue DB not dropped, try `db:drop:queue` / `db:drop:all` / `db:drop:primary` variants (detect via `bin/rails -T db:drop`).
    - fallback: use `dropdb` (from nix devshell) for:
      - `inventory_system_test${TEST_ENV_NUMBER}`
      - `inventory_system_test${TEST_ENV_NUMBER}_queue`
  - Ensure no cross-branch DB contamination.

  **Must NOT do**:
  - Do not touch production DB settings.

  **Recommended Agent Profile**:
  - **Category**: unspecified-high
  - **Skills**: []

  **Parallelization**:
  - Can Run In Parallel: NO (depends on worktree + sequential loop)
  - Blocked By: 1-3
  - Blocks: 5-11

  **References**:
  - `config/database.yml` (test DB names via `TEST_ENV_NUMBER`, queue DB also)
  - `spec/rails_helper.rb` (`maintain_test_schema!` requires migrations applied)
  - `flake.nix` shellHook exports local DB env vars (`INVENTORY_SYSTEM_DATABASE_*`)

  **Acceptance Criteria**:
  - [ ] For two different fail branches, DB names differ (via different `TEST_ENV_NUMBER`).
  - [ ] `bundle exec rspec` does not fail due to pending migrations.

  **QA Scenarios**:
  ```
  Scenario: isolated test db
    Tool: Bash
    Steps:
      1. In one worktree: TEST_ENV_NUMBER=_bench_a RAILS_ENV=test bin/rails db:prepare
      2. In another:   TEST_ENV_NUMBER=_bench_b RAILS_ENV=test bin/rails db:prepare
      3. Assert both complete 0
    Evidence: .sisyphus/bench-logs/task4-db-prepare.log
  ```

- [x] 5. RSpec runner wrapper + PASS/FAIL capture + log files

  **What to do**:
  - Implement helper to run rspec with:
    - `bundle exec rspec` (no custom formatters unless needed)
    - redirect stdout+stderr to a log file
    - capture exit code reliably
    - enforce timeout (`timeout <n>s ...`) to prevent hangs
  - For each run record:
    - exit code
    - elapsed time
    - PASS/FAIL status (PASS iff exit 0)
  - Store logs under `.sisyphus/bench-logs/<ts>/<branch>/rspec-{pre,post}.log`.
  - Reduce repeated bundler installs across worktrees:
    - set `BUNDLE_PATH` (and optionally `GEM_HOME`) to a shared cache dir under `.sisyphus/bundle-cache/` for the duration of the run.

  **Recommended Agent Profile**:
  - **Category**: quick
  - **Skills**: []

  **Parallelization**:
  - Can Run In Parallel: YES (with Task 6)
  - Blocked By: 4
  - Blocks: 6-9

  **References**:
  - `AGENTS.md` suggests `bundle exec rspec`.

  **Acceptance Criteria**:
  - [ ] If rspec passes, status recorded as PASS and rc=0.
  - [ ] If rspec fails, status recorded as FAIL and rc!=0.

  **QA Scenarios**:
  ```
  Scenario: capture failure
    Tool: Bash
    Preconditions: run on known failing branch
    Steps:
      1. MODEL=x bin/benchmark-runner --filter removing-transaction --dry-run-rspec-only
      2. Assert: rspec-pre.log exists and results table marks FAIL
    Evidence: .sisyphus/bench-logs/<ts>/.../rspec-pre.log
  ```

- [x] 6. PROMPT.md generation per fail branch (include failing rspec output)

  **What to do**:
  - On fail branch worktree before opencode:
    - run rspec once (pre)
    - generate `PROMPT.md` at repo root in that worktree.
  - `PROMPT.md` should include (minimal but sufficient):
    - repo context (Rails 8.1 API-only, see AGENTS.md summary)
    - branch under repair
    - explicit instruction: goal is `bundle exec rspec` green; do not change intended business rules; avoid scope creep
    - include failing rspec output (full output or at least failure summary + backtraces)
    - include explicit non-interactive constraints: commit changes if needed; no user questions; run tests
  - Ensure PROMPT.md generation is deterministic.

  **Must NOT do**:
  - Do not include secrets.

  **Recommended Agent Profile**:
  - **Category**: quick
  - **Skills**: []

  **Parallelization**:
  - Can Run In Parallel: YES (with Task 5)
  - Blocked By: 5
  - Blocks: 7

  **References**:
  - `AGENTS.md` for domain invariants to include in prompt.

  **Acceptance Criteria**:
  - [ ] Each branch run has a `PROMPT.md` saved in its worktree.
  - [ ] `PROMPT.md` contains the rspec-pre log (or excerpt) used.

  **QA Scenarios**:
  ```
  Scenario: prompt contains rspec failures
    Tool: Bash
    Steps:
      1. Run one branch with `--stop-after-prompt`
      2. Assert: worktree/PROMPT.md exists and includes string "Failures:" or failing example lines
    Evidence: .sisyphus/bench-logs/<ts>/.../prompt-check.log
  ```

- [ ] 7. opencode run invocation (non-interactive) + timeout + log capture

  **What to do**:
  - Invoke opencode in worktree using prompt content:
    - `opencode run` with model from `MODEL`.
    - feed prompt via file or stdin (whichever opencode supports).
    - runner should auto-detect supported flags once at startup by parsing `opencode run --help` and choose one of:
      - `opencode run --prompt-file PROMPT.md ...`
      - `opencode run --prompt "$(cat PROMPT.md)" ...`
      - `opencode run < PROMPT.md ...`
    - set a hard timeout (tool `timeout`) to prevent hangs
    - capture stdout+stderr to `.sisyphus/bench-logs/<ts>/<branch>/opencode.log`
  - Ensure opencode runs in the worktree root so it modifies correct checkout.
  - After opencode, record:
    - exit code
    - duration

  **Guardrails**:
  - If opencode exits non-zero, mark branch as FAIL and continue.

  **Recommended Agent Profile**:
  - **Category**: unspecified-high
  - **Skills**: []

  **Parallelization**:
  - Can Run In Parallel: NO
  - Blocked By: 6
  - Blocks: 8-9

  **References**:
  - Validate actual flags with `opencode run --help` (script can do this at startup and log).

  **Acceptance Criteria**:
  - [ ] opencode logs saved for each branch.
  - [ ] opencode cannot hang beyond timeout.

  **QA Scenarios**:
  ```
  Scenario: opencode timeout
    Tool: Bash
    Steps:
      1. MODEL=x bin/benchmark-runner --filter removing-transaction --timeout-opencode-sec 1
      2. Assert: opencode log exists and status recorded (FAIL/ERROR) without hanging
    Evidence: .sisyphus/bench-logs/<ts>/.../opencode.log
  ```

- [ ] 8. Git branch mgmt + auto-commit policy

  **What to do**:
  - For each fail branch:
    - create fix branch name per Task 2 from fail branch tip
    - add worktree at fix branch
  - After opencode + rspec-post:
    - if rspec PASS and `git status --porcelain` non-empty → commit
    - commit includes: all changes, message format in Commit Strategy
    - record resulting commit SHA
  - If rspec FAIL: do not commit by default (optional `--commit-failing` flag).

  **Must NOT do**:
  - No push.
  - No force operations.

  **Recommended Agent Profile**:
  - **Category**: quick
  - **Skills**: ["git-master"]

  **Parallelization**:
  - Can Run In Parallel: NO
  - Blocked By: 7
  - Blocks: 9

  **References**:
  - Git safety constraints: non-interactive, no force.

  **Acceptance Criteria**:
  - [ ] On PASS+dirty, fix branch has 1 new commit and clean status.
  - [ ] On FAIL, status recorded and no commit (default).

  **QA Scenarios**:
  ```
  Scenario: auto-commit on pass
    Tool: Bash
    Steps:
      1. Run a branch expected to be fixable
      2. Assert: git log -1 shows bench(fix) msg; git status clean
    Evidence: .sisyphus/bench-logs/<ts>/.../git.log
  ```

- [ ] 9. Results writer: `.sisyphus/benchmark-results.md` + artifact index

  **What to do**:
  - Create/overwrite results file at start with header + table:
    - columns: timestamp, model, fail branch, fix branch, opencode rc, rspec pre rc, rspec post rc, status (PASS/FAIL/ERROR/SKIPPED), commit sha, log dir
  - Append one row per branch at end of each branch run (even on failure).
  - Also write a baseline row for `v1/working` (branch column = `v1/working`, fix branch empty) with rspec rc.
  - Ensure markdown is valid and stable for later parsing.

  **Recommended Agent Profile**:
  - **Category**: quick
  - **Skills**: []

  **Parallelization**:
  - Can Run In Parallel: YES (with Task 10)
  - Blocked By: 5-8
  - Blocks: 11, F1

  **Acceptance Criteria**:
  - [ ] Results file exists and has 7 rows after full run.
  - [ ] Results file includes a baseline row for `v1/working`.
  - [ ] Each row’s log dir exists.

  **QA Scenarios**:
  ```
  Scenario: results table
    Tool: Bash
    Steps:
      1. MODEL=x bin/benchmark-runner --filter removing-transaction
      2. Assert: grep 'removing-transaction' .sisyphus/benchmark-results.md
    Evidence: .sisyphus/benchmark-results.md
  ```

- [ ] 10. Hardening: resume/skip, crash-safety, keep-worktrees

  **What to do**:
  - Support `--skip-existing` default:
    - if fix branch already exists, record SKIPPED and continue.
  - Support `--resume`:
    - if results already has a row for branch+model, skip.
  - Implement crash-safe trap:
    - always write partial results.
    - always flush logs.

  **Recommended Agent Profile**:
  - **Category**: unspecified-high
  - **Skills**: []

  **Parallelization**:
  - Can Run In Parallel: YES (with Task 9)
  - Blocks: 11

  **Acceptance Criteria**:
  - [ ] Interrupting run (SIGINT) still leaves a valid markdown results file.

  **QA Scenarios**:
  ```
  Scenario: interrupt
    Tool: Bash
    Steps:
      1. Start runner in background; kill after first branch
      2. Assert: benchmark-results.md exists and is valid markdown table
    Evidence: .sisyphus/bench-logs/interrupt.log
  ```

- [ ] 11. End-to-end validation mode (baseline + single-branch)

  **What to do**:
  - Baseline step:
    - checkout (or worktree) `v1/working`
    - run `bundle exec rspec` (with DB isolated too, via TEST_ENV_NUMBER)
    - if baseline fails → abort benchmark run and write failure row "BASELINE".
  - Single-branch mode (`--filter`) must run full loop for 1 branch.

  **Recommended Agent Profile**:
  - **Category**: unspecified-high
  - **Skills**: []

  **Parallelization**:
  - Can Run In Parallel: NO
  - Blocked By: 1-10

  **Acceptance Criteria**:
  - [ ] `MODEL=x bin/benchmark-runner --filter removing-transaction` completes and writes 1 row.

  **QA Scenarios**:
  ```
  Scenario: baseline abort
    Tool: Bash
    Steps:
      1. Temporarily set an invalid DB host env var
      2. Run runner; assert it aborts during baseline with clear message
    Evidence: .sisyphus/bench-logs/baseline.log
  ```

---

## Final Verification Wave
- F1: run full benchmark across all 7 branches; ensure results table + logs present; ensure no leftover worktrees.

---

## Commit Strategy
- Script should commit only on fix branches and only if:
  - rspec PASS AND working tree dirty.
- Commit msg: `bench(fix): <fail-branch-suffix> via <model>`.

---

## Success Criteria
- `MODEL=... bin/benchmark-runner` completes with exit 0 when baseline green and runner executed.
- `.sisyphus/benchmark-results.md` has 1 row per fail branch.
- Each row references existing opencode + rspec logs.
- `git worktree list` shows no leftover benchmark worktrees (unless `--keep-worktrees`).
