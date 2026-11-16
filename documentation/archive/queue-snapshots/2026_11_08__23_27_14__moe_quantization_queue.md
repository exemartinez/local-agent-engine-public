# MoE quantization benchmark queue

Local inference. Windows host tests use a static AST gate and a Python socket guard; this is not an OS sandbox.
Models are downloaded one at a time and removed after their artifacts are recorded.

16K context; 2048-token reasoning budget. Memory-fit decisions are heuristic, not guarantees.

| Model | Quantization | Status | Results |
| --- | --- | --- | --- |
| GPT-OSS 20B | MXFP4 | pass | 2/2 runs; 2 passed |
| GPT-OSS 20B | Q3_K_M | resource_guard | 1/1 runs; 0 passed |
| GPT-OSS 20B | Q4_K_M | skipped_memory_estimate | estimated weight and context budget exceeds available RAM/VRAM |
| Qwen3-Coder 30B-A3B | Q2_K | fail | 1/1 runs; 0 passed |
| Qwen3-Coder 30B-A3B | Q3_K_S | resource_guard | 1/1 runs; 0 passed |
| GLM-4.7-Flash 30B-A3B | Q3_K_S | skipped_memory_estimate | memory estimate failed after download |
| GLM-4.7-Flash 30B-A3B | Q2_K | resource_guard | 1/1 runs; 0 passed |
| GLM-4.7-Flash 30B-A3B | Q4_K_M | skipped_memory_estimate | estimated weight and context budget exceeds available RAM/VRAM |
| Qwen3.5 35B-A3B | UD-IQ3_S | skipped_memory_estimate | estimated weight and context budget exceeds available RAM/VRAM |
| Qwen3.5 35B-A3B | UD-IQ2_M | skipped_observed_resource_guard | same machine and file hit low-memory guard on 2026-11-06 |
| Qwen3.5 35B-A3B | Q4_K_M | skipped_memory_estimate | estimated weight and context budget exceeds available RAM/VRAM |

Detailed artifacts and exact file SHA-256 values: `C:\workspace\local-agent-engine\benchmarks\api_sync\runs\2026_11_08__23_27_14_591016__multi-model__windows_queue`.

Safety-gate rejections and timeouts are not passing coding tasks.
