# Benchmarks

This directory contains LLM evaluation suites used to compare models on coding, data extraction, Rails application repair, and frontend generation tasks. Each benchmark is a self-contained subproject.

## Layout

```
benchmarks/
├── coding-auto-complete/       # Coding completion/model ranking data
├── rails-inventory-system/     # Rails API repair benchmark
├── real-estate-normalizer/     # Real-estate data extraction (Python)
├── real-estate-normalizer-v2/  # Variant of the normalizer
└── real-estate-page-design/    # HTML page generation benchmark
```

## Shared Patterns

- **Input**: Most Python benchmarks read `PROMPT.md` for instructions and `data.json` for the dataset.
- **Output**: Results land in `outputs/`.
- **Credentials**: API keys come from environment variables (`OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `OPENROUTER_API_KEY`, etc.) or from `~/benchmark-providers.json`.
- **Automation**: Some suites generate `.sisyphus/` artifacts, worktrees, and branches. Know whether you are cleaning transient artifacts or deleting valuable results.

## Running Benchmarks

### Rails Inventory System

```bash
cd benchmarks/rails-inventory-system

# Automated single-branch benchmark
make benchmark MODEL=openrouter/openai/gpt-4o

# Interactive manual benchmark
make benchmark-manual
```

See [`rails-inventory-system/AGENTS.md`](rails-inventory-system/AGENTS.md) for Rails-specific setup and testing.

### Python Benchmarks (Real-Estate Normalizer / v2)

```bash
cd benchmarks/real-estate-normalizer
python run_benchmarks.py --model openai/gpt-4o
```

Add `--openrouter` when the model identifier is an OpenRouter route.

### Coding Auto-Complete

This benchmark is primarily data-driven (`openrouter_models.json`, `index.html`, CSVs, and Markdown reports). It does not have a standalone runner script in this directory; it is consumed by external ranking or comparison workflows.

### Real-Estate Page Design

A design-generation benchmark that produces HTML pages and evaluation plans. Check `PROMPT.md` and the `pages/`/`plans/` directories for the current task definition.

## Environment Setup

Set one or more provider keys before running:

```bash
export OPENAI_API_KEY="sk-..."
export ANTHROPIC_API_KEY="sk-ant-..."
export OPENROUTER_API_KEY="sk-or-v1-..."
export GROQ_API_KEY="gsk-..."
export DEEPSEEK_API_KEY="sk-..."
export XAI_API_KEY="xai-..."
```

Or create `~/benchmark-providers.json`:

```json
{
  "version": 1,
  "credentials": [
    {
      "provider": "openai",
      "type": "apiKey",
      "key": "sk-..."
    }
  ]
}
```

## Common Gotchas

- Never commit API keys. They must stay in the environment or in `~/benchmark-providers.json`.
- `outputs/`, `__pycache__/`, `.sisyphus/`, and worktree directories are ignored by Git but can clutter `git status`.
- Rails benchmarks mutate Git worktrees and branches; use `make clean-benchmark` carefully.
- Run a small/cheap model before burning quota on a full benchmark sweep.
