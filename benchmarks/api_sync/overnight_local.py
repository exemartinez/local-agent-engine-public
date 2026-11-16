"""Local-only, generation-only overnight benchmark; generated code is never run."""
import argparse
import ctypes
import json
import os
import re
from pathlib import Path
import shutil
import subprocess
import sys
import time
from datetime import datetime
from urllib.request import Request, urlopen

from runner import ROOT, extract_code

URL = "http://127.0.0.1:11434"
MODEL = "qwen3-coder:30b"  # Installed Qwen3-Coder 30B-A3B MoE.
GIB = 1024 ** 3
MIB = 1024 ** 2


class MemoryStatus(ctypes.Structure):
    _fields_ = [("length", ctypes.c_ulong), ("load", ctypes.c_ulong),
                ("total_phys", ctypes.c_ulonglong), ("avail_phys", ctypes.c_ulonglong),
                ("total_page", ctypes.c_ulonglong), ("avail_page", ctypes.c_ulonglong),
                ("total_virtual", ctypes.c_ulonglong), ("avail_virtual", ctypes.c_ulonglong),
                ("avail_extended", ctypes.c_ulonglong)]


def memory():
    status = MemoryStatus()
    status.length = ctypes.sizeof(status)
    if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):
        raise OSError("GlobalMemoryStatusEx failed")
    return {"ram_available_bytes": status.avail_phys, "ram_total_bytes": status.total_phys,
            "commit_available_bytes": status.avail_page, "commit_limit_bytes": status.total_page}


def api(path, payload=None, timeout=5):
    request = Request(URL + path, data=None if payload is None else json.dumps(payload).encode(),
                      headers={"Content-Type": "application/json"})
    with urlopen(request, timeout=timeout) as response:
        return json.load(response)


def gpu():
    cmd = ["nvidia-smi", "--query-gpu=temperature.gpu,memory.used,memory.total,utilization.gpu",
           "--format=csv,noheader,nounits"]
    output = subprocess.run(cmd, capture_output=True, text=True, timeout=8, check=True,
                            creationflags=subprocess.CREATE_NO_WINDOW).stdout.strip().splitlines()[0]
    temperature, used, total, utilization = (int(value.strip()) for value in output.split(","))
    return {"gpu_c": temperature, "vram_used_mib": used, "vram_total_mib": total,
            "gpu_util_pct": utilization}


def windows_paging():
    command = ("$m=Get-CimInstance Win32_PerfFormattedData_PerfOS_Memory; "
               "$p=Get-CimInstance Win32_PageFileUsage; "
               "$c=Get-CimInstance Win32_PerfFormattedData_PerfOS_Processor -Filter \"Name='_Total'\"; "
               "@{pages_input_per_sec=$m.PagesInputPersec; page_reads_per_sec=$m.PageReadsPersec; "
               "cpu_util_pct=$c.PercentProcessorTime; "
               "pagefile_used_mib=($p | Measure-Object CurrentUsage -Sum).Sum; "
               "pagefile_allocated_mib=($p | Measure-Object AllocatedBaseSize -Sum).Sum} | ConvertTo-Json -Compress")
    try:
        result = subprocess.run(["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", command],
                                capture_output=True, text=True, timeout=8, check=True,
                                creationflags=subprocess.CREATE_NO_WINDOW)
        return json.loads(result.stdout)
    except Exception as exc:
        return {"paging_error": str(exc)}


def sample():
    data = {"timestamp": datetime.now().isoformat(timespec="seconds"),
            "disk_free_bytes": shutil.disk_usage(ROOT).free, **memory(), **gpu(), **windows_paging()}
    try:
        data["ollama_loaded"] = api("/api/ps").get("models", [])
    except Exception as exc:
        data["ollama_error"] = str(exc)
    return data


def worker(request_file, output_file):
    payload = json.loads(Path(request_file).read_text(encoding="utf-8"))
    request = Request(URL + "/api/chat", data=json.dumps(payload).encode(),
                      headers={"Content-Type": "application/json"})
    with urlopen(request, timeout=3600) as response, Path(output_file).open("w", encoding="utf-8") as out:
        for line in response:
            event = json.loads(line)
            out.write(json.dumps({"received_monotonic": time.monotonic(), "event": event}) + "\n")
            out.flush()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--hours", type=float, default=8.0, help="overall limit, at most 8 hours")
    parser.add_argument("--call-timeout", type=int, default=1800, help="seconds per call")
    parser.add_argument("--calls", type=int, default=1, choices=range(1, 5), help="independent generations, 1–4")
    parser.add_argument("--sample-seconds", type=int, default=10, choices=range(5, 61))
    parser.add_argument("--min-start-ram-gib", type=float, default=9, help="minimum available RAM at startup; default 9 GiB, minimum 3 GiB")
    parser.add_argument("--preflight", action="store_true", help="check prerequisites only, without inference")
    args = parser.parse_args()
    if not 0 < args.hours <= 8 or args.call_timeout <= 0 or not 3 <= args.min_start_ram_gib <= 64:
        parser.error("hours must be > 0 and <= 8; call timeout must be positive; startup RAM must be 3–64 GiB")
    if os.name != "nt":
        parser.error("resource monitor currently requires Windows and NVIDIA GPU")

    now = datetime.now().strftime("%Y_%m_%d__%H_%M_%S_%f")
    label = re.sub(r"[^A-Za-z0-9._-]+", "-", MODEL).strip(".-_")
    run = ROOT / "runs" / (now + "__" + label + "__overnight_moe")
    run.mkdir(parents=True)
    start = time.monotonic()
    summary = {"model": MODEL, "status": "starting", "started": datetime.now().isoformat(),
               "calls": [], "generated_code_executed": False, "correctness": "not evaluated",
               "limits": {"hours": args.hours, "call_timeout_seconds": args.call_timeout,
                          "min_disk_gib": 8, "min_start_available_ram_gib": args.min_start_ram_gib, "min_available_ram_mib": 256,
                          "max_gpu_c": 85, "consecutive_samples": 3}}
    proc = None

    def save():
        summary["elapsed_seconds"] = round(time.monotonic() - start, 3)
        (run / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")

    def report():
        rows = ["# Local overnight MoE run", "", f"Status: {summary['status']}",
                f"Model: {MODEL}", f"Elapsed: {summary['elapsed_seconds']:.1f} seconds", "",
                "Generated code was not executed; correctness and test success are unknown.", "",
                "See summary.json, samples.jsonl, prompts and raw response streams in this folder."]
        (run / "report.md").write_text("\n".join(rows) + "\n", encoding="utf-8")

    save()
    try:
        installed = api("/api/tags").get("models", [])
        if not any(item.get("name") == MODEL for item in installed):
            raise RuntimeError(f"{MODEL} is not installed; no download was attempted")
        first = sample()
        if first.get("ollama_error") or first.get("ollama_loaded"):
            raise RuntimeError("Ollama must be reachable and have no loaded models before this exclusive run")
        (run / "preflight.json").write_text(json.dumps(first, indent=2), encoding="utf-8")
        if first["disk_free_bytes"] < 8 * GIB or first["ram_available_bytes"] < args.min_start_ram_gib * GIB or first["gpu_c"] >= 85:
            raise RuntimeError(f"preflight failed: need >=8 GiB disk, >={args.min_start_ram_gib:g} GiB available RAM and GPU below 85 C")
        if args.preflight:
            summary["status"] = "preflight_ok"
            return 0
        materials = "\n\n".join((ROOT / name).read_text(encoding="utf-8") for name in ("spec.md", "plan.md", "tasks.md"))
        tests = (ROOT / "public_tests/test_sync.py").read_text(encoding="utf-8")
        skeleton = (ROOT / "skeleton/sync_app.py").read_text(encoding="utf-8")
        prompt = "Implement sync_app.py in full. Return only Python code.\n\n" + materials + "\n\nPUBLIC TESTS:\n" + tests + "\n\nSKELETON:\n" + skeleton
        deadline = start + args.hours * 3600
        summary["status"] = "running"
        save()
        with (run / "samples.jsonl").open("a", encoding="utf-8") as samples:
            for number in range(args.calls):
                if time.monotonic() >= deadline:
                    summary["status"] = "overall_timeout"
                    break
                payload = {"model": MODEL, "messages": [{"role": "user", "content": prompt}],
                           "stream": True, "keep_alive": "1m",
                           "options": {"temperature": 0, "seed": 42 + number, "num_ctx": 8192, "num_predict": 8192}}
                request_file = run / f"request_{number}.json"
                stream_file = run / f"response_{number}.jsonl"
                request_file.write_text(json.dumps(payload, indent=2), encoding="utf-8")
                call_start = time.monotonic()
                with (run / f"worker_{number}.stderr.log").open("w") as error_file:
                    proc = subprocess.Popen([sys.executable, str(Path(__file__).resolve()), "--worker", str(request_file), str(stream_file)],
                                            stdout=subprocess.DEVNULL, stderr=error_file,
                                            creationflags=subprocess.CREATE_NO_WINDOW)
                stop_reason, bad_samples, failed_samples = None, 0, 0
                while proc.poll() is None:
                    try:
                        data = sample()
                        data["call"] = number
                        samples.write(json.dumps(data) + "\n")
                        samples.flush()
                        unsafe = data["ram_available_bytes"] < 256 * MIB or data["gpu_c"] >= 85 or data["disk_free_bytes"] < 8 * GIB
                        bad_samples = bad_samples + 1 if unsafe else 0
                        failed_samples = 0
                    except Exception as exc:
                        samples.write(json.dumps({"error": str(exc), "call": number}) + "\n")
                        samples.flush()
                        failed_samples += 1
                    if bad_samples >= 3 or failed_samples >= 3:
                        stop_reason = "resource_guard" if bad_samples >= 3 else "monitor_failed"
                    elif time.monotonic() >= deadline:
                        stop_reason = "overall_timeout"
                    elif time.monotonic() - call_start >= args.call_timeout:
                        stop_reason = "call_timeout"
                    if stop_reason:
                        proc.terminate()
                        proc.wait(timeout=15)
                        # Exclusive preflight and documented no-concurrent-use rule establish ownership.
                        subprocess.run(["ollama", "stop", MODEL], capture_output=True, timeout=30,
                                       creationflags=subprocess.CREATE_NO_WINDOW)
                        break
                    time.sleep(args.sample_seconds)
                events = []
                if stream_file.exists():
                    for line in stream_file.read_text(encoding="utf-8").splitlines():
                        try:
                            events.append(json.loads(line))
                        except json.JSONDecodeError:
                            pass
                chunks = [e for e in events if e["event"].get("message", {}).get("content")]
                output = "".join(e["event"]["message"]["content"] for e in chunks)
                final = next((e["event"] for e in reversed(events) if e["event"].get("done")), {})
                (run / f"candidate_{number}.py.txt").write_text(extract_code(output), encoding="utf-8")
                call = {"attempt": number, "seconds": round(time.monotonic() - call_start, 3),
                        "first_token_seconds": round(chunks[0]["received_monotonic"] - call_start, 3) if chunks else None,
                        "exit_code": proc.returncode, "stop_reason": stop_reason, "done_reason": final.get("done_reason"),
                        "output_tokens": final.get("eval_count"), "eval_duration_ns": final.get("eval_duration")}
                if final.get("eval_count") and final.get("eval_duration"):
                    call["tokens_per_second"] = round(final["eval_count"] * 1e9 / final["eval_duration"], 3)
                summary["calls"].append(call)
                save()
                if stop_reason or proc.returncode != 0 or not final:
                    summary["status"] = stop_reason or "request_failed"
                    break
            else:
                summary["status"] = "generation_complete_awaiting_review"
    except Exception as exc:
        summary["status"] = "error"
        summary["error"] = f"{type(exc).__name__}: {exc}"
    finally:
        if proc is not None and proc.poll() is None:
            proc.terminate()
            proc.wait(timeout=15)
            try:
                subprocess.run(["ollama", "stop", MODEL], capture_output=True, timeout=30,
                               creationflags=subprocess.CREATE_NO_WINDOW)
            except Exception as exc:
                summary["cleanup_error"] = str(exc)
        save()
        report()
        print(f"{summary['status']}: {run}", flush=True)
        if summary.get("error"):
            print(summary["error"], flush=True)
    return 0 if summary["status"] == "generation_complete_awaiting_review" else 1


if __name__ == "__main__":
    if len(sys.argv) == 4 and sys.argv[1] == "--worker":
        worker(sys.argv[2], sys.argv[3])
    else:
        sys.exit(main())
