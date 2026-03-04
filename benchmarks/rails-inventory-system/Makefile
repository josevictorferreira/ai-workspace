.PHONY: benchmark clean-benchmark help

# Default model if none is specified
MODEL ?= openrouter/openai/gpt-oss-120b:exacto

# Compute the model slug for cleanup (matches script logic)
MODEL_SLUG = $(shell echo "$(MODEL)" | tr '[:upper:]' '[:lower:]' | tr -c 'a-z0-9' '_' | tr -s '_' | sed 's/^_\|_$$//g')

help:
	@echo "Model Benchmarking Automation"
	@echo ""
	@echo "Usage:"
	@echo "  make benchmark MODEL=<model_identifier>"
	@echo ""
	@echo "Examples:"
	@echo "  make benchmark MODEL=openrouter/openai/gpt-4o"
	@echo "  make benchmark MODEL=openrouter/anthropic/claude-3.5-sonnet"
	@echo ""
	@echo "Targets:"
	@echo "  benchmark        Clean old artifacts and run the benchmark for the specified MODEL"
	@echo "  clean-benchmark  Hard clean worktrees and branches for the current MODEL"

benchmark: clean-benchmark
	@echo "===> Starting benchmark for: $(MODEL)"
	@MODEL="$(MODEL)" ./bin/benchmark-runner-fast

clean-benchmark:
	@echo "===> Cleaning artifacts for: $(MODEL_SLUG)"
	@git worktree prune
	@rm -rf .sisyphus/worktrees-fast/fast-$(MODEL_SLUG)
	@git branch -D v1/fix/$(MODEL_SLUG) 2>/dev/null || true
