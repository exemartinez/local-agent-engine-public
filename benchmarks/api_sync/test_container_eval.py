import subprocess
from types import SimpleNamespace

import container_eval


def test_runtime_missing_fails_closed(monkeypatch):
    monkeypatch.setattr(container_eval.shutil, "which", lambda _: None)
    try:
        container_eval.ready()
    except RuntimeError as exc:
        assert "not installed" in str(exc)
    else:
        raise AssertionError("missing runtime must not be accepted")


def test_timeout_removes_only_owned_container(tmp_path, monkeypatch):
    calls = []

    def fake_command(args, timeout):
        calls.append(args)
        if args[1] == "run":
            raise subprocess.TimeoutExpired(args, timeout)
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(container_eval, "command", fake_command)
    result = container_eval.run_container(tmp_path, ["tests"], 1)
    run, cleanup = calls
    assert result["timeout"] is True
    assert "none" in run and "--read-only" in run and "no-new-privileges" in run
    assert cleanup[:3] == ["docker", "rm", "-f"]
    assert cleanup[3] == run[run.index("--name") + 1]


def test_isolation_probe_failure_is_not_accepted(tmp_path, monkeypatch):
    monkeypatch.setattr(container_eval, "run_container", lambda *a, **k: {"exit_code": 1, "output": "unsafe"})
    try:
        container_eval.verify_isolation(tmp_path)
    except RuntimeError as exc:
        assert "probe failed" in str(exc)
    else:
        raise AssertionError("probe failure must stop evaluation")
