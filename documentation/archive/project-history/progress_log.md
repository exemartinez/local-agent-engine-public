# Execution progress log

## 2026-11-02 — refreshed baseline observation

### Milestone: prerequisite assessment

Status: **blocked before installation**. This is a refreshed observation; it does not replace the historical inventories.

| Measurement | Observed value | Baseline gate | Result |
|---|---:|---:|---|
| Installed RAM | 15.77 GiB | — | Informational |
| Available RAM | 1.32 GiB | >= 6 GiB | Blocked |
| C: free disk | 58.04 GiB | >= 20 GiB | Pass |
| GPU | RTX 3070 Laptop, 8 GiB VRAM | — | Informational |
| Free VRAM | 6.39 GiB | — | Informational |
| Pagefile | 16.15 GiB allocated; 1.67 GiB in use | Not model capacity | Informational |

The previous disk-space blocker is resolved. Available host RAM remains insufficient for the intended 4B baseline, so no model or inference runtime was downloaded or installed.

### Software and service state

- Ollama, OpenCode, llama-server, and llama-cli were not found.
- No listener was present on the expected Ollama port (`127.0.0.1:11434`).
- No inference, paid API usage, or cloud inference was performed.

### Memory-pressure evidence

Largest observed working sets included PyCharm (~2.98 GiB), ChatGPT (~0.66 GiB), Chrome (~0.48 GiB), Microsoft Defender (~0.40 GiB), Steam web helper (~0.32 GiB), and Edge WebView (~0.31 GiB). These are observations only; none were terminated or modified.

### Next actionable step

Free at least 4.68 GiB of additional available RAM by closing or suspending applications with no unsaved work, then rerun `scripts/preflight.ps1`. Do not enlarge the pagefile or download a model to bypass this gate.

### 30B status

**No-go in the current observed state.** The 30B assessment remains an estimate until a separate resource budget and measured baseline justify any attempt. No 30B download or load was attempted.

## 2026-11-02 — resume-gate recheck

The operator requested installation of Ollama and the recommended baseline model. A fresh gate check recorded 1.80 GiB available RAM, 58.03 GiB free disk, and 6.46 GiB free VRAM. Disk and VRAM were adequate, but host RAM remained below the 6 GiB baseline gate. Ollama was still absent. Per the stop condition, no installer or model download was started.

## 2026-11-02 — Qwen2.5-Coder 7B local trial

### Resource gate and installation

After closing previously authorized unused applications (PyCharm and Steam), the pre-download measurement was 6.59 GiB available RAM and 52.92 GiB free disk. The `qwen2.5-coder:7b` Q4_K_M model was pulled from Ollama successfully (4.7 GB download).

### Direct coding baseline

The model was tested three times at 2,048 context tokens with temperature zero. Each response returned a correct `mean(values)` implementation that rejects empty input. The first request took 33.771 s including a 15.426 s model load; warm requests took 0.458 s and 0.472 s at 80.39 and 79.86 generated tokens/s. Ollama reported 100% GPU placement, using 4.6 GB at the 2K context window.

### OpenCode integration attempt

OpenCode connected to the local model and entered the disposable `coding-baseline` fixture with edit permission limited to the fixture and shell/network denied. It did not perform an edit: it emitted a malformed edit call (`oldString: "mean ="`) and repeatedly planned the same action until the session was stopped. The fixture remained unchanged. With OpenCode's 4,096 context configuration, Ollama reported 100% GPU placement and 4.8 GB model memory; host free RAM was 5.84 GiB.

### Result and next step

**Direct coding: pass. GPU acceleration: pass. OpenCode autonomous edit: fail.** The 7B model is a materially stronger local direct-code option than the earlier 4B baseline, but it has not met the agentic acceptance criterion. Restore a working local Python interpreter, then rerun the fixture with a minimal tool-call configuration or an OpenCode/Ollama compatibility adjustment before considering a larger model.

## 2026-11-03 — Pi local-agent configuration and Qwen3.5 4B probe

### Pi configuration

- Pi 1.5.0 is installed and connected to the local Ollama OpenAI-compatible endpoint only (`127.0.0.1:11434/v1`); no paid or cloud provider was configured.
- Pi installed its local `fd` and `ripgrep` helpers under the user Pi directory.
- User-level Pi defaults now enable `read`, `powershell`, `edit`, `write`, `grep`, `find`, and `ls`. Native PowerShell replaces model-facing Bash on Windows.
- The local model picker includes Qwen2.5-Coder 7B and Qwen3.5 4B.

### Structured tool-call probe

- Qwen2.5-Coder 7B returned a JSON-shaped tool request as ordinary assistant text through Ollama. It is unsuitable for Pi autonomous tool execution in this setup.
- Qwen3.5 4B returned a structured `tool_calls` response to the identical local endpoint probe.
- Pi then executed a verified `ls` call with Qwen3.5 4B, received the actual repository listing, and summarized it. This proves the Pi/Ollama/tool loop, not merely a successful connection.

### Disposable coding-agent probe

- Qwen3.5 4B used Pi's `read` tool on the implementation and test fixture, then used `edit` to modify only `test-repos/coding-baseline/math_utils.py`.
- It changed the mean denominator to `len(values)` and added explicit `ValueError` handling for an empty sequence. Independent execution from the fixture directory passed both unit tests (`test_mean`, `test_empty`).
- Agent quality remains mixed: after the correct edit it issued flawed PowerShell verification commands and exhausted the configured 4K context window. Treat this as a tool-execution pass, coding-task pass, and efficiency/recovery limitation.

### Performance and placement

- Partial reproducible latency run: `benchmarks/results/qwen3.5_4b_latency_20261103.csv`. Four completed warm request rows measured 84.93–88.21 generated tokens/s at 512–2,083 actual input tokens and 128/512 output caps. The run did not reach its summary stage, so these rows are partial evidence only.
- During an 8K-context request, Ollama reported Qwen3.5 4B at 100% GPU on the RTX 3070 Laptop GPU, with 5,455 MiB of 8,192 MiB VRAM used. At that moment, C: had 58.96 GiB free.

### Next-model resource gate — 2026-11-03

- Fresh measurement before evaluating another local model: 0.45 GiB available RAM of 15.77 GiB; pagefile 16.78 GiB allocated and 1.96 GiB in use; C: 51.44 GiB free.
- Largest active working sets: PyCharm 2.78 GiB, loaded Ollama runner 2.11 GiB, ChatGPT 0.65 GiB, Discord 0.39 GiB, with Chrome processes also active.
- Disk is adequate but host-memory headroom is not. No additional model was downloaded or loaded. Resume the larger-model evaluation only after voluntarily closing/suspending enough applications to restore at least 6 GiB available RAM; do not enlarge the pagefile to bypass this gate.

### Stop-condition verification — 2026-11-03

- Before a further inference run, available RAM fell to 0.32 GiB with approximately 3,467 Pages Input/sec and 639 Page Reads/sec. This met the severe-paging stop condition, so no new inference benchmark was started.
- The existing Qwen3.5 runner was allowed to expire normally. After it unloaded, available RAM recovered to 2.57 GiB. This is improved but remains below the 6 GiB safety gate.

## 2026-11-03 — Qwen raw-JSON tool-call bridge

- Installed a local Pi extension at `~/.pi/agent/extensions/raw-json-tool-bridge.ts`.
- Scope is deliberately limited to Qwen model IDs. It converts only a standalone, valid JSON object of the form `{"name":"active-tool","arguments":{...}}` into a Pi tool-call block.
- The extension rejects non-Qwen output, mixed prose/JSON output, unknown or inactive tool names, non-object arguments, and invalid JSON. Pi then performs its normal tool argument preparation and schema validation before any execution.
- The extension loaded successfully during a no-model `pi --list-models` check. A live inference test remains deferred while available host RAM is below the established safety gate.

## 2026-11-03 — controlled local-model rotation benchmark

- Updated `benchmarks/benchmark.py` to enumerate installed Ollama models, warm models before measurement, retain partial rows, record errors instead of aborting, query resident model placement, and write a per-model summary.
- With 6.48 GiB available RAM and 58.96 GiB free disk, benchmarked Qwen2.5-Coder 7B and Qwen3.5 4B: 18/18 rows each, zero errors, 8K context. Their raw combined result is `benchmarks/results/all_installed_ollama_benchmark_20261103_complete.csv`.
- Preserved raw result artifacts, then removed both completed tags. Downloaded, tool-probed, and benchmarked LFM2.5 8B-A1B: 18/18 rows, native tool calls, 199.30 median generated tokens/sec, 0.32 s median TTFT, and 2.65 s median end-to-end. Removed the completed tag after recording results.
- Downloaded, tool-probed, and benchmarked Llama 3 Groq Tool Use 8B: 18/18 rows, native tool calls, 77.19 median generated tokens/sec, 0.94 s median TTFT, and 3.68 s median end-to-end. It remains installed as the latest rotation candidate.
- `documentation/archive/project-history/final_recommendation.md` was updated after each completed pass. It currently recommends reinstalling LFM2.5 8B as the performance default, with the qualification that raw throughput is not a coding-agent quality benchmark.

## 2026-11-03 — Python-quality extension and 30B feasibility probe

- Extended `benchmarks/benchmark.py` with a quality-only mode: two deterministic attempts each for built-ins-only `mean`, `slugify`, and non-mutating `merge_intervals`. Generated code is parsed through a restricted AST and executed with safe built-ins only. Leading model `<think>` blocks are removed before code extraction.
- Llama 3 Groq Tool Use 8B scored 2/6 valid attempts: both `mean` attempts passed; slug and interval merge failed. LFM2.5 8B scored 4/6: mean and interval merge passed; slug failed. Qwen3.5 9B Q4_K_M also scored 4/6 at 4K context, but generated the quality-task code at roughly 59–61 tokens/sec versus LFM at roughly 194–201 tokens/sec.
- Downloaded Qwen3-Coder 30B (18 GB local artifact) only to conduct a controlled 2K-context, one-token load probe. Available RAM collapsed to 0.84 GiB and paging reached approximately 224,390 Pages Input/sec / 1,698 Page Reads/sec before any response. The probe was terminated and model unloaded; RAM recovered to 6.58 GiB. This is a measured NO-GO, not merely an estimate.
- Removed the unsuccessful 30B, Groq, Qwen3.5 9B, and other rotated tags after preserving evidence. Reinstalled LFM2.5 8B as the sole local model and updated Pi's local catalog to it.

## 2026-11-03 — live LFM2.5 Pi-agent probe

- Ran a disposable three-test `clamp` repair task through Pi with `lfm2.5:8b`. The model issued one native `read` tool call and received the implementation, then emitted a raw multi-tool JSON object for the next reads as ordinary assistant text. Pi did not execute that object.
- The fixture implementation was unchanged. Independent `python -m unittest -v` execution recorded two failures of three tests. This is a reproducible multi-step Pi tool-loop failure, despite LFM's successful direct OpenAI-compatible structured-tool probe.
- LFM remains the measured speed/direct-generation leader, but is now recommended only for supervised prompts. It is not evidence of a reliable Pi coding agent.

## 2026-11-04 — DeepSeek-Coder-V2 Lite bounded feasibility probe

- Fresh pre-download gate passed: 7.67 GiB minimum available RAM, 49.25 GiB free disk, no loaded Ollama model, and low paging. Downloaded the official 8.9 GB `deepseek-coder-v2:lite` artifact.
- A monitored one-token request at 2K context was stopped on its first sample. Paging reached 35,267 Pages Input/sec and 1,879 Page Reads/sec before any response; this exceeded the severe-paging limit. The model was immediately unloaded.
- Recovery check: 7.52 GiB available RAM, no loaded model, and max 130 Pages Input/sec / 22 Page Reads/sec. Raw process-output paths: `benchmarks/logs/deepseek-coder-v2-lite-load-probe-20261104-014937.stdout.log` and `benchmarks/logs/deepseek-coder-v2-lite-load-probe-20261104-014937.stderr.log`.
- Verdict: measured NO-GO. No further 9 GB-plus model artifact is justified on this 16 GiB host; the 30B NO-GO remains confirmed.

## 2026-11-04 — revised fallback latency and Pi evaluation

- Added `scripts/fallback_latency_probe.py` and `scripts/run_fallback_probe.ps1`. The wrapper records streamed TTFT/completion plus RAM, paging, NVIDIA temperature/VRAM/use, and stops only for missed deadlines or sustained severe paging.
- LFM2.5 8B passed the warm direct clamp probe at 0.066 s TTFT / 1.178 s completion with a 256-token cap; its 96-token cold output was truncated by exposed reasoning.
- Qwen3.5 4B passed direct cold/warm clamp probes at 4.408 s / 0.105 s TTFT and 4.653 s / 0.342 s completion. It independently repaired and tested a failing `clamp` fixture and recovered a failing `parse_port` fixture through Pi; the latter took about 19 seconds. Its 2K deterministic quality score was 2/6.
- Qwen3-Coder 30B passed direct cold/warm clamp probes at 45.740 s / 0.192 s TTFT and 49.181 s / 2.079 s completion, and scored 6/6 in the deterministic quality suite. Its direct cold run severely paged but recovered after unload. A clean 2K Pi repair task made no tool action or edit in approximately 175 seconds and was terminated; it is unsuitable as a Pi agent but conditionally usable for direct batch prompts.
