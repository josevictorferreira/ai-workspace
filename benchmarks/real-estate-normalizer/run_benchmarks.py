import json
import requests
import argparse
import time
from pathlib import Path


def run_benchmarks(model_name, api_url):
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
        },
        "data": {},
    }

    Path("outputs").mkdir(exist_ok=True)

    benchmark_start_time = time.time()

    for index, raw_row in listings.items():
        print(f"Processing row {index}...")

        full_prompt = f"{prompt_template}\n\n{json.dumps(raw_row, ensure_ascii=False)}"

        payload = {
            "model": model_name,
            "messages": [{"role": "user", "content": full_prompt}],
            "temperature": 0.0,
            "max_tokens": -1,
            "stream": False,
        }

        try:
            start_time = time.time()
            response = requests.post(
                f"{api_url}/v1/chat/completions", json=payload, timeout=60
            )
            duration = time.time() - start_time
            response.raise_for_status()

            result_json = response.json()
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

    output_path = f"outputs/{model_name}.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(outputs, f, ensure_ascii=False, indent=2)

    print(f"Done! outputs saved to {output_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Run benchmarks for real estate normalization."
    )
    parser.add_argument("--model", type=str, required=True, help="Model name to use")
    parser.add_argument(
        "--url", type=str, default="http://10.10.10.10:1234", help="API base URL"
    )

    args = parser.parse_args()
    run_benchmarks(args.model, args.url)
