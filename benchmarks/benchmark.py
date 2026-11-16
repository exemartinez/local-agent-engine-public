"""Reproducible, local-only Ollama streaming benchmark.

Runs named models or every model installed in the local Ollama instance. It
persists each completed or failed case immediately, so a context-limit error,
timeout, or interrupted run remains useful evidence rather than discarding
earlier samples. Prompt sizes are approximate targets; Ollama reports the
actual token counts used for every request.
"""

import argparse
import ast
import csv
import json
import math
import re
import statistics
import time
import urllib.error
import urllib.request
from pathlib import Path

BASE = "http://127.0.0.1:11434"
FIELDNAMES = [
    "model", "model_size_bytes", "target_input_tokens", "output_cap",
    "repetition", "prompt_length_verified", "status", "error",
    "actual_input_tokens", "actual_output_tokens", "ttft_s", "e2e_s",
    "tpot_s", "chunk_gap_median_s", "generated_tokens_s",
    "prefill_tokens_s", "total_tokens_s", "done_reason", "processor",
    "context", "resident_vram_bytes",
]
QUALITY_FIELDNAMES = [
    "model", "case", "attempt", "status", "error", "response_s",
    "actual_input_tokens", "actual_output_tokens", "generated_tokens_s",
]

QUALITY_PROMPTS = {
    "mean": """Return only Python code. Define mean(values). It must return the arithmetic mean, raise ValueError for an empty sequence, and not mutate the input. Do not include Markdown or explanation.""",
    "slugify": """Return only Python code. Define slugify(value) using only Python built-ins; do not import modules. It must trim whitespace, lowercase text, replace every contiguous non-alphanumeric span with one hyphen, and remove leading/trailing hyphens. Do not include Markdown or explanation.""",
    "merge_intervals": """Return only Python code. Define merge_intervals(intervals) using only Python built-ins; do not import modules. Given a list of [start, end] integer pairs, return sorted merged pairs; overlapping or touching intervals merge. Do not mutate the input. Do not include Markdown or explanation.""",
}


def api_json(path, body=None, timeout=180):
    data = None if body is None else json.dumps(body).encode("utf-8")
    request = urllib.request.Request(
        BASE + path, data=data, headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def installed_models():
    payload = api_json("/api/tags", timeout=30)
    return {model["name"]: model.get("size", "") for model in payload.get("models", [])}


def resident_model(model):
    try:
        payload = api_json("/api/ps", timeout=10)
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError):
        return {"processor": "", "context": "", "resident_vram_bytes": ""}
    for item in payload.get("models", []):
        if item.get("name") == model:
            return {
                "processor": item.get("details", {}).get("processor", item.get("processor", "")),
                "context": item.get("context_length", ""),
                "resident_vram_bytes": item.get("size_vram", ""),
            }
    return {"processor": "", "context": "", "resident_vram_bytes": ""}


def request(model, prompt, cap, context):
    body = {
        "model": model,
        "prompt": prompt,
        "stream": True,
        "think": False,
        "keep_alive": "30s",
        "options": {"num_ctx": context, "num_predict": cap, "temperature": 0, "seed": 42},
    }
    req = urllib.request.Request(
        BASE + "/api/generate", data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    start = time.perf_counter()
    stamps, final = [], {}
    with urllib.request.urlopen(req, timeout=240) as response:
        for line in response:
            item = json.loads(line)
            if item.get("response"):
                stamps.append(time.perf_counter())
            if item.get("done"):
                final = item
    if not final:
        raise RuntimeError("stream ended without final statistics")
    elapsed = time.perf_counter() - start
    count = final.get("eval_count", 0)
    gaps = [b - a for a, b in zip(stamps, stamps[1:])]
    return {
        "actual_input_tokens": final.get("prompt_eval_count", 0),
        "actual_output_tokens": count,
        "ttft_s": stamps[0] - start if stamps else "",
        "e2e_s": elapsed,
        "tpot_s": (stamps[-1] - stamps[0]) / (count - 1) if len(stamps) > 1 and count > 1 else "",
        "chunk_gap_median_s": statistics.median(gaps) if gaps else "",
        "generated_tokens_s": count / (final["eval_duration"] / 1e9) if final.get("eval_duration") else "",
        "prefill_tokens_s": final.get("prompt_eval_count", 0) / (final["prompt_eval_duration"] / 1e9)
        if final.get("prompt_eval_duration") else "",
        "total_tokens_s": (count + final.get("prompt_eval_count", 0)) / elapsed,
        "done_reason": final.get("done_reason", ""),
    }


def generate_text(model, prompt, context):
    start = time.perf_counter()
    payload = api_json("/api/generate", {
        "model": model, "prompt": prompt, "stream": False, "think": False,
        "keep_alive": "30s",
        "options": {"num_ctx": min(context, 4096), "num_predict": 512, "temperature": 0, "seed": 42},
    }, timeout=240)
    elapsed = time.perf_counter() - start
    count = payload.get("eval_count", 0)
    return payload.get("response", ""), {
        "response_s": elapsed,
        "actual_input_tokens": payload.get("prompt_eval_count", 0),
        "actual_output_tokens": count,
        "generated_tokens_s": count / (payload["eval_duration"] / 1e9) if payload.get("eval_duration") else "",
    }


def extract_python(text):
    text = re.sub(r"^\s*<think>.*?</think>\s*", "", text, flags=re.DOTALL | re.IGNORECASE)
    match = re.search(r"```(?:python)?\s*(.*?)```", text, flags=re.DOTALL | re.IGNORECASE)
    return (match.group(1) if match else text).strip()


def quality_namespace(code):
    tree = ast.parse(code, mode="exec")
    forbidden = (ast.Import, ast.ImportFrom, ast.With, ast.AsyncWith,
                 ast.ClassDef, ast.Global, ast.Nonlocal)
    if any(isinstance(node, forbidden) for node in ast.walk(tree)):
        raise ValueError("generated code contains a forbidden construct")
    safe_methods = {"append", "copy", "isalnum", "isdigit", "isspace", "join", "lower", "replace", "sort", "split", "strip"}
    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute) and (node.attr.startswith("_") or node.attr not in safe_methods):
            raise ValueError("generated code uses an unsafe attribute")
    safe_builtins = {"ValueError": ValueError, "all": all, "any": any, "dict": dict,
                     "enumerate": enumerate, "len": len, "list": list, "max": max,
                     "min": min, "range": range, "set": set, "sorted": sorted,
                     "str": str, "sum": sum, "tuple": tuple, "zip": zip}
    namespace = {"__builtins__": safe_builtins}
    exec(compile(tree, "<model-output>", "exec"), namespace, namespace)
    return namespace


def validate_quality_case(name, namespace):
    if name == "mean":
        values = [2, 4, 6]
        if namespace["mean"](values) != 4 or values != [2, 4, 6]:
            raise AssertionError("mean returned an incorrect value or mutated input")
        try:
            namespace["mean"]([])
        except ValueError:
            return
        raise AssertionError("mean did not raise ValueError for empty input")
    if name == "slugify":
        if namespace["slugify"]("  Hello, World!  ") != "hello-world":
            raise AssertionError("slugify basic case failed")
        if namespace["slugify"]("Python__API v2") != "python-api-v2":
            raise AssertionError("slugify separator case failed")
        return
    if name == "merge_intervals":
        values = [[5, 7], [1, 3], [3, 4], [10, 12]]
        if namespace["merge_intervals"](values) != [[1, 4], [5, 7], [10, 12]]:
            raise AssertionError("merge_intervals returned an incorrect result")
        if values != [[5, 7], [1, 3], [3, 4], [10, 12]]:
            raise AssertionError("merge_intervals mutated input")
        return
    raise ValueError(f"unknown quality case: {name}")


def run_quality_case(model, name, context):
    text, metrics = generate_text(model, QUALITY_PROMPTS[name], context)
    namespace = quality_namespace(extract_python(text))
    validate_quality_case(name, namespace)
    return metrics


def write_rows(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDNAMES, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def numeric(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def summarise(rows):
    summary = []
    for model in sorted({row["model"] for row in rows}):
        for target in (512, 2048, 4096):
            for cap in (128, 512):
                group = [row for row in rows if row["model"] == model and row["target_input_tokens"] == target
                         and row["output_cap"] == cap and row["status"] == "ok"]
                for metric in ("ttft_s", "tpot_s", "e2e_s", "generated_tokens_s", "prefill_tokens_s"):
                    values = sorted(row[metric] for row in group if numeric(row.get(metric)))
                    if values:
                        summary.append({
                            "model": model, "target_input_tokens": target, "output_cap": cap,
                            "metric": metric, "n": len(values), "mean": statistics.mean(values),
                            "median": statistics.median(values),
                            "p95_nearest_rank": values[max(0, math.ceil(0.95 * len(values)) - 1)],
                            "stdev": statistics.stdev(values) if len(values) > 1 else 0,
                            "note": "Prompt target is approximate; p95 is descriptive for small samples.",
                        })
    return summary


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", action="append", dest="models", help="Model to benchmark; repeatable")
    parser.add_argument("--all-installed", action="store_true", help="Benchmark every model returned by Ollama /api/tags")
    parser.add_argument("--repetitions", type=int, default=3)
    parser.add_argument("--context", type=int, default=8192)
    parser.add_argument("--quality", action="store_true", help="Run deterministic restricted Python-quality cases")
    parser.add_argument("--quality-only", action="store_true", help="Skip latency rows and run only Python-quality cases")
    parser.add_argument("--quality-attempts", type=int, default=1)
    parser.add_argument("--output", type=Path, default=Path("benchmarks/results/benchmark_runs.csv"))
    args = parser.parse_args()
    if args.repetitions < 1:
        parser.error("repetitions must be positive")
    if args.quality_attempts < 1:
        parser.error("quality-attempts must be positive")
    if args.quality_only:
        args.quality = True
    if not args.models and not args.all_installed:
        parser.error("choose --model MODEL or --all-installed")

    available = installed_models()
    models = list(args.models or [])
    if args.all_installed:
        models.extend(name for name in available if name not in models)
    if not models:
        parser.error("no installed models found")

    rows = []
    if not args.quality_only:
        for model in models:
            try:
                request(model, "Return the Python expression 1+1.", 16, min(args.context, 2048))
            except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, RuntimeError, json.JSONDecodeError) as exc:
                rows.append({"model": model, "model_size_bytes": available.get(model, ""), "target_input_tokens": 0,
                             "output_cap": 16, "repetition": "warmup", "prompt_length_verified": False,
                             "status": "warmup_error", "error": str(exc)})
                write_rows(args.output, rows)

        for model in models:
            for target in (512, 2048, 4096):
                for cap in (128, 512):
                    for repetition in range(args.repetitions):
                        prompt = f"Experiment {target}-{cap}-{repetition}.\n" + ("# Python data processing example\n" * (target // 6))
                        prompt += "\nWrite Python functions for validating and sorting records with examples."
                        row = {
                            "model": model, "model_size_bytes": available.get(model, ""),
                            "target_input_tokens": target, "output_cap": cap, "repetition": repetition,
                            "prompt_length_verified": False, "status": "ok", "error": "",
                        }
                        try:
                            row.update(request(model, prompt, cap, args.context))
                            row.update(resident_model(model))
                        except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, RuntimeError, json.JSONDecodeError) as exc:
                            row.update({"status": "error", "error": str(exc)})
                        rows.append(row)
                        write_rows(args.output, rows)

        args.output.with_suffix(".summary.json").write_text(json.dumps(summarise(rows), indent=2), encoding="utf-8")
    if args.quality:
        quality_rows = []
        quality_path = args.output.with_name(args.output.stem + "_quality.csv")
        for model in models:
            for name in QUALITY_PROMPTS:
                for attempt in range(args.quality_attempts):
                    row = {"model": model, "case": name, "attempt": attempt, "status": "pass", "error": ""}
                    try:
                        row.update(run_quality_case(model, name, args.context))
                    except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, RuntimeError,
                            json.JSONDecodeError, SyntaxError, ValueError, KeyError, AssertionError) as exc:
                        row.update({"status": "fail", "error": str(exc)})
                    quality_rows.append(row)
                    with quality_path.open("w", newline="", encoding="utf-8") as handle:
                        writer = csv.DictWriter(handle, fieldnames=QUALITY_FIELDNAMES, extrasaction="ignore")
                        writer.writeheader()
                        writer.writerows(quality_rows)
        print(f"Completed {len(quality_rows)} Python-quality rows; failures: {sum(row['status'] != 'pass' for row in quality_rows)}.")
    if not args.quality_only:
        failures = sum(row["status"] != "ok" for row in rows)
        print(f"Completed {len(rows)} recorded rows for {len(models)} model(s); failures: {failures}.")


if __name__ == "__main__":
    main()
