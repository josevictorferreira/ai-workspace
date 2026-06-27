"""Boundary parser: raw TOML bytes to a validated immutable profile (T2).

Untrusted profile bytes are parsed exactly once with stdlib ``tomllib`` into a
:class:`Profile`. Every field is narrowed to a typed value at this boundary;
publisher SHA-256, pinned revisions, mutable-URL rejection, uniqueness, weight
totals, and the exact context/VRAM invariants are enforced here. Nothing
unvalidated crosses into the interior.
"""

from __future__ import annotations

import tomllib
from collections.abc import Mapping
from pathlib import Path
from typing import TypeIs

from llama_optimizer.models import (
    Backend,
    BackendId,
    BackendIdentity,
    CandidateId,
    CandidateRole,
    ContextSize,
    CorpusId,
    CorpusIdentity,
    FileBytes,
    HardwareSnapshot,
    LlamaCppBuild,
    MaxNativeCombinations,
    MetricWeight,
    ModelCandidate,
    MutableUrlError,
    NixPackagePath,
    RecommendationStatus,
    RecommendationWeights,
    RevisionId,
    Seed,
    TemplateIdentity,
    TemplateName,
    VramBytes,
    WeightQuant,
    parse_metric_weight,
    parse_revision,
    parse_sha256,
)
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
    Profile,
)
from llama_optimizer.search_space import parse_search_space

_WEIGHT_FIELDS = {
    "prompt_throughput": "prompt_throughput_weight",
    "generation_throughput": "generation_throughput_weight",
    "ttft_p95": "ttft_p95_weight",
    "request_latency_p95": "request_latency_p95_weight",
    "quality_margin": "quality_margin_weight",
    "vram_headroom": "vram_headroom_weight",
}


def _is_str_mapping(value: object) -> TypeIs[Mapping[str, object]]:
    """Narrow ``object`` to a fully-typed string-keyed mapping."""
    return isinstance(value, Mapping)


def _is_obj_list(value: object) -> TypeIs[list[object]]:
    """Narrow ``object`` to a fully-typed list of objects."""
    return isinstance(value, list)


def parse_profile(path: str | Path) -> Profile:
    """Read and parse a profile TOML file from ``path``."""
    with Path(path).open("rb") as handle:
        data = handle.read()
    return parse_profile_bytes(data)


def parse_profile_bytes(data: bytes) -> Profile:
    """Parse raw profile bytes into a validated :class:`Profile`."""
    try:
        table = tomllib.loads(data.decode("utf-8"))
    except (tomllib.TOMLDecodeError, UnicodeDecodeError) as exc:
        raise ProfileParseError(reason=f"invalid TOML: {exc}") from exc
    if not table:
        raise ProfileParseError(reason="profile document is empty")
    return _build_profile(table)


def _build_profile(table: Mapping[str, object]) -> Profile:
    profile_section = _section(table, "profile")
    context = _required_int(profile_section, "context_size")
    if context != int(REQUIRED_CONTEXT_SIZE):
        raise ProfileContextError(
            actual=context, reason=f"context_size must be {int(REQUIRED_CONTEXT_SIZE)}"
        )
    vram = _required_int(profile_section, "vram_limit_bytes")
    if vram != int(REQUIRED_VRAM_LIMIT_BYTES):
        raise ProfileVramError(
            actual=vram, reason=f"vram_limit_bytes must be {int(REQUIRED_VRAM_LIMIT_BYTES)}"
        )

    llama_cpp_section = _section(table, "llama_cpp")
    hardware_section = _section(table, "hardware")
    quality_section = _section(table, "quality")
    template_raw = table.get("template")
    if not _is_str_mapping(template_raw):
        raise MissingIdentityError(identity="template", reason="template identity is required")
    template = _parse_template(template_raw)

    candidates = _parse_candidates(table.get("candidates"))
    backends = _parse_backends(table.get("backends"))
    corpora = _parse_corpora(table.get("corpora"))
    if not corpora:
        raise MissingIdentityError(
            identity="corpus", reason="at least one corpus identity is required"
        )
    weights = _parse_weights(_section(table, "recommendation"))

    search_table = table.get("search")
    if not _is_str_mapping(search_table):
        raise ProfileParseError(reason="[search] must be a mapping")
    search_space = parse_search_space(search_table)

    return Profile(
        profile_id=_required_str(profile_section, "id"),
        profile_version=_required_str(profile_section, "version"),
        optimizer_version=_required_str(profile_section, "optimizer_version"),
        context_size=ContextSize(context),
        vram_limit_bytes=VramBytes(vram),
        seed=Seed(_required_int(profile_section, "seed")),
        max_native_combinations=MaxNativeCombinations(int(search_space.max_native_combinations)),
        recommendation_status=RecommendationStatus(
            _required_str(quality_section, "recommendation_status")
        ),
        quality_reason=_required_str(quality_section, "reason"),
        llama_cpp_build=LlamaCppBuild(
            build_label=_required_str(llama_cpp_section, "build_label"),
            fork_ref=_required_str(llama_cpp_section, "fork_ref"),
        ),
        hardware=HardwareSnapshot(
            gpu=_required_str(hardware_section, "gpu"),
            rocm_driver_label=_required_str(hardware_section, "rocm_driver_label"),
            vram_total_bytes=VramBytes(_required_int(hardware_section, "vram_total_bytes")),
        ),
        template=template,
        candidates=candidates,
        backends=backends,
        corpora=corpora,
        recommendation_weights=weights,
        search_space=search_space,
    )


def _section(table: Mapping[str, object], key: str) -> Mapping[str, object]:
    """Extract a required sub-section mapping, raising a typed error if absent."""
    raw = table.get(key)
    if not _is_str_mapping(raw):
        raise ProfileParseError(reason=f"missing or non-mapping section [{key}]")
    return raw


def _required_int(section: Mapping[str, object], key: str) -> int:
    raw = section.get(key)
    if not isinstance(raw, int) or isinstance(raw, bool):
        raise ProfileParseError(reason=f"{key} must be an integer")
    return raw


def _required_str(section: Mapping[str, object], key: str) -> str:
    raw = section.get(key)
    if not isinstance(raw, str):
        raise ProfileParseError(reason=f"{key} must be a string")
    return raw


def _parse_template(section: Mapping[str, object]) -> TemplateIdentity:
    return TemplateIdentity(
        name=TemplateName(_required_str(section, "name")),
        sha256=parse_sha256(section.get("sha256"), field="template.sha256"),
    )


def _parse_candidates(raw: object) -> tuple[ModelCandidate, ...]:
    if not _is_obj_list(raw):
        return ()
    seen: dict[str, None] = {}
    parsed: list[ModelCandidate] = []
    for item in raw:
        entry = _as_mapping(item, "candidates")
        candidate_id = _required_str(entry, "id")
        if candidate_id in seen:
            raise DuplicateIdentityError(
                kind="candidate", duplicate_id=candidate_id, reason="duplicate candidate id"
            )
        seen[candidate_id] = None
        revision = parse_revision(entry.get("revision"), field=f"{candidate_id}.revision")
        parsed.append(
            ModelCandidate(
                candidate_id=CandidateId(candidate_id),
                weight_quant=WeightQuant(_required_str(entry, "weight_quant")),
                role=CandidateRole(_required_str(entry, "role")),
                file_sha256=parse_sha256(
                    entry.get("file_sha256"), field=f"{candidate_id}.file_sha256"
                ),
                file_bytes=FileBytes(_required_int(entry, "file_bytes")),
                revision=revision,
                url=_immutable_url(_required_str(entry, "url"), candidate_id, revision),
                filename=_required_str(entry, "filename"),
                nix_package=NixPackagePath(_required_str(entry, "nix_package")),
            )
        )
    return tuple(parsed)


def _parse_backends(raw: object) -> tuple[BackendIdentity, ...]:
    if not _is_obj_list(raw):
        raise ProfileParseError(reason="[backends] must be an array of tables")
    seen: dict[str, None] = {}
    parsed: list[BackendIdentity] = []
    for item in raw:
        entry = _as_mapping(item, "backends")
        backend_id = _required_str(entry, "id")
        if backend_id in seen:
            raise DuplicateIdentityError(
                kind="backend", duplicate_id=backend_id, reason="duplicate backend id"
            )
        seen[backend_id] = None
        parsed.append(
            BackendIdentity(
                backend_id=BackendId(backend_id),
                backend=Backend(_required_str(entry, "backend")),
                nix_package=NixPackagePath(_required_str(entry, "nix_package")),
            )
        )
    return tuple(parsed)


def _parse_corpora(raw: object) -> tuple[CorpusIdentity, ...]:
    if raw is None:
        return ()
    if not _is_obj_list(raw):
        raise ProfileParseError(reason="[corpora] must be an array of tables")
    parsed: list[CorpusIdentity] = []
    for item in raw:
        entry = _as_mapping(item, "corpora")
        corpus_id = _required_str(entry, "id")
        parsed.append(
            CorpusIdentity(
                corpus_id=CorpusId(corpus_id),
                sha256=parse_sha256(entry.get("sha256"), field=f"corpora.{corpus_id}.sha256"),
            )
        )
    return tuple(parsed)


def _parse_weights(section: Mapping[str, object]) -> RecommendationWeights:
    """Parse the six balanced weights, validating finiteness, sign, and total."""
    weights: dict[str, MetricWeight] = {}
    for name, toml_key in _WEIGHT_FIELDS.items():
        weights[name] = parse_metric_weight(section.get(toml_key), field=toml_key)
    return RecommendationWeights(**weights)


def _immutable_url(url: str, candidate_id: str, revision: RevisionId) -> str:
    """Reject mutable ``resolve/main`` URLs; the URL must pin the revision."""
    if "resolve/main" in url or f"resolve/{revision}/" not in url:
        raise MutableUrlError(
            field=f"{candidate_id}.url",
            reason=f"model URL must resolve at pinned revision {revision}, not a mutable ref",
            value=url,
        )
    return url


def _as_mapping(item: object, section: str) -> Mapping[str, object]:
    if not _is_str_mapping(item):
        raise ProfileParseError(reason=f"each [[{section}]] entry must be a mapping")
    return item
