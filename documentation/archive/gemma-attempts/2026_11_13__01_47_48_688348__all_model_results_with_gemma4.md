# Local coding-model results — consolidated

## Standard API-to-SQLite coding benchmark

Elapsed time covers the unattended generation, repairs and tests, excluding download. Public and hidden scores refer to the final candidate. The public suite has 27 tests, the hidden suite 12; public passes also require 90% line coverage. A completed task is not proof of production readiness. Different protocols and quantizations are not interchangeable.

| Model | Quantization | Latest outcome | Public | Hidden | Time |
|---|---|---|---:|---:|---:|
| GPT-OSS 20B | MXFP4 | **Pass — three runs** | 27/27 each | 12/12 each | 21m 07s; 13m 47s; 21m 35s |
| GPT-OSS 20B | Q3_K_M | Load stopped: low RAM | — | — | 1m 36s |
| GPT-OSS 20B | Q4_K_M | Incomplete generation after four calls | — | — | 38m 47s |
| Qwen3-Coder 30B-A3B | Q2_K | Fail | 23/27 | 4/12 | 5m 26s |
| Qwen3-Coder 30B-A3B | Q3_K_S | Fail | 25/27 | 6/12 | 7m 06s |
| GLM-4.7-Flash 30B-A3B | Q3_K_S | Fail | 22/27 | 4/12 | 17m 04s |
| GLM-4.7-Flash 30B-A3B | Q2_K | Incomplete generation after four calls | — | — | 28m 23s |
| GLM-4.7-Flash 30B-A3B | Q4_K_M | Load stopped: low RAM | — | — | 1m 58s |
| Qwen3.5 35B-A3B | UD-IQ3_S | Fail | 27/27 | 7/12 | 7m 58s |
| Qwen3.5 35B-A3B | UD-IQ2_M | Fail | 27/27 | 8/12 | 8m 28s |
| Qwen3.5 35B-A3B | Q4_K_M | Load stopped: low RAM | — | — | 2m 07s |
| Gemma 4 26B-A4B | Q4_0 | resource_guard | — | — | 132.3 |

The original eleven configurations were attempted; the Gemma 4 row records a separate follow-up. Six have full public/hidden outcomes (one passing configuration, five failing configurations). Two produced incomplete code; three could not load before the resource stop. No configurations remain pending in the completed retry queue, though those five have no full test score. GPT-OSS MXFP4's first pass used seed 42 / temperature 0, and the two repeats used seeds 43 and 44 / temperature 0.2. All passes are on one task.

## Other previously tested models and protocols

These results use shorter tasks or an earlier supervised version of the API-to-SQLite protocol. They are not directly comparable with the unattended table above. Quantization is unspecified where not established by the saved record.

| Model | Earlier observed result | Pi or agent evidence |
|---|---|---|
| LFM2.5 8B-A1B | 4/6 Python smoke cases; median 199.30 tok/s. Earlier supervised API task: 2/27 public, 0/12 hidden. | Read worked, but multi-tool output was emitted as text; no reliable complete Pi loop demonstrated. |
| Qwen3.5 4B | 2/6 Python smoke cases; median 79.05 tok/s. Earlier supervised API task ended in collection error. | Completed two small disposable repairs and tests, including recovery. |
| Qwen2.5-Coder 7B | Median 71.03 tok/s in earlier direct benchmark. | Emitted raw JSON tool text; used a model-specific bridge. |
| Llama 3 Groq Tool Use 8B | 2/6 smoke cases; median 77.19 tok/s. | Tool-format probe only. |
| Qwen3.5 9B Q4_K_M | 4/6 smoke cases; about 59–61 tok/s for code calls. | No Pi task recorded. |
| Qwen3 8B | 2/6 smoke cases; about 66–74 tok/s for mean. | No Pi task recorded. |
| Qwen3-Coder 30B, Ollama | 6/6 small Python cases; separate supervised API task: 24/27 public and 5/12 hidden. | No observable tool action in a bounded ~175 s Pi repair. |
| DeepSeek-Coder-V2 Lite | Load stopped during severe paging before output; no coding score. | No completed Pi task recorded. |

## Interpretation and evidence

- The strongest result on the standard batch task is GPT-OSS 20B MXFP4, with three passing runs of that single task. No other configuration passed the full public and hidden suite in that protocol.
- Scores from the small smoke tests and supervised chat-v3 are useful historical context, not fair head-to-head scores against the unattended runs. The Qwen3-Coder 30B Ollama result and the Q2/Q3 GGUF rows are separate runs and must not be conflated.
- Resource-stop results do not prove the model cannot code; incomplete responses do not provide a complete public/hidden score. No inference is currently queued by the completed controller.
- Windows-host tests used a static code gate and Python socket guard, not an OS sandbox.
- Latest retry data: `benchmarks/api_sync/runs/2026_11_12__19_34_52_860664__seven_retry/controller.json` and `documentation/archive/retry-snapshots/2026_11_12__19_34_52_860664__seven_model_retry_report.md`.
- Earlier results and sources: `documentation/archive/benchmark-history/2026_11_10__13_39_32__complete_local_model_benchmark_comparison.md`; GPT-OSS first-pass audit: `documentation/archive/benchmark-history/2026_11_06__17_49_48__gpt_oss_passing_run_audit.md`; raw runs in `benchmarks/api_sync/runs/`.

## Gemma 4 follow-up

Status: **resource_guard**. Exact queue artifacts: `C:\workspace\local-agent-engine\benchmarks\api_sync\runs\2026_11_13__01_47_48_908345__Gemma-4-26B-A4B-Q4_0__windows_queue\queue.json`. Download: official ggml-org GGUF; local inference; no cloud API.

Details: ConnectionResetError: [WinError 10054] An existing connection was forcibly closed by the remote host
