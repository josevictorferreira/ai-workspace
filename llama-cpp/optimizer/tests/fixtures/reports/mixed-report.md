# Optimizer report

**Status:** selected `beta`
**Run:** `run-10`
**Manifest:** `manifest-ornith-v1` (`bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb`)
**Resume mode:** `exact`

## Provenance and environment
- gpu=AMD Radeon
- optimizer=0.1.0
- profile=ornith
- rocm=6.4

## Drift diagnostics
- no drift detected

## Pareto frontier
- alpha: score=0.2
- beta: score=0.8

### `alpha`
- prompt_throughput: value=100, direction=benefit, min=90, max=100, normalized=1, weight=0.2, contribution=0.2
- generation_throughput: value=40, direction=benefit, min=40, max=45, normalized=0, weight=0.3, contribution=0
- ttft_p95: value=200, direction=cost, min=180, max=200, normalized=0, weight=0.15, contribution=0
- request_latency_p95: value=500, direction=cost, min=450, max=500, normalized=0, weight=0.15, contribution=0
- quality_margin: value=0.2, direction=benefit, min=0.2, max=0.3, normalized=0, weight=0.15, contribution=0
- vram_headroom: value=1000, direction=benefit, min=1000, max=2000, normalized=0, weight=0.05, contribution=0

### `beta`
- prompt_throughput: value=90, direction=benefit, min=90, max=100, normalized=0, weight=0.2, contribution=0
- generation_throughput: value=45, direction=benefit, min=40, max=45, normalized=1, weight=0.3, contribution=0.3
- ttft_p95: value=180, direction=cost, min=180, max=200, normalized=1, weight=0.15, contribution=0.15
- request_latency_p95: value=450, direction=cost, min=450, max=500, normalized=1, weight=0.15, contribution=0.15
- quality_margin: value=0.3, direction=benefit, min=0.2, max=0.3, normalized=1, weight=0.15, contribution=0.15
- vram_headroom: value=2000, direction=benefit, min=1000, max=2000, normalized=1, weight=0.05, contribution=0.05

## Incomplete candidates
- none

## Trials and failures
- alpha: scored
- beta: scored
- dominated: scored
- failed: crash

## Raw artifacts
- [raw/attempt-alpha/metrics.json](raw/attempt-alpha/metrics.json) — `aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa` (attempt-alpha)
- [raw/attempt-beta/metrics.json](raw/attempt-beta/metrics.json) — `aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa` (attempt-beta)
- [raw/attempt-dominated/metrics.json](raw/attempt-dominated/metrics.json) — `aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa` (attempt-dominated)
- [raw/attempt-failed/metrics.json](raw/attempt-failed/metrics.json) — `aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa` (attempt-failed)

## Reproduction commands
```console
nix develop .#optimizer --command uv run --project optimizer --frozen pytest optimizer/tests -q
```
