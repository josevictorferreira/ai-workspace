"""Behavior tests for fail-closed total-VRAM telemetry (T5).

Locks the hard-channel contract verified locally:

    rocm-smi --showmeminfo vram --json
    -> {"card0":{"VRAM Total Memory (B)":"17163091968",
                 "VRAM Total Used Memory (B)":"807677952"}}

Values are string-encoded bytes; the device key is ``card0``. Total used VRAM
is compared against exactly ``13,958,643,712`` bytes (13 GiB). Anything below
the limit permits launch; the exact limit and one byte over are breaches.
Missing/malformed/stale hard telemetry fails closed as ``telemetry-loss``.
Diagnostics (temperature/power/use/clocks/PCIe) are best-effort and never a
hidden hard gate. No GPU, model, or network is required.
"""

from __future__ import annotations

import stat
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from llama_optimizer.telemetry import (
    DEVICE_KEY,
    TOTAL_FIELD,
    USED_FIELD,
    VRAM_CEILING_BYTES,
    Bytes,
    Diagnostics,
    HardChannel,
    RocmSmiProvider,
    TelemetryLossError,
    is_breach,
    parse_diagnostics,
    parse_hard_channel,
)

FIXTURE = Path(__file__).resolve().parent / "fixtures" / "bin" / "rocm-smi"
_CEILING = 13_958_643_712
_NOW = datetime(2026, 6, 28, 12, 0, 0, tzinfo=UTC)


def _ensure_executable() -> None:
    mode = FIXTURE.stat().st_mode
    if not mode & stat.S_IXUSR:
        FIXTURE.chmod(mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


_ensure_executable()


# --- Hard-channel parsing ---------------------------------------------------


class TestParseHardChannel:
    def test_parses_verified_local_shape(self) -> None:
        # Given the exact verified local rocm-smi hard-channel payload.
        raw = (
            '{"card0":{"VRAM Total Memory (B)":"17163091968",'
            '"VRAM Total Used Memory (B)":"807677952"}}'
        )
        # When parsing it.
        sample = parse_hard_channel(raw, collected_at=_NOW)
        # Then total/used are typed bytes and the raw payload is retained.
        assert sample.total == Bytes(17_163_091_968)
        assert sample.used == Bytes(807_677_952)
        assert sample.collected_at == _NOW
        assert sample.raw == raw

    def test_strips_surrounding_whitespace(self) -> None:
        # Given a valid payload padded with newlines/spaces.
        raw = '\n  {"card0":{"VRAM Total Memory (B)":"17163091968","VRAM Total Used Memory (B)":"1"}}  \n'  # noqa: E501
        # When parsing it.
        sample = parse_hard_channel(raw, collected_at=_NOW)
        # Then it parses (bytes are not confused by surrounding whitespace).
        assert sample.used == Bytes(1)

    @pytest.mark.parametrize(
        ("raw", "reason_fragment"),
        [
            ("", "empty"),
            ("not json at all", "malformed"),
            ("{}", "malformed"),
            ('{"card0":{}}', "malformed"),
            ('{"card1":{}}', "malformed"),
            ('{"card0":{"VRAM Total Memory (B)":"17163091968"}}', "malformed"),
            (
                '{"card0":{"VRAM Total Memory (B)":"x","VRAM Total Used Memory (B)":"1"}}',
                "malformed",
            ),
            (
                '{"card0":{"VRAM Total Memory (B)":"1","VRAM Total Used Memory (B)":"y"}}',
                "malformed",
            ),
            (
                '{"card0":{"VRAM Total Memory (B)":17163091968,"VRAM Total Used Memory (B)":"1"}}',
                "malformed",
            ),
            (
                '{"card0":{"VRAM Total Memory (B)":"1","VRAM Total Used Memory (B)":-100}}',
                "malformed",
            ),
        ],
    )
    def test_rejects_malformed_missing_or_untyped(self, raw: str, reason_fragment: str) -> None:
        # Given a payload that is empty, malformed, missing fields/keys, or non-string bytes.
        # When parsing it.
        with pytest.raises(TelemetryLossError) as exc:
            _ = parse_hard_channel(raw, collected_at=_NOW)
        # Then it fails closed with a reason mentioning the offending fragment.
        assert reason_fragment in exc.value.reason

    def test_rejects_non_string_bytes_is_typed_not_validated(self) -> None:
        # Given a payload where used bytes is a JSON number, not a string.
        raw = '{"card0":{"VRAM Total Memory (B)":"17163091968","VRAM Total Used Memory (B)":807677952}}'  # noqa: E501
        # When parsing it.
        # Then it fails closed (boundary narrows to str, never re-validates).
        with pytest.raises(TelemetryLossError):
            _ = parse_hard_channel(raw, collected_at=_NOW)

    def test_ignores_extra_devices_but_keeps_card0(self) -> None:
        # Given a payload with an extra device alongside card0.
        raw = (
            '{"card0":{"VRAM Total Memory (B)":"17163091968","VRAM Total Used Memory (B)":"100"},'
            '"card1":{"VRAM Total Memory (B)":"17163091968","VRAM Total Used Memory (B)":"200"}}'
        )
        # When parsing it.
        sample = parse_hard_channel(raw, collected_at=_NOW)
        # Then card0 is authoritative (per-process VRAM is never summed as the hard signal).
        assert sample.used == Bytes(100)


# --- Breach boundary --------------------------------------------------------


class TestBreachBoundary:
    def test_one_byte_below_ceiling_is_not_breach(self) -> None:
        # Given a sample one byte under the exact ceiling.
        sample = HardChannel(
            total=Bytes(17_163_091_968),
            used=Bytes(_CEILING - 1),
            collected_at=_NOW,
            raw="",
        )
        # When checking breach.
        # Then it is feasible (at-or-over blocks; one under does not).
        assert not is_breach(sample)

    def test_exact_ceiling_is_breach(self) -> None:
        # Given a sample at exactly the ceiling.
        sample = HardChannel(
            total=Bytes(17_163_091_968),
            used=Bytes(_CEILING),
            collected_at=_NOW,
            raw="",
        )
        # When checking breach.
        # Then at-the-limit blocks launch.
        assert is_breach(sample)

    def test_one_byte_over_ceiling_is_breach(self) -> None:
        # Given a sample one byte over the ceiling.
        sample = HardChannel(
            total=Bytes(17_163_091_968),
            used=Bytes(_CEILING + 1),
            collected_at=_NOW,
            raw="",
        )
        # When checking breach.
        # Then it is a breach.
        assert is_breach(sample)

    def test_ceiling_constant_is_exact(self) -> None:
        # Given the plan's exact hard constant.
        # Then the module exposes it verbatim.
        assert Bytes(13_958_643_712) == VRAM_CEILING_BYTES
        assert DEVICE_KEY == "card0"
        assert TOTAL_FIELD == "VRAM Total Memory (B)"
        assert USED_FIELD == "VRAM Total Used Memory (B)"


# --- RocmSmi provider against the real fake fixture -------------------------


class TestRocmSmiProvider:
    def test_samples_below_limit_hard_channel(self) -> None:
        # Given the fake fixture in valid mode with low usage.
        provider = RocmSmiProvider(str(FIXTURE), timeout=timedelta(seconds=5))
        env = {"ROCM_SMI_MODE": "valid", "ROCM_SMI_USED_BYTES": "807677952"}
        # When sampling via the real subprocess.
        with pytest.MonkeyPatch().context() as ctx:
            for k, v in env.items():
                ctx.setenv(k, v)
            sample = provider.sample()
        # Then it parses strictly and reports below-limit usage.
        assert sample.used == Bytes(807_677_952)
        assert not is_breach(sample)

    def test_exact_limit_sample_is_breach(self) -> None:
        # Given the fake fixture emitting exactly the ceiling.
        provider = RocmSmiProvider(str(FIXTURE), timeout=timedelta(seconds=5))
        # When sampling.
        with pytest.MonkeyPatch().context() as ctx:
            ctx.setenv("ROCM_SMI_MODE", "exact")
            sample = provider.sample()
        # Then the sample is at the limit and is a breach.
        assert sample.used == Bytes(_CEILING)
        assert is_breach(sample)

    def test_one_byte_over_sample_is_breach(self) -> None:
        # Given the fake fixture emitting one byte over the ceiling.
        provider = RocmSmiProvider(str(FIXTURE), timeout=timedelta(seconds=5))
        # When sampling.
        with pytest.MonkeyPatch().context() as ctx:
            ctx.setenv("ROCM_SMI_MODE", "breach")
            ctx.setenv("ROCM_SMI_USED_BYTES", str(_CEILING + 1))
            sample = provider.sample()
        # Then the sample is over the limit and is a breach.
        assert sample.used == Bytes(_CEILING + 1)
        assert is_breach(sample)

    @pytest.mark.parametrize(
        ("mode", "reason_fragment"),
        [
            ("malformed", "malformed"),
            ("empty", "empty"),
            ("missing_field", "VRAM Total Used Memory"),
            ("nonstring", "VRAM Total Memory"),
            ("no_card", "card0"),
        ],
    )
    def test_malformed_or_missing_fails_closed(self, mode: str, reason_fragment: str) -> None:
        # Given the fake fixture emitting malformed/missing/untyped hard output.
        provider = RocmSmiProvider(str(FIXTURE), timeout=timedelta(seconds=5))
        # When sampling.
        with pytest.MonkeyPatch().context() as ctx:
            ctx.setenv("ROCM_SMI_MODE", mode)
            # Then it raises telemetry-loss with the offending reason.
            with pytest.raises(TelemetryLossError) as exc:
                _ = provider.sample()
        assert reason_fragment in exc.value.reason

    def test_missing_command_fails_closed(self, tmp_path: Path) -> None:
        # Given a provider pointing at a nonexistent rocm-smi binary.
        missing = tmp_path / "does-not-exist-smi"
        provider = RocmSmiProvider(str(missing), timeout=timedelta(seconds=5))
        # When sampling.
        # Then it fails closed as telemetry-loss (missing command).
        with pytest.raises(TelemetryLossError) as exc:
            _ = provider.sample()
        assert "missing" in exc.value.reason or "command" in exc.value.reason

    def test_provider_timeout_fails_closed(self) -> None:
        # Given the fake fixture hanging past the provider timeout.
        provider = RocmSmiProvider(str(FIXTURE), timeout=timedelta(milliseconds=300))
        # When sampling.
        with pytest.MonkeyPatch().context() as ctx:
            ctx.setenv("ROCM_SMI_MODE", "hang")
            # Then it fails closed as telemetry-loss (deadline).
            with pytest.raises(TelemetryLossError) as exc:
                _ = provider.sample()
        assert "timeout" in exc.value.reason or "deadline" in exc.value.reason

    def test_diagnostics_snapshot_is_best_effort(self) -> None:
        # Given the fake fixture emitting a diagnostics table.
        provider = RocmSmiProvider(str(FIXTURE), timeout=timedelta(seconds=5))
        # When reading diagnostics.
        with pytest.MonkeyPatch().context() as ctx:
            ctx.setenv("ROCM_SMI_MODE", "diagnostics")
            diag = provider.diagnostics()
        # Then it returns a typed snapshot without raising (never a hard gate).
        assert isinstance(diag, Diagnostics)
        assert diag.raw

    def test_diagnostics_never_raises_on_garbage(self) -> None:
        # Given the fake fixture emitting a non-rocm table.
        provider = RocmSmiProvider(str(FIXTURE), timeout=timedelta(seconds=5))
        # When reading diagnostics.
        with pytest.MonkeyPatch().context() as ctx:
            ctx.setenv("ROCM_SMI_MODE", "diag_malformed")
            diag = provider.diagnostics()
        # Then it returns an empty snapshot rather than failing the trial.
        assert isinstance(diag, Diagnostics)

    def test_diagnostics_missing_command_returns_empty(self, tmp_path: Path) -> None:
        # Given a provider pointing at a nonexistent binary.
        missing = tmp_path / "no-smi"
        provider = RocmSmiProvider(str(missing), timeout=timedelta(seconds=5))
        # When reading diagnostics.
        diag = provider.diagnostics()
        # Then it yields an empty snapshot (best-effort, never a hard gate).
        assert isinstance(diag, Diagnostics)
        assert diag.temperature is None


class TestParseDiagnostics:
    def test_extracts_known_sensors(self) -> None:
        # Given a diagnostics table with temperature/power/use/clocks/pcie.
        raw = (
            "================================= ROCm System Interface =================================\n"  # noqa: E501
            "GPU[0]              : temperature: 46.0c\n"
            "GPU[0]              :     average power: 118.0W\n"
            "GPU[0]              : GPU use: 6%\n"
            "GPU[0]              : GPU-CLK: 2528MHz\n"
            "GPU[0]              : PCIe (TX/RX): 0.23GB/s / 1.04GB/s\n"
        )
        # When parsing it.
        diag = parse_diagnostics(raw)
        # Then each sensor is captured as an opaque string.
        assert diag.temperature == "46.0c"
        assert diag.power == "118.0W"
        assert diag.gpu_use == "6%"
        assert diag.clocks == "2528MHz"
        assert diag.pcie == "0.23GB/s / 1.04GB/s"
        assert diag.raw == raw

    def test_garbage_returns_empty_snapshot(self) -> None:
        # Given a non-rocm table.
        # When parsing it.
        diag = parse_diagnostics("totally not a rocm-smi table\n")
        # Then no sensor is captured but the raw text is retained.
        assert diag.temperature is None
        assert diag.power is None
        assert diag.gpu_use is None
        assert diag.clocks is None
        assert diag.pcie is None


# --- Static guard: no type escape hatches -----------------------------------


class TestNoTypingEscapeHatchesInTelemetry:
    """First-party telemetry source must not silence the type checker."""

    def test_no_escape_hatches_in_telemetry_or_supervisor_source(self) -> None:
        # Given every first-party module touched by T5.
        src_dir = Path(__file__).resolve().parent.parent / "src" / "llama_optimizer"
        targets = sorted(
            p for name in ("telemetry.py", "supervisor.py") for p in (src_dir / name,).__iter__()
        )
        targets = [src_dir / "telemetry.py", src_dir / "supervisor.py"]
        offenders: list[str] = []
        for py_file in targets:
            if not py_file.exists():
                offenders.append(f"{py_file.name}: missing module")
                continue
            for line_no, line in enumerate(py_file.read_text().splitlines(), start=1):
                stripped = line.strip()
                if (
                    "type: ignore" in stripped
                    or "# noqa" in stripped
                    or "from typing import Any" in stripped
                    or "import Any" in stripped
                    or "cast(" in stripped
                    or "typing.Any" in stripped
                    or "typing.cast" in stripped
                ):
                    offenders.append(f"{py_file.name}:{line_no}: {stripped}")
        # Then none of them contain an escape hatch.
        assert not offenders, "escape hatches found:\n" + "\n".join(offenders)
