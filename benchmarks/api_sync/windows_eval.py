"""Conservative Windows host test gate. This is NOT an OS security sandbox."""
import ast
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time

from runner import ROOT

ALLOWED_MODULES = {"argparse", "datetime", "json", "logging", "math", "os", "re", "sqlite3", "sys", "time", "typing",
                   "urllib", "urllib.request", "urllib.error", "urllib.parse"}
FORBIDDEN_NAMES = {"open", "exec", "eval", "compile", "__import__", "getattr", "setattr", "delattr", "globals", "locals", "vars", "breakpoint", "input", "memoryview", "object", "type", "super", "help"}
FORBIDDEN_ATTRS = {"system", "popen", "startfile", "spawn", "fork", "exec", "eval", "open", "remove", "unlink", "rmdir", "rename", "replace", "chmod", "chdir", "walk", "listdir", "scandir", "getcwd", "environb", "getenvb", "putenv", "unsetenv", "modules", "path_hooks", "meta_path", "builtin_module_names", "settrace", "setprofile", "load_extension", "enable_load_extension", "iterdump", "backup", "FileHandler", "FileType", "urlretrieve", "urlopen_cached", "run", "Popen", "system", "ctypes", "os", "sys", "subprocess", "builtins"}


def screen(source):
    """Reject dangerous syntax before import; defense in depth, not a sandbox."""
    try:
        tree = ast.parse(source)
    except SyntaxError as exc:
        return f"Invalid Python: {exc}"
    safe_type_calls = {id(n.value) for n in ast.walk(tree) if isinstance(n, ast.Attribute) and n.attr == "__name__"
                       and isinstance(n.value, ast.Call) and isinstance(n.value.func, ast.Name)
                       and n.value.func.id == "type" and len(n.value.args) == 1
                       and isinstance(n.value.args[0], ast.Name) and not n.value.keywords}
    safe_type_names = {id(n.func) for n in ast.walk(tree) if isinstance(n, ast.Call) and id(n) in safe_type_calls}
    sensitive_aliases = {"os": "os", "sys": "sys"}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name in ("os", "sys"):
                    sensitive_aliases[alias.asname or alias.name] = alias.name
    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            modules = [n.name for n in node.names] if isinstance(node, ast.Import) else [node.module or ""]
            if any(m not in ALLOWED_MODULES for m in modules) or (isinstance(node, ast.ImportFrom) and (node.level or any(n.name == "*" for n in node.names))):
                return f"Import outside allowed benchmark subset: {modules}"
            if isinstance(node, ast.ImportFrom) and any(n.name in FORBIDDEN_NAMES or n.name in FORBIDDEN_ATTRS or n.name.startswith("__") for n in node.names):
                return "Forbidden imported symbol"
            if isinstance(node, ast.ImportFrom) and node.module in ("os", "sys"):
                allowed = {"os": {"getenv", "environ"}, "sys": {"argv", "stderr", "stdout", "exit"}}[node.module]
                if any(n.name not in allowed for n in node.names):
                    return "Forbidden operating-system import"
        if isinstance(node, ast.Name) and ((node.id in FORBIDDEN_NAMES and id(node) not in safe_type_names) or node.id.startswith("__") and node.id != "__name__"):
            return f"Forbidden name: {node.id}"
        if isinstance(node, ast.Attribute) and ((node.attr.startswith("__") and id(node.value) not in safe_type_calls) or node.attr in FORBIDDEN_ATTRS):
            return f"Forbidden attribute: {node.attr}"
        if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name) and node.value.id in sensitive_aliases:
            allowed = {"os": {"getenv", "environ"}, "sys": {"argv", "stderr", "stdout", "exit"}}[sensitive_aliases[node.value.id]]
            if node.attr not in allowed:
                return "Forbidden operating-system attribute"
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            if re.search(r"(?i)([a-z]:[\\/]|\\\\|\battach\s+database\b|\bvacuum\s+into\b|load_extension|/etc/|/home/|/users/)", node.value):
                return "Forbidden filesystem or SQL escape string"
        if isinstance(node, (ast.Global, ast.Nonlocal)):
            return "Global/nonlocal declarations are outside the allowed subset"
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) and node.decorator_list:
            return "Decorators are outside the allowed subset"
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            for default in [*node.args.defaults, *(v for v in node.args.kw_defaults if v is not None)]:
                try:
                    ast.literal_eval(default)
                except (ValueError, TypeError):
                    return "Function defaults must be literals"
            if any(isinstance(n, ast.Call) for annotation in [node.returns, *(a.annotation for a in [*node.args.posonlyargs, *node.args.args, *node.args.kwonlyargs])] if annotation is not None for n in ast.walk(annotation)):
                return "Calls in annotations are not allowed"
        if isinstance(node, ast.ClassDef) and (node.bases or node.keywords or any(not isinstance(x, (ast.FunctionDef, ast.Pass)) and not (isinstance(x, ast.Expr) and isinstance(x.value, ast.Constant) and isinstance(x.value.value, str)) for x in node.body)):
            # Ordinary exception subclasses are allowed, but no arbitrary class-body code.
            if node.keywords or not all(isinstance(x, ast.Name) and x.id in {"Exception", "ValueError", "RuntimeError"} for x in node.bases) or any(not isinstance(x, (ast.FunctionDef, ast.Pass)) and not (isinstance(x, ast.Expr) and isinstance(x.value, ast.Constant) and isinstance(x.value.value, str)) for x in node.body):
                return "Unsafe class definition"
    for statement in tree.body:
        if isinstance(statement, (ast.Import, ast.ImportFrom, ast.FunctionDef, ast.ClassDef)):
            continue
        if isinstance(statement, ast.Expr) and isinstance(statement.value, ast.Constant) and isinstance(statement.value.value, str):
            continue
        if isinstance(statement, (ast.Assign, ast.AnnAssign)):
            value = statement.value
            if value is None:
                continue
            try:
                ast.literal_eval(value)
                continue
            except (ValueError, TypeError):
                return "Top-level assignment must be a literal"
        if (isinstance(statement, ast.If) and not statement.orelse and isinstance(statement.test, ast.Compare)
                and isinstance(statement.test.left, ast.Name) and statement.test.left.id == "__name__"
                and len(statement.test.ops) == 1 and isinstance(statement.test.ops[0], ast.Eq)
                and len(statement.test.comparators) == 1 and isinstance(statement.test.comparators[0], ast.Constant)
                and statement.test.comparators[0].value == "__main__"):
            continue
        return f"Top-level action rejected: {type(statement).__name__}"
    return None


def evaluate(candidate, suite, timeout=60):
    if suite not in ("public", "hidden"):
        raise ValueError("invalid suite")
    source = candidate.read_text(encoding="utf-8")
    rejection = screen(source)
    if rejection:
        return {"exit_code": 1, "output": "SAFETY_GATE_REJECTED: " + rejection, "seconds": 0, "safety_rejected": True}
    stage = candidate.parent / (candidate.stem + "__host_" + suite)
    stage.mkdir(exist_ok=False)
    (stage / "sync_app.py").write_text(source, encoding="utf-8")
    tests = ROOT / (suite + "_tests")
    env = {k: v for k, v in os.environ.items() if k.upper() in {"SYSTEMROOT", "WINDIR", "PATH", "TEMP", "TMP", "COMSPEC", "PATHEXT"}}
    env.update(PYTHONPATH=os.pathsep.join((str(stage), str(ROOT))), PYTEST_DISABLE_PLUGIN_AUTOLOAD="1", COVERAGE_FILE=str(stage / ".coverage"))
    args = [sys.executable, "-m", "pytest", "-p", "pytest_cov", "-p", "network_guard", str(tests), "-q", "--tb=short",
            "-o", "cache_dir=" + str(stage / ".pytest_cache"), "--basetemp=" + str(stage / ".test_tmp")]
    if suite == "public":
        args += ["--cov=sync_app", "--cov-report=term", "--cov-fail-under=90"]
    started = time.monotonic()
    try:
        result = subprocess.run(args, cwd=stage, env=env, capture_output=True, text=True, timeout=timeout)
        return {"exit_code": result.returncode, "output": result.stdout + result.stderr, "seconds": time.monotonic()-started}
    except subprocess.TimeoutExpired:
        return {"exit_code": None, "output": "Test timeout", "seconds": time.monotonic()-started, "timeout": True}
