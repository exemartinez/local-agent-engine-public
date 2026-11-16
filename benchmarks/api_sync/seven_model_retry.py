"""Resume seven unmeasured MoE configurations with durable reports and safe stops.

Local inference only. Windows test gate is NOT a security sandbox. No model
files, personal data, reports or existing runs are removed by this controller.
"""
import argparse
import copy
import json
import os
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

from windows_queue import GIB, MODELS, ROOT, wait_for_memory, gpu
import time

TARGETS = {
    ("GPT-OSS 20B", "Q3_K_M"), ("GPT-OSS 20B", "Q4_K_M"),
    ("Qwen3-Coder 30B-A3B", "Q3_K_S"),
    ("GLM-4.7-Flash 30B-A3B", "Q3_K_S"), ("GLM-4.7-Flash 30B-A3B", "Q2_K"),
    ("GLM-4.7-Flash 30B-A3B", "Q4_K_M"), ("Qwen3.5 35B-A3B", "Q4_K_M"),
}
RESERVE_GIB = 8.5


def write_json(path, data):
    temporary = path.with_suffix(path.suffix + '.tmp')
    temporary.write_text(json.dumps(data, indent=2), encoding='utf-8')
    os.replace(temporary, path)


def prepare_single(source, key):
    state = copy.deepcopy(source)
    if state.get('status') == 'running':
        raise ValueError('Cannot resume a running queue')
    matches = [m for m in state['models'] if (m['model'], m['quantization']) == key]
    if len(matches) != 1:
        raise ValueError(f'Expected one matching configuration: {key}')
    row = matches[0]
    # Previous queue and underlying raw evidence are retained unchanged.
    for field in ('result_summary', 'error', 'cleanup_error', 'replicates', 'benchmark'):
        row.pop(field, None)
    row['status'] = 'pending'
    return state


def low_ram_guard_only(benchmark):
    """Continue only if the last three telemetry samples show RAM, not heat/disk."""
    try:
        samples = [json.loads(line) for line in (Path(benchmark) / 'samples.jsonl').read_text(encoding='utf-8').splitlines() if line.strip()]
        recent = samples[-3:]
        return len(recent) == 3 and all(
            sample['ram_available_bytes'] < 256 * 1024 ** 2
            and sample['disk_free_bytes'] >= 8 * GIB and sample['gpu_c'] < 85
            for sample in recent)
    except (OSError, ValueError, KeyError, TypeError):
        return False


def recover_after_guard():
    recovery = wait_for_memory(time.monotonic() + 600, min_available=3 * GIB)
    if not recovery['stable']:
        return False, recovery
    try:
        recovery['gpu_c'] = gpu()['gpu_c']
        recovery['disk_free_bytes'] = shutil.disk_usage(ROOT).free
        return recovery['gpu_c'] < 85 and recovery['disk_free_bytes'] >= 8 * GIB, recovery
    except Exception as exc:
        recovery['error'] = str(exc)
        return False, recovery


def report_text(control):
    rows = ['# Seven-configuration unattended benchmark', '',
            f"Status: **{control['status']}**", '',
            'Local inference; Windows static gate and socket guard are not an OS sandbox.',
            'Model-fit estimates and stabilization waits are bypassed; emergency RAM, disk, GPU and monitor guards remain active.',
            'A RAM-only guard advances after confirmed recovery; heat, disk and monitoring failures halt the controller. Pending entries are not coding failures.', '',
            '| Model | Quantization | Prior outcome | Retry outcome | Calls | Elapsed s | Evidence |',
            '| --- | --- | --- | --- | ---: | ---: | --- |']
    for item in control['models']:
        link = item.get('benchmark') or item.get('queue') or '—'
        rows.append(f"| {item['model']} | {item['quantization']} | {item['prior_status']} | {item['status']} | {item.get('calls', '—')} | {item.get('seconds', '—')} | `{link}` |")
    rows += ['', f"Disk reserve: {RESERVE_GIB} GiB plus the model download. Passes, failures and incomplete generations advance; RAM-only stops advance after recovery; other resource/monitor errors stop.",
             'Reported elapsed time excludes download unless a queue record explicitly says otherwise.',
             f"Original queue (preserved): `{control['source_queue']}`.",
             'Raw results and model-generated code are retained in their run directories. Only downloads owned by the underlying queue are cleaned up.',
             'A coding pass requires public tests, 90% coverage and hidden tests; loading stops are not quality scores.']
    rows += ['', '## Previous benchmark results (preserved)', '', '| Model | Quantization | Prior status | Summary |', '| --- | --- | --- | --- |']
    for prior in control.get('prior_results', []):
        rows.append(f"| {prior['model']} | {prior['quantization']} | {prior['status']} | {prior.get('result_summary', '')} |")
    rows += ['', 'Historical small-model and Pi results: `documentation/archive/benchmark-history/2026_11_10__13_39_32__complete_local_model_benchmark_comparison.md`.']
    if control.get('reason'):
        rows += ['', f"Reason: {control['reason']}"]
    return '\n'.join(rows) + '\n'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, default=ROOT / 'runs/2026_11_09__01_26_42_255477__multi-model__windows_queue/queue.json')
    parser.add_argument('--resume-controller', type=Path, help='preserve results and retry only pending entries from a stopped controller')
    args = parser.parse_args()
    source = json.loads(args.source.read_text(encoding='utf-8-sig'))
    if source.get('status') == 'running':
        raise SystemExit('Source queue is still running; refusing to start')
    manifest = {(m[0], m[1]): m for m in MODELS}
    if not TARGETS <= manifest.keys():
        raise SystemExit('Seven-model manifest no longer matches the queue')
    prior = {(r['model'], r['quantization']): r for r in source['models']}
    if not TARGETS <= prior.keys():
        raise SystemExit('Source queue does not contain all seven configurations')
    stamp = datetime.now().strftime('%Y_%m_%d__%H_%M_%S_%f')
    run = ROOT / 'runs' / (stamp + '__seven_retry')
    run.mkdir(parents=True)
    report = ROOT.parent.parent / 'documentation' / 'archive' / 'retry-snapshots' / (stamp + '__seven_model_retry_report.md')
    report.parent.mkdir(parents=True, exist_ok=True)
    selected = [m for m in MODELS if (m[0], m[1]) in TARGETS]
    control = {'status': 'running', 'source_queue': str(args.source.resolve()), 'prior_results': source['models'], 'models': [
        {'model': m[0], 'quantization': m[1], 'prior_status': prior[(m[0], m[1])]['status'], 'status': 'pending'} for m in selected]}

    if args.resume_controller:
        previous = json.loads(args.resume_controller.read_text(encoding='utf-8-sig'))
        if previous.get('status') == 'running':
            raise SystemExit('Cannot resume a running controller')
        previous_items = {(x['model'], x['quantization']): x for x in previous['models']}
        if set(previous_items) != TARGETS:
            raise SystemExit('Previous controller does not match target manifest')
        control['models'] = [copy.deepcopy(previous_items[(m[0], m[1])]) for m in selected]
        if any(item['status'] == 'running' for item in control['models']):
            raise SystemExit('Previous controller has an unresolved running entry')
        control['resumed_controller'] = str(args.resume_controller.resolve())

    def save():
        write_json(run / 'controller.json', control)
        report.write_text(report_text(control), encoding='utf-8')

    save()
    for index, (model, quant, repo, filename, expected_gb) in enumerate(selected):
        item = control['models'][index]
        if item['status'] != 'pending':
            continue
        free = shutil.disk_usage(ROOT).free
        required = int(expected_gb * 1e9 + RESERVE_GIB * GIB)
        if free < required:
            control.update(status='blocked_disk', reason=f'{model} {quant}: {free / 1e9:.2f} GB free; at least {required / 1e9:.2f} GB required including reserve.')
            save()
            break
        resume = run / f'{index:02d}__resume.json'
        write_json(resume, prepare_single(source, (model, quant)))
        item['status'] = 'running'
        save()
        command = [sys.executable, str(ROOT / 'windows_queue.py'), '--resume-from', str(resume),
                   '--download-reserve-gib', str(RESERVE_GIB), '--allow-memory-overcommit']
        result = subprocess.run(command, capture_output=True, text=True, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        (run / f'{index:02d}__stdout.log').write_text(result.stdout, encoding='utf-8')
        (run / f'{index:02d}__stderr.log').write_text(result.stderr, encoding='utf-8')
        try:
            output = json.loads(result.stdout)
            child_path = Path(output['run']) / 'queue.json'
            child = json.loads(child_path.read_text(encoding='utf-8'))
            row = next(r for r in child['models'] if (r['model'], r['quantization']) == (model, quant))
            item.update(status=row['status'], queue=str(child_path), benchmark=row.get('benchmark'))
            if row.get('replicates'):
                item.update(calls=row['replicates'][-1]['calls'], seconds=row['replicates'][-1]['seconds'])
            if row.get('error'):
                item['error'] = row['error']
            if child['status'] == 'resource_guard' and row['status'] == 'resource_guard' and row.get('benchmark') and low_ram_guard_only(row['benchmark']):
                recovered, recovery = recover_after_guard()
                item['recovery'] = recovery
                save()
                if recovered:
                    continue
            if result.returncode != 0 or child['status'] != 'complete' or row['status'] not in ('pass', 'fail', 'incomplete_generation'):
                control.update(status='stopped', reason=f"{model} {quant}: queue={child['status']}, model={row['status']}; inspect child evidence.")
                save()
                break
        except (ValueError, OSError, KeyError, StopIteration) as exc:
            item['status'] = 'controller_error'
            control.update(status='stopped', reason=f'Cannot read runner result: {exc}; see stdout/stderr logs.')
            save()
            break
        save()
    else:
        control['status'] = 'complete'
        save()
    print(json.dumps({'status': control['status'], 'run': str(run), 'report': str(report)}, indent=2))
    return 0 if control['status'] == 'complete' else 1


if __name__ == '__main__':
    raise SystemExit(main())
