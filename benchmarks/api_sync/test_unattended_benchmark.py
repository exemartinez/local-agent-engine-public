import json

import unattended_benchmark as benchmark


def test_incomplete_responses_are_not_treated_as_tests():
    assert benchmark.incomplete_response({"message": {"content": ""}, "finish_reason": "stop"})
    assert benchmark.incomplete_response({"message": {"content": "partial"}, "finish_reason": "length"})
    assert not benchmark.incomplete_response({"message": {"content": "print(1)"}, "finish_reason": "stop"})


def test_no_isolation_means_no_server_or_model_deletion(tmp_path, monkeypatch):
    root = tmp_path / "benchmark"
    (root / "runs").mkdir(parents=True)
    model_dir = root / "model-downloads"
    model_dir.mkdir()
    model = model_dir / "candidate.gguf"
    model.write_bytes(b"synthetic placeholder")
    executable = tmp_path / "llama-server.exe"
    executable.write_text("not executed")
    monkeypatch.setattr(benchmark, "ROOT", root)
    monkeypatch.setattr(benchmark, "container_eval", type("Guard", (), {
        "ready": staticmethod(lambda: (_ for _ in ()).throw(RuntimeError("no docker")))
    }))
    monkeypatch.setattr(benchmark.argparse._sys, "argv", ["unattended_benchmark.py", "--model", str(model),
        "--llama-server", str(executable), "--delete-model-after"])
    monkeypatch.setattr(benchmark.subprocess, "Popen", lambda *a, **k: (_ for _ in ()).throw(AssertionError("server started")))
    assert benchmark.main() == 1
    assert model.exists()
    result = json.loads(next((root / "runs").glob("*/result.json")).read_text())
    assert result["status"] == "error"
    assert "no docker" in result["error"]
    assert result["calls"] == []
