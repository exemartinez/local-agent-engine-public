# Removal of tested local models

At the user's direction, the already-benchmarked Ollama models `qwen3.5:4b` and `lfm2.5:8b` were removed on 2026-11-05 after their results were preserved. Qwen3-Coder 30B had already been removed at the user's request. `ollama list` subsequently showed no installed models, and the system drive had approximately 54.3 GB free. No model result, report, or benchmark input was removed.

The comparable coding-task results and their limitations are in `..\benchmark-history\2026_11_05__02_13_45__api_sync_chat_v3_results.md`; previous performance and agent tests remain in the other reports and raw run directories. Earlier documents may describe models as installed because those statements reflect their historical measurement dates, not the current installation state. Future comparisons require downloading one candidate at a time and deleting it only after recording its results, as requested.
