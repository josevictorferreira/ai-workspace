# Auto evaluator + HTML report

## Context

### Original Request
Build automatic evaluator that reads every `outputs/**/*.json`, cleans each LLM `result` string (strip fences, maybe `<think>`), evaluates vs prompt rules + create expected normalized outputs for 10 cases, then generate root `index.html` table comparing models (name, size, runtime, tokens, score).

### Interview Summary
- `data.json` is benchmark INPUT, not ground truth.
- Score priority:
  1) valid JSON parse after cleaning
  2) has all required keys, exact names, no extras
  3) correct types + enums per `PROMPT.md`
  4) correctness of extracted values (address/price/etc) vs golden expected.
- Weighted scoring (structure dominates). Runtime/tokens/model size informational only.

### Research Findings
- Outputs file schema: root `{metadata,data}`
  - `metadata.model`
  - `metadata.total_benchmark_time_seconds`
  - `metadata.total_prompt_tokens`
  - `metadata.total_completion_tokens`
  - `data[case_id].result` is string (may be raw JSON, `null`, fenced ```json)
  - `data[case_id].metrics`: `{duration_seconds,prompt_tokens,completion_tokens,tokens_per_second}`
- `PROMPT.md` defines strict schema + extraction rules.

### Metis Review (gaps addressed)
- Must handle noisy outputs incl markdown, non-json prefixes, malformed json.
- Must not “repair” model values (only evaluate).
- Recommend separate golden file + robust extractor.

---

## Work Objectives

### Core Objective
Provide deterministic evaluation + report generation for this benchmark.

### Concrete Deliverables
- `golden_expected.json` (or similar) containing expected normalized outputs for cases 0..9.
- `evaluate.py` (single entrypoint ok, can include helpers) that outputs:
  - `evaluation.json` (machine-readable scores + per-case breakdown)
  - `index.html` at repo root (table + drilldown)

### Definition of Done
- `python evaluate.py` runs from repo root and:
  - emits `evaluation.json`
  - writes/overwrites `index.html`
  - exits 0
- `index.html` opens in browser and shows all models in `outputs/`.

### Must Have
- Robust cleaning/parsing of `result` strings (fences, leading chatter, `<think>` removal if present).
- Strict validation against schema from `PROMPT.md` (keys, types, enums, country=="BR").
- Weighted scoring: structure-first, then values vs golden.
- HTML includes: model name, model size (best-effort), total runtime, total tokens, final score.

### Must NOT Have (Guardrails)
- Do not mutate or “fix” the model output JSON when scoring (only parse/clean wrappers).
- Do not include runtime/tokens/model size in score.
- Do not change benchmark prompt or regenerate outputs.

---

## Verification Strategy

### Test Decision
- **Infrastructure exists**: unknown/likely none.
- **User wants tests**: default NO → do manual verification with golden spot checks.

Manual QA will be explicit commands + expected artifacts.

---

## Scoring Spec (deterministic)

### Cleaning / Parsing
For each `data[case_id].result` string:
1. If result is JSON null / "null" / empty → parse failure.
2. Strip `<think>...</think>` blocks if present.
3. Strip markdown fences:
   - leading/trailing ``` or ```json
   - also handle surrounding prose like "Here is the JSON:" by extracting first `{` .. last `}` substring.
4. Attempt `json.loads`.
5. If still fails: classify as `parse_error` (no “json repair” libs unless explicitly added).

### Validation (schema compliance)
Required keys = EXACT set in `PROMPT.md`.
- Missing key: penalty.
- Extra key: penalty.
- Types:
  - `title`, `description`, `raw_address`, `street`, `street_number`, `complement`, `neighborhood`, `city`, `state` => string or null
  - numeric fields => int/float or null (allow ints for float fields)
  - count fields => int or null (reject floats/strings)
  - `normalized_features` => list[str] ONLY (empty ok)
  - `property_type` in {house, apartment, land, commercial, other} or null
  - `listing_status` in {for_sale, for_rent} or null
  - `country` MUST be "BR" (string)

### Value correctness vs Golden
Golden expected provides per-case target normalized JSON.
Comparison rules:
- Numbers: exact equality after normalizing to float; treat 350000 and 350000.0 as equal.
- Strings: trimmed whitespace equality (default). (No casefold.)
- `null` vs missing: missing already penalized in schema stage.
- `normalized_features`: compare as sets (order-insensitive) OR exact list order? (default: set compare).

### Weights (default; editable in script constants)
Per case score 0..100:
- 40: parseable JSON
- 30: schema keys exact (all present, no extras)
- 20: types/enums valid
- 10: value accuracy vs golden

Overall model score = average over 10 cases.
Also output sub-scores for transparency.

---

## Task Flow

1) Build golden expected → 2) Implement evaluator → 3) Generate HTML report → 4) Manual verification.

---

## TODOs

- [x] 1. Locate all outputs + infer model-size display

  **What to do**:
  - Enumerate `outputs/**/*.json`.
  - Define model id string:
    - primary: `metadata.model`
    - fallback: filename.
  - Define model size string heuristic (informational): parse from model id / filename (e.g., `14b`, `3b`, `135m`), else `unknown`.

  **Parallelizable**: YES

  **References**:
  - `outputs/*.json:metadata.model` - model id source

  **Acceptance Criteria**:
  - Print or store list of models found (count matches files).

- [x] 2. Create golden expected outputs for cases 0..9

  **What to do**:
  - Read `data.json` rows 0..9.
  - For each row, produce expected normalized JSON according to `PROMPT.md` rules.
  - Save as `golden_expected.json`:
    - `{ "0": {normalized...}, ... "9": {...} }`

  **Must NOT do**:
  - Do not infer values not explicit in row fields or in title/description.

  **Parallelizable**: YES (per-case)

  **References**:
  - `data.json:data[0..9]` - raw input
  - `PROMPT.md` - schema + extraction rules

  **Acceptance Criteria**:
  - `golden_expected.json` exists and validates: each case has exact required keys.

- [x] 3. Implement robust result cleaning + JSON extraction

  **What to do**:
  - Write function `clean_result(str)->str` handling:
    - `<think>...</think>` blocks removal
    - stripping ``` fences
    - extracting substring between first `{` and last `}` if extra text present
  - Write `parse_result(cleaned)->(obj|error)`.

  **Parallelizable**: YES

  **References**:
  - `outputs/*.json:data.*.result` - common noise patterns (fences/prose)

  **Acceptance Criteria**:
  - On a sample of models incl small/noisy ones, parsing succeeds when JSON is present.

- [x] 4. Implement schema validator per PROMPT.md

  **What to do**:
  - Hardcode required keys list (from `PROMPT.md`).
  - Validate: missing, extra, types, enums, `country=="BR"`.
  - Emit structured errors (for HTML + json report).

  **Parallelizable**: YES

  **References**:
  - `PROMPT.md:Output schema + rules`.

  **Acceptance Criteria**:
  - Validator returns deterministic pass/fail + list of issues.

- [x] 5. Implement scoring + aggregation

  **What to do**:
  - Implement per-case scoring with weights (constants).
  - Implement value comparison vs `golden_expected.json`.
  - Aggregate per model: avg score, per-component subscores.

  **Parallelizable**: NO (depends on 2,3,4)

  **Acceptance Criteria**:
  - `evaluation.json` includes:
    - per model: totals + subscores
    - per case: parse/schema/type/value subscores + issues

- [x] 6. Generate `index.html` report

  **What to do**:
  - Single HTML file at repo root.
  - Table columns:
    - model
    - size (heuristic)
    - total time sec (`metadata.total_benchmark_time_seconds`)
    - total tokens prompt+completion
    - final score
  - Add per-model expandable section or second table for per-case breakdown (recommended).

  **Parallelizable**: NO (depends on 5)

  **References**:
  - `outputs/*.json:metadata.total_*` for runtime/tokens

  **Acceptance Criteria**:
  - Opening `index.html` shows all models; values match `evaluation.json`.

- [x] 7. Add CLI UX + docs-in-comments

  **What to do**:
  - `python evaluate.py` default paths (`outputs/`, `golden_expected.json`).
  - Flags optional: `--outputs`, `--golden`, `--out-json`, `--out-html`.

  **Parallelizable**: YES

  **Acceptance Criteria**:
  - Running with `--help` prints usage.

- [x] 8. Manual verification run

  **What to do**:
  - Run `python evaluate.py`.
  - Confirm artifacts generated.
  - Spot check one model + one case where output is fenced markdown.

  **Parallelizable**: NO

  **Acceptance Criteria**:
  - `evaluation.json` created
  - `index.html` created
  - Exit code 0

---

## Commit Strategy
- Single commit preferred after all files added (unless you want incremental).

---

## Success Criteria
- Evaluator runs end-to-end on current repository outputs.
- Score ranking reflects structure compliance first.
- HTML report enables quick model comparison.
