"""Build a read-only index of historical local benchmark run directories."""
import json
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent
RUNS = ROOT / 'runs'


def index():
    stamp = datetime.now().strftime('%Y_%m_%d__%H_%M_%S')
    path = ROOT.parent.parent / 'documentation' / 'reports' / f'{stamp}__benchmark_run_folder_index.md'
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = ['# Benchmark run folder index', '',
             'Existing folder names and contents are unchanged. Model names come from each saved result; queue/controller folders may contain multiple models.',
             'A dash means the metadata did not identify a model. Outcome is the stored status, not a claim that tests ran.', '',
             '| Folder | Model or type | Status |', '| --- | --- | --- |']
    for folder in sorted(RUNS.iterdir(), reverse=True):
        if not folder.is_dir():
            continue
        model, status = '—', '—'
        metadata = next((folder / n for n in ('result.json', 'controller.json', 'queue.json') if (folder / n).is_file()), None)
        if metadata:
            try:
                data = json.loads(metadata.read_text(encoding='utf-8-sig'))
                raw = data.get('model')
                if raw:
                    model = str(raw).replace('\\', '/').split('/')[-1].replace('|', '\\|')
                elif isinstance(data.get('models'), list):
                    model = f"{len(data['models'])} configurations (queue/controller)"
                status = str(data.get('status', '—')).replace('|', '\\|')
            except (OSError, ValueError, TypeError):
                model, status = 'metadata unreadable', 'unknown'
        relative = '../../benchmarks/api_sync/runs/' + folder.name + '/'
        lines.append(f'| [{folder.name}]({relative}) | {model} | {status} |')
    path.write_text('\n'.join(lines) + '\n', encoding='utf-8')
    print(path)


if __name__ == '__main__':
    index()
