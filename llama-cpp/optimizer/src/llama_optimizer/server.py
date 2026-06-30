"""Exact-32K llama-server finalist validation with drift-aware scheduling (T9).

Re-exports the split responsibility modules so callers can import from
``llama_optimizer.server``. Finalists are started through the T5 supervisor
with ``--ctx-size 32768`` and a matching model/backend/runtime identity.
Readiness, versioned coding/tool-use/concurrency/latency workloads, raw
metrics/responses, and synchronized telemetry are captured per finalist.
"""

from __future__ import annotations

from llama_optimizer.server_classify import classify_server_exit
from llama_optimizer.server_command import build_server_command
from llama_optimizer.server_http import WorkloadRecord
from llama_optimizer.server_parser import (
    ParsedResponse,
    ReadinessResult,
    parse_readiness,
    parse_responses,
    parse_server_metrics,
)
from llama_optimizer.server_runner import ValidationPlan, run_supervised_server, validate_finalists
from llama_optimizer.server_schedule import (
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
    EligibilityStatus,
    FinalistEntry,
    FinalistRequest,
    FinalistResult,
    LifecycleRecord,
    MetricsParseError,
    ReadinessTimeoutError,
    RequestKind,
    RequestSpec,
    ScheduledFinalist,
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
    "EligibilityStatus",
    "FinalistEntry",
    "FinalistRequest",
    "FinalistResult",
    "LifecycleRecord",
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
    "ValidationPlan",
    "WorkloadRecord",
    "build_server_command",
    "classify_server_exit",
    "interleave_requests",
    "parse_readiness",
    "parse_responses",
    "parse_server_metrics",
    "run_supervised_server",
    "schedule_finalists",
    "total_request_count",
    "validate_finalists",
]
