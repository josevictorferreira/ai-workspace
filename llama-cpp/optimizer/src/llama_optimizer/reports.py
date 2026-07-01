"""Feasible-Pareto selection facade for deterministic optimizer reports.

Public API re-exported for the report contract: the typed value objects live in
:mod:`llama_optimizer.report_models` and deterministic serialization lives in
:mod:`llama_optimizer.report_render`. This module owns weight validation, the
feasible-only candidate filter, Pareto domination, and the transparent balanced
score whose per-metric contributions reproduce the selected winner.
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING, Final, assert_never

from llama_optimizer import report_render
from llama_optimizer.report_models import (
    CandidateConfig,
    MetricContribution,
    MetricDirection,
    MetricSpec,
    ReportCandidate,
    ReportMetadata,
    ReportRequest,
    ReportResult,
    ReportWeightError,
)

if TYPE_CHECKING:
    from pathlib import Path

    from llama_optimizer.ledger_dump import AttemptDump, TrialDump

__all__ = [
    "CandidateConfig",
    "MetricContribution",
    "MetricDirection",
    "MetricSpec",
    "ReportCandidate",
    "ReportMetadata",
    "ReportRequest",
    "ReportResult",
    "ReportWeightError",
    "generate_report",
    "write_reports",
]

_REQUIRED: Final[dict[str, MetricDirection]] = {
    "prompt_throughput": MetricDirection.BENEFIT,
    "generation_throughput": MetricDirection.BENEFIT,
    "ttft_p95": MetricDirection.COST,
    "request_latency_p95": MetricDirection.COST,
    "quality_margin": MetricDirection.BENEFIT,
    "vram_headroom": MetricDirection.BENEFIT,
}
_KEYS: Final[dict[str, str]] = {
    "prompt_throughput": "prompt_throughput",
    "generation_throughput": "generation_throughput",
    "ttft_p95": "ttft_ms_p95",
    "request_latency_p95": "request_latency_ms_p95",
    "quality_margin": "quality_margin",
    "vram_headroom": "vram_headroom",
}

type _Scored = tuple[CandidateConfig, dict[str, float]]


def _normalized_specs(specs: tuple[MetricSpec, ...]) -> tuple[MetricSpec, ...]:
    names = tuple(item.name for item in specs)
    duplicates = sorted({name for name in names if names.count(name) > 1})
    if duplicates or set(names) != set(_REQUIRED):
        msg = f"duplicate metric names {duplicates}; required metrics {sorted(_REQUIRED)}"
        raise ReportWeightError(msg)
    invalid = [
        item.name
        for item in specs
        if item.direction is not _REQUIRED[item.name]
        or not math.isfinite(item.weight)
        or item.weight <= 0.0
    ]
    if invalid:
        msg = f"required metric directions and positive weights: {invalid}"
        raise ReportWeightError(msg)
    total = sum(item.weight for item in specs)
    return tuple(MetricSpec(item.name, item.direction, item.weight / total) for item in specs)


def _scored_attempt(trial: TrialDump) -> AttemptDump | None:
    eligible = [
        item
        for item in trial["attempts"]
        if item["phase"] == "succeeded"
        and item["outcome"] is None
        and not any(sample["breached"] for sample in item["telemetry"])
    ]
    if not eligible:
        return None
    return max(eligible, key=lambda item: (item["attempt_number"], item["attempt_id"]))


def _candidate_values(
    attempt: AttemptDump, specs: tuple[MetricSpec, ...]
) -> dict[str, float] | None:
    if any(_KEYS[item.name] not in attempt["metrics"] for item in specs):
        return None
    return {item.name: attempt["metrics"][_KEYS[item.name]] for item in specs}


def _dominates(
    left: dict[str, float], right: dict[str, float], specs: tuple[MetricSpec, ...]
) -> bool:
    weak: list[bool] = []
    strict: list[bool] = []
    for item in specs:
        match item.direction:
            case MetricDirection.BENEFIT:
                weak.append(left[item.name] >= right[item.name])
                strict.append(left[item.name] > right[item.name])
            case MetricDirection.COST:
                weak.append(left[item.name] <= right[item.name])
                strict.append(left[item.name] < right[item.name])
            case unreachable:
                assert_never(unreachable)
    return all(weak) and any(strict)


def _normalize(value: float, minimum: float, maximum: float, direction: MetricDirection) -> float:
    if maximum == minimum:
        return 1.0
    match direction:
        case MetricDirection.BENEFIT:
            return (value - minimum) / (maximum - minimum)
        case MetricDirection.COST:
            return (maximum - value) / (maximum - minimum)
        case unreachable:
            assert_never(unreachable)


def _score(
    candidate: _Scored, frontier: tuple[_Scored, ...], specs: tuple[MetricSpec, ...]
) -> ReportCandidate:
    contributions: list[MetricContribution] = []
    for item in specs:
        values = tuple(entry[1][item.name] for entry in frontier)
        minimum, maximum = min(values), max(values)
        value = candidate[1][item.name]
        normalized = round(_normalize(value, minimum, maximum, item.direction), 12)
        weight = round(item.weight, 12)
        contributions.append(
            MetricContribution(
                item.name,
                item.direction,
                value,
                minimum,
                maximum,
                normalized,
                weight,
                round(normalized * weight, 12),
            )
        )
    return ReportCandidate(
        config=candidate[0],
        metrics=tuple((item.name, candidate[1][item.name]) for item in specs),
        contributions=tuple(contributions),
        score=round(sum(item.contribution for item in contributions), 12),
    )


def _feasible(
    request: ReportRequest, specs: tuple[MetricSpec, ...]
) -> tuple[list[_Scored], list[str]]:
    trials = {item["config_id"]: item for item in request.ledger["trials"]}
    complete: list[_Scored] = []
    incomplete: list[str] = []
    for config in sorted(request.configs, key=lambda item: item.config_id):
        trial = trials.get(config.config_id)
        if config.constraint_violations or trial is None or trial["outcome"] is not None:
            continue
        attempt = _scored_attempt(trial)
        if attempt is None:
            continue
        values = _candidate_values(attempt, specs)
        if values is None:
            incomplete.append(config.config_id)
        else:
            complete.append((config, values))
    return complete, incomplete


def generate_report(request: ReportRequest) -> ReportResult:
    """Generate deterministic JSON and Markdown from an authoritative ledger dump."""
    specs = _normalized_specs(request.metrics)
    complete, incomplete = _feasible(request, specs)
    raw = tuple(
        candidate
        for candidate in complete
        if not any(
            other[0].config_id != candidate[0].config_id
            and _dominates(other[1], candidate[1], specs)
            for other in complete
        )
    )
    frontier = tuple(
        sorted((_score(item, raw, specs) for item in raw), key=lambda item: item.config.config_id)
    )
    selected = (
        min(frontier, key=lambda item: (-item.score, item.config.config_id)) if frontier else None
    )
    return report_render.result(request, frontier, selected, tuple(sorted(incomplete)))


def write_reports(request: ReportRequest, output_dir: Path) -> ReportResult:
    """Write report.json and report.md without mutating Nix sources."""
    result = generate_report(request)
    output_dir.mkdir(parents=True, exist_ok=True)
    _ = (output_dir / "report.json").write_text(result.json_text, encoding="utf-8")
    _ = (output_dir / "report.md").write_text(result.markdown_text, encoding="utf-8")
    return result
