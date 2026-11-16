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
| GLM-4.7-Flash 30B-A3B | Q3_K_S | pending |  |
| GLM-4.7-Flash 30B-A3B | Q2_K | pending |  |
| GLM-4.7-Flash 30B-A3B | Q4_K_M | pending |  |
| Qwen3.5 35B-A3B | UD-IQ3_S | pending |  |
| Qwen3.5 35B-A3B | UD-IQ2_M | pending |  |
| Qwen3.5 35B-A3B | Q4_K_M | pending |  |

Detailed artifacts and exact file SHA-256 values: `C:\workspace\local-agent-engine\benchmarks\api_sync\runs\2026_11_06__21_54_32_648851__multi-model__windows_queue`.

Safety-gate rejections and timeouts are not passing coding tasks.
