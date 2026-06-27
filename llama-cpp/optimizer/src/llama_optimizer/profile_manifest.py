"""Parsed profile and normalized manifest dataclasses (T2).

``Profile`` is the validated boundary object produced by the parser;
``Manifest`` is the serializable normalized form bound from a profile. The
canonical JSON emitter is byte-deterministic (sorted keys). Required project
invariants (context ``32768``, VRAM ceiling ``13_958_643_712``) live here so
every module agrees on the exact pinned constants.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import TYPE_CHECKING

from llama_optimizer.models import ContextSize, VramBytes

if TYPE_CHECKING:
    from llama_optimizer.models import (
        BackendIdentity,
        CorpusIdentity,
        HardwareSnapshot,
        LlamaCppBuild,
        MaxNativeCombinations,
        ModelCandidate,
        RecommendationStatus,
        RecommendationWeights,
        Seed,
        TemplateIdentity,
    )
    from llama_optimizer.search_space import SearchSpace

# --- Project invariants (exact pinned constants) --------------------------
REQUIRED_CONTEXT_SIZE: ContextSize = ContextSize(32768)
REQUIRED_VRAM_LIMIT_BYTES: VramBytes = VramBytes(13_958_643_712)


@dataclass(frozen=True, slots=True)
class Profile:
    """A validated, immutable optimizer profile."""

    profile_id: str
    profile_version: str
    optimizer_version: str
    context_size: ContextSize
    vram_limit_bytes: VramBytes
    seed: Seed
    max_native_combinations: MaxNativeCombinations
    recommendation_status: RecommendationStatus
    quality_reason: str
    llama_cpp_build: LlamaCppBuild
    hardware: HardwareSnapshot
    template: TemplateIdentity
    candidates: tuple[ModelCandidate, ...]
    backends: tuple[BackendIdentity, ...]
    corpora: tuple[CorpusIdentity, ...]
    recommendation_weights: RecommendationWeights
    search_space: SearchSpace


@dataclass(frozen=True, slots=True)
class Manifest:
    """The normalized, serializable manifest bound from a :class:`Profile`."""

    profile_id: str
    profile_version: str
    optimizer_version: str
    context_size: ContextSize
    vram_limit_bytes: VramBytes
    seed: Seed
    max_native_combinations: MaxNativeCombinations
    recommendation_status: RecommendationStatus
    quality_reason: str
    llama_cpp_build: LlamaCppBuild
    hardware: HardwareSnapshot
    template: TemplateIdentity
    candidates: tuple[ModelCandidate, ...]
    backends: tuple[BackendIdentity, ...]
    corpora: tuple[CorpusIdentity, ...]
    recommendation_weights: RecommendationWeights


def build_manifest(profile: Profile) -> Manifest:
    """Normalize a validated profile into its immutable serializable manifest."""
    return Manifest(
        profile_id=profile.profile_id,
        profile_version=profile.profile_version,
        optimizer_version=profile.optimizer_version,
        context_size=profile.context_size,
        vram_limit_bytes=profile.vram_limit_bytes,
        seed=profile.seed,
        max_native_combinations=profile.max_native_combinations,
        recommendation_status=profile.recommendation_status,
        quality_reason=profile.quality_reason,
        llama_cpp_build=profile.llama_cpp_build,
        hardware=profile.hardware,
        template=profile.template,
        candidates=profile.candidates,
        backends=profile.backends,
        corpora=profile.corpora,
        recommendation_weights=profile.recommendation_weights,
    )


def manifest_to_dict(manifest: Manifest) -> dict[str, object]:
    """Serialize a manifest into JSON-compatible primitives in canonical keys."""
    return {
        "context_size": int(manifest.context_size),
        "vram_limit_bytes": int(manifest.vram_limit_bytes),
        "optimizer_version": manifest.optimizer_version,
        "profile_id": manifest.profile_id,
        "profile_version": manifest.profile_version,
        "seed": int(manifest.seed),
        "max_native_combinations": int(manifest.max_native_combinations),
        "recommendation_status": manifest.recommendation_status.value,
        "quality_reason": manifest.quality_reason,
        "llama_cpp_build": {
            "build_label": manifest.llama_cpp_build.build_label,
            "fork_ref": manifest.llama_cpp_build.fork_ref,
        },
        "hardware": {
            "gpu": manifest.hardware.gpu,
            "rocm_driver_label": manifest.hardware.rocm_driver_label,
            "vram_total_bytes": int(manifest.hardware.vram_total_bytes),
        },
        "template": {
            "name": str(manifest.template.name),
            "sha256": str(manifest.template.sha256),
        },
        "candidates": [_candidate_to_dict(c) for c in manifest.candidates],
        "backends": [
            {
                "id": str(b.backend_id),
                "backend": b.backend.value,
                "nix_package": str(b.nix_package),
            }
            for b in manifest.backends
        ],
        "corpora": [{"id": str(c.corpus_id), "sha256": str(c.sha256)} for c in manifest.corpora],
        "recommendation": {"weights": manifest.recommendation_weights.to_dict()},
    }


def _candidate_to_dict(candidate: ModelCandidate) -> dict[str, object]:
    """Serialize one model candidate into JSON-compatible primitives."""
    return {
        "id": str(candidate.candidate_id),
        "weight_quant": candidate.weight_quant.value,
        "role": candidate.role.value,
        "file_sha256": str(candidate.file_sha256),
        "file_bytes": int(candidate.file_bytes),
        "revision": str(candidate.revision),
        "url": candidate.url,
        "filename": candidate.filename,
        "nix_package": str(candidate.nix_package),
    }


def canonical_manifest_json(manifest: Manifest) -> str:
    """Emit canonical, byte-deterministic JSON for the manifest (sorted keys)."""
    return json.dumps(manifest_to_dict(manifest), sort_keys=True, indent=2) + "\n"
