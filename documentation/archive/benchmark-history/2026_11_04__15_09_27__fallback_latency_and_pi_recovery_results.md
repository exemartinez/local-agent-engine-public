# Fallback latency and Pi recovery results

## Scope

This local-only Ollama/Pi run measured cold and warm latency, generated-code correctness, telemetry, and independently verified Pi repairs.

## Configuration

- Prompt: Python `clamp(value, lower, upper)`.
- Context: 2,048 tokens; first-token deadline: 60 seconds; completion deadline: 180 seconds; keep-alive: 10 minutes.
- Telemetry: RAM, Pages Input/sec, Page Reads/sec, NVIDIA temperature, VRAM, and GPU use.
- Scripts: `scripts/fallback_latency_probe.py` and `scripts/run_fallback_probe.ps1`.

## Direct fallback results

| Model | Run | TTFT | Completion | Output | Result |
|---|---|---:|---:|---|---|
| LFM2.5 8B | Cold, 96-token cap | 10.563 s | 11.047 s | Reasoning consumed cap; code truncated | Latency pass; output-cap failure |
| LFM2.5 8B | Warm, 256-token cap | **0.066 s** | 1.178 s | Complete `clamp`; independently validated | Pass |
| Qwen3.5 4B | Cold, 256-token cap | 4.408 s | 4.653 s | Complete `clamp`; independently validated | Pass |
| Qwen3.5 4B | Warm, 256-token cap | **0.105 s** | **0.342 s** | Complete `clamp`; independently validated | Pass |

LFM's cold/warm difference is largely model-load latency. Its long `<think>` block means that a 96-token output cap is insufficient for reliable direct code output. With a 256-token cap, its extracted `clamp` implementation passed all three boundary tests.

Qwen3.5 returned direct code without exposed reasoning and used only 21 output tokens.

## Warm telemetry snapshots

| Model | Available RAM | Pages Input/sec | Page Reads/sec | GPU temperature | VRAM used / total |
|---|---:|---:|---:|---:|---:|
| LFM2.5 8B | 4.782 GiB | 142.49 | 15.94 | 56 C | 6,471 / 8,192 MiB |
| Qwen3.5 4B | 4.681 GiB | 8.88 | 2.96 | 55 C | 5,072 / 8,192 MiB |

Both models met the 30–60 second fallback budget. Neither reached a sustained-paging threshold and the machine remained responsive.

## Pi repair and recovery evidence

Pi with `qwen3.5:4b` inspected the intentionally broken `test-repos/lfm-agent-probe/math_utils.py`, changed only the faulty clamp expression, and reported success. Independent verification ran all three fixture tests successfully.

For recovery, `test-repos/qwen-recovery-probe/port_utils.py` initially returned `int(value)` without port-range validation. Two of its three tests failed: ports 0 and 65536 did not raise `ValueError`. Pi inspected implementation and tests, edited only `parse_port`, added conversion/range validation, and reported success. Independent `python -m unittest -v` then passed all three tests. The Pi command completed in about 19 seconds wall-clock, including its tool loop.

## Current recommendation

- **Best direct/supervised fallback:** LFM2.5 8B. Use a >=256 output cap and strip/review its reasoning before applying code. Its multi-step Pi loop remains unreliable.
- **Best Pi fallback:** Qwen3.5 4B. It passed cold/warm timing, generated valid code, repaired a failing fixture, and recovered a second failing implementation. It is slower than LFM but is the current recommended Pi model.
- Both tags remain installed while larger-model fallback tests are pending. Qwen3-Coder 30B and DeepSeek-Coder-V2 Lite still require the revised latency protocol; their prior paging-only probes do not establish response-time verdicts.

## Raw evidence

- `benchmarks/results/2026_11_04__15_04_14__fallback_probe__lfm2.5_8b.summary.json`
- `benchmarks/results/2026_11_04__15_04_36__fallback_probe__lfm2.5_8b.summary.json`
- `benchmarks/results/2026_11_04__15_06_53__fallback_probe__qwen3.5_4b.summary.json`
- `benchmarks/results/2026_11_04__15_07_08__fallback_probe__qwen3.5_4b.summary.json`
