# Overnight MoE generation controller

`benchmarks/api_sync/overnight_local.py` is a Windows/NVIDIA, local-only generation controller for the already installed `qwen3-coder:30b` (30B total / 3.3B active MoE). It makes no paid or cloud inference calls, downloads nothing, never executes generated code, and does not need Codex open. All output is retained under `benchmarks/api_sync/runs/*__overnight_moe/`. This is generation timing and resource monitoring, not a complete autonomous coding benchmark: there is no automatic test, repair loop, coding-quality score, or time-to-passing-project measurement.

In PowerShell at `C:\workspace\local-agent-engine`, first check prerequisites without starting inference:

```powershell
.venv\Scripts\python.exe benchmarks\api_sync\overnight_local.py --preflight
```

Once preflight succeeds and you have decided to run it, start the local controller. Keep this terminal and the laptop awake; the controller does not change Windows power settings:

```powershell
.venv\Scripts\python.exe benchmarks\api_sync\overnight_local.py --hours 8 --call-timeout 1800 --calls 1
```

`--calls 1` is one independent generation, not an eight-hour workload; `--calls 2` through `4` request independent attempts with distinct seeds, with a shared eight-hour ceiling. Every call has a default 30-minute limit. The requested call can finish early. A polling cycle can take longer than its sample interval, so deadlines are approximate. Recorded `request_*.json` contains the exact public prompt and options; `response_*.jsonl` contains streamed output and receive times. `summary.json` and `report.md` contain status and timings. `candidate_*.py.txt` is saved as text and is not executed.

Preflight refuses to start if any Ollama model is already loaded, if disk free space is below 8 GiB, available RAM is below 9 GiB, or GPU temperature is at least 85°C. The 9 GiB startup threshold is a conservative operational choice, not a guarantee of sufficient headroom. During a call the controller checks every cycle for available RAM below 256 MiB, disk below 8 GiB, or GPU temperature at least 85°C; three consecutive unsafe samples stop the client and run `ollama stop qwen3-coder:30b`. Three consecutive mandatory-monitor failures also stop it. Do not use Ollama concurrently during this exclusive run: the stop command affects that loaded model. The controller cannot guarantee recovery from a total OS hang, sudden power loss, an unresponsive driver, or its own abrupt termination.

The startup-only RAM threshold can be explicitly overridden with `--min-start-ram-gib`, with a minimum of 3 GiB; the chosen value is recorded in `summary.json`. On 2026-11-05 the user requested a run with the memory available, so it was launched with a 5 GiB startup threshold. The low-memory stop guard was retained. Lowering the threshold does not provide additional memory or guarantee responsiveness.

Samples contain physical RAM availability, commit limit/availability, disk free space, GPU utilization, temperature and VRAM, CPU utilization, pagefile usage and paging rates where Windows counters are available, and Ollama's reported model placement. Missing paging counters are recorded as errors. CPU temperature is not captured. RAM and pagefile figures are different measurements: commit availability is not the same as free pagefile capacity. Paging alone does not stop the run. Time to first output and output tokens/second are recorded when Ollama supplies them. These counters and guard thresholds have not been validated under actual 30B load in this version.

Afterward, inspect the candidate and imports before any execution. A venv and socket guard are not a security sandbox. Only execute a reviewed candidate in a disposable workspace; use public tests first, retain their logs, and run hidden acceptance tests only on the final candidate. The existing `timed_loop.py` has a review gate for its own model runs; the overnight controller does not automatically pass a candidate into it. Results cannot be represented as coding success until tests are actually run.

On 2026-11-05 an actual no-inference preflight observed about 5.3 GiB available RAM and was rejected after the startup threshold was tightened to 9 GiB. Free up memory by closing applications with the user's permission, then rerun preflight. No model was unloaded, downloaded, deleted, or run by the preflight. The 8 GiB disk guard applies to this already-installed model; it is not authorization or a space budget for downloading another model.
