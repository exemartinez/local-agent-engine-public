# MoE quantization benchmark queue

Local inference. Windows host tests use a static AST gate and a Python socket guard; this is not an OS sandbox.
Models are downloaded one at a time and removed after their artifacts are recorded.

| Model | Quantization | Status | Results |
| --- | --- | --- | --- |
| GPT-OSS 20B | MXFP4 | fail | 4 calls, 894.5s; see result.json |
| GLM-4.7-Flash 30B-A3B | Q3_K_S | fail | 4 calls, 948.6s; see result.json |
| GLM-4.7-Flash 30B-A3B | Q2_K | fail | 4 calls, 786.7s; see result.json |
| GLM-4.7-Flash 30B-A3B | Q4_K_M | resource_guard | 0 calls, 154.7s; see result.json |
| Qwen3.5 35B-A3B | UD-IQ3_S | pending |  |
| Qwen3.5 35B-A3B | UD-IQ2_M | pending |  |
| Qwen3.5 35B-A3B | Q4_K_M | pending |  |
| Qwen3-Coder 30B-A3B | Q3_K_S | pending |  |
| Qwen3-Coder 30B-A3B | Q2_K | pending |  |
| GPT-OSS 20B | Q3_K_M | pending |  |
| GPT-OSS 20B | Q4_K_M | pending |  |

Detailed artifacts and exact file SHA-256 values: `C:\workspace\local-agent-engine\benchmarks\api_sync\runs\2026_11_06__00_28_15_840493__multi-model__windows_queue`.

Safety-gate rejections and timeouts are not passing coding tasks.
