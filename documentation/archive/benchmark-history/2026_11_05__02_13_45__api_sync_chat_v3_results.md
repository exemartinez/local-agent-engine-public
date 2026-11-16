# API synchronization benchmark: chat-v3 results

The three installed models received the same specification, plan, tasks, skeleton, and public tests. Each got an initial call and up to three public-test feedback repairs; this revision also includes the public test source in each repair prompt. Only the final candidate was evaluated on the hidden suite. All inference was local through Ollama. Before each execution the candidate was manually reviewed; the test process blocked ordinary Python socket connections. A Python virtual environment and that guard are not an OS sandbox.

| Model | Total elapsed | Initial public | Final public | Final coverage | Final hidden | Calls / reviews | Result |
| --- | ---: | --- | --- | ---: | --- | --- | --- |
| Qwen3.5 4B | 174.55 s | 16/27 | Collection error | unavailable | Collection error | 4 / 4 | Fail |
| LFM2.5 8B | 221.98 s | Collection error | 2/27 | 42% | 0/12 | 4 / 4 | Fail |
| Qwen3-Coder 30B | 1,125.31 s | 24/27 | 24/27 | 80% | 5/12 | 4 / 4 | Fail |

Call durations in seconds: Qwen3.5 39.38, 14.17, 24.42, 5.66; LFM2.5 35.22, 32.05, 41.61, 41.34; Qwen3-Coder 205.50, 317.49, 308.80, 175.53. Total time includes test execution and manual safety-review waiting. Qwen3.5's final response ended at the configured generation length and contained incomplete Python. Qwen3-Coder's first repair added a comment but retained the failing logic, and its next two repairs repeated that file. Its GPU temperature was observed at 62–63°C; Windows reported physical memory as low as roughly 12–15 MB during one observation, with pagefile space remaining. Those are observations during this run, not a complete resource profile.

No candidate reached a passing project, so **time to a passing project is unknown**. Qwen3-Coder 30B is the provisional candidate for further *batch* coding evaluation because it produced the strongest result in this particular revision, but it is not a reliable unattended solution: it failed both test gates after almost 19 minutes, repeated ineffective repairs, and left very little RAM headroom. Qwen3.5 4B remains useful to retain: in the earlier chat-v2 run it passed 21/27 public and 7/12 hidden tests in 155.38 seconds, though it did not pass the task either. These single attempts do not prove a general ranking and earlier protocol results are not directly comparable to chat-v3.

The reference implementation passed 39/39 tests and 98.17% line coverage under the network guard. Passing tests and coverage do not prove production readiness. Raw prompts, responses, generated candidates, public and hidden logs, and timings are in:

- `benchmarks/api_sync/runs/2026_11_05__01_48_04_098343__timed__qwen3.5_4b`
- `benchmarks/api_sync/runs/2026_11_05__01_51_04_469352__timed__lfm2.5_8b`
- `benchmarks/api_sync/runs/2026_11_05__01_54_56_490741__timed__qwen3-coder_30b`

The procedure and protocol settings are in `benchmarks/api_sync/README.md`; the exploratory diagnosis is `2026_11_05__01_47_19__qwen30_repair_diagnostics.md`. No model was uninstalled based on this one task.

## Later overnight-controller trial

The 2026-11-05 local controller made one Qwen3-Coder 30B generation call in 192.969 seconds, with first output at 86.422 seconds. This is a single call, not a complete generate-and-repair loop, and is not directly comparable to the 1,125.31-second four-call result above. The resulting code matched the previously reviewed first candidate byte for byte; a later manual review and network-guarded test run recorded 24/27 public tests passing (80.41% line coverage) and 5/12 hidden tests passing. The result, response stream, resource samples, candidate and test logs are retained under `benchmarks/api_sync/runs/2026_11_05__20_30_53_771136__qwen3-coder-30b__overnight_moe`.

After preserving these results, the user requested removal to reclaim space. `ollama rm qwen3-coder:30b` succeeded on 2026-11-05; Qwen3.5 4B and LFM2.5 8B remained installed.
