"""OpenCode adapter for launching optimizer runs and reports.

This adapter wraps ``llama-cpp-opt run`` and ``llama-cpp-opt report``
for invocation from OpenCode agents. It uses ``--format json`` for
structured output parsing.

Permissions model:
  - ``run``: invoke optimizer search only
  - ``report``: read-only (read, grep, find, ls); excludes bash, edit, write

Environment: only explicit allowlisted variables are passed.
"""

from __future__ import annotations

import contextlib
import json
import os
import subprocess
from typing import TYPE_CHECKING

from llama_optimizer.adapters import (
    ADAPTER_PROTOCOL_VERSION,
    AdapterResult,
    AdapterVersionError,
    StructuredEvent,
    filter_env,
)

if TYPE_CHECKING:
    from pathlib import Path

# Default timeouts
_RUN_TIMEOUT_SECONDS = 3600  # 1 hour for full optimization run
_REPORT_TIMEOUT_SECONDS = 60  # 1 minute for report generation


def _parse_events(stdout: str) -> tuple[StructuredEvent, ...]:
    """Parse newline-delimited JSON events from CLI stdout.

    Unknown event types are tolerated (forward compatibility).
    Malformed JSON lines are skipped with a synthetic error event.
    """
    events: list[StructuredEvent] = []
    for line_num, raw_line in enumerate(stdout.splitlines(), start=1):
        line = raw_line.strip()
        if not line:
            continue
        try:
            data = json.loads(line)
        except json.JSONDecodeError:
            events.append(
                StructuredEvent(
                    event_type="parse_error",
                    data={"raw": line, "error": "malformed JSON"},
                    line_number=line_num,
                )
            )
            continue

        event_type = data.pop("event_type", "unknown")
        events.append(
            StructuredEvent(
                event_type=event_type,
                data=data,
                line_number=line_num,
            )
        )
    return tuple(events)


def _check_version(events: tuple[StructuredEvent, ...]) -> None:
    """Check protocol version from initial event.

    Raises AdapterVersionError if versions are incompatible.
    """
    for event in events:
        if "protocol_version" in event.data:
            raw_version = event.data["protocol_version"]
            actual = int(str(raw_version))
            if actual != ADAPTER_PROTOCOL_VERSION:
                raise AdapterVersionError(ADAPTER_PROTOCOL_VERSION, actual)
            return
    # No version found - assume compatible (legacy CLI)


def run(
    profile_path: Path,
    *,
    timeout: float = _RUN_TIMEOUT_SECONDS,
    extra_args: tuple[str, ...] = (),
) -> AdapterResult:
    """Launch an optimizer run via ``llama-cpp-opt run``.

    Args:
        profile_path: Path to the immutable TOML profile.
        timeout: Maximum seconds to wait for completion.
        extra_args: Additional CLI arguments.

    Returns:
        AdapterResult with parsed events and stderr.

    Raises:
        AdapterVersionError: CLI version incompatible with adapter.

    """
    cmd = [
        "llama-cpp-opt",
        "run",
        "--format",
        "json",
        str(profile_path),
        *extra_args,
    ]

    env = filter_env(dict(os.environ))

    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            env=env,
            start_new_session=True,  # isolate process group
            check=False,
        )
        timed_out = False
    except subprocess.TimeoutExpired as exc:
        # Kill the process group on timeout
        if exc.cmd:
            with contextlib.suppress(ProcessLookupError, PermissionError):
                pid = getattr(exc, "pid", None)
                if pid is not None:
                    os.killpg(os.getpgid(pid), 9)
        return AdapterResult(
            events=(),
            stderr=str(exc),
            return_code=-1,
            timed_out=True,
        )

    events = _parse_events(proc.stdout)
    _check_version(events)

    return AdapterResult(
        events=events,
        stderr=proc.stderr,
        return_code=proc.returncode,
        timed_out=timed_out,
    )


def report(
    run_dir: Path,
    *,
    timeout: float = _REPORT_TIMEOUT_SECONDS,
    extra_args: tuple[str, ...] = (),
) -> AdapterResult:
    """Generate a report via ``llama-cpp-opt report``.

    This is a read-only operation. The run directory is immutable;
    report generation cannot influence ledger or search outcomes.

    Args:
        run_dir: Path to the completed run directory.
        timeout: Maximum seconds to wait.
        extra_args: Additional CLI arguments.

    Returns:
        AdapterResult with parsed events and stderr.

    Raises:
        AdapterVersionError: CLI version incompatible with adapter.

    """
    cmd = [
        "llama-cpp-opt",
        "report",
        "--format",
        "json",
        str(run_dir),
        *extra_args,
    ]

    env = filter_env(dict(os.environ))

    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            env=env,
            start_new_session=True,
            check=False,
        )
        timed_out = False
    except subprocess.TimeoutExpired as exc:
        if exc.cmd:
            with contextlib.suppress(ProcessLookupError, PermissionError):
                pid = getattr(exc, "pid", None)
                if pid is not None:
                    os.killpg(os.getpgid(pid), 9)
        return AdapterResult(
            events=(),
            stderr=str(exc),
            return_code=-1,
            timed_out=True,
        )

    events = _parse_events(proc.stdout)
    _check_version(events)

    return AdapterResult(
        events=events,
        stderr=proc.stderr,
        return_code=proc.returncode,
        timed_out=timed_out,
    )
