"""Core dataclasses and exceptions for llama-bench screening (T6).

This module owns the typed value objects exchanged by the command builder,
JSONL parser, and supervised runner. Keeping the types in one file lets the
parser and runner depend on a stable, lightweight contract.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, override

from llama_optimizer.profile_manifest import REQUIRED_CONTEXT_SIZE

if TYPE_CHECKING:
    from collections.abc import Mapping
    from pathlib import Path

    from llama_optimizer.lifecycle import AttemptId, NonScoredOutcome, TrialId
    from llama_optimizer.supervisor import SupervisorResult


@dataclass
class MeasurementFailureError(ValueError):
    """Malformed, missing, or identity-mismatched bench output."""

    reason: str

    @override
    def __str__(self) -> str:
        return f"measurement-failure: {self.reason}"


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

    @property
    def context_size(self) -> int:
        """The exact, immutable context/depth for every comparable trial."""
        return int(REQUIRED_CONTEXT_SIZE)

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
