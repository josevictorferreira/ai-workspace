# Auto-Evaluator Learnings

## Overview
Automatic evaluation system for real-estate-normalizer benchmark that reads LLM outputs, validates JSON schema, and generates comparison reports.

## Key Components

### 1. Golden Expected Outputs (`golden_expected.json`)
- Created expected normalized outputs for 10 test cases (0-9)
- Based on raw data in `data.json` and extraction rules from `PROMPT.md`
- Each case has 24 fields matching required schema

### 2. Result Cleaning (`clean_result()`)
- Handles thinker tags: `<thinker>...</thinker>`
- Strips markdown fences: ```json ... ```
- Extracts JSON from prose: finds first `{` to last `}`
- Empty/null results classified as parse failures

### 3. Schema Validation
Required keys (24 total):
```
title, description, price, bedrooms_count, bathrooms_count,
parking_spaces_count, property_type, listing_status, raw_address,
street, street_number, complement, neighborhood, city, state,
country, normalized_features, total_area_m2, private_area_m2,
suites_count, floors_count, year_built, condo_fee, property_tax
```

Validation rules:
- Missing key: -5 points
- Extra key: -5 points
- Type errors: -3 points each
- Enum errors: -5 points each
- Country != "BR": -10 points

### 4. Scoring Weights (per case, max 100)
- Parseable JSON: 40 pts
- Schema keys: 30 pts
- Types/enums: 20 pts
- Value accuracy: 10 pts

### 5. Model Size Heuristic
Extracts size from model name/filename:
- Patterns: `135m`, `3b`, `7b`, `14b`, `90m`, `350m`, `1.2b`, `1.7b`, `4b`
- Falls back to "unknown" if no pattern found

### 6. Output Files
- `evaluation.json`: Machine-readable scores with per-case breakdown
- `index.html`: Interactive HTML report with sortable table and expandable details

## Results Summary
- 11 models evaluated
- Best: qwen3-4b-2507 (99.0 score)
- Worst: falcon-h1-tiny-90m-instruct (45.5 score)

## Usage
```bash
python evaluate.py                    # default paths
python evaluate.py --outputs dir/     # custom outputs
python evaluate.py --html report.html # custom output
```

## Issues Resolved
1. JSON parsing error: Missing closing bracket in compare_values()
2. Dataclass defaults: parse_success required default value
3. Missing case data: Handle cases where data.get(case_id) returns None
