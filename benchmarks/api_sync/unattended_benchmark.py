"""Local llama.cpp generation with Docker-isolated, bounded test feedback."""
import argparse
import hashlib
import json
import re
import socket
import subprocess
import threading
import time
from datetime import datetime
from pathlib import Path
from urllib.request import Request, urlopen

import container_eval
import overnight_local
import windows_eval
from runner import ROOT, extract_code


def request_json(url, payload=None, timeout=3):
    request = Request(url, data=None if payload is None else json.dumps(payload).encode(),
                      headers={"Content-Type": "application/json"})
    with urlopen(request, timeout=timeout) as response:
        return json.load(response)


def incomplete_response(choice):
    return not (choice.get("message", {}).get("content") or "").strip() or choice.get("finish_reason") == "length"


def model_folder_label(model_path):
    """Create a Windows-safe, traceable label from the actual model filename."""
    label = re.sub(r"[^A-Za-z0-9._-]+", "-", model_path.stem).strip(".-_")
    return label[:120] or "unknown-model"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", type=Path, required=True, help="local GGUF file; never deleted by this tool")
    parser.add_argument("--llama-server", type=Path, required=True, help="local llama-server executable")
    parser.add_argument("--port", type=int, default=18080)
    parser.add_argument("--hours", type=float, default=8)
    parser.add_argument("--request-timeout", type=int, default=1800)
    parser.add_argument("--min-start-ram-gib", type=float, default=9)
    parser.add_argument("--context-tokens", type=int, default=16384)
    parser.add_argument("--reasoning-budget", type=int, default=2048)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--temperature", type=float, default=0)
    parser.add_argument("--delete-model-after", action="store_true", help="delete tested GGUF after a completed result; restricted to model-downloads/")
    parser.add_argument("--windows-host-gate", action="store_true", help="use restricted AST gate and run tests on Windows host; not a security sandbox")
    parser.add_argument("--disable-low-ram-guard", action="store_true", help="user-approved: keep disk, GPU and monitor guards active")
    parser.add_argument("--disable-resource-guards", action="store_true", help="user-approved: disable RAM, disk, GPU and monitor resource stops")
    args = parser.parse_args()
    if not 0 < args.hours <= 8 or not 0.5 <= args.min_start_ram_gib <= 64 or not 1 <= args.port <= 65535 or args.context_tokens < 4096 or args.reasoning_budget < 0 or not 0 <= args.temperature <= 2:
        parser.error("invalid hours, startup memory threshold or port")
    run = ROOT / "runs" / (datetime.now().strftime("%Y_%m_%d__%H_%M_%S_%f") + "__" + model_folder_label(args.model) + "__unattended")
    run.mkdir(parents=True)
    start = time.monotonic()
    status = {"status": "preflight", "calls": [], "public_checks": [], "hidden_check": None,
              "model": str(args.model), "manual_interventions": 0, "model_cleanup": "not requested",
              "context_tokens": args.context_tokens, "reasoning_budget_tokens": args.reasoning_budget,
              "seed": args.seed, "temperature": args.temperature, "low_ram_guard_disabled": args.disable_low_ram_guard, "resource_guards_disabled": args.disable_resource_guards}
    server = None
    monitor_stop = threading.Event()
    guard_reason = []
    monitor = None

    def save():
        status["elapsed_seconds"] = round(time.monotonic()-start, 3)
        (run / "result.json").write_text(json.dumps(status, indent=2), encoding="utf-8")

    def watch():
        bad = errors = 0
        with (run / "samples.jsonl").open("a", encoding="utf-8") as out:
            while not monitor_stop.is_set():
                try:
                    sample = overnight_local.sample()
                    out.write(json.dumps(sample) + "\n")
                    out.flush()
                    unsafe = ((not args.disable_low_ram_guard and sample["ram_available_bytes"] < 256 * overnight_local.MIB) or
                              sample["disk_free_bytes"] < 8 * overnight_local.GIB or sample["gpu_c"] >= 85)
                    bad = bad + 1 if unsafe else 0
                    errors = 0
                except Exception as exc:
                    out.write(json.dumps({"error": str(exc)}) + "\n")
                    out.flush()
                    errors += 1
                if (not args.disable_resource_guards and (bad >= 3 or errors >= 3)) or time.monotonic() - start >= args.hours * 3600:
                    guard_reason.append("resource_guard" if bad >= 3 else "monitor_failed" if errors >= 3 else "overall_timeout")
                    if server is not None and server.poll() is None:
                        server.terminate()
                    return
                monitor_stop.wait(10)

    try:
        if args.windows_host_gate:
            status["test_environment"] = "Windows host with AST gate and Python socket guard; NOT an OS sandbox"
        else:
            container_eval.ready()
            container_eval.verify_isolation(run)
            status["test_environment"] = "Docker isolation"
        if not args.model.is_file() or not args.llama_server.is_file():
            raise RuntimeError("local GGUF model and llama-server executable are required")
        if args.delete_model_after:
            allowed = (ROOT / "model-downloads").resolve()
            if (not args.model.resolve().is_relative_to(allowed) or args.model.is_symlink() or
                    args.model.suffix.lower() != ".gguf"):
                raise RuntimeError("model deletion is limited to regular GGUF files inside model-downloads")
            status["model_cleanup"] = "pending"
        with socket.socket() as sock:
            sock.settimeout(1)
            if sock.connect_ex(("127.0.0.1", args.port)) == 0:
                raise RuntimeError("configured port is already in use")
        first = overnight_local.sample()
        if not args.disable_resource_guards and (first["ram_available_bytes"] < args.min_start_ram_gib * overnight_local.GIB or
                first["disk_free_bytes"] < 8 * overnight_local.GIB or first["gpu_c"] >= 85):
            raise RuntimeError("resource preflight failed")
        # Record an actual file hash so a result is tied to its exact quantization.
        digest = hashlib.sha256()
        with args.model.open("rb") as source:
            for chunk in iter(lambda: source.read(8 * 1024 * 1024), b""):
                digest.update(chunk)
        status["model_sha256"] = digest.hexdigest()
        status["status"] = "starting_server"
        save()
        with (run / "server.log").open("w", encoding="utf-8") as output:
            server = subprocess.Popen([str(args.llama_server.resolve()), "--model", str(args.model.resolve()),
                                       "--host", "127.0.0.1", "--port", str(args.port), "--ctx-size", str(args.context_tokens), "--reasoning-budget", str(args.reasoning_budget), "--device", "Vulkan0"],
                                      stdout=output, stderr=subprocess.STDOUT, creationflags=subprocess.CREATE_NO_WINDOW)
        monitor = threading.Thread(target=watch, daemon=True)
        monitor.start()
        base = f"http://127.0.0.1:{args.port}"
        for _ in range(180):
            if guard_reason or server.poll() is not None:
                raise RuntimeError("server stopped before ready")
            try:
                if request_json(base + "/health").get("status") == "ok":
                    break
            except Exception:
                pass
            time.sleep(1)
        else:
            raise RuntimeError("llama.cpp server startup timed out")
        status["status"] = "running"
        save()
        materials = "\n\n".join((ROOT / n).read_text(encoding="utf-8") for n in ("spec.md", "plan.md", "tasks.md"))
        tests = (ROOT / "public_tests/test_sync.py").read_text(encoding="utf-8")
        skeleton = (ROOT / "skeleton/sync_app.py").read_text(encoding="utf-8")
        prompt = "Implement sync_app.py in full. Return only Python code.\n\n" + materials + "\n\nPUBLIC TESTS:\n" + tests + "\n\nSKELETON:\n" + skeleton
        for attempt in range(4):
            if guard_reason:
                raise RuntimeError(guard_reason[0])
            (run / f"prompt_{attempt}.txt").write_text(prompt, encoding="utf-8")
            payload = {"model": "local", "messages": [{"role": "user", "content": prompt}],
                       "stream": False, "temperature": args.temperature, "seed": args.seed, "max_tokens": 8192}
            call_start = time.monotonic()
            response = request_json(base + "/v1/chat/completions", payload, args.request_timeout)
            choice = response["choices"][0]
            status["calls"].append({"seconds": time.monotonic() - call_start, "usage": response.get("usage"),
                                    "timings": response.get("timings"), "finish_reason": choice.get("finish_reason")})
            (run / f"response_{attempt}.json").write_text(json.dumps(response, indent=2), encoding="utf-8")
            raw_code = choice["message"].get("content") or ""
            code = extract_code(raw_code)
            candidate = run / f"candidate_{attempt}.py.txt"
            candidate.write_text(code, encoding="utf-8")
            if guard_reason:
                raise RuntimeError(guard_reason[0])
            incomplete = incomplete_response(choice)
            if incomplete:
                public = {"exit_code": None, "output": "INCOMPLETE_GENERATION: no complete answer before the output/context limit", "seconds": 0, "incomplete_generation": True}
            else:
                public = (windows_eval if args.windows_host_gate else container_eval).evaluate(candidate, "public")
            status["public_checks"].append(public)
            (run / f"public_{attempt}.log").write_text(public["output"], encoding="utf-8")
            save()
            if public["exit_code"] == 0 or attempt == 3:
                if guard_reason:
                    raise RuntimeError(guard_reason[0])
                if incomplete:
                    status["status"] = "incomplete_generation"
                    break
                hidden = (windows_eval if args.windows_host_gate else container_eval).evaluate(candidate, "hidden")
                status["hidden_check"] = hidden
                (run / "hidden_final.log").write_text(hidden["output"], encoding="utf-8")
                status["status"] = "pass" if public["exit_code"] == 0 and hidden["exit_code"] == 0 else "fail"
                break
            prompt = ("Return the full corrected sync_app.py as Python code only.\n\n" + materials +
                      "\n\nPUBLIC TEST SOURCE:\n" + tests + "\n\nCURRENT CODE:\n" + code +
                      "\n\nPUBLIC TEST FAILURES:\n" + public["output"][-12000:])
    except Exception as exc:
        status["status"] = guard_reason[0] if guard_reason else "error"
        status["error"] = f"{type(exc).__name__}: {exc}"
    finally:
        monitor_stop.set()
        if server is not None and server.poll() is None:
            server.terminate()
            try:
                server.wait(timeout=15)
            except subprocess.TimeoutExpired:
                server.kill()
                server.wait(timeout=15)
        if monitor is not None:
            monitor.join(timeout=30)
        save()
        (run / "report.md").write_text("# Unattended benchmark\n\nStatus: " + status["status"] +
                                       "\n\nSee result.json and logs in this directory.\n", encoding="utf-8")
        if args.delete_model_after and status["status"] in ("pass", "fail"):
            try:
                args.model.unlink()
                status["model_cleanup"] = "deleted after result and report were saved"
            except OSError as exc:
                status["model_cleanup"] = f"failed: {exc}"
            save()
        print(json.dumps({"run": str(run), "status": status["status"], "error": status.get("error")}, indent=2))
    return 0 if status["status"] in ("pass", "fail") else 1


if __name__ == "__main__":
    raise SystemExit(main())
