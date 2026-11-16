# MoE quantization benchmark queue

Local inference. Windows host tests use a static AST gate and a Python socket guard; this is not an OS sandbox.
Models are downloaded one at a time and removed after their artifacts are recorded.

16K context; 2048-token reasoning budget. Memory-fit decisions are heuristic, not guarantees.

| Model | Quantization | Status | Results |
| --- | --- | --- | --- |
| LFM2.5 8B-A1B | Q4_K_M | downloading |  |
| GPT-OSS 20B | MXFP4 | pending |  |

Detailed artifacts and exact file SHA-256 values: `C:\workspace\local-agent-engine\benchmarks\api_sync\runs\2026_11_07__01_03_30_849609__multi-model__windows_queue`.

Safety-gate rejections and timeouts are not passing coding tasks.

**Cancelled:** User requested the original pending-model queue instead; the partial LFM download was removed. No model was tested in this comparison.
