# MoE quantization benchmark queue

Local inference. Windows host tests use a static AST gate and a Python socket guard; this is not an OS sandbox.
Models are downloaded one at a time and removed after their artifacts are recorded.

16K context; 2048-token reasoning budget. Memory-fit decisions are heuristic, not guarantees.
Memory overcommit enabled: True; memory stabilization skipped and startup RAM minimum 0.5 GiB when enabled; runtime emergency guards remain active.

| Model | Quantization | Status | Results |
| --- | --- | --- | --- |
| Gemma 4 26B-A4B | Q4_0 | resource_guard | 1/1 runs; 0 passed |

Detailed artifacts and exact file SHA-256 values: `C:\workspace\local-agent-engine\benchmarks\api_sync\runs\2026_11_13__11_13_01_226506__Gemma-4-26B-A4B-Q4_0__windows_queue`.

Safety-gate rejections and timeouts are not passing coding tasks.
