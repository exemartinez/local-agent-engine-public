# API synchronization benchmark

The reference implementation is `../../src/sync_app.py`. The public specification, plan, tasks, skeleton, and tests are in this directory. Hidden tests are withheld from model prompts and used only after the final public repair attempt.

From the repository root in PowerShell, verify the reference with the project virtual environment:

```powershell
.venv\Scripts\python.exe -m pip install -r benchmarks\api_sync\requirements.txt
$env:PYTHONPATH = (Join-Path (Get-Location) 'src')
$env:PYTHONPATH += ";$(Join-Path (Get-Location) 'benchmarks\api_sync')"
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD = '1'
.venv\Scripts\python.exe -m pytest -p pytest_cov -p network_guard benchmarks\api_sync\public_tests benchmarks\api_sync\hidden_tests -q --cov=sync_app --cov-report=term-missing --cov-fail-under=90
```

Generate an initial candidate with, for example:

```powershell
.venv\Scripts\python.exe benchmarks\api_sync\runner.py --model qwen3-coder:30b --timeout 900
```

Each run gets a new directory in `runs/`, with the exact public prompt, raw response, extracted code, and generation timing. This driver generates **one attempt only**; it does not run tests or implement the full timed loop. `repair_once.py --help` describes a separate, manually invoked single repair request. Do not feed hidden test results to a model.

Before executing any generated module, review it and its imports for host filesystem, process, and network operations. A Python virtual environment is not a security sandbox. The user chose reviewed execution in the project environment for these trials; this requires manual intervention and cannot prove isolation. Do not execute an unreviewed candidate automatically.

The single-generation driver does not run tests or measure end-to-end time. For a manual test, put the reviewed `sync_app.py` in a unique candidate directory, set `PYTHONPATH` to that directory, and run the public tests from there. Keep `--basetemp` in that candidate directory. Use the hidden suite only after the last public repair, and do not feed its failures back to the model. Save test logs and record any manual review, test, and feedback time.

The review-gated `timed_loop.py` coordinator automates the bounded loop and records wall-clock time, including review waits:

```powershell
.venv\Scripts\python.exe benchmarks\api_sync\timed_loop.py --model qwen3.5:4b
```

Its `chat-v3-public-tests-in-repairs` protocol uses Ollama's chat endpoint, an 8192-token output limit, `think: false`, and the same bounded repair loop for each model. Public test source is included in repair prompts as well as the initial prompt, so parameterized inputs are available. It enables `network_guard.py` during tests to block ordinary Python socket connections. This is defense in depth for reviewed code, not a security sandbox, and malicious code could bypass it. Earlier runs used different protocols and should be reported separately.

The Windows queue (`windows_queue.py`) waits before each model download for three consecutive available-RAM readings at least 5 GiB with a maximum 512 MiB spread, sampled 10 seconds apart. It stops if this does not happen within 10 minutes or the overall deadline. Readings are saved in `queue.json`. These are operational heuristics, not proof that a particular model fits; the Q4 load previously exhausted memory despite recovery. The queue has not been restarted after this change. Windows host candidate tests use a static gate and socket guard; neither is an OS security boundary.

The revised queue uses a 16,384-token server context and a 2,048-token reasoning budget. Empty or length-truncated responses are recorded as incomplete generations rather than test failures. Before download and again before loading, it estimates a memory budget from available RAM and free VRAM, reserves 1 GiB RAM and 512 MiB VRAM, budgets 1 GiB for context/runtime, and permits a heuristic 1 GiB existing paging allowance. Model files exceeding this estimate are skipped, not scored as coding failures. The live watchdog remains necessary because actual GPU placement and context allocation vary. Reproducibility across model formats or reasoning templates is not guaranteed; examine raw outputs.

Reference result on 2026-11-05: 39 tests passed, 98.17% line coverage. See `../../documentation/archive/benchmark-history/2026_11_05__00_46_14__api_sync_comparison.md` for provisional results and caveats.
