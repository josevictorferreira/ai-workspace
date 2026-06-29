"""Exact-32K llama-server finalist validation with drift-aware scheduling (T9).

Re-exports the split responsibility modules so callers can import from
``llama_optimizer.server``. Finalists are started through the T5 supervisor
with ``--ctx-size 32768`` and a matching model/backend/runtime identity.
Readiness, versioned coding/tool-use/concurrency/latency workloads, raw
metrics/responses, and synchronized telemetry are captured per finalist.
"""

from __future__ import annotations

from llama_optimizer.server_command import build_server_command
from llama_optimizer.server_parser import (
    ParsedResponse,
    ReadinessResult,
    parse_readiness,
    parse_responses,
    parse_server_metrics,
)
from llama_optimizer.server_runner import classify_server_exit, run_supervised_server
from llama_optimizer.server_schedule import (
    ScheduledFinalist,
    ScheduledRequest,
    interleave_requests,
    schedule_finalists,
    total_request_count,
)
from llama_optimizer.server_types import (
    CODING_SPEC,
    CONCURRENCY_SPEC,
    DEFAULT_SERVER_CONFIG,
    LATENCY_SPEC,
    TOOL_USE_SPEC,
    FinalistEntry,
    FinalistRequest,
    FinalistResult,
    MetricsParseError,
    ReadinessTimeoutError,
    RequestKind,
    RequestSpec,
    ServerConfig,
    ServerError,
    ServerIdentity,
    ServerIdentityMismatchError,
    ServerMetrics,
)

__all__ = [
    "CODING_SPEC",
    "CONCURRENCY_SPEC",
    "DEFAULT_SERVER_CONFIG",
    "LATENCY_SPEC",
    "TOOL_USE_SPEC",
    "FinalistEntry",
    "FinalistRequest",
    "FinalistResult",
    "MetricsParseError",
    "ParsedResponse",
    "ReadinessResult",
    "ReadinessTimeoutError",
    "RequestKind",
    "RequestSpec",
    "ScheduledFinalist",
    "ScheduledRequest",
    "ServerConfig",
    "ServerError",
    "ServerIdentity",
    "ServerIdentityMismatchError",
    "ServerMetrics",
    "build_server_command",
    "classify_server_exit",
    "interleave_requests",
    "parse_readiness",
    "parse_responses",
    "parse_server_metrics",
    "run_supervised_server",
    "schedule_finalists",
    "total_request_count",
]
