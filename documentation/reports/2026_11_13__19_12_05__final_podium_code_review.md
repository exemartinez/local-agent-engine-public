# Final benchmark podium — code and evidence review

## Verdict

The original podium is a ranking **under the recorded tests for one API-to-SQLite coding task**, not a ranking of production-ready implementations. GPT-OSS 20B MXFP4 passed the public and hidden suites in three runs, but a review of one passing candidate found that its real CLI cannot invoke its HTTP fetcher correctly. The public CLI test's permissive mock masks that defect. Consequently, the benchmark's previous “winner” label overstated the evidence: **none of the three reviewed implementations is established as production-ready or fully compliant with the specification.**

The task asks for a standard-library API-to-SQLite synchronizer with validated paginated data, duplicate handling, retries, atomic transactions, a CLI, and safe completion logging. The public suite has 27 tests with a 90% minimum line-coverage requirement; the hidden suite has 12 tests. All API calls and sleeps in tests are intended to be mocked. Public tests were included in prompts and their failures fed back during repair; hidden tests were withheld. Passing withheld tests is valuable but cannot compensate for missing integration coverage.

## Podium by recorded final test results

| Rank | Model / quantization | Public | Hidden | End-to-end benchmark time | Why it ranked here |
|---|---|---:|---:|---:|---|
| 1 | GPT-OSS 20B MXFP4 | 27/27, three runs | 12/12, three runs | 21m 07s; 13m 47s; 21m 35s | Only configuration passing both saved suites across three runs. However, a reviewed passing candidate has a broken CLI integration.[^cli-gap] |
| 2 | Qwen3.5 35B-A3B UD-IQ2_M | 27/27 after repairs | 8/12 | 8m 28s | Highest hidden score among non-passing configurations that passed the public suite. |
| 3 | Qwen3.5 35B-A3B UD-IQ3_S | 27/27 after a repair | 7/12 | 7m 58s | Next-highest hidden score among configurations passing the public suite. |

Times are recorded unattended-run elapsed times, including model-server startup, generation and tests, but excluding model download. Second and third place are **failures**, not time to a successful implementation. The first GPT-OSS run used seed 42 and temperature 0; the two repeats used seeds 43 and 44 and temperature 0.2. Each Qwen score is one run. This limited evidence is not a general model-quality ranking or a statistical reliability estimate.

## 1. GPT-OSS 20B MXFP4

### What the code did well against the tests

The inspected candidate fetches pages through an injected function, validates page and item structure, uses `datetime.fromisoformat` plus a timezone check for timestamps, detects repeated cursors, collects the last occurrence of each ID, and uses an explicit SQLite `BEGIN` / `commit` / `rollback` transaction. It validates positive integer retry counts and finite nonnegative delays and uses exponential backoff for `TransientError`. Those behaviors align with the specified contract and explain why the saved public and hidden suites scored it well.

### What the tests missed

The [inspected passing implementation](../../benchmarks/api_sync/runs/2026_11_06__17_54_42_869800__gpt-oss-20b-MXFP4__unattended/candidate_2.py.txt) has these material defects:

1. **The real CLI is broken.** `sync()` calls `fetch_page(cursor)`, but `main()` passes `fetch_http_page` directly; that function requires `(url, cursor)`. A local reproduction calling `main()` with an example URL and temporary SQLite path returned 1 with `fetch_http_page() missing 1 required positional argument: 'cursor'`, before any HTTP call. The public CLI test replaces the real fetcher with a `Mock` that accepts either call shape, masking the integration error.
2. **Successful-completion logging is absent.** `sync()` accepts `logger` but does not use it. The hidden test only checks that record values are not logged; doing no logging satisfies that assertion while missing the specification's positive requirement.
3. **Connection lifecycle is incomplete.** `main()` opens a SQLite connection without explicitly closing it. During the reproduction on Windows, temporary-directory cleanup failed while the database file remained locked in the process. The process then exited; that cleanup failure is not a model test pass.

This is concrete evidence that the solution can satisfy the tests without satisfying the intended integration. It is not evidence of deliberate cheating. Only the seed-43 passing candidate was reviewed in detail for this report; the other two passes have not been independently code-audited here.

### Evidence

- [Run 1, seed 42](../../benchmarks/api_sync/runs/2026_11_06__12_37_32_350368__gpt-oss-20b-MXFP4__unattended/), [passing candidate](../../benchmarks/api_sync/runs/2026_11_06__12_37_32_350368__gpt-oss-20b-MXFP4__unattended/candidate_3.py.txt).
- [Run 2, seed 43](../../benchmarks/api_sync/runs/2026_11_06__17_54_42_869800__gpt-oss-20b-MXFP4__unattended/), [reviewed candidate](../../benchmarks/api_sync/runs/2026_11_06__17_54_42_869800__gpt-oss-20b-MXFP4__unattended/candidate_2.py.txt), [public output](../../benchmarks/api_sync/runs/2026_11_06__17_54_42_869800__gpt-oss-20b-MXFP4__unattended/public_2.log), [hidden output](../../benchmarks/api_sync/runs/2026_11_06__17_54_42_869800__gpt-oss-20b-MXFP4__unattended/hidden_final.log).
- [Run 3, seed 44](../../benchmarks/api_sync/runs/2026_11_06__18_08_51_060905__gpt-oss-20b-MXFP4__unattended/), [passing candidate](../../benchmarks/api_sync/runs/2026_11_06__18_08_51_060905__gpt-oss-20b-MXFP4__unattended/candidate_3.py.txt).
- [CLI test](../../benchmarks/api_sync/public_tests/test_sync.py) and [hidden tests](../../benchmarks/api_sync/hidden_tests/test_acceptance.py).

## 2. Qwen3.5 35B-A3B UD-IQ2_M

### Why it placed second

The [final candidate](../../benchmarks/api_sync/runs/2026_11_09__01_45_45_862763__Qwen3.5-35B-A3B-UD-IQ2_M__unattended/candidate_2.py.txt) iterates through pages, validates required record fields, follows cursors and handles retryable exceptions. Its CLI correctly binds URL and cursor using a lambda, unlike the inspected GPT-OSS candidate. After three model calls, its final public result was 27/27 at 90.48% line coverage. It passed 8/12 hidden tests, the strongest hidden score after GPT-OSS in the recorded run.

### Why it did not pass

The [hidden-test log](../../benchmarks/api_sync/runs/2026_11_09__01_45_45_862763__Qwen3.5-35B-A3B-UD-IQ2_M__unattended/hidden_final.log) records four failures: three impossible calendar/time values were accepted, and infinite retry delay was not rejected before fetching. Its timestamp check recognizes a timezone-shaped string but does not validate actual calendar values; its NaN check does not reject infinity.

Code review also identified contract gaps not established by that score: the CLI passes a no-op sleep function, so it does not actually wait between retries; the returned count queries all records in the table rather than only unique records committed in this sync; `CREATE TABLE` is not explicitly enclosed in a transaction beginning before schema creation; and CLI argument defaults prevent the documented retry environment variables from taking effect when options are omitted. These are source-based observations; they have not been newly scored through an expanded test suite.

## 3. Qwen3.5 35B-A3B UD-IQ3_S

### Why it placed third

The [final candidate](../../benchmarks/api_sync/runs/2026_11_09__01_31_14_155713__Qwen3.5-35B-A3B-UD-IQ3_S__unattended/candidate_1.py.txt) performs paginated fetching, tracks repeated cursors, validates required item fields, deduplicates by ID, uses upsert statements, and binds URL and cursor in the CLI. It passed all 27 public tests after one repair, then passed 7/12 hidden tests.

### Why it did not pass

Its [hidden-test log](../../benchmarks/api_sync/runs/2026_11_09__01_31_14_155713__Qwen3.5-35B-A3B-UD-IQ3_S__unattended/hidden_final.log) records five failures: database-failure rollback, three invalid-calendar cases, and rejection of infinite retry delay before fetching. The candidate checks only a timezone suffix rather than parsing the actual date; it does not explicitly roll back on database failure; and its parameter validation detects NaN but not infinity.

## Benchmark limitations and follow-up

- Public tests were supplied to the model, so improvement against them is expected; we cannot infer intent to overfit from the output. The real CLI failure demonstrates a **coverage gap**, not intentional deception.
- The hidden suite was withheld, but it also lacked a test combining the real `fetch_http_page` function with `main` while mocking only the underlying HTTP transport. It checked the absence of leaked data but did not require a completion log.
- The host execution protocol used a static AST gate and Python socket guard; it was not an OS sandbox. Some gate rejections may reflect conservative rules rather than faulty or malicious code.
- The practical next step is to add real-component CLI integration tests with mocked `urllib.request.urlopen`, verify that success logging occurs without sensitive data, test connection cleanup and transaction rollback, then re-evaluate saved candidates. Record old and new scores separately. This report does not claim those new tests have been implemented or run.
- The [full previous comparison](2026_11_13__12_53_39_441992__all_model_results_with_gemma4.md) includes the other configurations and Gemma. Three configurations stopped on loading and two produced incomplete responses in the earlier queue; their missing scores are not coding-quality verdicts.

## Task and scripts

- [Specification](../../benchmarks/api_sync/spec.md), [plan](../../benchmarks/api_sync/plan.md), [tasks](../../benchmarks/api_sync/tasks.md).
- [Public tests](../../benchmarks/api_sync/public_tests/test_sync.py), [hidden acceptance tests](../../benchmarks/api_sync/hidden_tests/test_acceptance.py).
- [Unattended benchmark](../../benchmarks/api_sync/unattended_benchmark.py) and [queue controller](../../benchmarks/api_sync/windows_queue.py).

[^cli-gap]: In the seed-43 run, `main()` passes the two-argument HTTP fetcher to a caller that supplies only the cursor. The public CLI test uses a permissive mock, so both recorded suites passed despite the broken real integration. See the [run-specific post-review note](../../benchmarks/api_sync/runs/2026_11_06__17_54_42_869800__gpt-oss-20b-MXFP4__unattended/report.md).
