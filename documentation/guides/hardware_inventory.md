# Hardware inventory — 2026-11-01

Measured locally; machine state is transient.

- CPU: Intel Core i7-10870H, 8 physical / 16 logical cores.
- RAM: two 8 GiB Samsung DIMMs; 16 GiB installed, 15.77 GiB OS-visible. Available at inventory: 0.42 GiB; subsequent sample 381 MiB.
- GPU: NVIDIA RTX 3070 Laptop, 8192 MiB dedicated VRAM, WDDM; driver 616.92. NVIDIA reports CUDA UMD compatibility 13.4; this does not establish an installed CUDA Toolkit.
- GPU snapshot: 2987 MiB used / 5205 MiB nominally free; 30% utilization, 68 C, 60 W draw / 125 W cap. This is shared current activity, not inference measurement or a fixed Windows reservation.
- Intel UHD Graphics and a Meta virtual monitor also enumerated. NVIDIA display is active and graphics processes are present; Intel is installed, but its current utilization was not measured.
- Windows 11 Home, 10.0.26300 build 26300.
- C: total 934.27 GiB, free 8.75 GiB. D: optical drive, zero free; not an alternate model destination.
- Page file: 43008 MiB allocated, 914 MiB used, peak 6289 MiB. One sampled interval: zero page reads/input per second; low free RAM alone does not prove active heavy paging.
- Power scheme: Balanced; unchanged. Detailed settings saved in benchmarks/logs/power-settings.txt.
- Python: reusable Codex runtime Python 3.12.14, scripts use its explicit path. WindowsApps python on PATH is an alias, not the verified interpreter.
- Git: reusable 2.53.0.windows.3.
- Ollama, OpenCode, nvcc, cmake, llama-cli/server: not discovered on PATH; common user Ollama location also absent. This is not an exhaustive whole-disk search.
- Relevant CUDA/OLLAMA/OPENCODE/PYTHON environment variables: none observed. PATH and executable locations preserved in benchmarks/results/hardware_inventory.json; credentials were not collected.

Evidence: benchmarks/results/hardware_inventory.json, benchmarks/logs/nvidia-smi.txt, benchmarks/logs/power-settings.txt.
