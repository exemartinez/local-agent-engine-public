# API sync benchmark: chat-v2 comparison

All inference used local Ollama. Each model received the same specification, plan, tasks, skeleton and public tests, then up to three public-test feedback repairs. The final candidate alone was checked against the hidden suite. Tests were run in the project virtual environment after manual review, with ordinary socket connections disabled by the pytest network guard. This is not an OS sandbox. The reference passed all 39 tests with 98.17% coverage under the guard.

The revised protocol uses `/api/chat`, `think: false`, temperature 0, seed 42, context 8192, and output budget 8192. Per-call timeout was 900 seconds; public-test timeout was 60 seconds. Measured elapsed time includes four human safety reviews and test execution. Each entry is one run, not a statistical estimate. The 30B run started cold after unloading the preceding model; the smaller models' load states varied.

| Model | Elapsed | Call times (seconds) | First public | Final public | Final coverage | Final hidden | Outcome |
| --- | ---: | --- | --- | --- | ---: | --- | --- |
| Qwen3.5 4B | 155.38 s | 32.28, 7.34, 17.91, 18.78 | 16/27 | 21/27 | 86% | 7/12 | Fail |
| LFM2.5 8B | 199.23 s | 35.02, 43.30, 17.25, 31.06 | Collection error | Collection error | unavailable | Collection error | Fail |
| Qwen3-Coder 30B | 880.89 s | 202.89, 236.05, 181.56, 164.78 | 24/27 | 24/27 | 80% | 5/12 | Fail |

All had four model calls, three repair opportunities, and four manual reviews. Qwen3.5's first repair ended at the generation length limit; LFM's first repair hit 8192 tokens and its final candidate failed to collect. The 30B output was byte-identical in every attempt, including after feedback. Its cause remains unknown: the endpoint change did not fix it. Earlier `/api/generate` runs are a separate protocol and are recorded in `2026_11_05__01_15_44__api_sync_timed_results.md`.

None completed this project, so time to a passing project is unknown and no result demonstrates autonomous production readiness. For now, **Qwen3.5 4B is the provisional practical choice** for supervised local batch work: it produced a comparable number of passing checks with more hidden checks passing, in about one sixth of the elapsed time, and used much less memory. Qwen3-Coder 30B passed more public tests, but its repeated repairs and roughly 15-minute unsuccessful run provide no evidence it is the better fallback here. This is one task and one configuration; additional tasks and a diagnosis of repeated 30B output are needed before a general model ranking. LFM remains installed because prior small-task measurements may have value and this trial alone does not settle every use case.

The per-run raw prompts, responses, code, logs and timing JSON are retained in `benchmarks/api_sync/runs/2026_11_05__01_19_04_527992__timed__qwen3.5_4b`, `2026_11_05__01_21_45_273240__timed__lfm2.5_8b`, and `2026_11_05__01_25_15_514806__timed__qwen3-coder_30b`. A preliminary 4B launch ended at the review gate because stdin closed, and another was stopped before execution when an unmocked HTTP alias was spotted; neither is included in the comparison. `benchmarks/api_sync/README.md` provides the procedure.
