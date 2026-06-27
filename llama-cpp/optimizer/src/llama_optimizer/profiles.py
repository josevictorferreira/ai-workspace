"""Public facade for the immutable profile schema (T2).

Re-exports the parsed :class:`Profile`, the normalized :class:`Manifest`, the
canonical JSON emitter, the ``tomllib`` boundary parsers, and every typed
profile/schema error. Callers import from this module; the implementation is
split across :mod:`profile_manifest`, :mod:`profile_parser`, and
:mod:`profile_errors` to keep each responsibility-focused module under the
250-line ceiling.
"""

from __future__ import annotations

from llama_optimizer.models import IneligibleWeightError, InvalidSha256Error, MutableUrlError
from llama_optimizer.profile_errors import (
    DuplicateIdentityError,
    MissingIdentityError,
    ProfileContextError,
    ProfileParseError,
    ProfileVramError,
)
from llama_optimizer.profile_manifest import (
    REQUIRED_CONTEXT_SIZE,
    REQUIRED_VRAM_LIMIT_BYTES,
    Manifest,
    Profile,
    build_manifest,
    canonical_manifest_json,
    manifest_to_dict,
)
from llama_optimizer.profile_parser import parse_profile, parse_profile_bytes

__all__ = [
    "REQUIRED_CONTEXT_SIZE",
    "REQUIRED_VRAM_LIMIT_BYTES",
    "DuplicateIdentityError",
    "IneligibleWeightError",
    "InvalidSha256Error",
    "Manifest",
    "MissingIdentityError",
    "MutableUrlError",
    "Profile",
    "ProfileContextError",
    "ProfileParseError",
    "ProfileVramError",
    "build_manifest",
    "canonical_manifest_json",
    "manifest_to_dict",
    "parse_profile",
    "parse_profile_bytes",
]
