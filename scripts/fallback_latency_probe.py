"""Stream one local Ollama coding request and record fallback-latency evidence.

The script emits a flushed EVENT line upon the first output token, allowing an
external PowerShell monitor to apply a first-token deadline while separately
sampling host paging and responsiveness. It uses only localhost Ollama.
"""

import argparse
import json
import time
import urllib.request


PROMPT = """Return only Python code for this function, with no Markdown:
def clamp(value, lower, upper):
    \"\"\"Return value bounded to inclusive [lower, upper].\"\"\"
"""


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", required=True)
    parser.add_argument("--context", type=int, default=2048)
    parser.add_argument("--cap", type=int, default=96)
    parser.add_argument("--timeout", type=int, default=180)
    parser.add_argument("--keep-alive", default="10m")
    args = parser.parse_args()

    body = {
        "model": args.model,
        "prompt": PROMPT,
        "stream": True,
        "think": False,
        "keep_alive": args.keep_alive,
        "options": {
            "num_ctx": args.context,
            "num_predict": args.cap,
            "temperature": 0,
            "seed": 42,
        },
    }
    request = urllib.request.Request(
        "http://127.0.0.1:11434/api/generate",
        data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    started = time.perf_counter()
    first_token = None
    text_parts = []
    final = {}
    try:
        with urllib.request.urlopen(request, timeout=args.timeout) as response:
            for raw_line in response:
                item = json.loads(raw_line)
                chunk = item.get("response", "")
                if chunk:
                    if first_token is None:
                        first_token = time.perf_counter()
                        print(
                            "EVENT " + json.dumps({
                                "kind": "first_token",
                                "ttft_s": first_token - started,
                            }),
                            flush=True,
                        )
                    text_parts.append(chunk)
                if item.get("done"):
                    final = item
    except Exception as exc:
        print(json.dumps({
            "status": "error",
            "model": args.model,
            "error": repr(exc),
            "elapsed_s": time.perf_counter() - started,
        }), flush=True)
        raise

    ended = time.perf_counter()
    print(json.dumps({
        "status": "ok",
        "model": args.model,
        "context": args.context,
        "cap": args.cap,
        "ttft_s": (first_token - started) if first_token else None,
        "e2e_s": ended - started,
        "actual_input_tokens": final.get("prompt_eval_count", 0),
        "actual_output_tokens": final.get("eval_count", 0),
        "generated_tokens_s": (
            final.get("eval_count", 0) / (final["eval_duration"] / 1e9)
            if final.get("eval_duration") else None
        ),
        "done_reason": final.get("done_reason", ""),
        "response": "".join(text_parts),
    }), flush=True)


if __name__ == "__main__":
    main()
