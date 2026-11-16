"""Local-only candidate generation; evaluation requires an isolated executor.

This driver intentionally never executes generated code on the host. It saves
each response and candidate in a unique directory for later isolated testing.
"""

import argparse
import json
import re
import shutil
import time
from datetime import datetime
from pathlib import Path
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parent
MODELS = ("qwen3-coder:30b", "qwen3.5:4b", "lfm2.5:8b")


def extract_code(response):
    response = re.sub(r"^\s*<think>.*?</think>\s*", "", response, flags=re.S | re.I)
    blocks = re.findall(r"```(?:python)?\s*\n(.*?)```", response, flags=re.S | re.I)
    return (max(blocks, key=len) if blocks else response).strip() + "\n"


def generate(model, prompt, timeout):
    payload = {"model": model, "prompt": prompt, "stream": False, "keep_alive": "5m", "options": {"temperature": 0, "seed": 42, "num_ctx": 8192, "num_predict": 4096}}
    request = Request("http://127.0.0.1:11434/api/generate", data=json.dumps(payload).encode(), headers={"Content-Type": "application/json"})
    with urlopen(request, timeout=timeout) as response:
        return json.load(response)


def generate_chat(model, prompt, timeout):
    """Use Ollama's model-specific chat renderer for instruction following."""
    payload = {"model": model, "messages": [{"role": "user", "content": prompt}],
               "stream": False, "think": False, "keep_alive": "5m",
               "options": {"temperature": 0, "seed": 42, "num_ctx": 8192, "num_predict": 8192}}
    request = Request("http://127.0.0.1:11434/api/chat", data=json.dumps(payload).encode(), headers={"Content-Type": "application/json"})
    with urlopen(request, timeout=timeout) as response:
        data = json.load(response)
    data["response"] = data.get("message", {}).get("content", "")
    return data


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", choices=MODELS, required=True)
    parser.add_argument("--timeout", type=int, default=900)
    args = parser.parse_args()
    stamp = datetime.now().strftime("%Y_%m_%d__%H_%M_%S_%f")
    candidate = ROOT / "runs" / f"{stamp}__{args.model.replace(':', '_')}"
    candidate.mkdir(parents=True, exist_ok=False)
    for name in ("spec.md", "plan.md", "tasks.md"):
        shutil.copy2(ROOT / name, candidate / name)
    shutil.copytree(ROOT / "public_tests", candidate / "public_tests", ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    skeleton = (ROOT / "skeleton" / "sync_app.py").read_text(encoding="utf-8")
    (candidate / "sync_app.py").write_text(skeleton, encoding="utf-8")
    sections = [(ROOT / name).read_text(encoding="utf-8") for name in ("spec.md", "plan.md", "tasks.md")]
    tests = (ROOT / "public_tests" / "test_sync.py").read_text(encoding="utf-8")
    prompt = "Implement sync_app.py in full. Return only Python code, optionally in one Python fence. Do not omit required features.\n\n" + "\n\n".join(sections) + "\n\nPUBLIC TESTS:\n" + tests + "\n\nPUBLIC SKELETON:\n" + skeleton
    (candidate / "prompt.txt").write_text(prompt, encoding="utf-8")
    start = time.monotonic()
    result = {"model": args.model, "status": "generation_error", "calls": 1, "repair_rounds": 0, "human_interventions": 0, "final_validation": "not run: isolated executor required"}
    try:
        data = generate(args.model, prompt, args.timeout)
        (candidate / "response.json").write_text(json.dumps(data, indent=2), encoding="utf-8")
        (candidate / "sync_app.py").write_text(extract_code(data.get("response", "")), encoding="utf-8")
        result.update(status="generated_unvalidated", done_reason=data.get("done_reason"), output_tokens=data.get("eval_count"))
    except Exception as exc:
        result["error"] = f"{type(exc).__name__}: {exc}"
    result["generation_seconds"] = time.monotonic() - start
    (candidate / "result.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps({"candidate": str(candidate), **result}, indent=2))


if __name__ == "__main__":
    main()
