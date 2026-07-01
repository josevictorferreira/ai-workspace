"""Deterministic JSON and Markdown rendering for optimizer reports."""

from __future__ import annotations

import copy
import json
from typing import TYPE_CHECKING

from llama_optimizer.report_models import (
    CandidateConfig,
    ReportCandidate,
    ReportRequest,
    ReportResult,
)

if TYPE_CHECKING:
    from llama_optimizer.ledger_dump import LedgerDump


def _config(config: CandidateConfig) -> dict[str, object]:
    return {
        "config_id": config.config_id,
        "constraint_violations": sorted(config.constraint_violations),
        "model_path": config.model_path,
        "nix_package": config.nix_package,
        "server_flags": list(config.server_flags),
    }


def _candidate(candidate: ReportCandidate) -> dict[str, object]:
    return {
        "config": _config(candidate.config),
        "contributions": [
            {
                "contribution": item.contribution,
                "direction": item.direction.value,
                "maximum": item.maximum,
                "minimum": item.minimum,
                "name": item.name,
                "normalized": item.normalized,
                "value": item.value,
                "weight": item.weight,
            }
            for item in candidate.contributions
        ],
        "metrics": dict(candidate.metrics),
        "score": candidate.score,
    }


def _ledger(ledger: LedgerDump) -> LedgerDump:
    result = copy.deepcopy(ledger)
    result["trials"].sort(key=lambda item: (item["config_id"], item["trial_id"]))
    for trial in result["trials"]:
        trial["attempts"].sort(key=lambda item: (item["attempt_number"], item["attempt_id"]))
        for attempt in trial["attempts"]:
            attempt["telemetry"].sort(key=lambda item: item["sampled_at"])
            attempt["artifacts"].sort(key=lambda item: (item["kind"], item["relative_path"]))
    result["checkpoints"].sort(key=lambda item: item["generation"])
    return result


def _metric_lines(candidate: ReportCandidate) -> list[str]:
    return [
        "- "
        + f"{item.name}: value={item.value:.12g}, direction={item.direction.value}, "
        + f"min={item.minimum:.12g}, max={item.maximum:.12g}, "
        + f"normalized={item.normalized:.12g}, weight={item.weight:.12g}, "
        + f"contribution={item.contribution:.12g}"
        for item in candidate.contributions
    ]


def markdown(
    request: ReportRequest,
    frontier: tuple[ReportCandidate, ...],
    selected: ReportCandidate | None,
    incomplete: tuple[str, ...],
) -> str:
    """Render the human-readable audit report."""
    status = (
        "no feasible candidate" if selected is None else f"selected `{selected.config.config_id}`"
    )
    metadata = request.metadata
    lines = [
        "# Optimizer report",
        "",
        f"**Status:** {status}",
        f"**Run:** `{request.ledger['run_id']}`",
        f"**Manifest:** `{metadata.manifest_id}` (`{metadata.manifest_hash}`)",
        f"**Resume mode:** `{metadata.resume_mode}`",
        "",
        "## Provenance and environment",
        *[f"- {item}" for item in sorted((*metadata.provenance, *metadata.environment))],
        "",
        "## Drift diagnostics",
        *[f"- {item}" for item in sorted(metadata.drift_diagnostics)],
        "",
        "## Pareto frontier",
    ]
    lines.extend(
        [f"- {item.config.config_id}: score={item.score:.12g}" for item in frontier]
        or ["No feasible candidate reached the complete finalist frontier."]
    )
    for candidate in frontier:
        lines.extend(["", f"### `{candidate.config.config_id}`", *_metric_lines(candidate)])
    lines.extend(["", "## Incomplete candidates"])
    lines.extend([f"- {item}" for item in incomplete] or ["- none"])
    lines.extend(["", "## Trials and failures"])
    configs = {item.config_id: item for item in request.configs}
    for trial in sorted(request.ledger["trials"], key=lambda item: item["config_id"]):
        config = configs.get(trial["config_id"])
        outcome = trial["outcome"] or "scored"
        violations = "" if config is None else ", ".join(config.constraint_violations)
        lines.append(
            f"- {trial['config_id']}: {outcome}" + (f"; {violations}" if violations else "")
        )
    lines.extend(["", "## Raw artifacts"])
    artifacts = sorted(
        (entry["relative_path"], entry["content_hash"], attempt["attempt_id"])
        for trial in request.ledger["trials"]
        for attempt in trial["attempts"]
        for entry in attempt["artifacts"]
    )
    lines.extend(
        [f"- [{path}]({path}) — `{digest}` ({attempt})" for path, digest, attempt in artifacts]
        or ["- none"]
    )
    lines.extend(["", "## Reproduction commands"])
    lines.extend(f"```console\n{item}\n```" for item in metadata.reproduction_commands)
    return "\n".join([*lines, ""])


def result(
    request: ReportRequest,
    frontier: tuple[ReportCandidate, ...],
    selected: ReportCandidate | None,
    incomplete: tuple[str, ...],
) -> ReportResult:
    """Render byte-stable serialized forms around the computed result."""
    attempts = [attempt for trial in request.ledger["trials"] for attempt in trial["attempts"]]
    data: dict[str, object] = {
        "frontier": [_candidate(item) for item in frontier],
        "incomplete": list(incomplete),
        "ledger": _ledger(request.ledger),
        "metadata": {
            "drift_diagnostics": sorted(request.metadata.drift_diagnostics),
            "environment": sorted(request.metadata.environment),
            "manifest_hash": request.metadata.manifest_hash,
            "manifest_id": request.metadata.manifest_id,
            "provenance": sorted(request.metadata.provenance),
            "reproduction_commands": list(request.metadata.reproduction_commands),
            "resume_mode": request.metadata.resume_mode,
        },
        "run_id": request.ledger["run_id"],
        "schema_version": 1,
        "selected": None if selected is None else _candidate(selected),
        "stage_counts": {
            "attempts": len(attempts),
            "failed_attempts": sum(item["outcome"] is not None for item in attempts),
            "frontier": len(frontier),
            "incomplete": len(incomplete),
            "trials": len(request.ledger["trials"]),
        },
        "status": "selected" if selected is not None else "no-feasible-candidate",
    }
    json_text = json.dumps(data, sort_keys=True, indent=2, ensure_ascii=False) + "\n"
    return ReportResult(
        frontier, selected, incomplete, json_text, markdown(request, frontier, selected, incomplete)
    )
