# Test repositories and fixtures

These are small **disposable agent probes**, not the main model-comparison benchmark and not one complete test suite per model. Some directories contain edits made during earlier agent attempts. Their current contents are historical results: do not assume a fixture is still in its original failing state or reset it without preserving evidence.

| Folder | Purpose |
| --- | --- |
| `coding-baseline/` | Initial broken `mean` exercise and its unit tests; `opencode.json` is a restrictive local OpenCode configuration. |
| `lfm-agent-probe/` | Small `clamp` repair used during local-model/Pi experiments; the name describes the experiment, not exclusive model ownership. |
| `qwen-recovery-probe/` | `parse_port` validation and unit tests used to check Pi recovery after a failed implementation. |
| `qwen30-agent-probe/` | `slugify` fixture used for a bounded Qwen3-Coder 30B Pi attempt. |

The shared, larger generation-and-test benchmark for the models is in [`benchmarks/api_sync/`](../benchmarks/api_sync/): read its specification, public tests, hidden tests, and timestamped run artifacts there. The [comparison and code review](../documentation/reports/2026_11_13__19_12_05__final_podium_code_review.md) explains the test limitations.
