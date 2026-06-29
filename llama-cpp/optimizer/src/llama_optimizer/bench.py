"""llama-bench JSONL execution and bounded screening (T6).

This module re-exports the split responsibility modules so callers can continue
importing from ``llama_optimizer.bench``.
"""

from __future__ import annotations

from llama_optimizer.bench_command import build_bench_command
from llama_optimizer.bench_parser import parse_bench_jsonl
from llama_optimizer.bench_runner import classify_child_exit, run_supervised_bench
from llama_optimizer.bench_types import (
    DEFAULT_BENCH_CONFIG,
    PP512,
    TG128,
    BenchConfig,
    BenchIdentity,
    BenchMeasurement,
    BenchResult,
    BenchSample,
    BenchScreenRequest,
    BenchScreenResult,
    BenchWorkload,
    MeasurementFailureError,
)

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
    "MeasurementFailureError",
    "build_bench_command",
    "classify_child_exit",
    "parse_bench_jsonl",
    "run_supervised_bench",
)
