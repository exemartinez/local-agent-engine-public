"""Run local Gemma 4 26B A4B Q4_0 through the existing coding benchmark."""
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path
import windows_queue

ROOT = windows_queue.ROOT
PROJECT = ROOT.parent.parent
BASE_REPORT = PROJECT / 'documentation/archive/benchmark-history/2026_11_13__01_40_24__all_model_results_comparison.md'
MODEL = ('Gemma 4 26B-A4B', 'Q4_0', 'ggml-org/gemma-4-26B-A4B-it-GGUF', 'gemma-4-26B-A4B-it-Q4_0.gguf', 14.6)


def queue_entry():
    windows_queue.MODELS = [MODEL]
    windows_queue.REPEAT_CONFIGS = {}
    sys.argv = ['windows_queue.py', '--download-reserve-gib', '8.5', '--allow-memory-overcommit', '--disable-low-ram-guard', '--disable-resource-guards']
    return windows_queue.main()


def main():
    stamp = datetime.now().strftime('%Y_%m_%d__%H_%M_%S_%f')
    run = ROOT / 'runs' / (stamp + '__gemma4_benchmark')
    run.mkdir(parents=True)
    report = PROJECT / 'documentation' / 'archive' / 'gemma-attempts' / (stamp + '__all_model_results_with_gemma4.md')
    report.parent.mkdir(parents=True, exist_ok=True)
    original = BASE_REPORT.read_text(encoding='utf-8-sig')
    state = {'status': 'starting', 'model': MODEL[0], 'quantization': MODEL[1], 'file': MODEL[3], 'low_ram_guard_disabled': True, 'resource_guards_disabled': True}
    marker = '| Qwen3.5 35B-A3B | Q4_K_M | Load stopped: low RAM | — | — | 2m 07s |'
    def save():
        (run / 'controller.json').write_text(json.dumps(state, indent=2), encoding='utf-8')
        gemma = f"| Gemma 4 26B-A4B | Q4_0 | {state['status']} | {state.get('public', '—')} | {state.get('hidden', '—')} | {state.get('seconds', '—')} |"
        updated = original.replace(marker, marker + '\n' + gemma, 1)
        updated = updated.replace('Eleven configurations were attempted.', 'The original eleven configurations were attempted; the Gemma 4 row records a separate follow-up.')
        updated += '\n## Gemma 4 follow-up\n\n' + f"Status: **{state['status']}**. Exact queue artifacts: `{state.get('queue', 'not yet available')}`. Download: official ggml-org GGUF; local inference; no cloud API. User disabled resource-based stops for RAM, disk, GPU temperature and monitoring; time limits remain active.\n"
        if state.get('error'):
            updated += f"\nDetails: {state['error']}\n"
        report.write_text(updated, encoding='utf-8')
    if marker not in original:
        raise RuntimeError('Comparison table marker missing; refusing to write misleading report')
    save()
    result = subprocess.run([sys.executable, str(Path(__file__).resolve()), '--queue-entry'], capture_output=True, text=True,
                            creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
    (run / 'queue.stdout.log').write_text(result.stdout, encoding='utf-8')
    (run / 'queue.stderr.log').write_text(result.stderr, encoding='utf-8')
    try:
        data = json.loads(result.stdout)
        queue = Path(data['run']) / 'queue.json'
        row = json.loads(queue.read_text(encoding='utf-8'))['models'][0]
        state.update(status=row['status'], queue=str(queue), sha256=row.get('sha256'), download_seconds=row.get('download_seconds'))
        if row.get('error'):
            state['error'] = row['error']
        if row.get('benchmark'):
            state['benchmark'] = row['benchmark']
            detail = json.loads((Path(row['benchmark']) / 'result.json').read_text(encoding='utf-8'))
            state['seconds'] = round(detail['elapsed_seconds'], 1)
            state['calls'] = len(detail['calls'])
            import re
            for field, check in [('public', (detail.get('public_checks') or [None])[-1]), ('hidden', detail.get('hidden_check'))]:
                if check:
                    matches = re.findall(r'\d+ (?:failed|passed)(?:, \d+ (?:failed|passed))*', check.get('output', ''))
                    state[field] = matches[-1] if matches else 'no score'
    except (ValueError, KeyError, OSError, IndexError) as exc:
        state.update(status='controller_error', error=f'{type(exc).__name__}: {exc}; inspect queue logs')
    save()
    print(json.dumps({'status': state['status'], 'run': str(run), 'report': str(report)}, indent=2))
    return 0 if state['status'] in ('pass', 'fail', 'incomplete_generation') else 1


if __name__ == '__main__':
    raise SystemExit(queue_entry() if '--queue-entry' in sys.argv else main())
