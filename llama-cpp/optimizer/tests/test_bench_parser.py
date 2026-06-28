"""Behavior tests for llama-bench JSONL parsing and command construction (T6).

Tests lock the parser contract: identity cross-check, raw sample retention,
missing-sample rejection, NaN/negative rejection, and malformed-output
classification. Tests lock the command builder: forced JSONL output, exact
32768 depth, warmup enabled (never disabled), repetitions/delay from config,
and argument arrays constructed without shell interpolation.

No GPU, model, or network is required.
"""

from __future__ import annotations

import json
import math

import pytest

from llama_optimizer.bench import (
    DEFAULT_BENCH_CONFIG,
    PP512,
    TG128,
    BenchConfig,
    BenchIdentity,
    MeasurementFailureError,
    build_bench_command,
    classify_child_exit,
    parse_bench_jsonl,
)
from llama_optimizer.lifecycle import NonScoredOutcome
from llama_optimizer.supervisor import ChildExit

_IDENTITY = BenchIdentity(
    model_filename="ornith-1.0-9b-Q4_K_M.gguf",
    n_gpu_layers=99,
    n_batch=2048,
    n_ubatch=512,
    type_k="f16",
    type_v="f16",
    n_threads=16,
    flash_attn=1,
    use_mmap=True,
)

_WORKLOADS = ("pp512", "tg128")


def _make_jsonl_line(  # noqa: PLR0913
    *,
    name: str = "pp512",
    n_prompt: int = 512,
    n_gen: int = 0,
    avg_ts: float = 250.0,
    samples_ns: list[int] | None = None,
    samples_ts: list[float] | None = None,
    model: str = _IDENTITY.model_filename,
    ngl: int = _IDENTITY.n_gpu_layers,
    batch: int = _IDENTITY.n_batch,
    ubatch: int = _IDENTITY.n_ubatch,
    type_k: str = _IDENTITY.type_k,
    type_v: str = _IDENTITY.type_v,
    threads: int = _IDENTITY.n_threads,
    flash: int = _IDENTITY.flash_attn,
    n_depth: int = 32768,
) -> str:
    """Build one JSONL line matching the llama-bench machine schema."""
    if samples_ns is None:
        samples_ns = [4_000_000, 4_032_000, 4_000_000]
    if samples_ts is None:
        samples_ts = [248.0, 250.0, 252.0]
    payload: dict[str, object] = {
        "build": 1234,
        "model": model,
        "name": name,
        "n_gpu_layers": ngl,
        "n_batch": batch,
        "n_ubatch": ubatch,
        "type_k": type_k,
        "type_v": type_v,
        "n_threads": threads,
        "flash_attn": flash,
        "n_prompt": n_prompt,
        "n_gen": n_gen,
        "n_depth": n_depth,
        "avg_ts": avg_ts,
        "stddev_ts": 2.0,
        "avg_ns": 4_010_666,
        "stddev_ns": 1000,
        "samples_ns": samples_ns,
        "samples_ts": samples_ts,
    }
    return json.dumps(payload)


# --- Command builder tests --------------------------------------------------


class TestBuildBenchCommand:
    def test_forces_jsonl_output(self) -> None:
        # Given a valid config and identity.
        cmd = build_bench_command("/usr/bin/llama-bench", DEFAULT_BENCH_CONFIG, _IDENTITY)
        # Then the output format is jsonl.
        assert "-o" in cmd
        assert cmd[cmd.index("-o") + 1] == "jsonl"

    def test_forces_exact_32768_depth(self) -> None:
        # Given any config.
        cmd = build_bench_command("/usr/bin/llama-bench", DEFAULT_BENCH_CONFIG, _IDENTITY)
        # Then depth is exactly 32768.
        assert "-d" in cmd
        assert cmd[cmd.index("-d") + 1] == "32768"

    def test_never_disables_warmup(self) -> None:
        # Given any config.
        cmd = build_bench_command("/usr/bin/llama-bench", DEFAULT_BENCH_CONFIG, _IDENTITY)
        # Then --no-warmup is never present.
        assert "--no-warmup" not in cmd

    def test_repetitions_and_delay_from_config(self) -> None:
        # Given a config with 5 repetitions and 2-second delay.
        config = BenchConfig(repetitions=5, delay_seconds=2, workloads=(PP512,))
        cmd = build_bench_command("/usr/bin/llama-bench", config, _IDENTITY)
        # Then -r is 5 and --delay is 2.
        assert cmd[cmd.index("-r") + 1] == "5"
        assert cmd[cmd.index("--delay") + 1] == "2"

    def test_explicit_backend_model_config_flags(self) -> None:
        # Given an identity with specific values.
        cmd = build_bench_command("/usr/bin/llama-bench", DEFAULT_BENCH_CONFIG, _IDENTITY)
        # Then every identity field appears as an explicit flag.
        assert cmd[cmd.index("-m") + 1] == _IDENTITY.model_filename
        assert cmd[cmd.index("-ngl") + 1] == "99"
        assert cmd[cmd.index("-b") + 1] == "2048"
        assert cmd[cmd.index("-ub") + 1] == "512"
        assert cmd[cmd.index("-ctk") + 1] == "f16"
        assert cmd[cmd.index("-ctv") + 1] == "f16"
        assert cmd[cmd.index("-t") + 1] == "16"
        assert cmd[cmd.index("-fa") + 1] == "on"
        assert cmd[cmd.index("-mmp") + 1] == "1"

    def test_workloads_as_comma_joined_values(self) -> None:
        # Given a config with pp512 and tg128 workloads.
        cmd = build_bench_command("/usr/bin/llama-bench", DEFAULT_BENCH_CONFIG, _IDENTITY)
        # Then -p and -n carry comma-joined workload values.
        assert cmd[cmd.index("-p") + 1] == "512,0"
        assert cmd[cmd.index("-n") + 1] == "0,128"

    def test_no_shell_interpolation(self) -> None:
        # Given an identity with special characters in the filename.
        identity = BenchIdentity(
            model_filename="safe-name.gguf",
            n_gpu_layers=1,
            n_batch=1,
            n_ubatch=1,
            type_k="f16",
            type_v="f16",
            n_threads=1,
            flash_attn=0,
            use_mmap=False,
        )
        cmd = build_bench_command("/usr/bin/llama-bench", DEFAULT_BENCH_CONFIG, identity)
        # Then every element is a standalone argv string (no shell metacharacters).
        assert all(isinstance(arg, str) for arg in cmd)
        assert any(";" not in arg for arg in cmd)

    def test_flash_attn_off_when_zero(self) -> None:
        # Given an identity with flash_attn=0.
        identity = BenchIdentity(
            model_filename="m.gguf",
            n_gpu_layers=1,
            n_batch=1,
            n_ubatch=1,
            type_k="f16",
            type_v="f16",
            n_threads=1,
            flash_attn=0,
            use_mmap=True,
        )
        cmd = build_bench_command("/usr/bin/llama-bench", DEFAULT_BENCH_CONFIG, identity)
        assert cmd[cmd.index("-fa") + 1] == "off"

    def test_mmp_zero_when_use_mmap_false(self) -> None:
        identity = BenchIdentity(
            model_filename="m.gguf",
            n_gpu_layers=1,
            n_batch=1,
            n_ubatch=1,
            type_k="f16",
            type_v="f16",
            n_threads=1,
            flash_attn=1,
            use_mmap=False,
        )
        cmd = build_bench_command("/usr/bin/llama-bench", DEFAULT_BENCH_CONFIG, identity)
        assert cmd[cmd.index("-mmp") + 1] == "0"


# --- JSONL parser happy path ------------------------------------------------


class TestParseBenchJsonlHappy:
    def test_parses_two_workloads_with_samples(self) -> None:
        # Given valid JSONL with pp512 and tg128 lines.
        raw = (
            _make_jsonl_line(name="pp512")
            + "\n"
            + _make_jsonl_line(
                name="tg128",
                n_prompt=0,
                n_gen=128,
                avg_ts=42.5,
                samples_ns=[3_000_000, 3_000_000, 2_990_000],
                samples_ts=[41.5, 42.5, 43.5],
            )
            + "\n"
        )
        # When parsing.
        result = parse_bench_jsonl(raw, expected=_IDENTITY, expected_workload_names=_WORKLOADS)
        # Then two measurements are extracted with raw samples retained.
        assert len(result.measurements) == 2
        pp = next(m for m in result.measurements if m.workload_name == "pp512")
        assert pp.avg_ts == 250.0
        assert len(pp.samples) == 3
        assert pp.samples[0].ns == 4_000_000
        assert pp.samples[0].ts == 248.0
        tg = next(m for m in result.measurements if m.workload_name == "tg128")
        assert tg.avg_ts == 42.5
        assert len(tg.samples) == 3
        assert result.raw_jsonl == raw

    def test_retains_every_per_repetition_sample(self) -> None:
        # Given JSONL with 5 repetitions.
        samples_ns = [1_000_000, 2_000_000, 3_000_000, 4_000_000, 5_000_000]
        samples_ts = [500.0, 250.0, 166.7, 125.0, 100.0]
        raw = _make_jsonl_line(name="pp512", samples_ns=samples_ns, samples_ts=samples_ts) + "\n"
        raw += (
            _make_jsonl_line(
                name="tg128",
                n_prompt=0,
                n_gen=128,
                samples_ns=samples_ns,
                samples_ts=[v / 2 for v in samples_ts],
            )
            + "\n"
        )
        # When parsing.
        result = parse_bench_jsonl(raw, expected=_IDENTITY, expected_workload_names=_WORKLOADS)
        # Then all 5 samples are retained per workload.
        pp = result.measurements[0]
        assert len(pp.samples) == 5
        assert [s.ns for s in pp.samples] == samples_ns


# --- JSONL parser failure cases ---------------------------------------------


class TestParseBenchJsonlFailures:
    def test_empty_output_is_measurement_failure(self) -> None:
        with pytest.raises(MeasurementFailureError, match="empty"):
            _ = parse_bench_jsonl("", expected=_IDENTITY, expected_workload_names=_WORKLOADS)

    def test_malformed_json_is_measurement_failure(self) -> None:
        raw = "this is not json\n"
        with pytest.raises(MeasurementFailureError, match="malformed"):
            _ = parse_bench_jsonl(raw, expected=_IDENTITY, expected_workload_names=_WORKLOADS)

    def test_wrong_model_identity_is_measurement_failure(self) -> None:
        raw = _make_jsonl_line(name="pp512", model="wrong-model.gguf") + "\n"
        raw += (
            _make_jsonl_line(name="tg128", model="wrong-model.gguf", n_prompt=0, n_gen=128) + "\n"
        )
        with pytest.raises(MeasurementFailureError, match="identity mismatch"):
            _ = parse_bench_jsonl(raw, expected=_IDENTITY, expected_workload_names=_WORKLOADS)

    def test_wrong_ngl_identity_is_measurement_failure(self) -> None:
        raw = _make_jsonl_line(name="pp512", ngl=50) + "\n"
        with pytest.raises(MeasurementFailureError, match="identity mismatch"):
            _ = parse_bench_jsonl(raw, expected=_IDENTITY, expected_workload_names=_WORKLOADS)

    def test_nan_throughput_is_measurement_failure(self) -> None:
        raw = _make_jsonl_line(name="pp512", avg_ts=math.nan) + "\n"
        with pytest.raises(MeasurementFailureError, match="avg_ts invalid"):
            _ = parse_bench_jsonl(raw, expected=_IDENTITY, expected_workload_names=_WORKLOADS)

    def test_negative_throughput_is_measurement_failure(self) -> None:
        raw = _make_jsonl_line(name="pp512", avg_ts=-1.0) + "\n"
        with pytest.raises(MeasurementFailureError, match="avg_ts invalid"):
            _ = parse_bench_jsonl(raw, expected=_IDENTITY, expected_workload_names=_WORKLOADS)

    def test_missing_samples_is_measurement_failure(self) -> None:
        payload: dict[str, object] = json.loads(_make_jsonl_line(name="pp512"))  # pyright: ignore[reportAny]
        payload["samples_ns"] = []
        payload["samples_ts"] = []
        raw = json.dumps(payload) + "\n"
        with pytest.raises(MeasurementFailureError, match="missing samples"):
            _ = parse_bench_jsonl(raw, expected=_IDENTITY, expected_workload_names=_WORKLOADS)

    def test_missing_workload_is_measurement_failure(self) -> None:
        raw = _make_jsonl_line(name="pp512") + "\n"
        with pytest.raises(MeasurementFailureError, match="missing workloads"):
            _ = parse_bench_jsonl(raw, expected=_IDENTITY, expected_workload_names=_WORKLOADS)

    def test_sample_count_mismatch_is_measurement_failure(self) -> None:
        raw = _make_jsonl_line(name="pp512", samples_ns=[1, 2, 3], samples_ts=[1.0, 2.0]) + "\n"
        with pytest.raises(MeasurementFailureError, match="sample count mismatch"):
            _ = parse_bench_jsonl(raw, expected=_IDENTITY, expected_workload_names=_WORKLOADS)


# --- Exit classification tests ----------------------------------------------


class TestClassifyChildExit:
    def test_unsupported_is_unsupported(self) -> None:
        outcome = classify_child_exit(ChildExit(returncode=1), "error: unsupported params")
        assert outcome is NonScoredOutcome.UNSUPPORTED

    def test_model_load_error_is_deterministic(self) -> None:
        outcome = classify_child_exit(ChildExit(returncode=1), "error: failed to load model")
        assert outcome is NonScoredOutcome.DETERMINISTIC_LOAD_FAILURE

    def test_other_error_is_transient(self) -> None:
        outcome = classify_child_exit(ChildExit(returncode=1), "error: something else")
        assert outcome is NonScoredOutcome.TRANSIENT_FAILURE

    def test_unsupported_checked_case_insensitively(self) -> None:
        outcome = classify_child_exit(ChildExit(returncode=2), "ERROR: UNSUPPORTED")
        assert outcome is NonScoredOutcome.UNSUPPORTED


# --- BenchConfig validation -------------------------------------------------


class TestBenchConfigValidation:
    def test_context_always_32768(self) -> None:
        config = BenchConfig(repetitions=1, delay_seconds=0, workloads=(PP512,))
        assert config.context_size == 32768

    def test_warmup_always_true(self) -> None:
        config = BenchConfig(repetitions=1, delay_seconds=0, workloads=(PP512,))
        assert config.warmup is True

    def test_zero_repetitions_rejected(self) -> None:
        with pytest.raises(ValueError, match="repetitions"):
            _ = BenchConfig(repetitions=0, delay_seconds=0, workloads=(PP512,))

    def test_negative_delay_rejected(self) -> None:
        with pytest.raises(ValueError, match="delay"):
            _ = BenchConfig(repetitions=1, delay_seconds=-1, workloads=(PP512,))

    def test_empty_workloads_rejected(self) -> None:
        with pytest.raises(ValueError, match="workload"):
            _ = BenchConfig(repetitions=1, delay_seconds=0, workloads=())


class TestBenchWorkloadImmutability:
    def test_pp512_constant(self) -> None:
        assert PP512.name == "pp512"
        assert PP512.n_prompt == 512
        assert PP512.n_gen == 0

    def test_tg128_constant(self) -> None:
        assert TG128.name == "tg128"
        assert TG128.n_prompt == 0
        assert TG128.n_gen == 128
