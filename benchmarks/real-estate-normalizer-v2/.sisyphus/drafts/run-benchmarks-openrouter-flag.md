# Draft: run_benchmarks uses OpenRouter without --openrouter

## Requirements (confirmed)
- Symptom: running `python3 run_benchmarks.py --model="nuextract-2.0-4b"` (no `--openrouter`) still calls OpenRouter.
- Error: 404 to `https://openrouter.ai/api/v1/chat/completions/v1/chat/completions` (note duplicated path).

## Technical Decisions
- TBD

## Research Findings
- TBD

## Open Questions
- What should default provider be when `--openrouter` omitted?
- Is `nuextract-2.0-4b` intended to run via OpenRouter or via another backend?
- What other flags/env vars influence provider selection?

## Scope Boundaries
- INCLUDE: fix provider selection + URL construction so OpenRouter only used when intended.
- EXCLUDE: model quality/benchmark logic changes.
