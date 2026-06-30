"""Typed value objects and errors for exact-32K llama-server finalists (T9).

Every finalist starts ``llama-server`` with ``--ctx-size 32768`` and a matching
model/backend/runtime identity. Weight quantization and KV-cache quantization
remain separate dimensions, inherited from the screening identity. Server
artifacts (readiness, metrics, responses) are parsed strictly at the boundary.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import TYPE_CHECKING

from llama_optimizer.profile_manifest import REQUIRED_CONTEXT_SIZE

if TYPE_CHECKING:
    from collections.abc import Mapping
    from pathlib import Path

    from llama_optimizer.lifecycle import AttemptId, NonScoredOutcome, TrialId
    from llama_optimizer.supervisor import SupervisorResult


class RequestKind(StrEnum):
    """Versioned workload request categories for finalist validation."""

    CODING = "coding"
    TOOL_USE = "tool-use"
    CONCURRENCY = "concurrency"
    LATENCY = "latency"


class EligibilityStatus(StrEnum):
    """Runtime eligibility gate state for a finalist before launch."""

    INFEASIBLE = "infeasible"
    UNSCREENED = "unscreened"
    SCREENED_REJECT = "screened-reject"
    QUALITY_FAIL = "quality-fail"
    ELIGIBLE = "eligible"


@dataclass(frozen=True, slots=True)
class RequestSpec:
    """One versioned workload request specification."""

    name: str
    kind: RequestKind


@dataclass(frozen=True, slots=True)
class ServerIdentity:
    """Model/backend/runtime identity for one llama-server finalist.

    A server may never be reused across differing identities; the command
    builder and the runner both enforce this.
    """

    model_filename: str
    backend: str
    build_label: str
    n_gpu_layers: int
    n_batch: int
    n_ubatch: int
    type_k: str
    type_v: str
    n_threads: int
    flash_attn: int
    use_mmap: bool


@dataclass(frozen=True, slots=True)
class ServerConfig:
    """Bounded finalist configuration (context enforced at 32768, warmup on)."""

    repetitions: int
    delay_seconds: int
    parallel: int
    readiness_timeout_seconds: int
    cooldown_seconds: int
    request_specs: tuple[RequestSpec, ...]

    def __post_init__(self) -> None:
        """Validate repetitions, delay, parallel, readiness, cooldown, specs."""
        if self.repetitions < 1:
            msg = f"repetitions must be >= 1, got {self.repetitions}"
            raise ValueError(msg)
        if self.delay_seconds < 0:
            msg = f"delay_seconds must be >= 0, got {self.delay_seconds}"
            raise ValueError(msg)
        if self.parallel < 1:
            msg = f"parallel must be >= 1, got {self.parallel}"
            raise ValueError(msg)
        if self.readiness_timeout_seconds < 1:
            msg = f"readiness_timeout_seconds must be >= 1, got {self.readiness_timeout_seconds}"
            raise ValueError(msg)
        if self.cooldown_seconds < 0:
            msg = f"cooldown_seconds must be >= 0, got {self.cooldown_seconds}"
            raise ValueError(msg)
        if not self.request_specs:
            msg = "at least one request spec is required"
            raise ValueError(msg)

    @property
    def context_size(self) -> int:
        """The exact, immutable context for every comparable finalist."""
        return int(REQUIRED_CONTEXT_SIZE)

    @property
    def warmup(self) -> bool:
        """Warmup is always enabled (never disabled by default)."""
        return True


# Versioned default coding/tool-use/concurrency/latency request specs.
CODING_SPEC: RequestSpec = RequestSpec(name="coding-v1", kind=RequestKind.CODING)
TOOL_USE_SPEC: RequestSpec = RequestSpec(name="tool-use-v1", kind=RequestKind.TOOL_USE)
CONCURRENCY_SPEC: RequestSpec = RequestSpec(name="concurrency-v1", kind=RequestKind.CONCURRENCY)
LATENCY_SPEC: RequestSpec = RequestSpec(name="latency-v1", kind=RequestKind.LATENCY)

DEFAULT_SERVER_CONFIG: ServerConfig = ServerConfig(
    repetitions=3,
    delay_seconds=1,
    parallel=2,
    readiness_timeout_seconds=30,
    cooldown_seconds=1,
    request_specs=(CODING_SPEC, TOOL_USE_SPEC, CONCURRENCY_SPEC, LATENCY_SPEC),
)


@dataclass(frozen=True, slots=True)
class ServerMetrics:
    """Parsed metrics from one finalist server run (raw distributions retained)."""

    prompt_throughput: float
    generation_throughput: float
    ttft_ms: tuple[float, ...]
    request_latency_ms: tuple[float, ...]
    slots: int
    errors: int
    quality_pass: bool


@dataclass(frozen=True, slots=True)
class FinalistEntry:
    """One feasible, quality-passing finalist eligible for scheduling."""

    finalist_id: str
    identity: ServerIdentity
    trial_id: TrialId
    eligibility: EligibilityStatus = EligibilityStatus.UNSCREENED


@dataclass(frozen=True, slots=True)
class ScheduledFinalist:
    """A finalist with its interleaved position in the run schedule."""

    position: int
    finalist: FinalistEntry


@dataclass(frozen=True, slots=True)
class FinalistRequest:
    """Bundle of inputs for one supervised llama-server finalist attempt."""

    trial_id: TrialId
    identity: ServerIdentity
    config: ServerConfig
    binary: str
    output_dir: Path


@dataclass(frozen=True, slots=True)
class FinalistResult:
    """Typed outcome of one supervised finalist attempt."""

    outcome: NonScoredOutcome | None
    metrics: ServerMetrics | None
    raw_readiness: str
    raw_metrics: str
    raw_responses: str
    raw_dispatch: str
    supervisor_result: SupervisorResult
    lifecycle: LifecycleRecord
    trial_id: TrialId
    attempt_id: AttemptId
    metrics_map: Mapping[str, float] = field(default_factory=dict[str, float])
    reason: str = ""


@dataclass(frozen=True, slots=True)
class LifecycleRecord:
    """Typed lifecycle trace of one supervised finalist run."""

    launched: bool
    ready: bool
    dispatched: bool
    port: int | None
    request_count: int
    delay_applied: bool
    cooldown_applied: bool
    terminated: bool
    failure: str


# --- Typed boundary errors -------------------------------------------------
@dataclass
class ServerError(ValueError):
    """Base typed error for server-artifact boundary failures."""

    reason: str

    def __post_init__(self) -> None:
        """Populate the base ValueError message so str() is never empty."""
        Exception.__init__(self, self.reason)


@dataclass
class ReadinessTimeoutError(ServerError):
    """The server readiness marker was missing within the bounded window."""


@dataclass
class MetricsParseError(ServerError):
    """Server metrics artifact was missing or malformed."""


@dataclass
class ServerIdentityMismatchError(ServerError):
    """Server metrics identity fields did not match the requested identity."""
