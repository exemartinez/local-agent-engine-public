# API-to-SQLite benchmark: preliminary progress

Status: **incomplete**. The objective is time to a tested, passing project; no candidate has been tested or repaired yet, and no winner can be selected.

The reference implementation in `src/sync_app.py` passed 31 public and hidden tests, with 98.17% line coverage on the combined test run. Tests mock HTTP and use temporary or in-memory SQLite databases. High coverage does not establish production readiness.

The same public spec, design, tasks, skeleton, and public tests were sent through localhost Ollama to each model. Initial output and request timing were saved in `benchmarks/api_sync/runs/`. No reference implementation or hidden tests were sent.

| Model | Initial generation | Output termination | Static Python syntax | Test result |
|---|---:|---|---|---|
| LFM2.5 8B | 32.016 s | stop, 3,625 tokens | Invalid at line 154 | Not run |
| Qwen3.5 4B | 66.703 s | length, 4,096 tokens | Valid | Not run |
| Qwen3-Coder 30B | 289.328 s | stop, 1,381 tokens | Valid | Not run |

These timings are single first generations, not total time to completion. Syntax was checked with `ast.parse` without executing candidate code. LFM's reported syntax error is a missing closing parenthesis in its generated conditional; this is not a measure of behavioral correctness. Qwen3.5 reached the output cap; syntactic validity does not prove completeness.

## Remaining work

The runner currently generates one candidate and explicitly refuses to execute it. It does not implement the required test-feedback and three-repair loop, hidden final validation, coverage scoring, or total time to validation. Those remain required for all three models.

Running model-generated code with ordinary host permissions would allow access outside the disposable folder. Docker and an installed WSL distribution were not found. Windows Sandbox optional-feature status requires an elevated query and no system setting has been changed. A verified executor with filesystem and network isolation is needed before running public or hidden tests against candidate code; its setup and any system changes require the appropriate user authorization. Once available, run all candidates under identical conditions and report first-pass and final test outcomes, coverage, calls, retries, elapsed time, and any interventions.
