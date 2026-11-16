"""Bounded local Ollama load probe for models that may exceed host resources."""

import argparse
import json
import time
import urllib.request


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", required=True)
    parser.add_argument("--context", type=int, default=2048)
    parser.add_argument("--timeout", type=int, default=90)
    args = parser.parse_args()
    payload = {
        "model": args.model,
        "prompt": "Reply with exactly: LOAD_PROBE_OK",
        "stream": False,
        "think": False,
        "keep_alive": "0",
        "options": {"num_ctx": args.context, "num_predict": 1, "temperature": 0, "seed": 42},
    }
    request = urllib.request.Request(
        "http://127.0.0.1:11434/api/generate",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    started = time.perf_counter()
    with urllib.request.urlopen(request, timeout=args.timeout) as response:
        result = json.loads(response.read().decode("utf-8"))
    print(json.dumps({
        "model": args.model,
        "elapsed_s": time.perf_counter() - started,
        "response": result.get("response", ""),
        "done_reason": result.get("done_reason", ""),
        "prompt_eval_count": result.get("prompt_eval_count", 0),
        "eval_count": result.get("eval_count", 0),
    }))


if __name__ == "__main__":
    main()
