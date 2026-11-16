import csv
import json
from pathlib import Path

lab=Path(__file__).resolve().parents[1]
inv=json.loads((lab/'benchmarks/results/hardware_inventory.json').read_text(encoding='utf-8-sig'))
def write(name,text):
    (lab/name).parent.mkdir(parents=True,exist_ok=True)
    (lab/name).write_text(text.strip()+'\n',encoding='utf-8')
ram=inv['os']['FreePhysicalMemory']/1048576
disk=inv['disk'][0]['FreeSpace']/2**30
write('hardware_inventory.md',f'''# Hardware inventory — 2026-11-01

Measured locally; machine state is transient.

- CPU: Intel Core i7-10870H, 8 physical / 16 logical cores.
- RAM: two 8 GiB Samsung DIMMs; 16 GiB installed, 15.77 GiB OS-visible. Available at inventory: {ram:.2f} GiB; subsequent sample 381 MiB.
- GPU: NVIDIA RTX 3070 Laptop, 8192 MiB dedicated VRAM, WDDM; driver 616.92. NVIDIA reports CUDA UMD compatibility 13.4; this does not establish an installed CUDA Toolkit.
- GPU snapshot: 2987 MiB used / 5205 MiB nominally free; 30% utilization, 68 C, 60 W draw / 125 W cap. This is shared current activity, not inference measurement or a fixed Windows reservation.
- Intel UHD Graphics and a Meta virtual monitor also enumerated. NVIDIA display is active and graphics processes are present; Intel is installed, but its current utilization was not measured.
- Windows 11 Home, 10.0.26300 build 26300.
- C: total 934.27 GiB, free {disk:.2f} GiB. D: optical drive, zero free; not an alternate model destination.
- Page file: 43008 MiB allocated, 914 MiB used, peak 6289 MiB. One sampled interval: zero page reads/input per second; low free RAM alone does not prove active heavy paging.
- Power scheme: Balanced; unchanged. Detailed settings saved in benchmarks/logs/power-settings.txt.
- Python: reusable Codex runtime Python 3.12.14, scripts use its explicit path. WindowsApps python on PATH is an alias, not the verified interpreter.
- Git: reusable 2.53.0.windows.3.
- Ollama, OpenCode, nvcc, cmake, llama-cli/server: not discovered on PATH; common user Ollama location also absent. This is not an exhaustive whole-disk search.
- Relevant CUDA/OLLAMA/OPENCODE/PYTHON environment variables: none observed. PATH and executable locations preserved in benchmarks/results/hardware_inventory.json; credentials were not collected.

Evidence: benchmarks/results/hardware_inventory.json, benchmarks/logs/nvidia-smi.txt, benchmarks/logs/power-settings.txt.
''')
write('feasibility_report.md','''# Feasibility assessment

Decision: NO-GO for 30B in the observed machine state. Baseline installation also blocked by current disk/RAM headroom. No model download attempted.

## 30B memory calculation

Official Ollama tag reports Q4_K_M, 30.5B parameters, approximately 19 GB weights (17.70 GiB). Size is rounded; exact manifest bytes were not downloaded. 3.3B active parameters reduce computation, not the requirement to store all experts.

Official architecture: 48 layers, 4 KV heads, head dimension 128. Conventional FP16 KV = 2 (K,V) * 48 * 4 * 128 * 2 bytes * context = 98304 bytes/token.

| Context | FP16 KV | Approximate Q8 KV payload | Approximate Q4 KV payload |
|---|---:|---:|---:|
| 2048 | 0.1875 GiB | 0.094 GiB | 0.047 GiB |
| 4096 | 0.375 GiB | 0.188 GiB | 0.094 GiB |
| 8192 | 0.750 GiB | 0.375 GiB | 0.188 GiB |

Quantized cache values omit block metadata, alignment and implementation constraints. They are estimates, not configurations tested here. Allow an additional estimated 1–3 GiB for runtime compute buffers, graph allocations and staging; host/GPU split depends on runtime and batch size. At 2K context, total budget approximately 18.9–20.9 GiB, excluding OS and unrelated applications. mmap does not make actively needed weights free.

A — fully in VRAM: impossible with 8 GiB for these 19 GB weights.

B — combined available physical memory: observed roughly 5.08 GiB GPU free plus 0.42 GiB host free = 5.50 GiB, dramatically insufficient. These pools are not interchangeable; this sum is only an optimistic upper bound. A cleaned 16 GiB machine might have 10–12 GiB host available plus 6–7 GiB GPU available; even then 17.7 GiB weights plus cache/overhead leaves an unsafe margin. Reassess measured availability rather than assuming every byte can be pooled.

C — significant disk paging: likely if loading were forced in current conditions, unacceptable for interactive coding agents. Existing pagefile size is not usable physical model capacity. No pagefile changes made.

An optimistic weight-only division using current free GPU memory suggests roughly 13/48 layer-equivalents on GPU. Real capacity is lower after cache/compute allocations; layers are not equal-sized and embeddings/output tensors complicate this estimate. This is not an observed offload count. Remaining weights would require roughly 13 GiB host residency, unavailable now.

CPU-offloaded expert computation is bounded by CPU memory bandwidth and CPU compute. Prefill also stresses compute and activation handling; decoding often stresses weight bandwidth. Layer offload normally transfers activations at boundaries, rather than all weights every token. Expert streaming strategies may add substantial PCIe weight traffic. PCIe link bandwidth was not benchmarked. No predicted tokens/sec is presented.

## Baseline gate

4B tag verified available: approximately 4.0 GB download including multimodal assets; text-model tensor blob reported 3.3 GB Q4_K_M. Ollama Windows documentation requires at least 4 GB installation space. With only 8.75 GiB disk free, installation plus weights leaves inadequate OS/download/extraction headroom. Lab policy: at least 20 GiB disk free and 6 GiB available host RAM before baseline installation. These are conservative operational thresholds, not vendor requirements. Prefer 25–30 GiB disk free if also adding llama.cpp binaries.

Start at 2048–4096 context, one model, one request, no cloud. 9B is optional and deferred. 30B additionally needs at least its 19 GB download plus software/staging and OS reserve; target 40 GiB free disk before reconsideration, and a separate measured physical-memory budget.

## Sources

- https://ollama.com/library/qwen3-coder:30b
- https://huggingface.co/Qwen/Qwen3-Coder-30B-A3B-Instruct/raw/main/config.json
- https://ollama.com/library/qwen3.5:4b
- https://docs.ollama.com/windows
''')
write('installation_log.md','''# Installation log — 2026-11-01

Created C:\\workspace\\local-agent-engine and its requested experiment directories. Collected read-only hardware, power and executable inventory. Verified existing Python 3.12.14 and Git 2.53.0.windows.3; reused them. Initialized only the isolated disposable test repository.

No packages, drivers, inference runtimes or models installed. No global environment variables, power settings, pagefile settings, firewall rules or existing applications changed. No inference API requests made. Official model/documentation pages were accessed for metadata only.

Prepared resource gate, loopback-only server launcher, preliminary streaming benchmark harness, isolated Python tests and example OpenCode configuration. These are preparation artifacts, not a working inference installation. The benchmark harness uses only the standard library. It records actual server token counts, approximate prompt targets and chunk timing honestly; hardware sampling and tokenizer-exact prompt construction remain unfinished.

Next: regain headroom, run scripts/preflight.ps1, install official Ollama Windows distribution, verify version and local endpoint, pull only qwen3.5:4b, inspect /api/show and /api/ps, then begin short smoke tests before the full matrix. Obtain official precompiled llama.cpp CUDA binaries rather than a full Toolkit when compatible; record release and hashes. Install OpenCode only after the local model works. Do not automatically run unreviewed downloads.
''')
write('opencode_configuration.md','''# OpenCode integration — prepared, not tested

OpenCode is not installed/discovered and no end-to-end task has succeeded. No integration or containment claim is made.

Prepared config: config/opencode.json. It selects only the local provider, uses http://127.0.0.1:11434/v1 and denies shell, external directories and network tools. Read/edit permissions are confined through tool policy and working directory; OpenCode permissions are not an OS security sandbox. Review current OpenCode version/schema and path behavior before enabling edits. Do not use --auto. Never connect a cloud provider for this experiment.

Launch from C:\\workspace\\local-agent-engine\\test-repos\\coding-baseline only, explicitly selecting ollama/qwen3.5:4b. Denying bash means trusted tests must initially run externally through the lab operator. Test recovery can be assessed by passing failing test output back to the same agent. For stronger containment use a dedicated restricted OS identity or VM after resource reassessment; do not grant unrestricted system access.

Success requires actual file edits, passing deterministic tests, a logged failed-test/recovery cycle, complete elapsed time and endpoint traffic evidence. None has been measured. Loopback configuration prevents selecting cloud inference in this config; it does not prove absence of all runtime telemetry/update traffic.

References: https://opencode.ai/docs/providers/ and https://opencode.ai/docs/permissions/
''')
write('final_recommendation.md','''# Engineering assessment — incomplete execution due to resources

No inference was run. The smaller-model environment and OpenCode integration are NOT yet functional. The success criterion has not been met; this report records a resource block rather than a benchmark conclusion.

1. **Can this laptop run 30B?** Not safely in its observed state. The weights exceed VRAM and current combined free physical memory by a large margin. A cleaned 16 GiB machine remains marginal; no loading experiment was justified.
2. **Useful interactive speed?** Unknown and unmeasured; current resource state is unsuitable. Do not infer performance from 3.3B active parameters.
3. **Largest practical coding model?** Not established. 4B is the appropriate first candidate; optional 9B requires a separate measured headroom and latency assessment.
4. **Best coding quality per second?** Unknown until deterministic quality and timing measurements exist.
5. **32/64 GiB RAM?** Additional RAM would materially improve host weight residency for 30B and reduce paging risk. It would not increase GPU offload capacity or guarantee interactive speed. Verify exact laptop memory support before selecting any upgrade; no compatibility/purchase recommendation was established.
6. **8 GiB VRAM versus RAM?** Both matter. Current RAM scarcity blocks loading; 8 GiB VRAM limits acceleration even with more host memory.
7. **Reliable local agent?** Not demonstrated. Requires baseline tool calling, actual OpenCode edits/tests and recovery evidence.
8. **Minimum sensible change?** First regain free disk and available RAM at no cost. Baseline gate is 20 GiB disk and 6 GiB available RAM. Do not purchase hardware based on this incomplete experiment. For 30B, larger host memory helps feasibility but full GPU residency is the clearer performance path.
9. **3090 24 GiB / 5090 32 GiB / workstation?** Capacity inference only: 24 GiB can potentially hold these 17.7 GiB quantized weights with modest context and overhead; 32 GiB provides more cache/runtime headroom. A larger-RAM workstation enables more host offload, but does not itself guarantee GPU-speed decoding. No comparative speed or device compatibility measured. These are separate-system capacity scenarios, not supported internal laptop GPU upgrades.
10. **Zero paid inference tokens?** The intended loopback stack can operate without a paid inference provider; this experiment made zero inference calls. This Codex conversation itself is separate from the future local inference environment.

| Metric | 4B | 9B | 30B |
|---|---|---|---|
| Model size | Official tag ~4.0 GB; not downloaded | Not verified/downloaded | Official tag ~19 GB; not downloaded |
| Quantization | Q4_K_M text weights per official tag | Not verified | Q4_K_M per official tag |
| GPU offload | Unmeasured | Unmeasured | Unmeasured |
| Peak VRAM / system RAM | Unmeasured | Unmeasured | Unmeasured |
| TTFT p50 / p95 | Unmeasured | Unmeasured | Unmeasured |
| TPOT p50 / tokens/sec | Unmeasured | Unmeasured | Unmeasured |
| Coding success / time per success | Unmeasured | Unmeasured | Unmeasured |
| Agent compatibility | Untested | Untested | Untested |
| Status | BLOCKED: current resources | Optional, deferred | NOT VIABLE in observed resource state |

Benchmark CSVs contain headers only. No fabricated rows, speeds, success rates or memory measurements. Sources and budget details are in feasibility_report.md.
''')
# Historical empty CSV placeholders are no longer generated.
config={'$schema':'https://opencode.ai/config.json','enabled_providers':['ollama'],
 'model':'ollama/qwen3.5:4b','small_model':'ollama/qwen3.5:4b',
 'provider':{'ollama':{'npm':'@ai-sdk/openai-compatible','name':'Local Ollama',
 'options':{'baseURL':'http://127.0.0.1:11434/v1'},
 'models':{'qwen3.5:4b':{'name':'Qwen3.5 4B local','limit':{'context':4096,'output':512}}}}},
 'permission':{'*':'deny','read':'allow','list':'allow','glob':'allow','grep':'allow',
 'edit':'ask','external_directory':'deny','bash':'deny','webfetch':'deny','websearch':'deny'}}
write('config/opencode.json',json.dumps(config,indent=2))
write('test-repos/coding-baseline/math_utils.py','''def mean(values):
    """Exercise fixture: intentionally incorrect for bug-fix evaluation."""
    return sum(values) / (len(values) + 1)
''')
write('test-repos/coding-baseline/test_math_utils.py','''import unittest
from math_utils import mean

class MeanTests(unittest.TestCase):
    def test_mean(self):
        self.assertEqual(mean([2, 4, 6]), 4)
    def test_empty(self):
        with self.assertRaises(ValueError):
            mean([])

if __name__ == '__main__':
    unittest.main()
''')
write('test-repos/coding-baseline/README.md','''# Disposable coding fixture

math_utils.mean contains an intentional bug. Tests should fail initially.
Task: repair mean, raise ValueError for empty input, and preserve the input.
No model has attempted this task. Other required evaluation categories remain
to be implemented: generation, test generation, refactoring, SQL, multi-file,
error diagnosis and tool execution. Do not report this fixture as the full suite.
''')
print('Reports and preparation artifacts written; inference remains blocked.')
