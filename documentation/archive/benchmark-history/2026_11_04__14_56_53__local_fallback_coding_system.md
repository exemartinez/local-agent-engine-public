# Local fallback coding system — evidence, protocol, and current verdict

## Purpose

Establish a no-cost, local Ollama/Pi fallback for Python work when cloud coding
models are unavailable. The decision target is not peak tokens per second: it
is whether a model can repeatedly inspect files, make a narrow correct edit,
run tests, and recover when needed within a usable per-call latency budget.

All work described here used `127.0.0.1:11434` only. No paid or cloud
inference was used.

## Laptop and current state

| Item | Measured state |
|---|---|
| CPU | Intel Core i7-10870H |
| GPU | NVIDIA RTX 3070 Laptop GPU, 8 GiB VRAM |
| Host RAM | 15.77 GiB usable |
| Pagefile | approximately 16 GiB configured |
| Installed model | `lfm2.5:8b`, 5.2 GB |
| Free disk at latest model audit | 49.97 GiB |

All unsuccessful Ollama model tags from the earlier rotation were removed.
The installed LFM model is retained because it is the direct-code speed and
smoke-quality leader. It is **not** yet a reliable autonomous Pi agent.

## What was measured

The reproducible direct benchmark is `benchmarks/benchmark.py`. It used 8,192
context tokens, three repetitions of six streaming cases, approximately 512 /
2,048 / 4,096 input tokens, and 128 / 512 output caps. Time-to-first-token
(TTFT), end-to-end time, generated throughput, and resident placement were
recorded in CSV immediately after each case.

The Python smoke probe asks for built-ins-only implementations of `mean`,
`slugify`, and non-mutating `merge_intervals`, twice each. It parses and
validates the generated code locally. A smoke score is not a substitute for a
repository-level coding evaluation.

| Model | Direct benchmark / quality evidence | Pi-agent evidence | Interpretation |
|---|---|---|---|
| Qwen2.5-Coder 7B | 71.03 tok/s median; 9.26 s TTFT | Raw JSON tool text; Qwen bridge needed | Useful direct diff generator, weak agent behavior |
| Qwen3.5 4B | 79.05 tok/s; 3.24 s TTFT | Completed a disposable edit-and-test task | Best demonstrated Pi agent, but inefficient after the edit |
| LFM2.5 8B-A1B | **199.30 tok/s**; **0.32 s TTFT**; **4/6** smoke | First `read` succeeded, subsequent multi-tool request was emitted as text | Best supervised/direct fallback, not autonomous Pi |
| Llama 3 Groq Tool Use 8B | 77.19 tok/s; 0.94 s TTFT; 2/6 smoke | Native tool-format probe only | Does not beat LFM or Qwen3.5 4B |
| Qwen3.5 9B Q4_K_M | 4/6 smoke; ~59–61 tok/s code calls | Not Pi-tested | Equal small smoke score to LFM, substantially slower |
| Qwen3 8B | 2/6 smoke; ~66–74 tok/s on mean | Not Pi-tested | Does not beat LFM |

Raw evidence is retained under `benchmarks/results/`, including
`all_installed_ollama_benchmark_20261103_complete.csv` and the per-model
quality CSV files.

## Important correction: paging is not latency

The earlier 30B and DeepSeek Lite load probes were stopped because Windows
hard-paging was severe. `Pages Input/sec` is the number of memory pages read
from disk to resolve hard faults; `Page Reads/sec` is the corresponding disk
read-operation rate. These values indicate memory pressure and possible loss
of responsiveness. They are not a direct measure of TTFT or completion time.

Consequently, neither model has a measured response-time verdict:

| Model | What happened | What is known | What remains unknown |
|---|---|---|---|
| Qwen3-Coder 30B | 2K, one-token probe was stopped before output | RAM reached 0.84 GiB; paging about 224,390 Pages Input/sec and 1,698 Page Reads/sec | Cold/warm TTFT, completion time, coding quality |
| DeepSeek-Coder-V2 Lite | 2K, one-token probe stopped on first monitor sample | paging about 35,267 Pages Input/sec and 1,879 Page Reads/sec; recovery was clean after unload | Cold/warm TTFT, completion time, coding quality |

These models are not practical interactive candidates based on present memory
pressure. They are also not yet proven unusable as deliberately slow,
off-hours batch fallbacks. That distinction is the reason for the revised
protocol below.

## Revised latency-budget protocol

`scripts/fallback_latency_probe.py` streams a fixed Python `clamp` repair and
prints a flushed first-token event plus final TTFT, completion time, token
counts, output rate, and response. `scripts/run_fallback_probe.ps1` launches
it, samples RAM, hard paging, NVIDIA temperature/VRAM/use, and writes timestamped
CSV/JSON/log evidence. The wrapper stops only after a missed deadline or
sustained severe paging (30 consecutive one-second samples by default).

For every candidate, run:

1. **Cold run:** 2K context, 96-token cap, 10-minute keep-alive. Record model
   load plus TTFT and completion time.
2. **Warm run:** repeat while resident. This is the relevant Pi-call measure.
3. **Direct validation:** execute/validate the returned `clamp` code.
4. **Pi repair task:** inspect two files, fix one intentional Python defect,
   run unit tests, then demonstrate recovery after a failed implementation.
5. **Recovery:** unload the model and measure RAM/paging return to baseline.

### Decision budget

| Measure | Target | Maximum acceptable for fallback |
|---|---:|---:|
| Warm TTFT | <=30 s | 60 s |
| Warm small-code completion (<=96 tokens) | <=60 s | 90 s |
| Cold startup | Recorded separately | May exceed target only for an off-hours session |
| Correct code / tests | Pass | Required |
| Pi multi-step tool loop | Complete | Required for an agent recommendation |

Abort only for sustained loss of system responsiveness, thermal instability,
data risk, or a documented latency/quality-budget failure—not merely because
the paging counters first become nonzero.

## Current recommendation

- **Install/use now for supervised code work:** LFM2.5 8B. It is fast,
  GPU-resident in the tested configuration, and produces the strongest measured
  direct Python result. Use narrow prompts, attached files, and review edits.
- **Use when true Pi autonomy is needed:** Qwen3.5 4B is the only candidate
  that has completed the disposable Pi edit-and-test task. It must be
  reinstalled for that use and is slower/less efficient than LFM.
- **Not decided:** Qwen3-Coder 30B and DeepSeek-Coder-V2 Lite as deliberately
  slow batch fallbacks. Their previous probes measured memory pressure, not
  response latency. They require the revised cold/warm protocol when adequate
  RAM headroom is available.

## Evidence and change log

- `documentation/archive/project-history/final_recommendation.md`: historical benchmark narrative;
  sections on 30B and DeepSeek identify unmeasured latency.
- `documentation/archive/project-history/progress_log.md`: chronological work log. Some older entries
  reflect the prior safety-gate wording; this document is the current
  interpretation for the fallback objective.
- `benchmarks/logs/deepseek-coder-v2-lite-load-probe-20261104-014937.*.log`: preserved
  process output from the aborted prior probe.
- `scripts/fallback_latency_probe.py`: local-only TTFT/completion probe.
- `scripts/run_fallback_probe.ps1`: reproducible telemetry wrapper and
  deadline/sustained-paging controller.
