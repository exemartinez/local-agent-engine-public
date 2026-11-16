# Feasibility assessment

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
