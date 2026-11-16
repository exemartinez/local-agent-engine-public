import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from types import SimpleNamespace

import overnight_local as overnight


def test_worker_records_stream_without_executing_output(tmp_path, monkeypatch):
    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            assert self.path == "/api/chat"
            self.rfile.read(int(self.headers["Content-Length"]))
            self.send_response(200)
            self.end_headers()
            for event in ({"message": {"content": "print('candidate')"}, "done": False},
                          {"done": True, "eval_count": 4, "eval_duration": 1000000000}):
                self.wfile.write(json.dumps(event).encode() + b"\n")

        def log_message(self, *args):
            pass

    server = HTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        monkeypatch.setattr(overnight, "URL", f"http://127.0.0.1:{server.server_port}")
        request = tmp_path / "request.json"
        output = tmp_path / "stream.jsonl"
        request.write_text(json.dumps({"stream": True}), encoding="utf-8")
        overnight.worker(request, output)
        events = [json.loads(line) for line in output.read_text(encoding="utf-8").splitlines()]
        assert events[0]["event"]["message"]["content"] == "print('candidate')"
        assert events[1]["event"]["done"] is True
        assert events[0]["received_monotonic"] <= events[1]["received_monotonic"]
    finally:
        server.shutdown()
        thread.join()
        server.server_close()


def test_sustained_low_ram_stops_worker(tmp_path, monkeypatch):
    for name in ("spec.md", "plan.md", "tasks.md", "public_tests/test_sync.py", "skeleton/sync_app.py"):
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("public material", encoding="utf-8")
    monkeypatch.setattr(overnight, "ROOT", tmp_path)
    monkeypatch.setattr(overnight.sys, "argv", ["overnight_local.py", "--sample-seconds", "5"])
    monkeypatch.setattr(overnight, "api", lambda *a, **k: {"models": [{"name": overnight.MODEL}]})
    good = {"disk_free_bytes": 20 * overnight.GIB, "ram_available_bytes": 10 * overnight.GIB,
            "gpu_c": 40, "ollama_loaded": []}
    bad = dict(good, ram_available_bytes=100 * overnight.MIB)
    samples = iter([good, bad, bad, bad])
    monkeypatch.setattr(overnight, "sample", lambda: next(samples))
    monkeypatch.setattr(overnight.time, "sleep", lambda _: None)

    class Child:
        returncode = None

        def poll(self):
            return self.returncode

        def terminate(self):
            self.returncode = 1

        def wait(self, timeout=None):
            return self.returncode

    child = Child()
    monkeypatch.setattr(overnight.subprocess, "Popen", lambda *a, **k: child)
    stopped = []
    monkeypatch.setattr(overnight.subprocess, "run", lambda args, **k: stopped.append(args) or SimpleNamespace(returncode=0))
    assert overnight.main() == 1
    summary = json.loads(next((tmp_path / "runs").glob("*/summary.json")).read_text())
    assert summary["status"] == "resource_guard"
    assert child.returncode == 1
    assert stopped == [["ollama", "stop", overnight.MODEL]]
    assert summary["generated_code_executed"] is False
