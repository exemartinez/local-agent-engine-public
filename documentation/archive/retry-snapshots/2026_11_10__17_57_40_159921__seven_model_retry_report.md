# Seven-configuration unattended benchmark

Status: **blocked_disk**

Local inference; Windows static gate and socket guard are not an OS sandbox.
Model-fit estimates and stabilization waits are bypassed; emergency RAM, disk, GPU and monitor guards remain active.
An emergency stop halts the controller. Pending entries are not coding failures.

| Model | Quantization | Prior outcome | Retry outcome | Calls | Elapsed s | Evidence |
| --- | --- | --- | --- | ---: | ---: | --- |
| GPT-OSS 20B | Q3_K_M | resource_guard | pending | — | — | `—` |
| GPT-OSS 20B | Q4_K_M | skipped_memory_estimate | pending | — | — | `—` |
| Qwen3-Coder 30B-A3B | Q3_K_S | resource_guard | pending | — | — | `—` |
| GLM-4.7-Flash 30B-A3B | Q3_K_S | skipped_memory_estimate | pending | — | — | `—` |
| GLM-4.7-Flash 30B-A3B | Q2_K | resource_guard | pending | — | — | `—` |
| GLM-4.7-Flash 30B-A3B | Q4_K_M | resource_guard | pending | — | — | `—` |
| Qwen3.5 35B-A3B | Q4_K_M | resource_guard | pending | — | — | `—` |

Disk reserve: 8.5 GiB plus the model download. Normal passes and failures advance; resource/monitor errors stop.
Reported elapsed time excludes download unless a queue record explicitly says otherwise.
Original queue (preserved): `C:\workspace\local-agent-engine\benchmarks\api_sync\runs\2026_11_09__01_26_42_255477__multi-model__windows_queue\queue.json`.
Raw results and model-generated code are retained in their run directories. Only downloads owned by the underlying queue are cleaned up.
A coding pass requires public tests, 90% coverage and hidden tests; loading stops are not quality scores.

## Previous benchmark results (preserved)

| Model | Quantization | Prior status | Summary |
| --- | --- | --- | --- |
| GPT-OSS 20B | MXFP4 | pass | 2/2 runs; 2 passed |
| GPT-OSS 20B | Q3_K_M | resource_guard | 1/1 runs; 0 passed |
| GPT-OSS 20B | Q4_K_M | skipped_memory_estimate | estimated weight and context budget exceeds available RAM/VRAM |
| Qwen3-Coder 30B-A3B | Q2_K | fail | 1/1 runs; 0 passed |
| Qwen3-Coder 30B-A3B | Q3_K_S | resource_guard | 1/1 runs; 0 passed |
| GLM-4.7-Flash 30B-A3B | Q3_K_S | skipped_memory_estimate | memory estimate failed after download |
| GLM-4.7-Flash 30B-A3B | Q2_K | resource_guard | 1/1 runs; 0 passed |
| GLM-4.7-Flash 30B-A3B | Q4_K_M | resource_guard | 1/1 runs; 0 passed |
| Qwen3.5 35B-A3B | UD-IQ3_S | fail | 1/1 runs; 0 passed |
| Qwen3.5 35B-A3B | UD-IQ2_M | fail | 1/1 runs; 0 passed |
| Qwen3.5 35B-A3B | Q4_K_M | resource_guard | 1/1 runs; 0 passed |

Historical small-model and Pi results: `documentation/archive/benchmark-history/2026_11_10__13_39_32__complete_local_model_benchmark_comparison.md`.

Reason: GPT-OSS 20B Q3_K_M: 6.95 GB free; at least 22.03 GB required including reserve.
