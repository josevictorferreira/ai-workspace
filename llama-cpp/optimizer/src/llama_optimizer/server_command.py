"""Build argument arrays for ``llama-server`` without shell interpolation.

Forces ``--ctx-size 32768`` (the exact, immutable project context), warmup
enabled (``--warmup`` is always passed), backend/model/runtime flags from the
identity, profile parallelism, and enabled metrics/slots. All values are
separate argv elements; no shell interpolation is used. A non-32768 context is
rejected before the command is constructed.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from llama_optimizer.profile_manifest import REQUIRED_CONTEXT_SIZE

if TYPE_CHECKING:
    from llama_optimizer.server_types import ServerConfig, ServerIdentity


def build_server_command(
    binary: str,
    config: ServerConfig,
    identity: ServerIdentity,
    *,
    port: int = 0,
) -> list[str]:
    """Construct the llama-server argument array without shell interpolation.

    The context is always :data:`REQUIRED_CONTEXT_SIZE` (32768); the config's
    own ``context_size`` property is cross-checked against this constant so a
    drift in the config object can never reach the command line.
    """
    if config.context_size != int(REQUIRED_CONTEXT_SIZE):
        msg = f"context must be {int(REQUIRED_CONTEXT_SIZE)}, got {config.context_size}"
        raise ValueError(msg)

    fa_val = "on" if identity.flash_attn == 1 else "off"
    mmp_val = "1" if identity.use_mmap else "0"
    return [
        binary,
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
        "--ctx-size",
        str(config.context_size),
        "--parallel",
        str(config.parallel),
        "--metrics",
        "--slots",
        "--warmup",
        "--host",
        "127.0.0.1",
        "--port",
        str(port),
    ]
