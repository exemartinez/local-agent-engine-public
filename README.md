# Local Agent Engine

An evidence-first investigation of local, no-paid-API coding models on a Windows gaming laptop. The project measures generated-code correctness, elapsed time, resource pressure and agent behavior; it retains prompts, responses, candidate code and test output so the findings can be reviewed.

## Current findings

- On the API-to-SQLite coding task, **GPT-OSS 20B MXFP4** passed 27 public and 12 hidden tests in three recorded runs, each taking about 14–22 minutes excluding download. This is the strongest recorded score on that task, not a production-readiness verdict.
- A later review found that one passing GPT-OSS candidate has a **broken CLI-to-fetch integration**. A permissive mock masked the defect. The test suite and original podium therefore overstate what was demonstrated. See the [final podium and code review](documentation/reports/2026_11_13__19_12_05__final_podium_code_review.md).
- Qwen3.5 35B IQ2 and IQ3 passed the public suite but failed hidden checks. Several larger configurations stopped under severe RAM pressure or produced incomplete code. Gemma 4 26B Q4 generated candidates but did not pass the complete protocol.
- Smaller-model direct and Pi probes are documented separately; their smoke scores are **not comparable** to the larger batch task. One Qwen3.5 4B Pi setup completed small edit/test fixtures; that does not establish reliable autonomous coding.
- The recorded host is an Alienware laptop with an RTX 3070 Laptop GPU (8 GiB VRAM) and approximately 16 GiB RAM. Memory and disk availability change over time. Model files were removed after testing to recover disk; no local models were listed at the last audit.

## Research question and method

The investigation started with a practical question: **can mixture-of-experts coding models run usefully on an existing laptop when cloud inference is unavailable?** We tested locally on an Alienware m15 R4 with 16 GiB installed RAM and an NVIDIA RTX 3070 Laptop GPU with 8 GiB VRAM. Parameter count, active parameters and quantization do not by themselves determine whether a model fits or produces useful work.

The main task asked each model to implement a Python API-to-SQLite synchronizer from a specification, plan and task list. The runner supplied public tests and bounded repair feedback, then evaluated the last candidate against a separate set of checks. The project retains generated code, prompts, test output, timing, hashes and system telemetry. Smaller direct-generation and Pi-agent experiments used different protocols and are reported separately.

| Configuration | Recorded outcome on the main task | Elapsed, excluding download |
| --- | --- | --- |
| GPT-OSS 20B MXFP4 | 27/27 public and 12/12 hidden in three runs; later code review found a CLI integration defect in one passing candidate | 13m 47s–21m 35s |
| Qwen3.5 35B IQ2 | 27/27 public; 8/12 hidden | 8m 28s |
| Qwen3.5 35B IQ3 | 27/27 public; 7/12 hidden | 7m 58s |
| Gemma 4 26B Q4 | Final candidate rejected by the static gate; no complete score | about 16m 30s |

**Interpretation:** These are results from one coding problem, not production-readiness certifications. Public tests were available to models during repairs. The withheld checks missed a real integration defect: the CLI test replaced the fetcher with a permissive mock. Other configurations ran into memory stops or returned incomplete code; missing scores are not proof of poor model quality. See the [full comparison](documentation/reports/2026_11_13__12_53_39_441992__all_model_results_with_gemma4.md), [run index](documentation/reports/2026_11_13__13_58_54__benchmark_run_folder_index.md), and [code review](documentation/reports/2026_11_13__19_12_05__final_podium_code_review.md).

## Repository map

| Path | Purpose |
| --- | --- |
| [`benchmarks/api_sync/`](benchmarks/api_sync/) | Shared specification, plan, tasks, public and hidden tests, Python benchmark runners and per-attempt artifacts under `runs/`. |
| [`benchmarks/results/`](benchmarks/results/) | Cross-benchmark measurements, summaries, inventories and local traceability backups; raw task-specific artifacts remain beside their runs. |
| [`benchmarks/logs/`](benchmarks/logs/) | Local controller, diagnostic and telemetry logs; logs inside an individual run remain in that run folder. |
| [`benchmarks/benchmark.py`](benchmarks/benchmark.py) | Earlier direct local-inference latency/throughput driver. |
| [`documentation/`](documentation/) | Current reports and guides, plus archived queue snapshots and historical investigations. Start with its README; later audits can supersede older conclusions. |
| [`config/`](config/) | Historical restrictive OpenCode example and explanation of the actual model manifest; no model credentials. |
| [`scripts/`](scripts/) | Windows preflight, local Ollama, telemetry, inventory and traceability helpers. Read each script before running it; some are historical or change system configuration. |
| [`src/sync_app.py`](src/sync_app.py) | One hand-written **reference implementation** of the shared API-sync task, not an application containing all generated models. Model candidates are saved under `benchmarks/api_sync/runs/`. |
| [`test-repos/`](test-repos/) | Small disposable agent repair fixtures, distinct from the shared batch benchmark. See its README. |

The historical header-only root CSV placeholders are not actual results. `.coverage` is an ignored local SQLite database created by coverage.py: it records files and line/branch execution data, not source-code quality or a guarantee that all use cases were tested.

## Reproducing the benchmark

Read [`benchmarks/api_sync/README.md`](benchmarks/api_sync/README.md), the [specification](benchmarks/api_sync/spec.md), and the [final code-review audit](documentation/reports/2026_11_13__19_12_05__final_podium_code_review.md) before comparing results. The benchmark uses public tests for feedback and a withheld suite for final scoring. `candidate_*.py.txt`, `prompt_*.txt`, `response_*.json`, test logs, `result.json` and telemetry are retained in each run directory. Folder names identify the model where the model is known; multi-model queues are labeled accordingly.

The Windows host evaluator uses a static AST gate and a Python socket guard. **It is not an operating-system sandbox.** Generated code was executed under that limited gate for recorded runs. Isolated execution is preferable for untrusted generated code; a separate Docker evaluator exists but was not demonstrated in the original Windows runs. Certain experimental runs explicitly disabled resource stops at the user's request; do not assume all historical scripts have safe default limits. No cloud inference was intended in the recorded local benchmarks.

To run the existing lightweight controller tests in the project's Python environment:

```powershell
.\.venv\Scripts\python.exe -m pytest benchmarks/api_sync/test_windows_queue.py benchmarks/api_sync/test_seven_model_retry.py -q
```

A virtual environment, models and runtimes are not included. Model download sizes, licenses, GPU support, available RAM and disk headroom must be checked before new runs.

## Roadmap

1. Strengthen the benchmark: exercise the real CLI-to-fetch integration while mocking only network transport; require safe completion logging and test cleanup and rollback. Re-evaluate saved candidates under the revised suite without overwriting historical scores.
2. Evaluate the leading candidates on additional independent tasks and report time to a genuinely passing solution, including repairs and resource limits.
3. Make model selection and execution settings explicit and reproducible; document which agent configurations actually work before presenting them as supported.
4. Prepare the repository and supporting materials for publication.
5. Improve reproducible, OS-isolated execution and document its platform requirements; keep benchmark results and safety-gate rejections distinct.

## License

Copyright © 2026 Ezequiel Martinez.

Original project material is licensed under the **GNU Lesser General Public License, version 3.0 only** (LGPL-3.0-only). See [LICENSE](LICENSE) and the accompanying [GNU GPL 3.0 text](COPYING.GPL-3.0). Third-party models, software and other materials remain subject to their respective rights and licenses.
