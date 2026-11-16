# API-to-SQLite benchmark: provisional comparison

> **Update:** The hidden suite was expanded after the first evaluation. Qwen30's final candidate passes 4 of 12 hidden tests: it fails three invalid-calendar checks, four additional 5xx classification checks, and an infinite-delay validation check. Qwen3.5 passes 5 of 12, after invalid-date tests were tightened to verify that a page was actually fetched; its public suite still fails 7 tests. LFM's final candidate does not parse and was not run against hidden tests. The reference passes all 39 public plus expanded hidden tests at 98.17% coverage. No hidden failures were fed back to any candidate. The 4/4 figure below is the earlier, smaller hidden suite only. None of the candidates has passed the expanded benchmark.

## Results

| Model | First public result | Final public | Final hidden | Generation calls | Sum of generation times |
|---|---|---|---|---:|---:|
| Qwen3-Coder 30B | 24/27 pass | 27/27, 94% line coverage | 4/4 pass | 2 | 496.734 s |
| Qwen3.5 4B | 0/27; extracted module empty | 20/27, 49% line coverage | 0/4 | 4 | 192.640 s |
| LFM2.5 8B | Syntax error | Syntax error after three repairs | Not run: module cannot be imported | 4 | 111.735 s |

The leading candidate for this one batch task is **Qwen3-Coder 30B**, but it has not passed the expanded withheld suite. LFM and Qwen3.5 reached the 4,096-token limit on several calls. The summed request durations are not end-to-end time to a passing project: they exclude test execution, manual review, scheduling gaps, and benchmark preparation.

## Limitations

- The public suite was corrected after initial generation to remove an unfair assumption about the urllib import style. All first-generation prompts contained the same earlier version; later tests used the corrected version. Results are not a fully pre-registered trial.
- Feedback summaries and code review were performed manually. The runner does not implement an automatic complete test-feedback loop or record intervention duration. The per-run `result.json` files say `generated_unvalidated` because subsequent manual evaluations did not update them; consult this report alongside the saved outputs.
- Candidate code was inspected and tested in the user's virtual environment at their request. A virtual environment is not a security sandbox. All HTTP interactions in the tests were mocked; no real service or credentials were used.
- Only four hidden tests exist. Passing them and achieving high line coverage do not establish full specification compliance or production readiness. For example, Qwen30's repair validates timestamp shape with a regular expression rather than validating calendar dates. Its transaction and HTTP behavior require broader adversarial coverage.
- This is one sample per model, not a statistical comparison. Other output limits, prompts, task decomposition, or a different harness may change the results.

## Evidence

The spec, plan, tasks, public and hidden tests, skeleton, generation and repair scripts, and model artifacts are under `benchmarks/api_sync/`. The reference application is `src/sync_app.py`; its combined reference suite passed 31 tests with 98.17% coverage. The Qwen30 final candidate is `benchmarks/api_sync/runs/2026_11_04__19_50_11_530325__qwen3-coder_30b/repair_1.py`. The corrected public tests passed 27/27 and hidden tests passed 4/4 when run on its reviewed copy.

## Remaining work

Implement and validate a reproducible end-to-end runner that preserves test logs, review/intervention counts, wall-clock elapsed time, and identical feedback and stopping rules. Strengthen hidden tests against calendar-invalid timestamps, transport errors, atomic table creation/rollback, configuration edges, and credential leakage, then rerun all candidates fairly. Do not expose those tests to models during repairs. Keep the existing models: prior experiments demonstrated separate direct or Pi value, and these preliminary trials do not justify removing them.
