"""Fail-closed total-VRAM telemetry for trial supervision (T5).

The hard channel is the verified local ``rocm-smi --showmeminfo vram --json``
shape::

    {"card0":{"VRAM Total Memory (B)":"17163091968",
              "VRAM Total Used Memory (B)":"807677952"}}

Values are string-encoded bytes; the device key is ``card0``. Total used VRAM
is parsed strictly at the boundary and compared against exactly
``13,958,643,712`` bytes (13 GiB). Anything missing, malformed, or untyped
fails closed as :class:`TelemetryLossError`. Diagnostics
(temperature/power/use/clocks/PCIe) are best-effort and never a hard gate.
AMD-SMI is an interface seam only; the v1 concrete provider is rocm-smi.
"""

from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Final, NewType, Protocol, final

# --- Semantic primitives ----------------------------------------------------
# Bytes is distinct from a bare int so the compiler refuses to mix a VRAM
# reading with an attempt number or a generation counter.
Bytes = NewType("Bytes", int)

#: Exact hard ceiling for total RX 6900 XT VRAM (13 GiB), including desktop.
VRAM_CEILING_BYTES: Final[Bytes] = Bytes(13_958_643_712)

#: Verified local device key and string-encoded byte field names.
DEVICE_KEY: Final[str] = "card0"
TOTAL_FIELD: Final[str] = "VRAM Total Memory (B)"
USED_FIELD: Final[str] = "VRAM Total Used Memory (B)"
_DIAG_TIMEOUT: Final[timedelta] = timedelta(seconds=5)

# Staged regex checks give field-specific failure reasons without json.loads
# (which returns bare Any and would trigger reportAny under strict mode).
_HAS_CARD0: Final[re.Pattern[str]] = re.compile(r'"card0"\s*:')
_HAS_TOTAL_FIELD: Final[re.Pattern[str]] = re.compile(r'"VRAM Total Memory \(B\)"\s*:')
_HAS_USED_FIELD: Final[re.Pattern[str]] = re.compile(r'"VRAM Total Used Memory \(B\)"\s*:')
_HAS_TOTAL_STRING: Final[re.Pattern[str]] = re.compile(r'"VRAM Total Memory \(B\)"\s*:\s*"')
_HAS_USED_STRING: Final[re.Pattern[str]] = re.compile(r'"VRAM Total Used Memory \(B\)"\s*:\s*"')
_HARD_CHANNEL_RE: Final[re.Pattern[str]] = re.compile(
    r'"card0"\s*:\s*\{\s*'
    + r'"VRAM Total Memory \(B\)"\s*:\s*"(\d+)"\s*,\s*'
    + r'"VRAM Total Used Memory \(B\)"\s*:\s*"(\d+)"\s*'
    + r"\}"
)


@dataclass(frozen=True, slots=True)
class HardChannel:
    """One strict total-device VRAM reading from the hard channel."""

    total: Bytes
    used: Bytes
    collected_at: datetime
    raw: str


@dataclass(frozen=True, slots=True)
class Diagnostics:
    """Best-effort sensor snapshot. Sensors are opaque strings; never a hard gate."""

    temperature: str | None
    power: str | None
    gpu_use: str | None
    clocks: str | None
    pcie: str | None
    raw: str


@dataclass
class TelemetryLossError(ValueError):
    """Hard telemetry was missing, malformed, stale, or timed out.

    Mutable (no frozen/slots) so the BaseException traceback layout stays
    intact; the message is set via ``Exception.__init__`` in ``__post_init__``.
    """

    reason: str
    raw: str

    def __post_init__(self) -> None:
        """Populate the base ``ValueError`` message so ``str()`` is never empty."""
        detail = f": {self.raw}" if self.raw else ""
        Exception.__init__(self, f"telemetry-loss: {self.reason}{detail}")


class HardChannelProvider(Protocol):
    """Reads the hard channel and a best-effort diagnostic snapshot."""

    def sample(self) -> HardChannel:
        """Return one strict hard-channel reading or raise :class:`TelemetryLossError`."""
        ...

    def diagnostics(self) -> Diagnostics:
        """Return a best-effort diagnostic snapshot. Never a hard gate."""
        ...


# --- Strict boundary parse --------------------------------------------------


def parse_hard_channel(raw: str, *, collected_at: datetime) -> HardChannel:
    """Parse the verified rocm-smi hard-channel JSON strictly.

    Empty, non-JSON, missing ``card0``, missing fields, non-string bytes, or
    negative values all fail closed as :class:`TelemetryLossError` with a
    field-specific reason.
    """
    stripped = raw.strip()
    if not stripped:
        raise TelemetryLossError(reason="empty hard-channel output", raw=raw)
    if not _HAS_CARD0.search(stripped):
        raise TelemetryLossError(reason=f"malformed: missing {DEVICE_KEY} device", raw=raw)
    if not _HAS_TOTAL_FIELD.search(stripped):
        raise TelemetryLossError(reason=f"malformed: missing {TOTAL_FIELD} field", raw=raw)
    if not _HAS_TOTAL_STRING.search(stripped):
        raise TelemetryLossError(reason=f"malformed: {TOTAL_FIELD} must be a string", raw=raw)
    if not _HAS_USED_FIELD.search(stripped):
        raise TelemetryLossError(reason=f"malformed: missing {USED_FIELD} field", raw=raw)
    if not _HAS_USED_STRING.search(stripped):
        raise TelemetryLossError(reason=f"malformed: {USED_FIELD} must be a string", raw=raw)
    match = _HARD_CHANNEL_RE.search(stripped)
    if match is None:
        raise TelemetryLossError(
            reason="malformed: hard-channel byte values are non-numeric", raw=raw
        )
    total_str, used_str = match.groups()
    return HardChannel(
        total=Bytes(int(total_str)),
        used=Bytes(int(used_str)),
        collected_at=collected_at,
        raw=raw,
    )


def is_breach(sample: HardChannel, *, ceiling: Bytes = VRAM_CEILING_BYTES) -> bool:
    """Return whether total used VRAM is at or over the ceiling (>= blocks)."""
    return sample.used >= ceiling


def is_stale(sample: HardChannel, *, now: datetime, max_staleness: timedelta) -> bool:
    """Return whether a reading is older than the configured staleness window."""
    return now - sample.collected_at > max_staleness


# --- Diagnostics parse (best-effort) ----------------------------------------


def _extract(raw: str, label: str) -> str | None:
    """Best-effort, case-insensitive extraction of the value after the label."""
    prefix = label.lower()
    for line in raw.splitlines():
        lowered = line.lower()
        if prefix in lowered and ":" in line:
            tail = line.rsplit(":", 1)[-1].strip()
            if tail:
                return tail
    return None


def parse_diagnostics(raw: str) -> Diagnostics:
    """Best-effort parse of a rocm-smi diagnostics table. Never raises."""
    return Diagnostics(
        temperature=_extract(raw, "temperature"),
        power=_extract(raw, "power"),
        gpu_use=_extract(raw, "gpu use"),
        clocks=_extract(raw, "clk"),
        pcie=_extract(raw, "pcie"),
        raw=raw,
    )


# --- v1 concrete provider: rocm-smi -----------------------------------------


@final
class RocmSmiProvider:
    """Concrete v1 provider over ``rocm-smi`` for the hard channel + diagnostics."""

    def __init__(self, binary: str, *, timeout: timedelta) -> None:
        self._hard_argv: Final[list[str]] = [binary, "--showmeminfo", "vram", "--json"]
        self._diag_argv: Final[list[str]] = [
            binary,
            "--showtemp",
            "--showpower",
            "--showuse",
            "--showclocks",
            "--showbus",
        ]
        self._timeout: Final[timedelta] = timeout

    def sample(self) -> HardChannel:
        """Run the hard-channel command and parse it strictly."""
        collected_at = datetime.now(UTC)
        completed = self._run(self._hard_argv, self._timeout)
        return parse_hard_channel(completed, collected_at=collected_at)

    def diagnostics(self) -> Diagnostics:
        """Run the diagnostics command and parse it best-effort. Never a hard gate."""
        try:
            raw = self._run(self._diag_argv, _DIAG_TIMEOUT)
        except (OSError, subprocess.SubprocessError, TelemetryLossError):
            raw = ""
        return parse_diagnostics(raw)

    def _run(self, argv: list[str], timeout: timedelta) -> str:
        try:
            completed = subprocess.run(
                argv,
                check=False,
                capture_output=True,
                text=True,
                timeout=timeout.total_seconds(),
            )
        except FileNotFoundError as exc:
            raise TelemetryLossError(reason="missing telemetry command", raw=argv[0]) from exc
        except subprocess.TimeoutExpired as exc:
            raise TelemetryLossError(reason="telemetry command timeout", raw=argv[0]) from exc
        return completed.stdout
