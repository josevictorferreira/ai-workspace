"""Read-only agent adapters for launching/reporting optimizer runs.

Adapters wrap ``llama-cpp-opt run`` and ``llama-cpp-opt report`` as
subprocess calls, parsing newline-delimited structured JSON events from
stdout while keeping diagnostic stderr separate.

Each adapter is version-gated: it checks the CLI schema version before
invoking and returns a clear ``AdapterVersionError`` on mismatch.

Permissions model:
  - ``run`` adapter: invoke optimizer search only
  - ``report`` adapter: read-only access (read, grep, find, ls)
    explicitly excluding bash, edit, write, credentials

All environment variables are passed via explicit allowlist; no
ambient environment leaks through.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

# --- Version gating ---------------------------------------------------------

ADAPTER_PROTOCOL_VERSION: int = 1
"""Current adapter protocol version. Bump when event schema changes."""


class AdapterVersionError(Exception):
    """CLI schema version incompatible with this adapter."""

    def __init__(self, expected: int, actual: int) -> None:
        self.expected = expected
        self.actual = actual
        super().__init__(
            f"Adapter protocol version {expected} incompatible with CLI version {actual}"
        )


# --- Event types ------------------------------------------------------------


class EventType(StrEnum):
    """Structured events emitted by the CLI to stdout."""

    RUN_STARTED = "run_started"
    TRIAL_STARTED = "trial_started"
    TRIAL_COMPLETED = "trial_completed"
    TRIAL_FAILED = "trial_failed"
    RUN_COMPLETED = "run_completed"
    RUN_FAILED = "run_failed"
    REPORT_GENERATED = "report_generated"


@dataclass(frozen=True, slots=True)
class StructuredEvent:
    """One parsed structured event from CLI stdout."""

    event_type: str
    data: dict[str, object]
    line_number: int


@dataclass(frozen=True, slots=True)
class AdapterResult:
    """Complete result from an adapter invocation."""

    events: tuple[StructuredEvent, ...]
    stderr: str
    return_code: int
    timed_out: bool


# --- Environment allowlist --------------------------------------------------

# Only these environment variables are passed to the subprocess.
_ENV_ALLOWLIST: frozenset[str] = frozenset(
    {
        "HOME",
        "PATH",
        "XDG_CACHE_HOME",
        "XDG_CONFIG_HOME",
        "XDG_DATA_HOME",
        "LANG",
        "LC_ALL",
        "TERM",
        "LLAMA_OPTIMIZER_RUN_GPU_SMOKE",
    }
)


def filter_env(base_env: dict[str, str]) -> dict[str, str]:
    """Return only allowlisted environment variables."""
    return {k: v for k, v in base_env.items() if k in _ENV_ALLOWLIST}
