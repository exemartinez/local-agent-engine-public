# Engineering assessment — benchmark in progress

## Scope and method

This report covers only local Ollama inference. It uses no paid API or cloud
inference. `benchmarks/benchmark.py` enumerates locally installed models,
warms each one, then runs three repetitions of six deterministic streaming
cases: approximate 512, 2,048, and 4,096-token prompts with 128- and
512-token output caps. Ollama reports the actual token counts. The script
persists each row immediately and records errors rather than discarding a
partial run.

Raw data: `benchmarks/results/all_installed_ollama_benchmark_20261103_complete.csv`.
The current run began with 6.48 GiB available RAM, 58.96 GiB free disk, and
no model loaded.

## Completed pass: Qwen2.5-Coder 7B

Qwen2.5-Coder 7B completed all 18 measured cases at an 8,192-token context
with no transport, timeout, or context-limit errors. Ollama reported 100% GPU
placement with an 8,192-token context and approximately 5.15 GB resident VRAM
in each recorded 512-token-input case.

| Measurement | Result |
|---|---:|
| Model download size | 4.68 GB |
| Measured cases | 18 / 18 successful |
| Generated throughput, median | 71.03 tokens/sec |
| Generated throughput, range | 69.12–75.86 tokens/sec |
| TTFT, median | 9.26 sec |
| TTFT, range | 2.96–24.73 sec |
| End-to-end time, median | 14.73 sec |
| End-to-end time, range | 4.78–32.11 sec |

Throughput is respectable for direct local generation. This does **not** make
it a reliable Pi agent: the separate Pi probe showed that it emits bare JSON
tool requests rather than native structured calls and then makes poor
tool-selection/recovery decisions. A Qwen-only Pi bridge can convert valid
standalone raw calls, but it cannot improve the model's reasoning.

## Completed pass: Qwen3.5 4B

Qwen3.5 4B completed all 18 measured cases at the same 8,192-token context
with no transport, timeout, or context-limit errors. Ollama reported 100% GPU
placement at that context; the raw rows record approximately 3.36 GB resident
VRAM for the model.

| Measurement | Result |
|---|---:|
| Model download size | 3.32 GB |
| Measured cases | 18 / 18 successful |
| Generated throughput, median | 79.05 tokens/sec |
| Generated throughput, range | 77.72–88.17 tokens/sec |
| TTFT, median | 3.24 sec |
| TTFT, range | 0.24–8.21 sec |
| End-to-end time, median | 6.73 sec |

Against the measured Qwen2.5-Coder 7B baseline, Qwen3.5 4B delivered 11.3%
higher median generation throughput, 65.0% lower median TTFT, and 54.3% lower
median end-to-end latency in this benchmark. It also produced native structured
Ollama tool calls in the separate Pi probe and completed the disposable coding
fixture. Its limitation is agent efficiency: after a correct edit it made poor
verification attempts and exhausted Pi's configured 4K agent context.

## Completed pass: LFM2.5 8B-A1B

`lfm2.5:8b` completed all 18 cases at the same 8,192-token context with zero
errors. It passed the direct native tool-call probe before benchmarking: Ollama
returned an OpenAI-compatible `tool_calls` object, rather than plain text.
Ollama reported 100% GPU placement and approximately 5.32 GB resident VRAM.

| Measurement | Result |
|---|---:|
| Model download size | 5.16 GB |
| Measured cases | 18 / 18 successful |
| Generated throughput, median | 199.30 tokens/sec |
| Generated throughput, range | 194.46–201.70 tokens/sec |
| TTFT, median | 0.32 sec |
| TTFT, range | 0.11–4.85 sec |
| End-to-end time, median | 2.65 sec |
| End-to-end time, range | 0.75–5.49 sec |

This is 2.80× the median generation throughput of Qwen2.5-Coder 7B and 2.52×
that of Qwen3.5 4B. It also has the strongest measured latency profile so far.
It passed direct structured-tool formatting, but failed a live Pi agent task:
after a successful first `read` call, it emitted a raw multi-tool JSON object
as assistant text rather than issuing the second native tool call. Pi did not
execute that object; the intentionally failing `clamp` fixture remained
unchanged and its three-test suite still had two failures. Therefore its raw
tool format and direct coding quality do not establish dependable Pi-agent
behavior.

## Completed pass: Llama 3 Groq Tool Use 8B

`llama3-groq-tool-use:8b` completed all 18 cases at an 8,192-token context
with zero errors. It passed the native tool-call probe: Ollama returned a
structured `tool_calls` object. Ollama reported 100% GPU placement and the raw
rows record approximately 5.56 GB resident VRAM.

| Measurement | Result |
|---|---:|
| Model download size | 4.66 GB |
| Measured cases | 18 / 18 successful |
| Generated throughput, median | 77.19 tokens/sec |
| Generated throughput, range | 73.15–80.57 tokens/sec |
| TTFT, median | 0.94 sec |
| TTFT, range | 0.25–4.85 sec |
| End-to-end time, median | 3.68 sec |
| End-to-end time, range | 1.84–7.78 sec |
| Natural stop before cap | 9 / 18 cases |

It has native tool formatting and a good TTFT, but its median generation rate
is only slightly below Qwen3.5 4B and 61% below LFM2.5 8B. Half of its prompts
stopped naturally before the requested output cap, so direct end-to-end
latency is not a like-for-like quality comparison with cap-limited responses.

## Deterministic Python-quality probe

The benchmark now includes a restricted, deterministic built-ins-only Python
probe: implement `mean`, `slugify`, and `merge_intervals`, then execute the
generated code with safe built-ins and validate behavior and input immutability.
Each case was attempted twice at 4K context.

Llama 3 Groq Tool Use 8B passed 2/6 attempts: both `mean` attempts passed;
both `slugify` attempts and both `merge_intervals` attempts failed. The latter
mutated its input, violating the contract. This is a small smoke score, not a
general coding benchmark, but it prevents selecting the model on throughput
alone. Raw evidence: `benchmarks/results/llama3_groq_tool_use_8b_quality_v3_driver_20261103_quality.csv`.

LFM2.5 8B-A1B passed 4/6 valid attempts: both `mean` attempts and both
`merge_intervals` attempts passed; both slug cases failed. Its initial quality
run included visible reasoning blocks in the generated text, so the harness was
updated to remove leading `<think>…</think>` blocks before parsing code; the
corrected raw evidence is
`benchmarks/results/lfm2.5_8b_quality_v2_driver_20261103_quality.csv`. LFM therefore
remains the best measured balance of speed, native tool formatting, and this
limited Python smoke score so far.

Qwen3.5 9B Q4_K_M also passed 4/6 attempts at a 4K context: both `mean` and
both `merge_intervals` attempts passed, while both slug cases failed. It was
100% GPU-resident at 4K with approximately 5.6 GB VRAM, but its coding-call
generation speed was about 59–61 tokens/sec, versus LFM's roughly 194–201
tokens/sec on the same suite. It does not displace LFM as the practical Python
development recommendation. Raw evidence:
`benchmarks/results/qwen3.5_9b_q4km_quality_driver_20261103_quality.csv`.

Qwen3 8B passed 2/6 attempts: both `mean` attempts passed, while both slug
cases and both interval-merge cases failed. Its generated code ran at roughly
66–74 tokens/sec on the mean prompt. It does not improve on LFM's quality or
speed result. Raw evidence: `benchmarks/results/qwen3_8b_quality_driver_20261103_quality.csv`.

## Cross-model comparison

All rows used 8,192-token context, the same six cases, and three repetitions.

| Model | Cases | Median tokens/sec | Median TTFT | Python smoke | Native tool calls | Status |
|---|---:|---:|---:|---:|---|---|
| Qwen2.5-Coder 7B | 18/18 | 71.03 | 9.26 sec | Not rerun | No; Qwen bridge required | Removed after pass |
| Qwen3.5 4B | 18/18 | 79.05 | 3.24 sec | Not rerun | Yes | Removed after pass |
| LFM2.5 8B-A1B | 18/18 | **199.30** | **0.32 sec** | **4/6** | Partial; live Pi task fails on second tool request | Installed/recommended for supervised use |
| Llama 3 Groq Tool Use 8B | 18/18 | 77.19 | 0.94 sec | 2/6 | Yes | Removed after pass |
| Qwen3.5 9B Q4_K_M | Quality-only | ~60 on code calls | 10.66 sec cold load | 4/6 | Not probed | Removed after pass |
| Qwen3 8B | Quality-only | ~66–74 on mean | 9.89 sec cold load | 2/6 | Not probed | Removed after pass |

## 30B feasibility

**Direct batch: conditional GO. Pi agent: NO-GO.** A revised 2K streaming
probe measured a 45.740-second cold TTFT and 49.181-second completion for a
valid Python `clamp` implementation; the warm request reached TTFT in 0.192
seconds and completed in 2.079 seconds. The deterministic Python suite passed
6/6 attempts, with warm cases taking 2.488–11.673 seconds. This makes Qwen3-
Coder 30B a usable direct, off-hours batch generator.

It remains severely CPU-offloaded (67% CPU / 33% GPU): the cold telemetry run
reached 0.005 GiB free RAM, 273,502.52 Pages Input/sec, and 15,248.03 Page
Reads/sec. It recovered above 10 GiB free RAM after unload. A clean, catalog-
controlled 2K Pi repair attempt made no tool call, edit, or final response in
about 175 seconds, so it fails the Pi-agent budget on this laptop. Full
evidence: `documentation/archive/benchmark-history/2026_11_04__15_35_10__qwen30_batch_and_qwen35_pi_comparison.md`.

## DeepSeek-Coder-V2 Lite feasibility

**Previous safety-gate stop; response latency remains unmeasured.**
`deepseek-coder-v2:lite` (15.7B MoE, 8.9 GB Q4 artifact) was downloaded only after a fresh resource gate passed:
7.67 GiB minimum available RAM, 49.25 GiB free disk, no loaded Ollama model,
and low paging. Its controlled 2,048-token, one-output-token load probe was
terminated on the first monitoring sample: RAM was still 7.53 GiB available,
but paging jumped to approximately 35,267 Pages Input/sec and 1,879 Page
Reads/sec. The model produced no response because the prior safety policy
terminated it. After `ollama stop`, available RAM was 7.52 GiB and paging fell
to a maximum 130 Pages Input/sec / 22 Page Reads/sec during recovery. It is
not currently a practical interactive choice, but a future batch-fallback
judgment requires the revised latency-budget probe rather than this one sample.

## Current recommendation and next rotation

**Use Qwen3.5 4B as the installed Pi fallback.** It repaired and tested two
disposable Python fixtures through Pi, including recovery from a failing
implementation, within roughly 19 seconds for the recovery task. Its direct
quality score is only 2/6, so tasks should be narrow and test-led.

**Use Qwen3-Coder 30B only as an optional direct batch generator.** Its direct
quality score is 6/6 and warm responses are fast, but it does not complete a
bounded Pi tool loop. LFM2.5 8B remains a fast supervised direct alternative;
its multi-step Pi loop is unreliable.

DeepSeek-Coder-V2 Lite and Qwen2.5-Coder 14B are both approximately 9 GB-class
local artifacts. Since the coding-specialized DeepSeek load probe already
caused severe paging with 7.67 GiB free RAM, a Qwen 14B download/load would
not be a justified or safe additional experiment on this 16 GiB host.

The current tags are LFM2.5 8B, Qwen3.5 4B, and Qwen3-Coder 30B. Previously
rotated Groq and Qwen2.5 tags remain removed.

The completed raw CSV and summary are retained before rotating model files.
All tested raw CSVs and per-model summaries are retained under `benchmarks/results/`.
The next evidence gate is deterministic Pi coding-task quality and recovery,
not another raw-throughput rotation. None of these 4–8B models changes the
30B NO-GO verdict.
