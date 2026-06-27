"""Nix flake contract tests for the Ornith 1.0 9B optimizer inputs (T3).

These are deterministic source-text assertions over ``flake.nix`` and the
immutable Ornith profile. They lock the contract that T3 introduces: immutable
revision-pinned candidate URLs for Q4_K_M/Q5_K_M/Q6_K/Q8_0, separately-buildable
package outputs, exact 32K context for the 9B ROCm/Vulkan apps (and 16K frozen
for the protected 35B apps), BF16 kept out of the realized/default closure, and
the dedicated optimizer package/app entrypoints.

No network, GPU, or model realization is required: the assertions read committed
source text only.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

# Immutable Hugging Face revision shared by every Ornith 1.0 9B candidate.
REVISION = "3296bc7a404871a72ac3f1903f561459c09b5c17"

# Publisher LFS SHA-256 provenance values (from the profile). These must NEVER
# be pasted into a Nix ``sha256`` field: they are content provenance, not Nix
# fixed-output SRI hashes.
PUBLISHER_SHAS = frozenset(
    {
        "5720d1f671b4996481274fffe01868c3c36e87c135cc8538471cc7bd6087b106",
        "d1b36095636c096b04ea09e798a7a378956f2fa9099340bd54add1954aaf149c",
        "33b6f6a3e3f05078438e12df8a4b55c8acf78ceadcc639d2af1cf35a026e8387",
        "d0e4bebaa8b3450c62090df1408f2ee5ccb2094f9c610ffde564a654483d4f37",
        "27bc753487eed85539c3aef63dd602b79cd060401b928c9ff7d30d5556eca260",
    },
)

REQUIRED_QUANTS = ("Q4_K_M", "Q5_K_M", "Q6_K", "Q8_0")


def _repo_root() -> Path:
    """Repository ``llama-cpp`` root holding ``flake.nix``."""
    return Path(__file__).resolve().parents[2]


@pytest.fixture(scope="module")
def flake_text() -> str:
    """Committed ``flake.nix`` source text."""
    return (_repo_root() / "flake.nix").read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def profile_text() -> str:
    """Committed Ornith 1.0 9B optimizer profile source text."""
    return (_repo_root() / "optimizer" / "profiles" / "ornith-1.0-9b.toml").read_text(
        encoding="utf-8",
    )


def _block_until_close(text: str, header: str) -> str:
    """Slice from ``header`` up to (and including) the next ``};`` line.

    Used to isolate a single ``apps.<name> = <call> { ... };`` definition so
    that context assertions are scoped to exactly one app and cannot match an
    unrelated app's flags.
    """
    start = text.index(header)
    close = text.index("};", start)
    return text[start : close + 2]


class TestImmutableCandidateInputs:
    def test_every_required_quant_is_pinned_to_the_immutable_revision(
        self,
        flake_text: str,
    ) -> None:
        # Given/When: the Ornith 9B candidate fetchurl declarations
        # Then: every required quant URL pins the immutable revision, never main
        for quant in REQUIRED_QUANTS:
            decl = f'"Ornith-1.0-9B-{quant}" = pkgs.fetchurl'
            assert decl in flake_text, f"missing fetchurl declaration for {quant}"
        for quant in REQUIRED_QUANTS:
            mutable = f"resolve/main/ornith-1.0-9b-{quant}.gguf"
            assert mutable not in flake_text, f"{quant} still uses mutable resolve/main URL"
            pinned = f"resolve/{REVISION}/ornith-1.0-9b-{quant}.gguf"
            assert pinned in flake_text, f"{quant} is not pinned to the immutable revision"

    def test_each_required_quant_is_a_separately_buildable_package(
        self,
        flake_text: str,
    ) -> None:
        for quant in REQUIRED_QUANTS:
            pkg = f'packages."Ornith-1.0-9B-{quant}"'
            assert pkg in flake_text, f"{pkg} package output is missing"

    def test_publisher_shas_are_not_used_as_nix_sri_hashes(
        self,
        flake_text: str,
    ) -> None:
        # Then: no publisher LFS SHA appears anywhere in flake.nix
        for sha in PUBLISHER_SHAS:
            assert sha not in flake_text, (
                f"publisher SHA {sha[:12]}... leaked into flake.nix as a Nix hash"
            )

    def test_publisher_shas_remain_in_profile_provenance(self, profile_text: str) -> None:
        for sha in PUBLISHER_SHAS:
            assert sha in profile_text, (
                f"publisher SHA {sha[:12]}... dropped from profile provenance"
            )


class TestBf16ReferenceOnly:
    def test_bf16_is_not_a_realized_or_default_package(self, flake_text: str) -> None:
        # BF16 is profile-only provenance: it must not be a fetchurl derivation
        # nor a separately-buildable/default package, so ordinary validation
        # never downloads the 17.9 GB reference artifact.
        assert '"Ornith-1.0-9B-BF16" = pkgs.fetchurl' not in flake_text, (
            "BF16 must not be a fetchurl derivation"
        )
        assert "packages.Ornith-1.0-9B-BF16" not in flake_text, (
            "BF16 must not be a separately-buildable package output"
        )
        assert "packages.default" in flake_text
        default_block = _block_until_close(flake_text, "packages.default")
        assert "BF16" not in default_block, "BF16 leaked into the default package"


class TestExactContextApps:
    def test_ornith_9b_rocm_app_uses_exact_32768_context(self, flake_text: str) -> None:
        block = _block_until_close(flake_text, "apps.ornith-9b = mkServerWithCtx {")
        assert 'ctxSize = "32768"' in block
        assert "81920" not in block

    def test_ornith_9b_vulkan_app_uses_exact_32768_context(self, flake_text: str) -> None:
        block = _block_until_close(
            flake_text,
            "apps.ornith-9b-vulkan = mkServerWithCtx {",
        )
        assert 'ctxSize = "32768"' in block
        assert "81920" not in block

    def test_ornith_35b_rocm_app_stays_at_16384(self, flake_text: str) -> None:
        block = _block_until_close(flake_text, "apps.ornith-35b = mkServerWithCtx {")
        assert 'ctxSize = "16384"' in block

    def test_ornith_35b_vulkan_app_stays_at_16384(self, flake_text: str) -> None:
        block = _block_until_close(
            flake_text,
            "apps.ornith-35b-vulkan = mkServerWithCtx {",
        )
        assert 'ctxSize = "16384"' in block


class TestOptimizerEntrypoints:
    def test_optimizer_package_exists(self, flake_text: str) -> None:
        assert "packages.llama-cpp-optimizer" in flake_text

    def test_optimizer_app_exists_and_forwards_arguments(self, flake_text: str) -> None:
        assert "apps.optimizer" in flake_text


class TestProtectedScope:
    def test_ornith_35b_model_url_is_untouched(self, flake_text: str) -> None:
        block = _block_until_close(flake_text, '"Ornith-1.0-35B-Q4_K_M" = pkgs.fetchurl')
        assert "resolve/main/ornith-1.0-35b-Q4_K_M.gguf" in block
        assert "sha256-/yUpGyWZ+5J6g15iTSs1QBBq9hdhw/pXrEJkBG2+wAI=" in block

    def test_hipfire_region_is_present(self, flake_text: str) -> None:
        assert "# --- Hipfire Apps ---" in flake_text
        assert "apps.hipfire = {" in flake_text

    def test_unrelated_omnicoder_model_is_untouched(self, flake_text: str) -> None:
        block = _block_until_close(
            flake_text,
            '"Tesslate_OmniCoder-9B-Q4_K_S" = pkgs.fetchurl',
        )
        assert "Tesslate_OmniCoder-9B-Q4_K_S.gguf" in block
        assert "sha256-88POLoyURf3H06u0ZwwEJaZOzP3JNhOqCj1xkn/3U7w=" in block

    def test_no_with_statement_in_new_ornith_or_optimizer_regions(
        self,
        flake_text: str,
    ) -> None:
        # Explicit-style invariant: the surgical edits must not introduce a
        # ``with`` expression. (Pre-existing code is already free of ``with``.)
        # Explicit-style invariant: the surgical edits must not introduce a
        # Nix ``with <attrset>;`` expression. The existing flake is already
        # free of ``with`` expressions; this guards against regressions. The
        # word "with" in the description prose must not trigger a false hit.
        assert re.search(r"with\s+(?:pkgs|lib|args|config|self)\s*;", flake_text) is None, (
            "a Nix 'with <attrset>;' expression was introduced"
        )
