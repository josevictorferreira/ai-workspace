#!/usr/bin/env python3
"""
Automatic evaluator for real-estate-normalizer benchmark.

Reads LLM outputs from outputs/, evaluates against golden expected values,
and generates evaluation.json and index.html report.
"""

import json
import re
import sys
import argparse
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, field, asdict
from html import escape as html_escape


# Configuration constants
OUTPUTS_DIR = "outputs"
GOLDEN_FILE = "golden_expected.json"
EVALUATION_FILE = "evaluation.json"
HTML_FILE = "index.html"

# Scoring weights (per case)
WEIGHT_PARSE = 40
WEIGHT_SCHEMA = 30
WEIGHT_TYPES = 20
WEIGHT_VALUES = 10

# Required schema keys (exact from PROMPT.md)
REQUIRED_KEYS = [
    "title", "description", "price", "bedrooms_count", "bathrooms_count",
    "parking_spaces_count", "property_type", "listing_status", "raw_address",
    "street", "street_number", "complement", "neighborhood", "city", "state",
    "country", "normalized_features", "total_area_m2", "private_area_m2",
    "suites_count", "floors_count", "year_built", "condo_fee", "property_tax"
]

# Valid enum values
VALID_PROPERTY_TYPES = {"house", "apartment", "land", "commercial", "other"}
VALID_LISTING_STATUS = {"for_sale", "for_rent"}
VALID_COUNTRY = "BR"


@dataclass
class CaseResult:
    """Result for a single test case."""
    case_id: str
    parse_success: bool = False
    parse_error: Optional[str] = None
    cleaned_result: Optional[str] = None
    
    # Schema validation
    schema_valid: bool = False
    missing_keys: List[str] = field(default_factory=list)
    extra_keys: List[str] = field(default_factory=list)
    type_errors: List[str] = field(default_factory=list)
    enum_errors: List[str] = field(default_factory=list)
    country_error: bool = False
    
    # Value comparison
    value_correct: bool = False
    value_errors: List[str] = field(default_factory=list)
    
    # Scores
    parse_score: float = 0.0
    schema_score: float = 0.0
    types_score: float = 0.0
    values_score: float = 0.0
    total_score: float = 0.0
    
    # Parsed JSON (if successful)
    parsed_data: Optional[Dict] = None


@dataclass
class ModelResult:
    """Result for a single model."""
    model_name: str
    model_size: str
    total_time_seconds: float
    total_prompt_tokens: int
    total_completion_tokens: int
    total_tokens: int
    platform: str = "local"  # "local" or "openrouter"
    cases: Dict[str, CaseResult] = field(default_factory=dict)
    overall_score: float = 0.0
    parse_score: float = 0.0
    schema_score: float = 0.0
    types_score: float = 0.0
    values_score: float = 0.0


def clean_result(result_str: str) -> str:
    """
    Clean LLM response string by removing thinker tags, markdown fences,
    and extracting the JSON portion.
    """
    if not result_str or result_str.strip() in ("null", "None"):
        return ""
    
    cleaned = result_str
    
    # Remove <thinker>...</thinker> blocks
    cleaned = re.sub(r'<thinker>.*?</thinker>', '', cleaned, flags=re.DOTALL | re.IGNORECASE)
    
    # Remove markdown code fences (```json or ```)
    cleaned = re.sub(r'^```json\s*', '', cleaned, flags=re.MULTILINE)
    cleaned = re.sub(r'^```\s*', '', cleaned, flags=re.MULTILINE)
    cleaned = re.sub(r'\s*```$', '', cleaned, flags=re.MULTILINE)
    
    # Handle prose prefixes like "Here is the JSON:" by extracting first { to last }
    first_brace = cleaned.find('{')
    last_brace = cleaned.rfind('}')
    if first_brace != -1 and last_brace != -1 and last_brace > first_brace:
        cleaned = cleaned[first_brace:last_brace + 1]
    
    return cleaned.strip()


def parse_json(cleaned: str) -> Tuple[Optional[Dict], Optional[str]]:
    """Parse JSON string, return (data, error)."""
    if not cleaned:
        return None, "Empty result"
    
    try:
        data = json.loads(cleaned)
        return data, None
    except json.JSONDecodeError as e:
        return None, f"JSON decode error: {str(e)}"


def validate_schema(data: Dict, required_keys: List[str]) -> Tuple[bool, List[str], List[str], List[str], List[str], bool]:
    """
    Validate JSON data against required schema.
    Returns: (valid, missing_keys, extra_keys, type_errors, enum_errors, country_error)
    """
    if not isinstance(data, dict):
        return False, [], [], ["Not a dictionary"], [], False
    
    missing_keys = []
    extra_keys = []
    type_errors = []
    enum_errors = []
    country_error = False
    
    # Check required keys
    for key in required_keys:
        if key not in data:
            missing_keys.append(key)
    
    # Check for extra keys
    for key in data:
        if key not in required_keys:
            extra_keys.append(key)
    
    # Validate country
    if 'country' in data:
        country = data['country']
        if country is not None and country != VALID_COUNTRY:
            country_error = True
    
    # Validate types and enums for each field
    string_fields = {"title", "description", "raw_address", "street", "street_number", 
                    "complement", "neighborhood", "city", "state", "country"}
    count_fields = {"bedrooms_count", "bathrooms_count", "parking_spaces_count", 
                   "suites_count", "floors_count", "year_built"}
    numeric_fields = {"price", "total_area_m2", "private_area_m2", "condo_fee", "property_tax"}
    list_fields = {"normalized_features"}
    
    for key, value in data.items():
        if value is None:
            continue
            
        if key in string_fields:
            if not isinstance(value, str):
                type_errors.append(f"{key}: expected string, got {type(value).__name__}")
        
        elif key in count_fields:
            if not isinstance(value, int):
                type_errors.append(f"{key}: expected int, got {type(value).__name__}")
        
        elif key in numeric_fields:
            if not isinstance(value, (int, float)):
                type_errors.append(f"{key}: expected number, got {type(value).__name__}")
        
        elif key in list_fields:
            if not isinstance(value, list):
                type_errors.append(f"{key}: expected list, got {type(value).__name__}")
            elif not all(isinstance(item, str) for item in value):
                type_errors.append(f"{key}: list should contain only strings")
        
        elif key == "property_type":
            if value not in VALID_PROPERTY_TYPES:
                enum_errors.append(f"property_type: invalid value '{value}'")
        
        elif key == "listing_status":
            if value not in VALID_LISTING_STATUS:
                enum_errors.append(f"listing_status: invalid value '{value}'")
    
    is_valid = (len(missing_keys) == 0 and len(extra_keys) == 0 and 
               len(type_errors) == 0 and len(enum_errors) == 0 and not country_error)
    
    return is_valid, missing_keys, extra_keys, type_errors, enum_errors, country_error


def normalize_value(value: Any) -> Any:
    """Normalize values for comparison (handle floats vs ints, None handling)."""
    if value is None:
        return None
    if isinstance(value, (int, float)):
        # Normalize numeric values
        return float(value)
    if isinstance(value, str):
        # Trim whitespace for strings
        return value.strip()
    if isinstance(value, list):
        # Normalize list by sorting (for feature lists), handle None values
        def sort_key(x):
            if x is None:
                return (0, "")  # None sorts first
            if isinstance(x, (int, float)):
                return (1, x)
            if isinstance(x, str):
                return (2, x.lower())
            return (3, str(x))
        return sorted([normalize_value(item) for item in value], key=sort_key)
    return value


def values_match(model_val: Any, golden_val: Any) -> bool:
    """Check if model value matches golden value (handles arrays for multiple acceptable options)."""
    model_norm = normalize_value(model_val)
    golden_norm = normalize_value(golden_val)
    
    # If golden is a list, model matches if it equals ANY element
    if isinstance(golden_norm, list):
        return model_norm in golden_norm
    
    return model_norm == golden_norm


def compare_values(model_data: Dict, golden_data: Dict) -> Tuple[bool, List[str]]:
    """Compare model output to golden expected, return (correct, errors)."""
    # Fields that should only be checked for presence (non-null), not exact match
    pass_through_fields = {"title", "description"}
    
    errors = []
    
    for key in golden_data:
        # Skip pass-through fields - only check they're present (not null)
        if key in pass_through_fields:
            if model_data.get(key) is None:
                errors.append(f"{key}: got None, expected non-null")
            continue
        
        model_val = model_data.get(key)
        golden_val = golden_data[key]
        
        if not values_match(model_val, golden_val):
            # Show acceptable options if golden is a list
            if isinstance(golden_val, list):
                errors.append(f"{key}: got {repr(model_val)}, expected one of {golden_val}")
            else:
                errors.append(f"{key}: got {repr(model_val)}, expected {repr(golden_val)}")
    
    # Check for extra keys in model (already penalized in schema, but report here too)
    for key in model_data:
        if key not in golden_data:
            errors.append(f"{key}: unexpected key (not in golden)")
    
    return len(errors) == 0, errors


def evaluate_case(case_id: str, result_str: str, golden_data: Dict) -> CaseResult:
    """Evaluate a single test case."""
    case = CaseResult(case_id=case_id)
    
    # Step 1: Clean and parse
    cleaned = clean_result(result_str)
    case.cleaned_result = cleaned if cleaned else None
    
    parsed_data, parse_error = parse_json(cleaned)
    if parse_error:
        case.parse_success = False
        case.parse_error = parse_error
        case.parse_score = 0
        case.total_score = 0
        return case
    
    case.parse_success = True
    case.parsed_data = parsed_data
    case.parse_score = WEIGHT_PARSE
    
    # Step 2: Schema validation
    (schema_valid, missing_keys, extra_keys, type_errors, 
     enum_errors, country_error) = validate_schema(parsed_data, REQUIRED_KEYS)
    
    case.schema_valid = schema_valid
    case.missing_keys = missing_keys
    case.extra_keys = extra_keys
    case.type_errors = type_errors
    case.enum_errors = enum_errors
    case.country_error = country_error
    
    # Schema score: penalty for missing/extra keys
    schema_penalty = 0
    schema_penalty += len(missing_keys) * 5
    schema_penalty += len(extra_keys) * 5
    case.schema_score = max(0, WEIGHT_SCHEMA - schema_penalty)
    
    # Step 3: Type validation score
    type_penalty = len(type_errors) * 3
    type_penalty += len(enum_errors) * 5
    if country_error:
        type_penalty += 10
    case.types_score = max(0, WEIGHT_TYPES - type_penalty)
    
    # Step 4: Value comparison
    if schema_valid and len(type_errors) == 0:
        value_correct, value_errors = compare_values(parsed_data, golden_data)
        case.value_correct = value_correct
        case.value_errors = value_errors
        
        value_penalty = len(value_errors) * 2
        case.values_score = max(0, WEIGHT_VALUES - value_penalty)
    else:
        case.values_score = 0
    
    # Calculate total score
    case.total_score = case.parse_score + case.schema_score + case.types_score + case.values_score
    
    return case


def extract_model_size(model_name: str, filename: str) -> str:
    """Extract model size from model name or filename."""
    # Try to parse common patterns from model name
    name_lower = model_name.lower() + "-" + filename.lower()
    
    # Common patterns: 135m, 3b, 7b, 14b, 90m, 350m, 1.2b, 1.7b, 4b, etc.
    patterns = [
        r'(\d+(?:\.\d+)?)[Bb]',
        r'[-_](\d+)[Bb]',
        r'(\d+(?:\.\d+)?b)',
        r'(\d+[mM])',
        r'[-_](\d+)[mM]',
    ]
    
    for pattern in patterns:
        match = re.search(pattern, name_lower)
        if match:
            size_str = match.group(1)
            # Normalize to consistent format
            if size_str.lower().endswith('b'):
                return f"{size_str.upper()}"
            else:
                return f"{size_str.upper()}M"
    
    # Try filename patterns
    filename_lower = filename.lower()
    for pattern in patterns:
        match = re.search(pattern, filename_lower)
        if match:
            size_str = match.group(1)
            if size_str.lower().endswith('b'):
                return f"{size_str.upper()}"
            else:
                return f"{size_str.upper()}M"
    
    return "unknown"


def load_outputs(outputs_dir: str) -> Dict[str, Dict]:
    """Load all output files from outputs directory."""
    outputs = {}
    outputs_path = Path(outputs_dir)
    
    if not outputs_path.exists():
        print(f"Warning: outputs directory '{outputs_dir}' not found")
        return outputs
    
    for json_file in outputs_path.glob("**/*.json"):
        try:
            with open(json_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                # Use filename as key
                key = json_file.name
                outputs[key] = data
        except Exception as e:
            print(f"Warning: Could not load {json_file}: {e}")
    
    return outputs


def load_golden(golden_file: str) -> Dict:
    """Load golden expected values."""
    with open(golden_file, 'r', encoding='utf-8') as f:
        return json.load(f)


def evaluate_outputs(outputs: Dict, golden: Dict) -> List[ModelResult]:
    """Evaluate all model outputs against golden expected values."""
    results = []
    
    for filename, output_data in outputs.items():
        metadata = output_data.get("metadata", {})
        data = output_data.get("data", {})
        
        model_name = metadata.get("model", filename)
        model_size = extract_model_size(model_name, filename)
        total_time = metadata.get("total_benchmark_time_seconds", 0)
        total_prompt = metadata.get("total_prompt_tokens", 0)
        total_completion = metadata.get("total_completion_tokens", 0)
        platform = metadata.get("run_platform", "local")
        
        model_result = ModelResult(
            model_name=model_name,
            model_size=model_size,
            total_time_seconds=total_time,
            total_prompt_tokens=total_prompt,
            total_completion_tokens=total_completion,
            total_tokens=total_prompt + total_completion,
            platform=platform,
        )
        
        # Evaluate each case
        case_scores = []
        parse_scores = []
        schema_scores = []
        types_scores = []
        values_scores = []
        
        for case_id in golden.keys():
            case_data = data.get(case_id)
            if case_data is None:
                # Skip missing cases
                continue
            result_str = case_data.get("result", "")
            golden_data = golden[case_id]
            
            case_result = evaluate_case(case_id, result_str, golden_data)
            model_result.cases[case_id] = case_result
            
            case_scores.append(case_result.total_score)
            parse_scores.append(case_result.parse_score)
            schema_scores.append(case_result.schema_score)
            types_scores.append(case_result.types_score)
            values_scores.append(case_result.values_score)
        
        # Calculate overall scores
        if case_scores:
            model_result.overall_score = sum(case_scores) / len(case_scores)
            model_result.parse_score = sum(parse_scores) / len(parse_scores)
            model_result.schema_score = sum(schema_scores) / len(schema_scores)
            model_result.types_score = sum(types_scores) / len(types_scores)
            model_result.values_score = sum(values_scores) / len(values_scores)
        
        results.append(model_result)
    
    # Sort by overall score descending
    results.sort(key=lambda x: x.overall_score, reverse=True)
    
    return results


def save_evaluation_json(results: List[ModelResult], output_file: str):
    """Save evaluation results to JSON file."""
    eval_data = {
        "summary": {
            "total_models": len(results),
            "best_model": results[0].model_name if results else None,
            "best_score": results[0].overall_score if results else 0,
        },
        "models": []
    }
    
    for model in results:
        model_data = {
            "model_name": model.model_name,
            "model_size": model.model_size,
            "platform": model.platform,
            "total_time_seconds": model.total_time_seconds,
            "total_tokens": model.total_tokens,
            "overall_score": round(model.overall_score, 2),
            "scores": {
                "parse": round(model.parse_score, 2),
                "schema": round(model.schema_score, 2),
                "types": round(model.types_score, 2),
                "values": round(model.values_score, 2),
            },
            "cases": {}
        }
        
        for case_id, case in model.cases.items():
            case_data = {
                "parse_success": case.parse_success,
                "parse_score": case.parse_score,
                "schema_valid": case.schema_valid,
                "schema_score": case.schema_score,
                "types_score": case.types_score,
                "values_score": case.values_score,
                "total_score": case.total_score,
            }
            
            if case.parse_error:
                case_data["parse_error"] = case.parse_error
            if case.missing_keys:
                case_data["missing_keys"] = case.missing_keys
            if case.extra_keys:
                case_data["extra_keys"] = case.extra_keys
            if case.type_errors:
                case_data["type_errors"] = case.type_errors
            if case.enum_errors:
                case_data["enum_errors"] = case.enum_errors
            if case.country_error:
                case_data["country_error"] = True
            if case.value_errors:
                case_data["value_errors"] = case.value_errors
            
            model_data["cases"][case_id] = case_data
        
        eval_data["models"].append(model_data)
    
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(eval_data, f, indent=2, ensure_ascii=False)


def generate_html_report(results: List[ModelResult], output_file: str):
    """Generate HTML comparison report."""
    html_parts = [
        '<!DOCTYPE html>',
        '<html lang="en">',
        '<head>',
        '    <meta charset="UTF-8">',
        '    <meta name="viewport" content="width=device-width, initial-scale=1.0">',
        '    <title>Real Estate Normalizer Benchmark Evaluation</title>',
        '    <style>',
        '        * { box-sizing: border-box; }',
        '        body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;',
        '               max-width: 1200px; margin: 0 auto; padding: 20px; background: #f5f5f5; }',
        '        h1 { color: #333; text-align: center; margin-bottom: 30px; }',
        '        table { width: 100%; border-collapse: collapse; background: white;',
        '                box-shadow: 0 2px 8px rgba(0,0,0,0.1); border-radius: 8px; overflow: hidden; }',
        '        th, td { padding: 12px 15px; text-align: left; border-bottom: 1px solid #eee; }',
        '        th { background: #4a90d9; color: white; font-weight: 600; }',
        '        tr:hover { background: #f8f9fa; }',
        '        .score { font-weight: bold; color: #2e7d32; }',
        '        .score-low { color: #c62828; }',
        '        .model-name { font-weight: 600; color: #333; }',
        '        .details { display: none; background: #fafafa; padding: 15px; }',
        '        .details.show { display: table-row; }',
        '        .case-details { background: white; padding: 15px; margin: 10px 0; ',
        '                        border-radius: 6px; border: 1px solid #e0e0e0; }',
        '        .case-header { font-weight: 600; margin-bottom: 10px; color: #555; }',
        '        .error { color: #c62828; font-size: 0.9em; }',
        '        .score-bar { background: #e0e0e0; border-radius: 4px; height: 20px; overflow: hidden; }',
        '        .score-fill { height: 100%; background: #4caf50; transition: width 0.3s; }',
        '        .score-fill.low { background: #ff9800; }',
        '        .score-fill.critical { background: #f44336; }',
        '        .toggle-btn { background: #4a90d9; color: white; border: none; padding: 6px 12px;',
        '                      border-radius: 4px; cursor: pointer; font-size: 0.85em; }',
        '        .toggle-btn:hover { background: #357abd; }',
        '    </style>',
        '</head>',
        '<body>',
        '    <h1>🏠 Real Estate Normalizer Benchmark Evaluation</h1>',
        '    <table>',
        '        <thead>',
        '            <tr>',
        '                <th>Model</th>',
        '                <th>Size</th>',
        '                <th>Platform</th>',
        '                <th>Time (s)</th>',
        '                <th>Tokens</th>',
        '                <th>Score</th>',
        '                <th>Details</th>',
        '            </tr>',
        '        </thead>',
        '        <tbody>'
    ]
    
    for model in results:
        score_class = "score"
        if model.overall_score < 50:
            score_class = "score-low"
        
        score_bar_class = ""
        if model.overall_score < 50:
            score_bar_class = "critical"
        elif model.overall_score < 80:
            score_bar_class = "low"
        
        html_parts.extend([
            f'            <tr>',
            f'                <td class="model-name">{html_escape(model.model_name)}</td>',
            f'                <td>{html_escape(model.model_size)}</td>',
            f'                <td>{html_escape(model.platform)}</td>',
            f'                <td>{model.total_time_seconds:.2f}</td>',
            f'                <td>{model.total_tokens:,}</td>',
            f'                <td class="{score_class}">{model.overall_score:.1f}</td>',
            f'                <td><button class="toggle-btn" onclick="toggleDetails(\'{html_escape(model.model_name)}\')">Show</button></td>',
            f'            </tr>',
            f'            <tr class="details" id="details-{html_escape(model.model_name)}">',
            f'                <td colspan="7">',
        ])
        
        # Add case details
        for case_id in sorted(model.cases.keys()):
            case = model.cases[case_id]
            case_bar_class = ""
            if case.total_score < 50:
                case_bar_class = "critical"
            elif case.total_score < 80:
                case_bar_class = "low"
            
            html_parts.extend([
                f'                        <div style="margin: 15px 0; padding: 10px; background: #f9f9f9; border-radius: 4px;">',
                f'                            <strong>Case {case_id}</strong>: {case.total_score:.1f}/100',
                f'                            <div class="score-bar" style="margin-top: 5px;">',
                f'                                <div class="score-fill {case_bar_class}" style="width: {case.total_score}%"></div>',
                f'                            </div>'
            ])
            
            # Add errors if any
            errors = []
            if case.parse_error:
                errors.append(f"Parse error: {case.parse_error}")
            if case.missing_keys:
                errors.append(f"Missing keys: {', '.join(case.missing_keys)}")
            if case.extra_keys:
                errors.append(f"Extra keys: {', '.join(case.extra_keys)}")
            if case.type_errors:
                errors.extend(case.type_errors)
            if case.enum_errors:
                errors.extend(case.enum_errors)
            if case.country_error:
                errors.append("Country must be 'BR'")
            if case.value_errors:
                errors.extend(case.value_errors)
            
            if errors:
                html_parts.append(f'                            <div class="error">')
                for error in errors:
                    html_parts.append(f'                                <div>• {html_escape(error)}</div>')
                html_parts.append(f'                            </div>')
            
            html_parts.append(f'                        </div>')
        
        html_parts.extend([
            f'                    </div>',
            f'                </td>',
            f'            </tr>'
        ])
    
    html_parts.extend([
        '        </tbody>',
        '    </table>',
        '    <script>',
        '        function toggleDetails(modelName) {',
        '            const row = document.getElementById("details-" + modelName);',
        '            const btn = event.target;',
        '            if (row.style.display === "table-row") {',
        '                row.style.display = "none";',
        '                btn.textContent = "Show";',
        '            } else {',
        '                row.style.display = "table-row";',
        '                btn.textContent = "Hide";',
        '            }',
        '        }',
        '    </script>',
        '</body>',
        '</html>'
    ])
    
    html_content = '\n'.join(html_parts)
    
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(html_content)


def main():
    parser = argparse.ArgumentParser(
        description="Evaluate LLM outputs for real-estate-normalizer benchmark"
    )
    parser.add_argument(
        "--outputs", "-o",
        default=OUTPUTS_DIR,
        help=f"Directory containing output JSON files (default: {OUTPUTS_DIR})"
    )
    parser.add_argument(
        "--golden", "-g",
        default=GOLDEN_FILE,
        help=f"Golden expected values JSON file (default: {GOLDEN_FILE})"
    )
    parser.add_argument(
        "--eval-json", "-e",
        default=EVALUATION_FILE,
        help=f"Output evaluation JSON file (default: {EVALUATION_FILE})"
    )
    parser.add_argument(
        "--html", "-H",
        default=HTML_FILE,
        help=f"Output HTML report file (default: {HTML_FILE})"
    )
    
    args = parser.parse_args()
    
    print(f"Loading golden expected values from {args.golden}...")
    golden = load_golden(args.golden)
    print(f"Loaded {len(golden)} golden cases")
    
    print(f"Loading outputs from {args.outputs}...")
    outputs = load_outputs(args.outputs)
    print(f"Loaded {len(outputs)} model outputs")
    
    print("Evaluating models...")
    results = evaluate_outputs(outputs, golden)
    print(f"Evaluated {len(results)} models")
    
    print(f"Saving evaluation results to {args.eval_json}...")
    save_evaluation_json(results, args.eval_json)
    
    print(f"Generating HTML report to {args.html}...")
    generate_html_report(results, args.html)
    
    print("\nEvaluation complete!")
    print(f"  - Evaluation JSON: {args.eval_json}")
    print(f"  - HTML Report: {args.html}")
    
    if results:
        print(f"\nBest model: {results[0].model_name} (score: {results[0].overall_score:.1f})")
        print(f"Worst model: {results[-1].model_name} (score: {results[-1].overall_score:.1f})")


if __name__ == "__main__":
    main()
