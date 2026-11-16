# Local coding-model benchmarks: consolidated comparison

## Decision and scope

The scheduled MoE quantization queue has processed all 11 configurations, but **not every configuration completed a coding benchmark**. Two were skipped on a memory estimate; five stopped under the resource guard; four produced a coding-task outcome. Skips and interrupted loads are not coding-quality failures. Results below preserve the latest queue's status and earlier separately labelled experiments.

**Best demonstrated batch candidate:** GPT-OSS 20B MXFP4 passed the API-to-SQLite task three times, including its hidden suite. The independent repeats use different seeds and temperature than the first run. This is one benchmark problem, not proof of production readiness or general reliability. **Best demonstrated Pi agent:** Qwen3.5 4B on small repair fixtures; this is a different benchmark and does not establish large-task reliability. No Ollama models were installed at the last check. Local inference only; no paid API calls were used in these experiments.

## Standard batch benchmark

The API-to-SQLite task provides a specification, plan, task list, Python skeleton and 27 public tests. The final candidate faces 12 withheld checks. The runner asks for a full Python implementation, supplies public-test feedback for bounded repairs, and requires at least 90% line coverage. Hidden results are not supplied during repairs. The reference implementation passed 39 tests with 98.17% line coverage. The Windows host uses a static code gate and Python socket guard; **it is not an OS security sandbox**. Passing tests or a coverage threshold does not prove production readiness.

For the table, elapsed time is the unattended run's wall time, including the model-server startup, generation and checks; it excludes model download. Values are not time to a successful project when the result failed. Per-model file sizes, hashes, sampling configuration, individual public checks, measurements, output and cleanup records are in the queue JSON and linked run directories. One row per configuration does not imply multiple independent samples.

| Model | Quantization | Latest outcome | Final public | Hidden | Calls | Elapsed | Interpretation |
|---|---|---|---|---|---:|---:|---|
| GPT-OSS 20B | MXFP4 | **Pass, 3 runs** | 27/27 each | 12/12 each | 4; 3; 4 | 21m 07s; 13m 47s; 21m 35s | First run seed 42/temp 0; repeats seeds 43–44/temp 0.2. First result exists outside latest queue. |
| GPT-OSS 20B | Q3_K_M | Resource guard | Not run | Not run | 0 | 1m 55s | Load stopped; quality unknown. |
| GPT-OSS 20B | Q4_K_M | Skipped | Not run | Not run | — | — | Estimated memory insufficient; not a model-quality test. |
| Qwen3-Coder 30B-A3B | Q2_K | Fail | 23/27 | 4/12 | 4 | 5m 26s | Four generated candidates did not pass; hidden failures remained. |
| Qwen3-Coder 30B-A3B | Q3_K_S | Resource guard | Not run | Not run | 0 | 1m 45s | Load stopped; quality unknown. |
| GLM-4.7-Flash 30B-A3B | Q3_K_S | Skipped | Not run | Not run | — | — | Downloaded, then memory estimate failed before load. |
| GLM-4.7-Flash 30B-A3B | Q2_K | Resource guard | Not run | Not run | 0 | 1m 31s | Load stopped; quality unknown. |
| GLM-4.7-Flash 30B-A3B | Q4_K_M | Resource guard | Not run | Not run | 0 | 3m 07s | Attempted with memory-fit estimate bypassed. |
| Qwen3.5 35B-A3B | UD-IQ3_S | Fail | 27/27 | 7/12 | 2 | 7m 58s | First candidate 25/27; repair passed public, failed hidden. |
| Qwen3.5 35B-A3B | UD-IQ2_M | Fail | 27/27 | 8/12 | 3 | 8m 28s | First candidate 24/27; repairs passed public, failed hidden. |
| Qwen3.5 35B-A3B | Q4_K_M | Resource guard | Not run | Not run | 0 | 2m 16s | Attempted with memory-fit estimate bypassed; available RAM fell below 100 MiB and paging was severe. |

The 11-row count above is **two skips, five resource-guard stops, three failed coding outcomes, and one configuration with passing outcomes**. Some configurations had previous attempts with different settings; the latest queue links its inherited run data. Download, load and checks differed between runs and a single sample per failing model cannot establish statistical reliability.

### GPT-OSS 20B MXFP4 passing runs

| Run | Seed / temperature | Calls | Elapsed | Public | Hidden | Evidence |
|---|---|---:|---:|---|---|---|
| 2026-11-06 12:37 | 42 / 0 | 4 | 1,267.422 s | 27/27 | 12/12 | `benchmarks/api_sync/runs/2026_11_06__12_37_32_350368__gpt-oss-20b-MXFP4__unattended/` |
| 2026-11-06 17:54 | 43 / 0.2 | 3 | 826.735 s | 27/27 | 12/12 | `benchmarks/api_sync/runs/2026_11_06__17_54_42_869800__gpt-oss-20b-MXFP4__unattended/` |
| 2026-11-06 18:08 | 44 / 0.2 | 4 | 1,294.968 s | 27/27 | 12/12 | `benchmarks/api_sync/runs/2026_11_06__18_08_51_060905__gpt-oss-20b-MXFP4__unattended/` |

The first run had static-gate rejections before its passing candidate; those are protocol outcomes and are not proof of malicious code. The 90% coverage threshold was used. See `2026_11_06__17_49_48__gpt_oss_passing_run_audit.md` for the first-run audit.

## Earlier API-to-SQLite comparison: separate protocol

These supervised Ollama chat-v3 trials used the same general task but a different execution/feedback workflow and manual safety reviews. Do not rank their wall times directly against the unattended queue.

| Model | Total elapsed | Final public | Final hidden | Calls | Outcome |
|---|---:|---|---|---:|---|
| Qwen3.5 4B | 174.55 s | Collection error | Collection error | 4 | Fail; final response incomplete. |
| LFM2.5 8B | 221.98 s | 2/27 | 0/12 | 4 | Fail. |
| Qwen3-Coder 30B | 1,125.31 s | 24/27 | 5/12 | 4 | Fail; repeated ineffective repairs. |

An earlier exploratory Qwen3-Coder 30B run reached 27/27 public but 4/12 expanded hidden tests. Its earlier 4/4 score used a smaller superseded hidden suite and is not directly comparable. See `2026_11_05__02_13_45__api_sync_chat_v3_results.md` and `2026_11_05__00_46_14__api_sync_comparison.md` for protocol and raw paths.

## Earlier small tasks and Pi-agent evidence

These were shorter Ollama probes, not the API-to-SQLite task. Metrics and scores cannot be compared directly with the batch table. Quantization is listed only where the original saved report identifies it; Ollama tags alone do not prove the exact quantization.

| Model | Direct-generation evidence | Pi or tool-use evidence |
|---|---|---|
| LFM2.5 8B-A1B | Median 199.30 tok/s on earlier direct benchmark; 4/6 Python smoke cases. Warm clamp completion 1.178 s. | First read worked, then multi-tool requests were emitted as text; not shown reliable for a multi-step Pi loop. |
| Qwen3.5 4B | Median 79.05 tok/s; 2/6 small Python smoke cases. Warm clamp completion 0.342 s. | Completed two separate disposable edit/test exercises, including recovery; one recovery took about 19 s. |
| Qwen2.5-Coder 7B | Median 71.03 tok/s on earlier direct benchmark. | Raw JSON tool calls appeared as text; a model-specific bridge was used. |
| Llama 3 Groq Tool Use 8B | Median 77.19 tok/s; 2/6 smoke cases. | Tool-format probe only. |
| Qwen3.5 9B Q4_K_M | 4/6 smoke cases; about 59–61 tok/s on code calls. | No Pi test recorded. |
| Qwen3 8B | 2/6 smoke cases; about 66–74 tok/s on mean. | No Pi test recorded. |
| Qwen3-Coder 30B, Ollama | 6/6 small Python smoke cases; cold clamp 49.181 s, warm 2.079 s; 67% CPU / 33% GPU on reported probe. Severe paging. | Bounded Pi repair made no observable tool action in about 175 s. |
| DeepSeek-Coder-V2 Lite | Load probe stopped under severe paging before output; coding quality and completion latency unknown. | No completed Pi test recorded. |

Sources: `2026_11_04__14_56_53__local_fallback_coding_system.md`, `2026_11_04__15_09_27__fallback_latency_and_pi_recovery_results.md`, `2026_11_04__15_35_10__qwen30_batch_and_qwen35_pi_comparison.md` and the associated CSV/JSON files under `benchmarks/results/`. The LFM speed figure and smoke result do not establish best performance on the larger task.

## Current limitations and next steps

1. Two planned MoE configurations lack coding results; five hit resource stops. Further runs need adequate headroom and a justified stop policy. The user-authorized overcommit attempts did not establish that every model could load safely.
2. The Qwen3.5 IQ3 and IQ2 coding runs completed and failed hidden checks; their shorter times are durations of unsuccessful runs, not time to working production code.
3. GPT-OSS passed three runs on a single task. Test a second independent Python task before making broad reliability claims. Reinstall only if the user wants to keep the model and confirms adequate disk headroom.
4. At the 2026-11-10 status check C: had 8.39 GB free, with no files found in the queue's model-download directory. The cause of the reduced free disk was not established. Avoid further large downloads until free space is investigated. Pagefile was observed at its configured 24 GiB allocation; that observation does not establish the cause of the disk-space change.
5. A later queue modification removed the stabilization wait for overcommit runs but was not applied to the already-running queue; it was unit tested, not demonstrated by these completed runs. Runtime emergency guards remained active in the reported runs.

## Primary evidence

- Latest complete queue record: `benchmarks/api_sync/runs/2026_11_09__01_26_42_255477__multi-model__windows_queue/queue.json`.
- Latest generated queue report: `documentation/archive/queue-snapshots/2026_11_09__01_26_42__moe_quantization_queue.md`.
- Test specification, runner, inputs and per-run artifacts: `benchmarks/api_sync/`.
- Reference audit: `documentation/archive/benchmark-history/2026_11_05__02_15_15__benchmark_audit.md`.
- Historical raw latency, quality and resource observations: `benchmarks/results/`, `benchmarks/logs/`, and the timestamped documents above.
- Historical README status may be stale; this report supersedes it for the results and limitations stated here.
