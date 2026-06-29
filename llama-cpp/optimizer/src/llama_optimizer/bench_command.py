"""Build argument arrays for ``llama-bench`` without shell interpolation."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from llama_optimizer.bench_types import BenchConfig, BenchIdentity


def build_bench_command(
    binary: str,
    config: BenchConfig,
    identity: BenchIdentity,
) -> list[str]:
    """Construct the llama-bench argument array without shell interpolation.

    Forces ``-o jsonl``, exact depth ``32768``, warmup enabled (``--no-warmup``
    is never passed), repetitions/delay from the config, and explicit
    backend/model/config flags from the identity. All values are separate argv
    elements; no shell interpolation is used.
    """
    fa_val = "on" if identity.flash_attn == 1 else "off"
    mmp_val = "1" if identity.use_mmap else "0"
    prompt_values = ",".join(str(w.n_prompt) for w in config.workloads)
    gen_values = ",".join(str(w.n_gen) for w in config.workloads)
    return [
        binary,
        "-o",
        "jsonl",
        "-r",
        str(config.repetitions),
        "--delay",
        str(config.delay_seconds),
        "-d",
        str(config.context_size),
        "-m",
        identity.model_filename,
        "-ngl",
        str(identity.n_gpu_layers),
        "-b",
        str(identity.n_batch),
        "-ub",
        str(identity.n_ubatch),
        "-ctk",
        identity.type_k,
        "-ctv",
        identity.type_v,
        "-t",
        str(identity.n_threads),
        "-fa",
        fa_val,
        "-mmp",
        mmp_val,
        "-p",
        prompt_values,
        "-n",
        gen_values,
    ]
