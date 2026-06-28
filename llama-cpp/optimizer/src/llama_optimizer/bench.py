"""llama-bench JSONL execution and bounded screening (T6).

Constructs argument arrays without shell interpolation, forces machine JSONL
output, exact context/depth 32768, warmup enabled, prompt/generation workloads,
and raw sample retention. Parses identity, average/stddev, and per-repetition
``samples_ns``/``samples_ts`` arrays, cross-checking returned identity against
the requested manifest. Every process is routed through T5
:class:`~llama_optimizer.supervisor.ProcessSupervisor`; every metric, raw line,
and artifact is written through T4 :class:`~llama_optimizer.ledger.Ledger`.

Closed outcome classification (exact T4 vocabulary):

* malformed / missing / identity-mismatched output -> ``measurement-failure``
* unsupported flag combinations                      -> ``unsupported``
* model-load errors                                  -> ``deterministic-load-failure``
* confirmed temporary launch errors                  -> ``transient-failure`` (retry-eligible)

None of these is ever converted to throughput zero.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import sys
from collections.abc import Mapping
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, TypeIs

from llama_optimizer.lifecycle import AttemptId, NonScoredOutcome, TrialId
from llama_optimizer.profile_manifest import REQUIRED_CONTEXT_SIZE

if TYPE_CHECKING:
    from collections.abc import Generator
    from pathlib import Path

    from llama_optimizer.ledger import Ledger
    from llama_optimizer.supervisor import (
        ChildExit,
        ProcessSupervisor,
        SupervisorConfig,
        SupervisorResult,
    )
    from llama_optimizer.telemetry import HardChannelProvider

__all__ = (
    "DEFAULT_BENCH_CONFIG",
    "PP512",
    "TG128",
    "BenchConfig",
    "BenchIdentity",
    "BenchMeasurement",
    "BenchResult",
    "BenchSample",
    "BenchScreenRequest",
    "BenchScreenResult",
    "BenchWorkload",
    "DeterministicLoadFailureError",
    "MeasurementFailureError",
    "UnsupportedConfigError",
    "build_bench_command",
    "classify_child_exit",
    "parse_bench_jsonl",
    "run_supervised_bench",
)

_REQUIRED_DEPTH = int(REQUIRED_CONTEXT_SIZE)


# --- Typed errors ----------------------------------------------------------


@dataclass
class MeasurementFailureError(ValueError):
    """Malformed, missing, or identity-mismatched bench output."""

    reason: str

    def __post_init__(self) -> None:
        """Populate the base ``ValueError`` message so ``str()`` is never empty."""
        Exception.__init__(self, f"measurement-failure: {self.reason}")
        Exception.__init__(self, f"measurement-failure: {self.reason}")


@dataclass
class UnsupportedConfigError(ValueError):
    """An unsupported flag combination was rejected at prelaunch."""

    reason: str

    def __post_init__(self) -> None:
        """Populate the base ``ValueError`` message so ``str()`` is never empty."""
        Exception.__init__(self, f"unsupported: {self.reason}")
        Exception.__init__(self, f"unsupported: {self.reason}")


@dataclass
class DeterministicLoadFailureError(ValueError):
    """A model-load error (nonzero exit classified as deterministic)."""

    reason: str

    def __post_init__(self) -> None:
        """Populate the base ``ValueError`` message so ``str()`` is never empty."""
        Exception.__init__(self, f"deterministic-load-failure: {self.reason}")
        Exception.__init__(self, f"deterministic-load-failure: {self.reason}")


# --- Immutable value objects -----------------------------------------------


@dataclass(frozen=True, slots=True)
class BenchWorkload:
    """One prompt/generation test workload for llama-bench screening."""

    name: str
    n_prompt: int
    n_gen: int


PP512: BenchWorkload = BenchWorkload(name="pp512", n_prompt=512, n_gen=0)
TG128: BenchWorkload = BenchWorkload(name="tg128", n_prompt=0, n_gen=128)


@dataclass(frozen=True, slots=True)
class BenchConfig:
    """Bounded bench configuration (context enforced at 32768, warmup always on)."""

    repetitions: int
    delay_seconds: int
    workloads: tuple[BenchWorkload, ...]

    def __post_init__(self) -> None:
        """Validate repetitions, delay, and workloads."""
        if self.repetitions < 1:
            msg = f"repetitions must be >= 1, got {self.repetitions}"
            raise ValueError(msg)
        if self.delay_seconds < 0:
            msg = f"delay_seconds must be >= 0, got {self.delay_seconds}"
            raise ValueError(msg)
        if not self.workloads:
            msg = "at least one workload is required"
            raise ValueError(msg)
        if self.repetitions < 1:
            msg = f"repetitions must be >= 1, got {self.repetitions}"
            raise ValueError(msg)
        if self.delay_seconds < 0:
            msg = f"delay_seconds must be >= 0, got {self.delay_seconds}"
            raise ValueError(msg)
        if not self.workloads:
            msg = "at least one workload is required"
            raise ValueError(msg)

    @property
    def context_size(self) -> int:
        """The exact, immutable context/depth for every comparable trial."""
        return _REQUIRED_DEPTH

    @property
    def warmup(self) -> bool:
        """Warmup is always enabled (never disabled by default)."""
        return True


DEFAULT_BENCH_CONFIG: BenchConfig = BenchConfig(
    repetitions=3, delay_seconds=1, workloads=(PP512, TG128)
)


@dataclass(frozen=True, slots=True)
class BenchIdentity:
    """The identity cross-check target parsed from returned JSONL lines."""

    model_filename: str
    n_gpu_layers: int
    n_batch: int
    n_ubatch: int
    type_k: str
    type_v: str
    n_threads: int
    flash_attn: int
    use_mmap: bool


@dataclass(frozen=True, slots=True)
class BenchSample:
    """One raw per-repetition measurement point (nanoseconds + tokens/s)."""

    ns: int
    ts: float


@dataclass(frozen=True, slots=True)
class BenchMeasurement:
    """Parsed measurement for one workload."""

    workload_name: str
    avg_ts: float
    stddev_ts: float
    samples: tuple[BenchSample, ...]


@dataclass(frozen=True, slots=True)
class BenchResult:
    """Parsed bench result for one config across all workloads."""

    model: str
    build: int
    measurements: tuple[BenchMeasurement, ...]
    raw_jsonl: str


@dataclass(frozen=True, slots=True)
class BenchScreenRequest:
    """Bundle of inputs for one supervised bench screening attempt."""

    trial_id: TrialId
    bench_config: BenchConfig
    identity: BenchIdentity
    binary: str
    output_dir: Path


@dataclass(frozen=True, slots=True)
class BenchScreenResult:
    """Typed outcome of one supervised bench attempt."""

    outcome: NonScoredOutcome | None
    result: BenchResult | None
    raw_jsonl: str
    supervisor_result: SupervisorResult
    trial_id: TrialId
    attempt_id: AttemptId
    metrics: Mapping[str, float] = field(default_factory=dict[str, float])


# --- Command builder --------------------------------------------------------


def build_bench_command(
    binary: str,
    config: BenchConfig,
    identity: BenchIdentity,
) -> list[str]:
    """Construct the llama-bench argument array without shell interpolation.

    Forces ``-o jsonl``, exact depth ``32768``, warmup enabled (``--no-warmup``
    is never passed), repetitions/delay from the config, and explicit
    backend/model/config flags from the identity. All values are separate argv
    elements; no shell interpolation is used.
    """
    fa_val = "on" if identity.flash_attn == 1 else "off"
    mmp_val = "1" if identity.use_mmap else "0"
    prompt_values = ",".join(str(w.n_prompt) for w in config.workloads)
    gen_values = ",".join(str(w.n_gen) for w in config.workloads)
    return [
        binary,
        "-o",
        "jsonl",
        "-r",
        str(config.repetitions),
        "--delay",
        str(config.delay_seconds),
        "-d",
        str(_REQUIRED_DEPTH),
        "-m",
        identity.model_filename,
        "-ngl",
        str(identity.n_gpu_layers),
        "-b",
        str(identity.n_batch),
        "-ub",
        str(identity.n_ubatch),
        "-ctk",
        identity.type_k,
        "-ctv",
        identity.type_v,
        "-t",
        str(identity.n_threads),
        "-fa",
        fa_val,
        "-mmp",
        mmp_val,
        "-p",
        prompt_values,
        "-n",
        gen_values,
    ]


# --- JSONL parser -----------------------------------------------------------


def _is_str_mapping(value: object) -> TypeIs[Mapping[str, object]]:
    """Narrow ``object`` to a fully-typed string-keyed mapping."""
    return isinstance(value, Mapping)


def _is_obj_list(value: object) -> TypeIs[list[object]]:
    """Narrow ``object`` to a fully-typed list of objects."""
    return isinstance(value, list)


def _loads_mapping(line: str) -> Mapping[str, object]:
    """Parse one JSON line into a string-keyed mapping or raise typed error."""
    try:
        parsed: object = json.loads(line)  # pyright: ignore[reportAny]
    except json.JSONDecodeError as exc:
        raise MeasurementFailureError(reason=f"malformed JSON line: {exc}") from exc
    if not _is_str_mapping(parsed):
        raise MeasurementFailureError(reason="expected a JSON object")
    return parsed


def _req_str(obj: Mapping[str, object], key: str) -> str:
    value = obj.get(key)
    if not isinstance(value, str):
        raise MeasurementFailureError(reason=f"missing or non-string field {key!r}")
    return value


def _req_int(obj: Mapping[str, object], key: str) -> int:
    value = obj.get(key)
    if not isinstance(value, int) or isinstance(value, bool):
        raise MeasurementFailureError(reason=f"missing or non-integer field {key!r}")
    return value


def _req_float(obj: Mapping[str, object], key: str) -> float:
    value = obj.get(key)
    if isinstance(value, int | float) and not isinstance(value, bool):
        return float(value)
    raise MeasurementFailureError(reason=f"missing or non-numeric field {key!r}")


def _req_int_list(obj: Mapping[str, object], key: str) -> list[int]:
    value = obj.get(key)
    if not _is_obj_list(value):
        raise MeasurementFailureError(reason=f"missing or non-list field {key!r}")
    result: list[int] = []
    for item in value:
        if not isinstance(item, int) or isinstance(item, bool):
            raise MeasurementFailureError(reason=f"non-integer in {key!r}")
        result.append(item)
    return result


def _req_float_list(obj: Mapping[str, object], key: str) -> list[float]:
    value = obj.get(key)
    if not _is_obj_list(value):
        raise MeasurementFailureError(reason=f"missing or non-list field {key!r}")
    result: list[float] = []
    for item in value:
        if isinstance(item, int | float) and not isinstance(item, bool):
            result.append(float(item))
        else:
            raise MeasurementFailureError(reason=f"non-numeric in {key!r}")
    return result


def _check_identity(obj: Mapping[str, object], expected: BenchIdentity) -> None:
    """Cross-check JSONL identity fields against the requested manifest."""
    checks: list[tuple[str, object, object]] = [
        ("model", _req_str(obj, "model"), expected.model_filename),
        ("n_gpu_layers", _req_int(obj, "n_gpu_layers"), expected.n_gpu_layers),
        ("n_batch", _req_int(obj, "n_batch"), expected.n_batch),
        ("n_ubatch", _req_int(obj, "n_ubatch"), expected.n_ubatch),
        ("type_k", _req_str(obj, "type_k"), expected.type_k),
        ("type_v", _req_str(obj, "type_v"), expected.type_v),
        ("n_threads", _req_int(obj, "n_threads"), expected.n_threads),
        ("flash_attn", _req_int(obj, "flash_attn"), expected.flash_attn),
    ]
    for field_name, actual, want in checks:
        if actual != want:
            raise MeasurementFailureError(
                reason=f"identity mismatch {field_name}: expected {want!r}, got {actual!r}"
            )


def parse_bench_jsonl(
    raw: str,
    expected: BenchIdentity,
    expected_workload_names: tuple[str, ...],
) -> BenchResult:
    """Parse raw JSONL lines, cross-check identity, and extract raw samples.

    Each line is one (config, workload) measurement. Identity fields are
    cross-checked against ``expected``. Per-repetition ``samples_ns`` and
    ``samples_ts`` arrays are retained in full. Malformed JSON, missing
    samples, NaN/negative throughput, and identity mismatches all raise
    :class:`MeasurementFailureError`.
    """
    lines = [ln for ln in raw.splitlines() if ln.strip()]
    if not lines:
        raise MeasurementFailureError(reason="empty JSONL output")

    measurements: list[BenchMeasurement] = []
    model = ""
    build = 0
    for line in lines:
        obj = _loads_mapping(line)
        _check_identity(obj, expected)
        if not model:
            model = _req_str(obj, "model")
            build = _req_int(obj, "build")
        name = _req_str(obj, "name")
        if name not in expected_workload_names:
            raise MeasurementFailureError(reason=f"unexpected workload {name!r}")
        avg_ts = _req_float(obj, "avg_ts")
        stddev_ts = _req_float(obj, "stddev_ts")
        if not math.isfinite(avg_ts) or avg_ts < 0:
            raise MeasurementFailureError(reason=f"avg_ts invalid for {name}: {avg_ts}")
        samples_ns = _req_int_list(obj, "samples_ns")
        samples_ts = _req_float_list(obj, "samples_ts")
        if not samples_ns or not samples_ts:
            raise MeasurementFailureError(reason=f"missing samples for {name}")
        if len(samples_ns) != len(samples_ts):
            raise MeasurementFailureError(reason=f"sample count mismatch for {name}")
        samples = tuple(
            BenchSample(ns=ns, ts=ts) for ns, ts in zip(samples_ns, samples_ts, strict=True)
        )
        measurements.append(
            BenchMeasurement(
                workload_name=name, avg_ts=avg_ts, stddev_ts=stddev_ts, samples=samples
            )
        )

    found = {m.workload_name for m in measurements}
    missing = set(expected_workload_names) - found
    if missing:
        raise MeasurementFailureError(reason=f"missing workloads: {sorted(missing)}")

    return BenchResult(
        model=model,
        build=build,
        measurements=tuple(measurements),
        raw_jsonl=raw,
    )


# --- Exit classification ----------------------------------------------------


def classify_child_exit(
    exit_code: ChildExit,
    stderr: str,
) -> NonScoredOutcome:
    """Classify a nonzero llama-bench exit into a closed T4 outcome.

    Exit 0 is never passed here (the caller parses output instead). The
    classification distinguishes unsupported flag combinations, model-load
    errors, and confirmed temporary launch errors.
    """
    if exit_code.returncode == 0:
        # Exit 0 means success; the caller parses output, not classifies exit.
        return NonScoredOutcome.MEASUREMENT_FAILURE
    lower = stderr.lower()
    if "unsupported" in lower:
        return NonScoredOutcome.UNSUPPORTED
    if "failed to load" in lower or "error loading model" in lower:
        return NonScoredOutcome.DETERMINISTIC_LOAD_FAILURE
    return NonScoredOutcome.TRANSIENT_FAILURE


# --- Stdio capture ----------------------------------------------------------


@contextmanager
def _capture_stdio(stdout_path: Path, stderr_path: Path) -> Generator[None]:
    """Redirect fd 1 and 2 to files so the supervised child inherits them.

    The supervisor launches the child with ``start_new_session=True`` and no
    explicit ``stdout=`` / ``stderr=`` redirection, so the child inherits the
    parent's file descriptors. Redirecting fd 1/2 before calling the supervisor
    captures the child's output without modifying the supervisor.
    """
    _ = sys.stdout.flush()
    _ = sys.stderr.flush()
    saved_out = os.dup(1)
    saved_err = os.dup(2)
    out_fd = os.open(str(stdout_path), os.O_WRONLY | os.O_CREAT | os.O_TRUNC)
    err_fd = os.open(str(stderr_path), os.O_WRONLY | os.O_CREAT | os.O_TRUNC)
    try:
        _ = os.dup2(out_fd, 1)
        _ = os.dup2(err_fd, 2)
        _ = os.close(out_fd)
        _ = os.close(err_fd)
        yield
    finally:
        _ = sys.stdout.flush()
        _ = sys.stderr.flush()
        _ = os.dup2(saved_out, 1)
        _ = os.dup2(saved_err, 2)
        _ = os.close(saved_out)
        _ = os.close(saved_err)


# --- Screening orchestrator -------------------------------------------------


def _extract_metrics(result: BenchResult) -> dict[str, float]:
    """Flatten parsed measurements into named metrics for the ledger."""
    metrics: dict[str, float] = {}
    for m in result.measurements:
        metrics[f"{m.workload_name}_avg_ts"] = m.avg_ts
        metrics[f"{m.workload_name}_stddev_ts"] = m.stddev_ts
    return metrics


def run_supervised_bench(
    supervisor: ProcessSupervisor,
    provider: HardChannelProvider,
    sup_config: SupervisorConfig,
    ledger: Ledger,
    request: BenchScreenRequest,
) -> BenchScreenResult:
    """Run one supervised llama-bench attempt and record everything to the ledger.

    Starts the attempt, builds the command from ``request``, captures stdio,
    routes the process through the T5 supervisor, classifies the outcome, parses
    JSONL, records metrics/artifacts/telemetry via T4, and completes the attempt.
    Never converts a failure to throughput zero.
    """
    request.output_dir.mkdir(parents=True, exist_ok=True)
    command = build_bench_command(request.binary, request.bench_config, request.identity)
    attempt = ledger.start_attempt(request.trial_id)
    stdout_path = request.output_dir / f"bench-{attempt.attempt_id}.stdout.jsonl"
    stderr_path = request.output_dir / f"bench-{attempt.attempt_id}.stderr.txt"

    with _capture_stdio(stdout_path, stderr_path):
        sup_result = supervisor.run(command, provider=provider, config=sup_config)

    raw_jsonl = stdout_path.read_text() if stdout_path.exists() else ""
    raw_stderr = stderr_path.read_text() if stderr_path.exists() else ""
    outcome: NonScoredOutcome | None = None
    parsed: BenchResult | None = None
    metrics: dict[str, float] = {}

    if isinstance(sup_result.outcome, NonScoredOutcome):
        outcome = sup_result.outcome
    elif sup_result.outcome.returncode != 0:
        outcome = classify_child_exit(sup_result.outcome, raw_stderr)
    else:
        try:
            parsed = parse_bench_jsonl(
                raw_jsonl,
                expected=request.identity,
                expected_workload_names=tuple(w.name for w in request.bench_config.workloads),
            )
            metrics = _extract_metrics(parsed)
        except MeasurementFailureError as exc:
            outcome = NonScoredOutcome.MEASUREMENT_FAILURE
            raw_stderr = f"{raw_stderr}\n{exc}"

    # Record raw artifact (always, even on failure for evidence).
    content_hash = hashlib.sha256(raw_jsonl.encode()).hexdigest()
    ledger.record_artifact(
        attempt_id=attempt.attempt_id,
        kind="bench-jsonl",
        relative_path=str(stdout_path),
        content_hash=content_hash,
    )
    if metrics:
        ledger.record_metrics(attempt.attempt_id, metrics)
    if sup_result.peak_used is not None:
        breached = outcome is NonScoredOutcome.RESOURCE_INFEASIBLE
        ledger.record_telemetry(
            attempt_id=attempt.attempt_id,
            vram_used_bytes=int(sup_result.peak_used),
            peak_vram_bytes=int(sup_result.peak_used),
            breached=breached,
        )

    if outcome is None:
        ledger.succeed_attempt(attempt.attempt_id)
    else:
        ledger.end_attempt_nonscored(
            attempt.attempt_id, outcome=outcome, reason=raw_stderr.strip() or outcome.value
        )

    return BenchScreenResult(
        outcome=outcome,
        result=parsed,
        raw_jsonl=raw_jsonl,
        supervisor_result=sup_result,
        trial_id=request.trial_id,
        attempt_id=attempt.attempt_id,
        metrics=metrics,
    )
