# Benchmark Runner Guide

Complete guide for running the Rails benchmark with LLM-based test fixing.

## Quick Start

```bash
# 1. Export your API key
export OPENROUTER_API_KEY_BENCHMARK="sk-or-v1-..."

# 2. Run the fast benchmark (single branch)
MODEL=openrouter/qwen/qwen3.6-27b bin/benchmark-runner-fast

# 3. Check results
cat .sisyphus/benchmark-results-fast.md
```

## Files

- `bin/benchmark-interactive` - Interactive sandbox for driving pi by hand
- `bin/benchmark-runner` - Full multi-branch benchmark
- `bin/benchmark-runner-fast` - Fast single-branch benchmark (v1/failing)
- `bin/benchmark-models.json` - pi providers and models, shared by all three
- `.sisyphus/benchmark-results.md` - Results from full runner
- `.sisyphus/benchmark-results-fast.md` - Results from fast runner

## Prerequisites

1. **Nix** installed with flakes enabled
2. **pi CLI** in PATH
3. **API key** for your preferred provider

## Step-by-Step Instructions

### Step 1: Configure Models and Credentials

All three scripts read one file: `bin/benchmark-models.json`. It is a pi
[`models.json`](https://github.com/earendil-works/pi-mono/blob/main/docs/models.md),
copied into a throwaway agent dir on every run so your own `~/.pi/agent` is never touched.

**Adding a model.** pi already ships the full OpenRouter catalog, so for an
OpenRouter model you usually add nothing at all — just pass it:

```bash
MODEL=openrouter/qwen/qwen3.6-27b bin/benchmark-runner-fast
```

Check whether pi already knows a model:

```bash
pi --list-models | grep qwen3.6
```

If it is missing (a brand-new model, or your own endpoint), add an entry under the
right provider in `bin/benchmark-models.json`:

```json
{
  "providers": {
    "openrouter": {
      "apiKey": "$OPENROUTER_API_KEY_BENCHMARK",
      "models": [
        { "id": "vendor/brand-new-model", "name": "Brand New Model (OpenRouter)" }
      ]
    }
  }
}
```

Entries merge into pi's built-in catalog, so only declare what pi does not already
know — declaring a known model replaces its real metadata (context window, thinking
support) with generic defaults.

**Adding a provider.** Give it a `baseUrl`, an `api`, and an `apiKey`:

```json
"my-endpoint": {
  "api": "openai-completions",
  "baseUrl": "http://10.10.10.10:11434/v1",
  "apiKey": "local",
  "models": [{ "id": "some-model.gguf", "name": "Some Model (Local)" }]
}
```

`apiKey` supports `$ENV_VAR` interpolation and `!command` shell lookups. A provider
whose key does not resolve is dropped silently — it will not appear in `pi --list-models`.

**Credentials.** The catalog currently reads these from the environment:

```bash
export OPENROUTER_API_KEY_BENCHMARK="sk-or-v1-..."
export BAILIAN_CODING_PLAN_API_KEY="sk-..."
```

### Step 2: Choose Runner

#### Fast Runner (Recommended for testing)

Single branch (`v1/failing`) only, creates fix branch `v1/fix/{model}`.

```bash
# Basic usage
MODEL=openrouter/qwen/qwen3.6-27b bin/benchmark-runner-fast

# With custom timeouts
MODEL=openrouter/anthropic/claude-sonnet-4-5 bin/benchmark-runner-fast \
  --timeout-pi-sec 3600 \
  --timeout-rspec-sec 600

# Keep worktrees for debugging
MODEL=openrouter/openai/gpt-oss-20b bin/benchmark-runner-fast --keep-worktrees
```

#### Full Runner (All fail branches)

Processes all `v1/fail/*` branches, creates fix branches `v1/fix/{suffix}/{model}`.

```bash
# Run all fail branches
MODEL=openrouter/qwen/qwen3.6-27b bin/benchmark-runner

# Run specific branch only
MODEL=openrouter/anthropic/claude-sonnet-4-5 bin/benchmark-runner \
  --filter "removing-transaction"

# Skip existing fix branches
MODEL=openrouter/openai/gpt-oss-20b bin/benchmark-runner --skip-existing
```

### Step 3: Monitor Progress

The script will output progress:

```
=== BASELINE: v1/working ===
Running rspec (baseline)... PASS

=== Processing: v1/fail/removing-transaction ===
Running rspec (pre)... FAIL (15 failures)
Generating PROMPT.md...
Running pi...
Running rspec (post)... PASS
Auto-committing changes...
Done: v1/fail/removing-transaction -> PASS

=== Benchmark Complete ===
Results: .sisyphus/benchmark-results.md
Logs: .sisyphus/bench-logs/20250301-120000/
```

### Step 4: View Results

```bash
# View markdown table
cat .sisyphus/benchmark-results.md
# or
cat .sisyphus/benchmark-results-fast.md

# View detailed logs
ls .sisyphus/bench-logs/latest/
```

Results table format:

| Timestamp | Model | Fail Branch | Fix Branch | Pre RC | Post RC | Status | Fixed |
|-----------|-------|-------------|------------|--------|---------|--------|-------|
| 2025-03-01-120000 | openrouter/qwen/qwen3.6-27b | v1/fail/removing-transaction | v1/fix/removing-transaction/openai_gpt_4o | 1 | 0 | PASS | 15 |

### Step 5: Inspect Fix (Optional)

```bash
# View the fix branch
git log v1/fix/removing-transaction/openai_gpt_4o --oneline -5

# Diff the changes
git diff v1/fail/removing-transaction..v1/fix/removing-transaction/openai_gpt_4o

# Checkout to examine
git worktree add ../fix-worktree v1/fix/removing-transaction/openai_gpt_4o
```

## Available Options

### Common Options (Both Runners)

| Flag | Description | Default |
|------|-------------|---------|
| `--models-config FILE` | pi `models.json` with providers/models | `bin/benchmark-models.json` |
| `--timeout-pi-sec SEC` | Timeout for the pi run | 3600 (fast), 300 (full) |
| `--timeout-rspec-sec SEC` | Timeout for rspec | 300 (fast), 120 (full) |
| `--keep-worktrees` | Don't remove worktrees after run | - |
| `--worktree-root PATH` | Where to create worktrees | .sisyphus/worktrees* |
| `-h, --help` | Show help | - |

### Full Runner Only

| Flag | Description | Default |
|------|-------------|---------|
| `--branches GLOB` | Branch pattern to process | `v1/fail/*` |
| `--filter REGEX` | Only process matching branches | - |
| `--skip-existing` | Skip if fix branch exists | - |
| `--print-names` | Debug: show derived names only | - |
| `--require-env VAR` | Require env var (repeatable) | - |

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `MODEL` | **Yes** | `<provider>/<model id>` as pi names it, e.g. `openrouter/qwen/qwen3.6-27b` |
| `OPENROUTER_API_KEY_BENCHMARK` | No* | Key for the `openrouter` provider |
| `BAILIAN_CODING_PLAN_API_KEY` | No* | Key for the `bailian-coding-plan` provider |

*Whichever keys `bin/benchmark-models.json` references. Run `pi --list-models` to see
which providers resolved.

## Troubleshooting

### "Error: MODEL env var required"

Set the MODEL variable:
```bash
MODEL=openrouter/qwen/qwen3.6-27b bin/benchmark-runner-fast
```

### "Error: pi not in PATH"

Install the pi coding agent:
```bash
npm install -g @earendil-works/pi-coding-agent
```

### Provider authentication fails

A provider whose `apiKey` does not resolve is dropped silently. Confirm it loaded:

```bash
pi --list-models | grep '^openrouter'
```

If nothing comes back, the key is unset:
```bash
echo $OPENROUTER_API_KEY_BENCHMARK
export OPENROUTER_API_KEY_BENCHMARK="sk-or-v1-..."
```

### RSpec times out

Increase timeout:
```bash
MODEL=openrouter/qwen/qwen3.6-27b bin/benchmark-runner-fast --timeout-rspec-sec 600
```

### pi times out

Large models may need more time:
```bash
MODEL=openrouter/anthropic/claude-opus-4 bin/benchmark-runner-fast --timeout-pi-sec 7200
```

### Worktree already exists

Remove existing worktrees:
```bash
git worktree list
git worktree remove .sisyphus/worktrees-fast/...
rm -rf .sisyphus/worktrees-fast/
```

### Nix shell not activating

Ensure nix is installed with flakes:
```bash
nix --version  # Should show 2.4+
```

## Example: Complete Workflow

```bash
# 1. Navigate to repo
cd /home/josevictor/Workspace/ai-workspace/benchmarks/rails-inventory-system

# 2. Set your API key
export OPENROUTER_API_KEY_BENCHMARK="sk-or-v1-..."

# 3. Confirm pi can see the model
pi --list-models | grep qwen3.6-27b

# 4. Run fast benchmark
MODEL=openrouter/qwen/qwen3.6-27b bin/benchmark-runner-fast

# 5. View results
cat .sisyphus/benchmark-results-fast.md

# 6. Inspect what the agent did
jq -r 'select(.type=="tool_execution_start") | .toolName' \
  .sisyphus/bench-logs-fast/*/openrouter_qwen_qwen3_6_27b/pi.jsonl

# 7. Check the fix
git log v1/fix/openrouter_qwen_qwen3_6_27b --oneline -3
```

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│  User runs: MODEL=x bin/benchmark-runner-fast               │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│  1. Nix re-exec (enters devShell if not already)           │
│     → Ruby, PostgreSQL, pi available                       │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│  2. Create worktree for v1/failing                         │
│     → Isolated checkout at .sisyphus/worktrees-fast/...    │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│  3. Setup isolated pi agent dir                            │
│     → HOME + PI_CODING_AGENT_DIR in a throwaway sandbox    │
│     → models.json copied from bin/benchmark-models.json    │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│  4. Run rspec (pre) - count failures                       │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│  5. Generate PROMPT.md with failing tests                  │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│  6. Run pi (isolated, no user config)                      │
│     → LLM reads PROMPT.md and fixes code                   │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│  7. Run rspec (post) - check if fixed                      │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│  8. Auto-commit if PASS                                    │
│     → Creates commit on v1/fix/{model}                     │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│  9. Record results to .sisyphus/benchmark-results-fast.md  │
└─────────────────────────────────────────────────────────────┘
```

## Isolation Guarantees

The benchmark scripts ensure **complete isolation**:

1. **Git isolation** - Worktrees keep repo changes separate
2. **DB isolation** - TEST_ENV_NUMBER creates unique test databases
3. **pi isolation** - `HOME` and `PI_CODING_AGENT_DIR` point at a throwaway sandbox
4. **No user config pollution** - `~/.pi/agent` is never touched
5. **Provider isolation** - `models.json` copied fresh from `bin/benchmark-models.json` each run

Your existing pi configuration and credentials in `~/.pi/agent` are **never modified** during benchmark runs.