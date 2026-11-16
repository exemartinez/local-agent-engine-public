"""Request one public-feedback repair; generated code is not executed."""
import argparse
import json
import time
from pathlib import Path
from runner import ROOT, MODELS, extract_code, generate

parser = argparse.ArgumentParser()
parser.add_argument("--candidate", type=Path, required=True)
parser.add_argument("--model", choices=MODELS, required=True)
parser.add_argument("--feedback", type=Path, required=True)
parser.add_argument("--round", type=int, choices=range(1, 4), required=True)
args = parser.parse_args()
candidate = args.candidate.resolve(strict=True)
if candidate.parent != (ROOT / "runs").resolve():
    raise SystemExit("candidate must be a direct child of benchmark runs")
source = candidate / ("sync_app.py" if args.round == 1 else f"repair_{args.round - 1}.py")
output = candidate / f"repair_{args.round}.py"
if output.exists():
    raise SystemExit("repair output already exists")
sections = [(ROOT / name).read_text(encoding="utf-8") for name in ("spec.md", "plan.md", "tasks.md")]
prompt = "Return the complete corrected sync_app.py as Python code only. Address the public test failures and retain all specified behavior.\n\n" + "\n\n".join(sections) + "\n\nCURRENT CODE:\n" + source.read_text(encoding="utf-8") + "\n\nPUBLIC FEEDBACK:\n" + args.feedback.read_text(encoding="utf-8")
(candidate / f"repair_{args.round}_prompt.txt").write_text(prompt, encoding="utf-8")
started = time.monotonic()
try:
    response = generate(args.model, prompt, 900)
    (candidate / f"repair_{args.round}_response.json").write_text(json.dumps(response, indent=2), encoding="utf-8")
    output.write_text(extract_code(response.get("response", "")), encoding="utf-8")
    result = {"status": "generated_unvalidated", "done_reason": response.get("done_reason"), "output_tokens": response.get("eval_count")}
except Exception as exc:
    result = {"status": "generation_error", "error": f"{type(exc).__name__}: {exc}"}
result.update(model=args.model, round=args.round, generation_seconds=time.monotonic()-started)
(candidate / f"repair_{args.round}_result.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
print(json.dumps(result, indent=2))
