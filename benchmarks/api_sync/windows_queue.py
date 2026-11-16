"""Sequential local GGUF download, Windows-gated evaluation, reporting and cleanup."""
import argparse
import hashlib
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

from runner import ROOT
from overnight_local import gpu, memory

GIB = 1024 ** 3
RUNTIME = ROOT / "runtime/llama-b12143/llama-server.exe"
MODELS = [
    ("GPT-OSS 20B", "MXFP4", "ggml-org/gpt-oss-20b-GGUF", "gpt-oss-20b-MXFP4.gguf", 12.1),
    ("GPT-OSS 20B", "Q3_K_M", "mradermacher/gpt-oss-20b-GGUF", "gpt-oss-20b.Q3_K_M.gguf", 12.9),
    ("GPT-OSS 20B", "Q4_K_M", "mradermacher/gpt-oss-20b-GGUF", "gpt-oss-20b.Q4_K_M.gguf", 15.8),
    ("Qwen3-Coder 30B-A3B", "Q2_K", "unsloth/Qwen3-Coder-30B-A3B-Instruct-GGUF", "Qwen3-Coder-30B-A3B-Instruct-Q2_K.gguf", 11.3),
    ("Qwen3-Coder 30B-A3B", "Q3_K_S", "unsloth/Qwen3-Coder-30B-A3B-Instruct-GGUF", "Qwen3-Coder-30B-A3B-Instruct-Q3_K_S.gguf", 13.3),
    ("GLM-4.7-Flash 30B-A3B", "Q3_K_S", "unsloth/GLM-4.7-Flash-GGUF", "GLM-4.7-Flash-Q3_K_S.gguf", 13.3),
    ("GLM-4.7-Flash 30B-A3B", "Q2_K", "unsloth/GLM-4.7-Flash-GGUF", "GLM-4.7-Flash-Q2_K.gguf", 11.3),
    ("GLM-4.7-Flash 30B-A3B", "Q4_K_M", "unsloth/GLM-4.7-Flash-GGUF", "GLM-4.7-Flash-Q4_K_M.gguf", 18.3),
    ("Qwen3.5 35B-A3B", "UD-IQ3_S", "unsloth/Qwen3.5-35B-A3B-GGUF", "Qwen3.5-35B-A3B-UD-IQ3_S.gguf", 13.6),
    ("Qwen3.5 35B-A3B", "UD-IQ2_M", "unsloth/Qwen3.5-35B-A3B-GGUF", "Qwen3.5-35B-A3B-UD-IQ2_M.gguf", 11.4),
    ("Qwen3.5 35B-A3B", "Q4_K_M", "unsloth/Qwen3.5-35B-A3B-GGUF", "Qwen3.5-35B-A3B-Q4_K_M.gguf", 22.0),
]
REPEAT_CONFIGS = {("GPT-OSS 20B", "MXFP4"): [(43, 0.2), (44, 0.2)]}


def wait_for_memory(deadline, *, sample=memory, clock=time.monotonic, sleep=time.sleep,
                    min_available=5 * GIB, tolerance=512 * 1024 ** 2, interval=10, max_wait=600):
    """Wait for three consecutive stable available-RAM readings; record each one."""
    limit = min(deadline, clock() + max_wait)
    readings = []
    while clock() < limit:
        value = sample()["ram_available_bytes"]
        readings.append(value)
        recent = readings[-3:]
        if len(recent) == 3 and min(recent) >= min_available and max(recent) - min(recent) <= tolerance:
            return {"stable": True, "samples_bytes": readings, "interval_seconds": interval}
        remaining = limit - clock()
        if remaining > 0:
            sleep(min(interval, remaining))
    return {"stable": False, "samples_bytes": readings, "interval_seconds": interval}


def assess_model_memory(model_bytes, available_ram, gpu_free):
    """Conservative, recorded estimate; actual placement and KV needs remain unknown."""
    ram_reserve = GIB
    gpu_reserve = 512 * 1024 ** 2
    context_runtime_reserve = GIB  # Heuristic for a 16K context, not a measured guarantee.
    paging_allowance = GIB  # Budget modest existing paging, without changing the pagefile.
    budget = max(0, available_ram - ram_reserve) + max(0, gpu_free - gpu_reserve) + paging_allowance - context_runtime_reserve
    return {"model_bytes": model_bytes, "available_ram_bytes": available_ram, "gpu_free_bytes": gpu_free,
            "ram_reserve_bytes": ram_reserve, "gpu_reserve_bytes": gpu_reserve,
            "context_runtime_reserve_bytes": context_runtime_reserve, "paging_allowance_bytes": paging_allowance,
            "estimated_weight_budget_bytes": budget, "fits_estimate": model_bytes <= budget}


def current_model_assessment(model_bytes):
    try:
        g = gpu()
        return assess_model_memory(model_bytes, memory()["ram_available_bytes"], (g["vram_total_mib"] - g["vram_used_mib"]) * 1024 ** 2)
    except Exception as exc:
        raise RuntimeError(f"resource monitor unavailable: {exc}") from exc


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--resume-from", type=Path, help="copy a finished queue and run only its pending entries")
    parser.add_argument("--download-reserve-gib", type=float, default=10, help="disk space to reserve during model download (minimum 8.5 GiB)")
    parser.add_argument("--allow-memory-overcommit", action="store_true", help="attempt previously skipped models while retaining runtime emergency guards")
    parser.add_argument("--disable-low-ram-guard", action="store_true", help="user-approved: disable runtime low-RAM stop")
    parser.add_argument("--disable-resource-guards", action="store_true", help="user-approved: disable RAM, disk, GPU and monitor resource stops")
    args = parser.parse_args()
    if not 8.5 <= args.download_reserve_gib <= 100:
        parser.error("download reserve must be between 8.5 and 100 GiB")
    label = re.sub(r"[^A-Za-z0-9._-]+", "-", MODELS[0][0] + "-" + MODELS[0][1]).strip(".-_") if len(MODELS) == 1 else "multi-model"
    run = ROOT / "runs" / (datetime.now().strftime("%Y_%m_%d__%H_%M_%S_%f") + "__" + label + "__windows_queue")
    run.mkdir(parents=True)
    model_dir = ROOT / "model-downloads"
    model_dir.mkdir(exist_ok=True)
    report = ROOT.parent.parent / "documentation" / "archive" / "queue-snapshots" / (datetime.now().strftime("%Y_%m_%d__%H_%M_%S") + "__moe_quantization_queue.md")
    report.parent.mkdir(parents=True, exist_ok=True)
    deadline = time.monotonic() + 8 * 3600
    records = [{"model": m, "quantization": q, "source": repo, "file": name, "status": "pending"} for m, q, repo, name, _ in MODELS]
    state = {"status": "running", "test_environment": "Windows host, static AST gate and socket guard; not a security sandbox", "models": records,
             "download_reserve_gib": args.download_reserve_gib, "allow_memory_overcommit": args.allow_memory_overcommit, "low_ram_guard_disabled": args.disable_low_ram_guard, "resource_guards_disabled": args.disable_resource_guards}
    if args.resume_from:
        previous = json.loads(args.resume_from.read_text(encoding="utf-8"))
        if previous.get("status") == "running":
            raise RuntimeError("refusing to resume a queue marked running")
        previous_models = previous.get("models", [])
        if len(previous_models) != len(records) or any(
            any(old.get(key) != new[key] for key in ("model", "quantization", "source", "file"))
            for old, new in zip(previous_models, records)
        ):
            raise RuntimeError("saved queue does not match the current model manifest")
        records = previous_models
        state["models"] = records
        state["resumed_from"] = str(args.resume_from.resolve())

    def save():
        (run / "queue.json").write_text(json.dumps(state, indent=2), encoding="utf-8")
        lines = ["# MoE quantization benchmark queue", "", "Local inference. Windows host tests use a static AST gate and a Python socket guard; this is not an OS sandbox.",
                 "Models are downloaded one at a time and removed after their artifacts are recorded.", "",
                 "16K context; 2048-token reasoning budget. Memory-fit decisions are heuristic, not guarantees.",
                 f"Memory overcommit enabled: {args.allow_memory_overcommit}; memory stabilization skipped and startup RAM minimum 0.5 GiB when enabled; low-RAM guard disabled: {args.disable_low_ram_guard}; all resource guards disabled: {args.disable_resource_guards}.", "",
                 "| Model | Quantization | Status | Results |", "| --- | --- | --- | --- |"]
        for row in records:
            lines.append(f"| {row['model']} | {row['quantization']} | {row['status']} | {row.get('result_summary', '')} |")
        lines += ["", "Detailed artifacts and exact file SHA-256 values: `" + str(run) + "`.", "", "Safety-gate rejections and timeouts are not passing coding tasks."]
        report.write_text("\n".join(lines) + "\n", encoding="utf-8")

    save()
    if not RUNTIME.is_file():
        state.update(status="blocked", error="portable llama-server is missing")
        save()
        return 1
    for index, (model, quant, repo, name, expected_gb) in enumerate(MODELS):
        row = records[index]
        if row["status"] != "pending":
            continue
        if time.monotonic() >= deadline:
            state["status"] = "overall_timeout"
            break
        target = model_dir / name
        partial = model_dir / (name + ".partial")
        owned = False
        try:
            if target.exists() or partial.exists():
                raise RuntimeError("destination exists; refusing to overwrite or delete it")
            if not args.allow_memory_overcommit and model == "Qwen3.5 35B-A3B" and quant == "UD-IQ2_M":
                row.update(status="skipped_observed_resource_guard", result_summary="same machine and file hit low-memory guard on 2026-11-06")
                continue
            row["status"] = "waiting_for_memory"
            save()
            row["memory_recovery"] = {"stable": True, "skipped": True, "reason": "memory stabilization disabled for overcommit run"} if args.allow_memory_overcommit else wait_for_memory(deadline)
            if not row["memory_recovery"]["stable"]:
                raise TimeoutError("available RAM did not stabilize within the recovery window")
            row["memory_estimate_before_download"] = current_model_assessment(int(expected_gb * 1e9))
            if not args.allow_memory_overcommit and not row["memory_estimate_before_download"]["fits_estimate"]:
                row.update(status="skipped_memory_estimate", result_summary="estimated weight and context budget exceeds available RAM/VRAM")
                continue
            if not args.disable_resource_guards and shutil.disk_usage(model_dir).free < int(expected_gb * 1e9) + args.download_reserve_gib * GIB:
                row.update(status="skipped_disk_headroom", result_summary="insufficient disk for model and configured reserve")
                continue
            row["status"] = "downloading"
            row["url"] = f"https://huggingface.co/{repo}/resolve/main/{name}"
            save()
            request = Request(row["url"], headers={"User-Agent": "local-agent-benchmark/1"})
            digest = hashlib.sha256()
            start = time.monotonic()
            with urlopen(request, timeout=120) as response, partial.open("xb") as stream:
                owned = True
                size = int(response.headers.get("Content-Length", "0"))
                if not args.disable_resource_guards and size and shutil.disk_usage(model_dir).free < size + args.download_reserve_gib * GIB:
                    row.update(status="skipped_disk_headroom", result_summary="insufficient disk for exact model size and configured reserve")
                    continue
                while True:
                    if time.monotonic() >= deadline:
                        raise TimeoutError("overall deadline reached during download")
                    block = response.read(4 * 1024 * 1024)
                    if not block:
                        break
                    stream.write(block)
                    digest.update(block)
                    if not args.disable_resource_guards and shutil.disk_usage(model_dir).free < 8 * GIB:
                        raise RuntimeError("disk reserve reached during download")
            row["download_seconds"] = round(time.monotonic() - start, 2)
            row["download_bytes"] = partial.stat().st_size
            if size and row["download_bytes"] != size:
                raise RuntimeError("incomplete download")
            row["sha256"] = digest.hexdigest()
            os.rename(partial, target)
            row["memory_estimate_before_load"] = current_model_assessment(row["download_bytes"])
            if not args.allow_memory_overcommit and not row["memory_estimate_before_load"]["fits_estimate"]:
                row.update(status="skipped_memory_estimate", result_summary="memory estimate failed after download")
                continue
            row["status"] = "benchmarking"
            save()
            attempts = REPEAT_CONFIGS.get((model, quant), [(42, 0.0)])
            row["replicates"] = []
            for rep, (seed, temperature) in enumerate(attempts):
                if rep:
                    row["between_replicate_recovery"] = {"stable": True, "skipped": True, "reason": "memory stabilization disabled for overcommit run"} if args.allow_memory_overcommit else wait_for_memory(deadline)
                    if not row["between_replicate_recovery"]["stable"]:
                        row.update(status="memory_recovery_timeout", result_summary="RAM did not stabilize between repeats")
                        state["status"] = "stopped"
                        break
                    row["repeat_memory_estimate"] = current_model_assessment(row["download_bytes"])
                    if not args.allow_memory_overcommit and not row["repeat_memory_estimate"]["fits_estimate"]:
                        row.update(status="skipped_memory_estimate", result_summary="second repeat exceeded memory estimate")
                        break
                if time.monotonic() >= deadline:
                    row.update(status="overall_timeout", result_summary="deadline before next repeat")
                    state["status"] = "overall_timeout"
                    break
                remaining = max(0.001, (deadline - time.monotonic()) / 3600)
                command = [sys.executable, str(ROOT / "unattended_benchmark.py"), "--model", str(target),
                           "--llama-server", str(RUNTIME), "--windows-host-gate", "--min-start-ram-gib", "0.5" if args.allow_memory_overcommit else "5",
                           "--hours", str(min(8, remaining)), "--request-timeout", "1800",
                           "--context-tokens", "16384", "--reasoning-budget", "2048",
                           "--seed", str(seed), "--temperature", str(temperature)]
                if args.disable_resource_guards:
                    command.append("--disable-resource-guards")
                if args.disable_low_ram_guard:
                    command.append("--disable-low-ram-guard")
                result = subprocess.run(command, capture_output=True, text=True, creationflags=subprocess.CREATE_NO_WINDOW)
                (run / f"{index:02d}_{rep}__runner.stdout.log").write_text(result.stdout, encoding="utf-8")
                (run / f"{index:02d}_{rep}__runner.stderr.log").write_text(result.stderr, encoding="utf-8")
                try:
                    outcome = json.loads(result.stdout)
                    details = json.loads((Path(outcome["run"]) / "result.json").read_text(encoding="utf-8"))
                    row["benchmark"] = outcome["run"]
                    row["replicates"].append({"run": outcome["run"], "status": details["status"], "seed": seed,
                                              "temperature": temperature, "calls": len(details["calls"]),
                                              "seconds": details["elapsed_seconds"]})
                    row["status"] = details["status"]
                    row["result_summary"] = f"{len(row['replicates'])}/{len(attempts)} runs; {sum(r['status'] == 'pass' for r in row['replicates'])} passed"
                    if details.get("error"):
                        row["error"] = details["error"]
                    if details["status"] in ("resource_guard", "monitor_failed", "overall_timeout"):
                        state["status"] = details["status"]
                        break
                    save()
                except (ValueError, KeyError, OSError) as exc:
                    row.update(status="error", error=f"runner result unavailable: {exc}")
                    state["status"] = "runner_error"
                    break
        except Exception as exc:
            row.update(status="error", error=f"{type(exc).__name__}: {exc}")
            row["result_summary"] = row["error"]
            if "resource monitor unavailable" in str(exc).lower():
                state["status"] = "monitor_failed"
            elif isinstance(exc, TimeoutError) or "disk" in str(exc).lower():
                state["status"] = "stopped"
        finally:
            # Only files created by this queue invocation are removed; existing files are never touched.
            if owned:
                for path in (partial, target):
                    if path.exists():
                        try:
                            path.unlink()
                        except OSError as exc:
                            row["cleanup_error"] = str(exc)
                            state["status"] = "cleanup_failed"
            save()
        if state["status"] != "running":
            break
    else:
        state["status"] = "complete"
    save()
    print(json.dumps({"status": state["status"], "run": str(run), "report": str(report)}, indent=2))
    return 0 if state["status"] == "complete" else 1


if __name__ == "__main__":
    raise SystemExit(main())
