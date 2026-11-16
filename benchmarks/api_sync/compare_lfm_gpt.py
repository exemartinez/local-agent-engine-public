"""Run the same local Python benchmark on LFM2.5 8B and GPT-OSS 20B, sequentially."""
import sys
import windows_queue


if __name__ == "__main__":
    windows_queue.MODELS = [
        ("LFM2.5 8B-A1B", "Q4_K_M", "LiquidAI/LFM2.5-8B-A1B-GGUF", "LFM2.5-8B-A1B-Q4_K_M.gguf", 5.16),
        ("GPT-OSS 20B", "MXFP4", "ggml-org/gpt-oss-20b-GGUF", "gpt-oss-20b-MXFP4.gguf", 12.1),
    ]
    # Same fixed seed and sampling for both; existing queue handles cleanup, limits and logs.
    windows_queue.REPEAT_CONFIGS = {}
    sys.exit(windows_queue.main())
