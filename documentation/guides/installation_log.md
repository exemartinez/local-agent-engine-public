# Installation log — 2026-11-01

Created C:\workspace\local-agent-engine and its requested experiment directories. Collected read-only hardware, power and executable inventory. Verified existing Python 3.12.14 and Git 2.53.0.windows.3; reused them. Initialized only the isolated disposable test repository.

No packages, drivers, inference runtimes or models installed. No global environment variables, power settings, pagefile settings, firewall rules or existing applications changed. No inference API requests made. Official model/documentation pages were accessed for metadata only.

Prepared resource gate, loopback-only server launcher, preliminary streaming benchmark harness, isolated Python tests and example OpenCode configuration. These are preparation artifacts, not a working inference installation. The benchmark harness uses only the standard library. It records actual server token counts, approximate prompt targets and chunk timing honestly; hardware sampling and tokenizer-exact prompt construction remain unfinished.

Next: regain headroom, run scripts/preflight.ps1, install official Ollama Windows distribution, verify version and local endpoint, pull only qwen3.5:4b, inspect /api/show and /api/ps, then begin short smoke tests before the full matrix. Obtain official precompiled llama.cpp CUDA binaries rather than a full Toolkit when compatible; record release and hashes. Install OpenCode only after the local model works. Do not automatically run unreviewed downloads.

2026-11-02: Relocated from C:\AI-Lab to C:\workspace\local-agent-engine at user request; updated script and documentation paths. Raw inventory/log snapshots retain their historical content.
