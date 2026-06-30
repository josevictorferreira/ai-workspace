"""Drift-aware finalist scheduling from the run seed (T9).

Finalist order is shuffled from the run seed so no finalist systematically
benefits from thermal warmup or cooldown position bias. Within each finalist,
versioned request specs are interleaved round-robin across raw repetitions,
with warmup always first. The schedule is fully deterministic from the seed
and the input order, so two runs with the same seed and finalists produce the
same interleaved sequence.

A deterministic LCG (linear congruential generator) drives the Fisher-Yates
shuffle instead of :mod:`random` so no cryptographic-suitability concern
(Ruff S311) applies while remaining fully reproducible.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Final

from llama_optimizer.server_types import ScheduledFinalist

if TYPE_CHECKING:
    from llama_optimizer.server_types import FinalistEntry, RequestSpec, ServerConfig

_LCG_MULTIPLIER: Final[int] = 6364136223846793005
_LCG_INCREMENT: Final[int] = 1442695040888963407
_LCG_MASK: Final[int] = 0xFFFFFFFFFFFFFFFF
_LCG_SHIFT: Final[int] = 33


@dataclass(frozen=True, slots=True)
class ScheduledRequest:
    """One interleaved request slot: warmup or a raw repetition."""

    is_warmup: bool
    spec: RequestSpec
    repetition: int


def _deterministic_shuffle(finalists: list[FinalistEntry], seed: int) -> list[FinalistEntry]:
    """Fisher-Yates shuffle driven by a seed-seeded LCG (not ``random.Random``)."""
    shuffled = list(finalists)
    state = seed & _LCG_MASK
    for i in range(len(shuffled) - 1, 0, -1):
        state = (state * _LCG_MULTIPLIER + _LCG_INCREMENT) & _LCG_MASK
        j = (state >> _LCG_SHIFT) % (i + 1)
        shuffled[i], shuffled[j] = shuffled[j], shuffled[i]
    return shuffled


def schedule_finalists(
    finalists: tuple[FinalistEntry, ...],
    seed: int,
) -> tuple[ScheduledFinalist, ...]:
    """Return finalists in a seeded-shuffled, reproducible order.

    An empty input yields an empty schedule. The shuffle uses a dedicated
    LCG seeded from ``seed`` so it is independent of global RNG state. The
    original input order is preserved for equal finalists.
    """
    if not finalists:
        return ()
    shuffled = _deterministic_shuffle(list(finalists), seed)
    return tuple(ScheduledFinalist(position=i, finalist=f) for i, f in enumerate(shuffled))


def interleave_requests(config: ServerConfig) -> tuple[ScheduledRequest, ...]:
    """Interleave request specs round-robin across repetitions; warmup first.

    Warmup runs every spec once (position 0) before the raw repetitions.
    Repetitions then round-robin: spec0-rep1, spec1-rep1, ..., spec0-rep2, ...
    so workload types are spread across the measurement window rather than
    clustered. The full per-repetition sequence is retained for evidence.
    """
    specs = config.request_specs
    sequence: list[ScheduledRequest] = [
        ScheduledRequest(is_warmup=True, spec=spec, repetition=0) for spec in specs
    ]
    for rep in range(1, config.repetitions + 1):
        sequence.extend(
            ScheduledRequest(is_warmup=False, spec=spec, repetition=rep) for spec in specs
        )
    return tuple(sequence)


def total_request_count(config: ServerConfig) -> int:
    """Return the total number of requests (warmup + raw repetitions)."""
    specs = len(config.request_specs)
    return specs + specs * config.repetitions
