# MoE quantization benchmark queue

Local inference. Windows host tests use a static AST gate and a Python socket guard; this is not an OS sandbox.
Models are downloaded one at a time and removed after their artifacts are recorded.

16K context; 2048-token reasoning budget. Memory-fit decisions are heuristic, not guarantees.

| Model | Quantization | Status | Results |
| --- | --- | --- | --- |
| GPT-OSS 20B | MXFP4 | pass | 4 calls, 1267.4s; see result.json |
| GLM-4.7-Flash 30B-A3B | Q3_K_S | skipped_memory_estimate | estimated weight and context budget exceeds available RAM/VRAM |
| GLM-4.7-Flash 30B-A3B | Q2_K | incomplete_generation | 4 calls, 1677.7s; see result.json |
| GLM-4.7-Flash 30B-A3B | Q4_K_M | skipped_memory_estimate | estimated weight and context budget exceeds available RAM/VRAM |
| Qwen3.5 35B-A3B | UD-IQ3_S | fail | 2 calls, 524.0s; see result.json |
| Qwen3.5 35B-A3B | UD-IQ2_M | resource_guard | 0 calls, 102.3s; see result.json |
| Qwen3.5 35B-A3B | Q4_K_M | pending |  |
| Qwen3-Coder 30B-A3B | Q3_K_S | pending |  |
| Qwen3-Coder 30B-A3B | Q2_K | pending |  |
| GPT-OSS 20B | Q3_K_M | pending |  |
| GPT-OSS 20B | Q4_K_M | pending |  |

Detailed artifacts and exact file SHA-256 values: `C:\workspace\local-agent-engine\benchmarks\api_sync\runs\2026_11_06__12_28_51_386020__multi-model__windows_queue`.

Safety-gate rejections and timeouts are not passing coding tasks.
