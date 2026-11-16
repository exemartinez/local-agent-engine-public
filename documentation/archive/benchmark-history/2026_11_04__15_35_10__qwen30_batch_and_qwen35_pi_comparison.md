# Qwen30 batch coding versus Qwen3.5 Pi coding

## Decision question

Can Qwen3-Coder 30B serve as a deliberately slow local coding fallback, and does it replace Qwen3.5 4B for Pi-based work?

## Qwen3-Coder 30B direct batch results

The local model was tested at 2,048 context tokens through the timestamped fallback telemetry wrapper.

| Run | TTFT | Completion | Output rate | Correct clamp | Placement |
|---|---:|---:|---:|---|---|
| Cold direct | 45.740 s | 49.181 s | 9.56 tok/s | Yes | 67% CPU / 33% GPU |
| Warm direct | 0.192 s | 2.079 s | 17.51 tok/s | Yes | 67% CPU / 33% GPU |

The cold request met the 60-second first-token and total-response target. The warm request was fast enough for normal direct work once the model was resident.

The initial cold probe caused severe paging: minimum available RAM was 0.005 GiB, maximum Pages Input/sec was 273,502.52, and maximum Page Reads/sec was 15,248.03. The model nevertheless produced valid code and the computer remained observable through the local telemetry controller. After `ollama stop`, RAM recovered above 10 GiB; paging fell from a short post-unload drain to a low later sample, and the GPU reached 61 C.

### Deterministic direct-code quality

At 2K context, Qwen3-Coder 30B passed **6/6** restricted Python cases:

| Case | Cold / warm response times | Result |
|---|---|---|
| `mean` | 40.469 s / 2.488 s | 2/2 pass |
| `slugify` | 9.085 s / 4.332 s | 2/2 pass |
| `merge_intervals` | 11.673 s / 7.756 s | 2/2 pass |

This makes it the strongest measured direct code generator in this project.

## Controlled Qwen3-Coder 30B Pi repair result

The model catalog was explicitly configured at 2K context and a single clean background Pi process was used. The disposable `qwen30-agent-probe` fixture began with two failing `slugify` tests.

The process made **no observable tool action, no file edit, and no final output** in approximately 175 seconds. It was then stopped as a documented batch-ceiling failure. Independent tests still had both original failures after termination.

An earlier foreground attempt was discarded from scoring because its process survived a tool timeout and contaminated the timing; this avoids claiming a repair whose completion boundary was not controlled.

**Verdict:** Qwen3-Coder 30B passes as a direct batch code generator but fails as a bounded Pi coding agent on this laptop.

## Qwen3.5 4B comparison

Qwen3.5 4B used the same 2K deterministic quality suite:

| Case | Result |
|---|---|
| `mean` | 2/2 pass |
| `slugify` | 0/2 pass |
| `merge_intervals` | 0/2 pass |
| Total | **2/6 pass** |

Its direct cold/warm clamp calls were 4.408 s / 0.105 s to first token and 4.653 s / 0.342 s to completion. Most importantly, it has independently repaired and tested two disposable Python fixtures through Pi:

1. Corrected `clamp`; all 3 tests passed.
2. Recovered a failed `parse_port`; both prior failing boundary tests were fixed and all 3 tests passed. The Pi command completed in about 19 seconds.

## Practical recommendation

**Recommended installed Pi fallback: Qwen3.5 4B.** It is the only candidate with demonstrated bounded Pi repair and test execution. Its direct smoke quality is weaker, so give it narrow tasks, explicit tests, and review its changes.

**Optional direct-only batch model: Qwen3-Coder 30B.** Keep it only if 18 GB of disk is acceptable and you will use it through a direct prompt/attached-file workflow, not autonomous Pi tools. Its cold call is about 50 seconds, warm calls are typically 2–12 seconds, and it uses severe CPU-offload paging.

LFM2.5 8B remains a very fast supervised direct option, but it has a repeatable multi-step Pi tool-loop failure. It does not displace Qwen3.5 for Pi use or Qwen30 for direct-code quality.

## Reproducible raw evidence

- `benchmarks/results/2026_11_04__15_17_20__fallback_probe__qwen3-coder_30b.summary.json`
- `benchmarks/results/2026_11_04__15_18_53__fallback_probe__qwen3-coder_30b.summary.json`
- `benchmarks/results/2026_11_04__15_32_01__qwen30_quality_driver_quality.csv`
- `benchmarks/results/2026_11_04__15_34_20__qwen35_quality_driver_quality.csv`
- `benchmarks/logs/2026_11_04__15_25_55__qwen30_pi_2k_repair.*.log`
