import json
import os
import requests
import argparse
import time
from pathlib import Path

debug = os.environ.get("DEBUG", "false").lower() == "true"


def check_model_has_reasoning(
    model_name, api_url, api_key, use_openrouter, max_retries=3
):
    """Check if a model supports reasoning by making a test request."""
    test_payload = {
        "model": model_name,
        "messages": [{"role": "user", "content": "Hello"}],
        "max_tokens": 10,
    }

    headers = {"Authorization": f"Bearer {api_key}"}

    for attempt in range(max_retries):
        try:
            response = requests.post(
                api_url,
                json=test_payload,
                headers=headers,
                timeout=30,
            )
            result = response.json()

            print(f"Model reasoning check response: {result}") if debug else None

            # Check for reasoning_content in the response (OpenRouter format)
            if "choices" in result:
                choice = result["choices"][0]
                if "message" in choice:
                    message = choice["message"]
                    if "reasoning_content" in message:
                        return True

            return False
        except Exception as e:
            if attempt < max_retries - 1:
                sleep_time = (2**attempt) * 2
                print(
                    f"Retry {attempt + 1}/{max_retries} for reasoning check: {e}, sleeping {sleep_time}s"
                )
                time.sleep(sleep_time)
            else:
                return False


def make_api_request_with_retry(url, payload, headers, max_retries=5):
    """Make API request with exponential backoff retry for rate limits."""
    for attempt in range(max_retries):
        try:
            response = requests.post(url, json=payload, headers=headers, timeout=180)

            print(
                f"API response status: {response.status_code}, attempt {attempt + 1}/{max_retries}"
            ) if debug else None

            # Check for rate limit (429) or server errors (5xx)
            if response.status_code == 429:
                # Rate limited - wait and retry with exponential backoff
                retry_after = response.headers.get("Retry-After")
                if retry_after:
                    wait_time = int(retry_after)
                else:
                    wait_time = (2**attempt) * 5

                print(f"Rate limited (429), waiting {wait_time}s before retry...")
                time.sleep(wait_time)
                continue

            response.raise_for_status()
            return response.json()

        except requests.exceptions.HTTPError:
            if response.status_code == 429:
                wait_time = (2**attempt) * 5
                print(f"HTTP 429 rate limit, waiting {wait_time}s before retry...")
                time.sleep(wait_time)
                continue
            else:
                raise

        except Exception as e:
            if attempt < max_retries - 1:
                wait_time = (2**attempt) * 5
                print(f"Request error: {e}, retrying in {wait_time}s...")
                time.sleep(wait_time)
            else:
                raise

    raise Exception(f"Max retries ({max_retries}) exceeded for API request")


def run_benchmarks(model_name, api_url, temperature=None, use_openrouter=False):
    with open("PROMPT.md", "r", encoding="utf-8") as f:
        prompt_template = f.read()

    with open("data.json", "r", encoding="utf-8") as f:
        data_file = json.load(f)
        listings = data_file.get("data", {})

    outputs = {
        "metadata": {
            "model": model_name,
            "total_benchmark_time_seconds": 0,
            "total_prompt_tokens": 0,
            "total_completion_tokens": 0,
            "run_platform": "openrouter" if use_openrouter else "local",
        },
        "data": {},
    }

    Path("outputs").mkdir(exist_ok=True)

    benchmark_start_time = time.time()

    # For OpenRouter, check if model supports reasoning and use low effort
    reasoning_mode = False
    if use_openrouter:
        api_key = os.environ.get("OPENROUTER_API_KEY_TERMINAL")
        if not api_key:
            raise ValueError("OPENROUTER_API_KEY_TERMINAL environment variable not set")

        # Check if model has reasoning capability
        if check_model_has_reasoning(model_name, api_url, api_key, use_openrouter):
            print(f"Model {model_name} supports reasoning, using low_effort mode...")
            reasoning_mode = True

    for index, raw_row in listings.items():
        print(f"Processing row {index}...")

        full_prompt = f"{prompt_template}\n\n{json.dumps(raw_row, ensure_ascii=False)}"

        payload = {
            "model": model_name,
            "messages": [{"role": "user", "content": full_prompt}],
            "max_tokens": 4096,
            "stream": False,
        }
        if temperature is not None:
            payload["temperature"] = temperature

        # OpenRouter specific settings
        if use_openrouter:
            # Use low_effort for reasoning models
            if reasoning_mode:
                payload["extra"] = {"reasoning": {"effort": "low"}}

            headers = {
                "Authorization": f"Bearer {os.environ.get('OPENROUTER_API_KEY_TERMINAL')}"
            }
        else:
            headers = {}

        try:
            start_time = time.time()

            print(f"[DEBUG] Making API request to {api_url}...")
            print(
                f"[DEBUG] Model: {model_name}, Prompt length: {len(full_prompt)} chars"
            ) if debug else None
            print(
                f"[DEBUG] Payload max_tokens: {payload['max_tokens']}"
            ) if debug else None

            result_json = make_api_request_with_retry(api_url, payload, headers)
            print(f"[DEBUG] API response received successfully") if debug else None
            print(f"API response: {result_json}") if debug else None
            duration = time.time() - start_time

            if "choices" not in result_json:
                print(f"Unexpected response structure: {result_json}")
                raise KeyError("'choices' not found in response")

            content = result_json["choices"][0]["message"]["content"].strip()
            usage = result_json.get("usage", {})

            prompt_tokens = usage.get("prompt_tokens", 0)
            completion_tokens = usage.get("completion_tokens", 0)
            tokens_per_second = completion_tokens / duration if duration > 0 else 0

            outputs["metadata"]["total_prompt_tokens"] += prompt_tokens
            outputs["metadata"]["total_completion_tokens"] += completion_tokens

            outputs["data"][index] = {
                "result": content,
                "metrics": {
                    "duration_seconds": duration,
                    "prompt_tokens": prompt_tokens,
                    "completion_tokens": completion_tokens,
                    "tokens_per_second": tokens_per_second,
                },
            }

        except Exception as e:
            print(f"Error processing index {index}: {e}")
            outputs["data"][index] = None

    outputs["metadata"]["total_benchmark_time_seconds"] = (
        time.time() - benchmark_start_time
    )

    # Sanitize model name for filename
    safe_model_name = model_name.replace("/", "_").replace(" ", "_")
    output_path = f"outputs/{safe_model_name}.json"
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(outputs, f, ensure_ascii=False, indent=2)

    print(f"Done! outputs saved to {output_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Run benchmarks for real estate normalization."
    )
    parser.add_argument("--model", type=str, required=True, help="Model name to use")
    parser.add_argument(
        "--url", type=str, default=None, help="API base URL (overrides auto-detection)"
    )
    parser.add_argument(
        "--temperature", type=float, default=None, help="Temperature for model sampling"
    )
    parser.add_argument("--openrouter", action="store_true", help="Use OpenRouter API")

    args = parser.parse_args()

    if args.url is None:
        args.url = (
            "https://openrouter.ai/api/v1/chat/completions"
            if args.openrouter
            else "http://localhost:1234/v1/chat/completions"
        )

    run_benchmarks(args.model, args.url, args.temperature, args.openrouter)
