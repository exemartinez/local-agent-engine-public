"""Interactive, review-gated benchmark coordinator; run in a terminal."""
import argparse
import json
import os
import shutil
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

from runner import ROOT, MODELS, extract_code, generate_chat


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", choices=MODELS, required=True)
    parser.add_argument("--request-timeout", type=int, default=900)
    parser.add_argument("--test-timeout", type=int, default=60)
    args = parser.parse_args()
    run = ROOT / "runs" / (datetime.now().strftime("%Y_%m_%d__%H_%M_%S_%f") + "__timed__" + args.model.replace(":", "_"))
    run.mkdir(parents=True, exist_ok=False)
    for name in ("spec.md", "plan.md", "tasks.md"):
        shutil.copy2(ROOT / name, run / name)
    shutil.copytree(ROOT / "public_tests", run / "public_tests", ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    skeleton = (ROOT / "skeleton" / "sync_app.py").read_text(encoding="utf-8")
    tests = (ROOT / "public_tests" / "test_sync.py").read_text(encoding="utf-8")
    materials = "\n\n".join((ROOT / name).read_text(encoding="utf-8") for name in ("spec.md", "plan.md", "tasks.md"))
    prompt = "Implement sync_app.py in full. Return only Python code.\n\n" + materials + "\n\nPUBLIC TESTS:\n" + tests + "\n\nSKELETON:\n" + skeleton
    started = time.monotonic()
    result = {"model": args.model, "protocol": "chat-v3-public-tests-in-repairs", "options": {"think": False, "temperature": 0, "seed": 42, "num_ctx": 8192, "num_predict": 8192}, "calls": [], "public_checks": [], "hidden_check": None, "manual_reviews": 0, "status": "in_progress"}

    def save():
        result["elapsed_seconds"] = time.monotonic() - started
        (run / "timed_result.json").write_text(json.dumps(result, indent=2), encoding="utf-8")

    def check(stage, hidden=False):
        env = os.environ.copy()
        env.update(PYTHONPATH=os.pathsep.join((str(stage), str(ROOT))), PYTEST_DISABLE_PLUGIN_AUTOLOAD="1", COVERAGE_FILE=str(stage / ".coverage"))
        test_path = ROOT / ("hidden_tests" if hidden else "public_tests")
        cmd = [sys.executable, "-m", "pytest", "-p", "pytest_cov", "-p", "network_guard", str(test_path), "-q", "--tb=short", "-o", "cache_dir=" + str(stage / ".pytest_cache"), "--basetemp=" + str(stage / (".hidden_tmp" if hidden else ".test_tmp"))]
        if not hidden:
            cmd += ["--cov=sync_app", "--cov-report=term", "--cov-fail-under=90"]
        begin = time.monotonic()
        try:
            proc = subprocess.run(cmd, cwd=stage, env=env, text=True, capture_output=True, timeout=args.test_timeout)
            return {"exit_code": proc.returncode, "seconds": time.monotonic() - begin, "output": proc.stdout + proc.stderr}
        except subprocess.TimeoutExpired as exc:
            return {"exit_code": None, "seconds": time.monotonic() - begin, "output": "Test timeout: " + str(exc)}

    for attempt in range(4):
        (run / f"prompt_{attempt}.txt").write_text(prompt, encoding="utf-8")
        begin = time.monotonic()
        try:
            response = generate_chat(args.model, prompt, args.request_timeout)
        except Exception as exc:
            result["calls"].append({"attempt": attempt, "seconds": time.monotonic()-begin, "error": repr(exc)})
            result["status"] = "generation_failed"
            save()
            return
        result["calls"].append({"attempt": attempt, "seconds": time.monotonic()-begin, "done_reason": response.get("done_reason"), "output_tokens": response.get("eval_count")})
        (run / f"response_{attempt}.json").write_text(json.dumps(response, indent=2), encoding="utf-8")
        stage = run / f"attempt_{attempt}"
        stage.mkdir()
        code = extract_code(response.get("response", ""))
        (stage / "sync_app.py").write_text(code, encoding="utf-8")
        save()
        result["manual_reviews"] += 1
        print(f"Review {stage / 'sync_app.py'} for host access. A venv is not a sandbox.", flush=True)
        try:
            confirmation = input("Type REVIEWED to run public tests, or anything else to stop: ").strip()
        except EOFError:
            confirmation = ""
        if confirmation != "REVIEWED":
            result["status"] = "review_rejected"
            save()
            return
        public = check(stage)
        result["public_checks"].append(public)
        (run / f"public_{attempt}.log").write_text(public["output"], encoding="utf-8")
        save()
        if public["exit_code"] == 0 or attempt == 3:
            hidden = check(stage, hidden=True)
            result["hidden_check"] = hidden
            (run / "hidden_final.log").write_text(hidden["output"], encoding="utf-8")
            result["status"] = "pass" if public["exit_code"] == 0 and hidden["exit_code"] == 0 else "fail"
            save()
            print(json.dumps({"run": str(run), "status": result["status"], "elapsed_seconds": result["elapsed_seconds"]}, indent=2))
            return
        feedback = public["output"][-12000:]
        prompt = "Return the full corrected sync_app.py as Python code only.\n\n" + materials + "\n\nPUBLIC TEST SOURCE:\n" + tests + "\n\nCURRENT CODE:\n" + code + "\n\nPUBLIC TEST FAILURES:\n" + feedback


if __name__ == "__main__":
    main()
