"""Fail-closed container execution of a candidate's tests; never imports candidate on host."""
import argparse
import json
import shutil
import subprocess
import tempfile
import time
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parent
IMAGE = "local-agent-engine-test:1"


def command(args, timeout):
    return subprocess.run(args, capture_output=True, text=True, timeout=timeout)


def ready():
    if not shutil.which("docker"):
        raise RuntimeError("Docker is not installed or is not on PATH")
    info = command(["docker", "info", "--format", "{{.OSType}}"], 15)
    if info.returncode or info.stdout.strip() != "linux":
        raise RuntimeError("A running Linux Docker engine is required")
    image = command(["docker", "image", "inspect", IMAGE], 15)
    if image.returncode:
        raise RuntimeError(f"Required prebuilt test image is missing: {IMAGE}")


def run_container(stage, args, timeout, entrypoint=None):
    name = "local-agent-eval-" + uuid.uuid4().hex
    cmd = ["docker", "run", "--rm", "--name", name, "--network", "none",
           "--read-only", "--cap-drop", "ALL", "--security-opt", "no-new-privileges",
           "--pids-limit", "128", "--memory", "1g", "--cpus", "2",
           "--user", "10001:10001", "--tmpfs", "/tmp:rw,noexec,nosuid,nodev,size=128m",
           "--mount", f"type=bind,src={stage.resolve()},dst=/work,readonly",
           "--env", "COVERAGE_FILE=/tmp/.coverage", "--env", "HOME=/tmp"]
    if entrypoint:
        cmd += ["--entrypoint", entrypoint]
    cmd += [IMAGE, *args]
    start = time.monotonic()
    try:
        result = command(cmd, timeout)
        return {"exit_code": result.returncode, "output": result.stdout + result.stderr,
                "seconds": time.monotonic() - start, "timeout": False}
    except subprocess.TimeoutExpired:
        return {"exit_code": None, "output": "Container test timeout", "seconds": time.monotonic()-start, "timeout": True}
    finally:
        # The random name belongs exclusively to this invocation; no other container is touched.
        try:
            command(["docker", "rm", "-f", name], 15)
        except (OSError, subprocess.TimeoutExpired):
            pass


def verify_isolation(stage):
    probe = ("import os,socket,sys; "
             "assert os.getuid()!=0; assert not os.path.exists('/var/run/docker.sock'); "
             "assert not os.path.exists('/work/private_sentinel'); "
             "s=socket.socket(); s.settimeout(2); "
             "r=s.connect_ex(('1.1.1.1',443)); assert r != 0; print('ISOLATION_PROBE_OK')")
    result = run_container(stage, ["-c", probe], 30, entrypoint="python")
    if result["exit_code"] != 0 or "ISOLATION_PROBE_OK" not in result["output"]:
        raise RuntimeError("Isolation probe failed: " + result["output"][-1000:])
    return result


def evaluate(candidate, suite, timeout=60):
    """Use only candidate and one suite; hidden tests never enter public stage."""
    if suite not in ("public", "hidden"):
        raise ValueError("suite must be public or hidden")
    ready()
    with tempfile.TemporaryDirectory(prefix="container_stage_", dir=ROOT / "runs") as tmp:
        stage = Path(tmp)
        shutil.copyfile(candidate, stage / "sync_app.py")
        shutil.copytree(ROOT / (suite + "_tests"), stage / "tests",
                        ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
        verify_isolation(stage)
        args = ["tests", "-q", "--tb=short", "-p", "no:cacheprovider", "--basetemp=/tmp/pytest"]
        if suite == "public":
            args += ["--cov=sync_app", "--cov-report=term", "--cov-fail-under=90"]
        return run_container(stage, args, timeout)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="check runtime and run isolation probe only")
    parser.add_argument("--candidate", type=Path)
    parser.add_argument("--suite", choices=("public", "hidden"), default="public")
    args = parser.parse_args()
    try:
        if args.check:
            ready()
            with tempfile.TemporaryDirectory(prefix="container_probe_", dir=ROOT / "runs") as tmp:
                result = verify_isolation(Path(tmp))
        elif args.candidate:
            result = evaluate(args.candidate, args.suite)
        else:
            parser.error("use --check or --candidate")
        print(json.dumps(result, indent=2))
        return 0 if result["exit_code"] == 0 else 1
    except (OSError, RuntimeError, subprocess.TimeoutExpired) as exc:
        print(json.dumps({"status": "blocked", "error": str(exc)}, indent=2))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
