import json
from pathlib import Path
from types import SimpleNamespace

import windows_eval
import windows_queue


def test_gate_rejects_direct_host_escape():
    for code in ("import subprocess", "from os import system", "open('secret')", "x = open('secret')", "def f(x=print(1)):\n pass"):
        assert windows_eval.screen(code), code


def test_gate_accepts_reference():
    assert windows_eval.screen(Path('src/sync_app.py').read_text(encoding='utf-8')) is None


def test_memory_wait_requires_three_stable_readings():
    values = iter([4, 6, 6.2, 5.9])
    elapsed = [0]
    result = windows_queue.wait_for_memory(100, sample=lambda: {"ram_available_bytes": next(values) * windows_queue.GIB},
        clock=lambda: elapsed[0], sleep=lambda seconds: elapsed.__setitem__(0, elapsed[0] + seconds),
        tolerance=0.5 * windows_queue.GIB)
    assert result["stable"] is True
    assert len(result["samples_bytes"]) == 4
    assert elapsed[0] == 30


def test_memory_wait_stops_on_timeout():
    elapsed = [0]
    result = windows_queue.wait_for_memory(25, sample=lambda: {"ram_available_bytes": 1},
        clock=lambda: elapsed[0], sleep=lambda seconds: elapsed.__setitem__(0, elapsed[0] + seconds))
    assert result["stable"] is False
    assert elapsed[0] == 25


def test_memory_estimate_distinguishes_small_and_large_models():
    ram, vram = int(6.2 * windows_queue.GIB), int(7.0 * windows_queue.GIB)
    assert windows_queue.assess_model_memory(int(12.1e9), ram, vram)["fits_estimate"]
    assert not windows_queue.assess_model_memory(int(18.3e9), ram, vram)["fits_estimate"]


def test_queue_saves_result_before_removing_only_its_download(tmp_path, monkeypatch):
    monkeypatch.setattr(windows_queue.sys, "argv", ["windows_queue.py"])
    root = tmp_path / "project" / "benchmarks" / "api_sync"
    root.mkdir(parents=True)
    (tmp_path / "project" / "documentation").mkdir()
    runtime = root / "llama-server.exe"
    runtime.write_text("fake")
    monkeypatch.setattr(windows_queue, "ROOT", root)
    monkeypatch.setattr(windows_queue, "RUNTIME", runtime)
    monkeypatch.setattr(windows_queue, "MODELS", [("synthetic", "Q3", "org/repo", "test.gguf", 0)])
    monkeypatch.setattr(windows_queue, "wait_for_memory", lambda deadline: {"stable": True, "samples_bytes": [10 * windows_queue.GIB] * 3})
    monkeypatch.setattr(windows_queue, "current_model_assessment", lambda size: {"fits_estimate": True})
    monkeypatch.setattr(windows_queue.shutil, "disk_usage", lambda _: SimpleNamespace(free=50 * windows_queue.GIB))

    class Response:
        headers = {"Content-Length": "3"}
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def read(self, _):
            value = getattr(self, "value", b"abc")
            self.value = b""
            return value

    monkeypatch.setattr(windows_queue, "urlopen", lambda *a, **k: Response())
    def fake_run(*args, **kwargs):
        result_dir = root / "runs" / "synthetic_child"
        result_dir.mkdir()
        (result_dir / "result.json").write_text(json.dumps({"status": "fail", "calls": [1], "elapsed_seconds": 2}))
        return SimpleNamespace(stdout=json.dumps({"run": str(result_dir)}), stderr="", returncode=0)
    monkeypatch.setattr(windows_queue.subprocess, "run", fake_run)
    assert windows_queue.main() == 0
    assert not (root / "model-downloads" / "test.gguf").exists()
    state = json.loads(next((root / "runs").glob('*__windows_queue/queue.json')).read_text())
    assert state["models"][0]["status"] == "fail"
    assert state["models"][0]["sha256"]
    assert list((tmp_path / "project" / "documentation" / "archive" / "queue-snapshots").glob('*__moe_quantization_queue.md'))


def test_gpt_repeats_use_two_seeds_before_file_cleanup(tmp_path, monkeypatch):
    monkeypatch.setattr(windows_queue.sys, "argv", ["windows_queue.py"])
    root = tmp_path / "project" / "benchmarks" / "api_sync"
    root.mkdir(parents=True)
    (tmp_path / "project" / "documentation").mkdir()
    runtime = root / "llama-server.exe"
    runtime.write_text("fake")
    monkeypatch.setattr(windows_queue, "ROOT", root)
    monkeypatch.setattr(windows_queue, "RUNTIME", runtime)
    monkeypatch.setattr(windows_queue, "MODELS", [("GPT-OSS 20B", "MXFP4", "org/repo", "test.gguf", 0)])
    monkeypatch.setattr(windows_queue, "wait_for_memory", lambda deadline: {"stable": True, "samples_bytes": [10 * windows_queue.GIB] * 3})
    monkeypatch.setattr(windows_queue, "current_model_assessment", lambda size: {"fits_estimate": True})
    monkeypatch.setattr(windows_queue.shutil, "disk_usage", lambda _: SimpleNamespace(free=50 * windows_queue.GIB))

    class Response:
        headers = {"Content-Length": "3"}
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def read(self, _):
            value = getattr(self, "value", b"abc")
            self.value = b""
            return value

    monkeypatch.setattr(windows_queue, "urlopen", lambda *a, **k: Response())
    calls = []
    def fake_run(command, **kwargs):
        assert (root / "model-downloads" / "test.gguf").exists()
        calls.append(command)
        result_dir = root / "runs" / f"child_{len(calls)}"
        result_dir.mkdir()
        (result_dir / "result.json").write_text(json.dumps({"status": "pass", "calls": [1], "elapsed_seconds": 2}))
        return SimpleNamespace(stdout=json.dumps({"run": str(result_dir)}), stderr="", returncode=0)
    monkeypatch.setattr(windows_queue.subprocess, "run", fake_run)
    assert windows_queue.main() == 0
    assert [c[c.index("--seed") + 1] for c in calls] == ["43", "44"]
    assert [c[c.index("--temperature") + 1] for c in calls] == ["0.2", "0.2"]
    assert not (root / "model-downloads" / "test.gguf").exists()
    state = json.loads(next((root / "runs").glob('*__windows_queue/queue.json')).read_text())
    assert len(state["models"][0]["replicates"]) == 2


def test_resume_preserves_finished_results_and_skips_them(tmp_path, monkeypatch):
    root = tmp_path / "project" / "benchmarks" / "api_sync"
    root.mkdir(parents=True)
    (tmp_path / "project" / "documentation").mkdir()
    runtime = root / "llama-server.exe"
    runtime.write_text("fake")
    previous = tmp_path / "previous.json"
    previous.write_text(json.dumps({"status": "resource_guard", "models": [
        {"model": "done", "quantization": "Q4", "source": "org/repo", "file": "done.gguf", "status": "pass", "result_summary": "original result"},
        {"model": "Qwen3.5 35B-A3B", "quantization": "UD-IQ2_M", "source": "org/repo", "file": "skip.gguf", "status": "pending"}]}))
    monkeypatch.setattr(windows_queue.sys, "argv", ["windows_queue.py", "--resume-from", str(previous)])
    monkeypatch.setattr(windows_queue, "ROOT", root)
    monkeypatch.setattr(windows_queue, "RUNTIME", runtime)
    monkeypatch.setattr(windows_queue, "MODELS", [("done", "Q4", "org/repo", "done.gguf", 0),
        ("Qwen3.5 35B-A3B", "UD-IQ2_M", "org/repo", "skip.gguf", 0)])
    monkeypatch.setattr(windows_queue, "urlopen", lambda *a, **k: (_ for _ in ()).throw(AssertionError("unexpected download")))
    assert windows_queue.main() == 0
    state = json.loads(next((root / "runs").glob('*__windows_queue/queue.json')).read_text())
    assert state["models"][0]["result_summary"] == "original result"
    assert state["models"][1]["status"] == "skipped_observed_resource_guard"
    assert json.loads(previous.read_text())["models"][1]["status"] == "pending"
