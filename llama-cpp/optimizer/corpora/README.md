# Optimizer Corpora

Versioned workload corpora for tiered quality gates (T8).

## Files

| File | Purpose | Lines |
| --- | --- | --- |
| `coding-smoke.jsonl` | Deterministic coding fixtures (functions, algorithms, SQL) | 5 |
| `tool-use-smoke.jsonl` | Tool-call scenarios (search, file ops, commands) | 5 |
| `long-context-smoke.jsonl` | Exact-32768 long-context retrieval scenarios | 3 |

## Design

Each corpus is a JSONL file where every line is a self-contained JSON object
with a stable `id` and `category` field. Corpora are intentionally **smoke**
sets: small, deterministic, and versioned so that quality-gate results are
reproducible without GPU or network access.

These are **not** generic Wikitext. The coding corpus contains real programming
tasks; the tool-use corpus contains realistic agent tool-call scenarios; the
long-context corpus targets exact 32768-token retrieval.

## Hash Binding

The SHA-256 of each file is verified by the quality module at evaluation time.
The declared hashes in `optimizer/profiles/ornith-1.0-9b.toml` are the profile's
provenance targets; any on-disk mismatch produces a typed quality failure.

Current on-disk hashes:

| Corpus | SHA-256 |
| --- | --- |
| `coding-smoke.jsonl` | `9dafe1fa0bd0a30140a85b414ec1181e83d871fb5124373007b555b6602bde15` |
| `tool-use-smoke.jsonl` | `cd78cb72ba3f6320824d88ac7e7dde28ba944400af8bae688fd7102d91c38071` |
| `long-context-smoke.jsonl` | `bb5456a9feb3d56618a154181ccb8212a1ceb1b7376105fe775a22548ecefa20` |

To compute the hash of a corpus file:

```bash
sha256sum optimizer/corpora/coding-smoke.jsonl
```

## Weight vs KV-Cache Quantization

Quality gates evaluate **weight quantization** (Q4_K_M, Q5_K_M, Q6_K, Q8_0) and
**runtime KV-cache quantization** (f16, q8_0, q4_0) as separate dimensions. A
quality evaluation record always carries a `QuantDimension` so weight-quant and
KV-cache results are never collapsed into one row.
