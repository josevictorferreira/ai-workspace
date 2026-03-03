# Benchmark Runner Guide

Complete guide for running the Rails benchmark with LLM-based test fixing.

## Quick Start

```bash
# 1. Export your API key
export OPENAI_API_KEY="sk-..."

# 2. Run the fast benchmark (single branch)
MODEL=openai/gpt-4o bin/benchmark-runner-fast

# 3. Check results
cat .sisyphus/benchmark-results-fast.md
```

## Files

- `bin/benchmark-runner` - Full multi-branch benchmark
- `bin/benchmark-runner-fast` - Fast single-branch benchmark (v1/failing)
- `.sisyphus/benchmark-results.md` - Results from full runner
- `.sisyphus/benchmark-results-fast.md` - Results from fast runner

## Prerequisites

1. **Nix** installed with flakes enabled
2. **opencode CLI** in PATH
3. **API key** for your preferred provider

## Step-by-Step Instructions

### Step 1: Set Provider Credentials

Choose ONE method:

#### Method A: Environment Variables (Recommended)

```bash
# For OpenAI
export OPENAI_API_KEY="sk-your-key-here"

# For Anthropic
export ANTHROPIC_API_KEY="sk-ant-your-key-here"

# For Groq
export GROQ_API_KEY="gsk-your-key-here"

# For DeepSeek
export DEEPSEEK_API_KEY="sk-your-key-here"

# For OpenRouter
export OPENROUTER_API_KEY="sk-or-v1-your-key-here"

# For xAI
export XAI_API_KEY="xai-your-key-here"
```

#### Method B: Provider Config File

Create `~/benchmark-providers.json`:

```json
{
  "version": 1,
  "credentials": [
    {
      "provider": "openai",
      "type": "apiKey",
      "key": "sk-your-key-here"
    },
    {
      "provider": "anthropic",
      "type": "apiKey",
      "key": "sk-ant-your-key-here"
    }
  ]
}
```

Then use `--provider-config`:

```bash
bin/benchmark-runner-fast --provider-config ~/benchmark-providers.json
```

### Step 2: Choose Runner

#### Fast Runner (Recommended for testing)

Single branch (`v1/failing`) only, creates fix branch `v1/fix/{model}`.

```bash
# Basic usage
MODEL=openai/gpt-4o bin/benchmark-runner-fast

# With custom timeouts
MODEL=anthropic/claude-sonnet-4-5 bin/benchmark-runner-fast \
  --timeout-opencode-sec 3600 \
  --timeout-rspec-sec 600

# Keep worktrees for debugging
MODEL=groq/llama-3.1-70b bin/benchmark-runner-fast --keep-worktrees
```

#### Full Runner (All fail branches)

Processes all `v1/fail/*` branches, creates fix branches `v1/fix/{suffix}/{model}`.

```bash
# Run all fail branches
MODEL=openai/gpt-4o bin/benchmark-runner

# Run specific branch only
MODEL=anthropic/claude-sonnet-4-5 bin/benchmark-runner \
  --filter "removing-transaction"

# Skip existing fix branches
MODEL=groq/llama-3.1-70b bin/benchmark-runner --skip-existing
```

### Step 3: Monitor Progress

The script will output progress:

```
=== BASELINE: v1/working ===
Running rspec (baseline)... PASS

=== Processing: v1/fail/removing-transaction ===
Running rspec (pre)... FAIL (15 failures)
Generating PROMPT.md...
Running opencode...
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
| 2025-03-01-120000 | openai/gpt-4o | v1/fail/removing-transaction | v1/fix/removing-transaction/openai_gpt_4o | 1 | 0 | PASS | 15 |

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
| `--provider-config FILE` | JSON file with provider credentials | - |
| `--timeout-opencode-sec SEC` | Timeout for opencode run | 1800 (fast), 300 (full) |
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
| `MODEL` | **Yes** | Model to use (e.g., `openai/gpt-4o`, `anthropic/claude-sonnet-4-5`) |
| `OPENAI_API_KEY` | No* | OpenAI API key |
| `ANTHROPIC_API_KEY` | No* | Anthropic API key |
| `GROQ_API_KEY` | No* | Groq API key |
| `DEEPSEEK_API_KEY` | No* | DeepSeek API key |
| `OPENROUTER_API_KEY` | No* | OpenRouter API key |
| `XAI_API_KEY` | No* | xAI API key |

*One provider credential is required, either via env var or `--provider-config`.

## Troubleshooting

### "Error: MODEL env var required"

Set the MODEL variable:
```bash
MODEL=openai/gpt-4o bin/benchmark-runner-fast
```

### "Error: opencode not in PATH"

Install opencode CLI:
```bash
npm install -g @opencode/cli
# or
yarn global add @opencode/cli
```

### Provider authentication fails

Ensure your API key is set correctly:
```bash
# Test the key is set
echo $OPENAI_API_KEY

# If empty, set it again
export OPENAI_API_KEY="sk-..."
```

### RSpec times out

Increase timeout:
```bash
MODEL=openai/gpt-4o bin/benchmark-runner-fast --timeout-rspec-sec 600
```

### Opencode times out

Large models may need more time:
```bash
MODEL=anthropic/claude-opus-4 bin/benchmark-runner-fast --timeout-opencode-sec 7200
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
export ANTHROPIC_API_KEY="sk-ant-api03-..."

# 3. Run fast benchmark
MODEL=anthropic/claude-sonnet-4-5 bin/benchmark-runner-fast

# 4. View results
cat .sisyphus/benchmark-results-fast.md

# 5. Check the fix
git log v1/fix/anthropic_claude_sonnet_4_5 --oneline -3
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
│     → Ruby, PostgreSQL, opencode available                 │
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
│  3. Setup isolated opencode config                         │
│     → XDG_* dirs in worktree/.opencode-isolated/           │
│     → auth.json with provider credentials                  │
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
│  6. Run opencode (isolated, no user config)                │
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
3. **Opencode isolation** - XDG dirs redirected per worktree
4. **No user config pollution** - ~/.config/opencode is never touched
5. **Provider isolation** - auth.json created fresh each run

Your existing opencode configuration in `~/.config/opencode` and credentials in `~/.local/share/opencode/auth.json` are **never modified** during benchmark runs.