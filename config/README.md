# Configuration

`opencode.json` is a historical **example** for the local Ollama `qwen3.5:4b` model with restrictive permissions. It does not install the model, prove that OpenCode can complete a task, or represent all models tested here. The project primarily evaluated direct local generation through `llama.cpp`; it did not establish working OpenCode configurations for every model.

The explicit GGUF model/quantization/source manifest for the batch queue is in [`benchmarks/api_sync/windows_queue.py`](../benchmarks/api_sync/windows_queue.py); Gemma's follow-up is in [`benchmarks/api_sync/gemma4_benchmark.py`](../benchmarks/api_sync/gemma4_benchmark.py). These are benchmark inputs, not ready-to-use agent profiles. See the saved results before selecting a model. No additional provider profile is supplied without evidence that it works.

[`models.catalog.json`](models.catalog.json) is a non-executable inventory of the 11 original GGUF configurations and Gemma follow-up. It records source and latest outcome; it does not claim the models are installed or agent integrations configured.
