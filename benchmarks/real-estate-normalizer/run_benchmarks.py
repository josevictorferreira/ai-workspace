import json
import requests
import argparse
import os
from pathlib import Path


def run_benchmarks(model_name, api_url):
    with open("PROMPT.md", "r", encoding="utf-8") as f:
        prompt_template = f.read()

    with open("data.json", "r", encoding="utf-8") as f:
        data_file = json.load(f)
        listings = data_file.get("data", {})

    results = {}

    Path("results").mkdir(exist_ok=True)

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
            response = requests.post(
                f"{api_url}/v1/chat/completions", json=payload, timeout=60
            )
            response.raise_for_status()

            result_json = response.json()
            content = result_json["choices"][0]["message"]["content"].strip()

            if content.startswith("```json"):
                content = (
                    content.replace("```json", "", 1).replace("```", "", 1).strip()
                )
            elif content.startswith("```"):
                content = content.replace("```", "", 1).replace("```", "", 1).strip()

            try:
                parsed_content = json.loads(content)
                results[index] = parsed_content
            except json.JSONDecodeError:
                print(
                    f"Warning: Model returned invalid JSON for index {index}. Storing raw string."
                )
                results[index] = content

        except Exception as e:
            print(f"Error processing index {index}: {e}")
            results[index] = None

    output_path = f"results/{model_name}.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    print(f"Done! Results saved to {output_path}")


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
