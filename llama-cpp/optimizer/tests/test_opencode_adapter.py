"""Tests for the OpenCode adapter."""

from __future__ import annotations

import json

import pytest

from llama_optimizer.adapters import (
    ADAPTER_PROTOCOL_VERSION,
    AdapterResult,
    AdapterVersionError,
    StructuredEvent,
    filter_env,
)
from llama_optimizer.adapters.opencode import _check_version, _parse_events


class TestParseEvents:
    def test_parses_valid_json_lines(self) -> None:
        stdout = json.dumps({"event_type": "run_started", "profile": "test.toml"}) + "\n"
        stdout += json.dumps({"event_type": "trial_completed", "trial_id": "t1"}) + "\n"
        events = _parse_events(stdout)
        assert len(events) == 2
        assert events[0].event_type == "run_started"
        assert events[1].event_type == "trial_completed"

    def test_tolerates_unknown_event_types(self) -> None:
        stdout = json.dumps({"event_type": "future_event", "data": 42}) + "\n"
        events = _parse_events(stdout)
        assert len(events) == 1
        assert events[0].event_type == "future_event"

    def test_handles_missing_event_type(self) -> None:
        stdout = json.dumps({"data": "no type"}) + "\n"
        events = _parse_events(stdout)
        assert len(events) == 1
        assert events[0].event_type == "unknown"

    def test_skips_empty_lines(self) -> None:
        stdout = "\n\n" + json.dumps({"event_type": "test"}) + "\n\n"
        events = _parse_events(stdout)
        assert len(events) == 1

    def test_handles_malformed_json(self) -> None:
        stdout = "not json\n"
        stdout += json.dumps({"event_type": "valid"}) + "\n"
        events = _parse_events(stdout)
        assert len(events) == 2
        assert events[0].event_type == "parse_error"
        assert events[1].event_type == "valid"

    def test_records_line_numbers(self) -> None:
        stdout = json.dumps({"event_type": "a"}) + "\n"
        stdout += "\n"  # empty line
        stdout += json.dumps({"event_type": "b"}) + "\n"
        events = _parse_events(stdout)
        assert events[0].line_number == 1
        assert events[1].line_number == 3

    def test_strips_event_type_from_data(self) -> None:
        stdout = json.dumps({"event_type": "test", "key": "value"}) + "\n"
        events = _parse_events(stdout)
        assert "event_type" not in events[0].data
        assert events[0].data["key"] == "value"


class TestCheckVersion:
    def test_matching_version_passes(self) -> None:
        events = (
            StructuredEvent(
                event_type="run_started",
                data={"protocol_version": ADAPTER_PROTOCOL_VERSION},
                line_number=1,
            ),
        )
        _check_version(events)  # should not raise

    def test_mismatched_version_raises(self) -> None:
        events = (
            StructuredEvent(
                event_type="run_started",
                data={"protocol_version": 999},
                line_number=1,
            ),
        )
        with pytest.raises(AdapterVersionError) as exc_info:
            _check_version(events)
        assert exc_info.value.expected == ADAPTER_PROTOCOL_VERSION
        assert exc_info.value.actual == 999

    def test_no_version_is_compatible(self) -> None:
        events = (
            StructuredEvent(
                event_type="run_started",
                data={"profile": "test.toml"},
                line_number=1,
            ),
        )
        _check_version(events)  # should not raise


class TestFilterEnv:
    def test_filters_to_allowlist(self) -> None:
        env = {"HOME": "/home/test", "SECRET_KEY": "abc", "PATH": "/usr/bin"}
        filtered = filter_env(env)
        assert "HOME" in filtered
        assert "PATH" in filtered
        assert "SECRET_KEY" not in filtered

    def test_preserves_allowlisted_values(self) -> None:
        env = {"HOME": "/custom/home"}
        filtered = filter_env(env)
        assert filtered["HOME"] == "/custom/home"


class TestAdapterResult:
    def test_fields(self) -> None:
        result = AdapterResult(
            events=(),
            stderr="",
            return_code=0,
            timed_out=False,
        )
        assert result.events == ()
        assert result.stderr == ""
        assert result.return_code == 0
        assert result.timed_out is False
