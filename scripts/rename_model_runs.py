"""Rename old unattended run folders and update repository text references.

Default is dry-run. --apply creates a rollback backup and manifest; --rollback
restores files and folder names from that manifest. Stop all benchmarks first.
"""
import argparse
import json
import os
import re
import shutil
from datetime import datetime
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[1]
RUNS = PROJECT / 'benchmarks' / 'api_sync' / 'runs'
BACKUPS = PROJECT / 'benchmarks' / 'results' / 'run_traceability_backups'
SKIP_DIRS = {'.git', '.venv', '.idea', 'node_modules', '__pycache__', 'run_traceability_backups', 'model-downloads', 'runtime'}
SKIP_EXTS = {'.exe', '.dll', '.gguf', '.zip', '.png', '.jpg', '.jpeg', '.gif', '.pdf', '.pyc', '.db', '.sqlite', '.db3', '.bin', '.pyd', '.so', '.ico'}


def make_plan():
    plan = {}
    pattern = re.compile(r"\d{4}_\d\d_\d\d__\d\d_\d\d_\d\d_\d+__(unattended|overnight_moe|windows_queue)")
    for folder in sorted(RUNS.iterdir()):
        match = pattern.fullmatch(folder.name)
        if not match or not folder.is_dir():
            continue
        if folder.is_symlink() or folder.resolve().parent != RUNS.resolve():
            raise RuntimeError(f'Unsafe run path: {folder}')
        kind = match.group(1)
        if kind == 'unattended':
            data = json.loads((folder / 'result.json').read_text(encoding='utf-8-sig'))
            model = str(data.get('model', '')).replace('\\', '/').rsplit('/', 1)[-1]
            if not model.lower().endswith('.gguf'):
                raise RuntimeError(f'Cannot determine model for {folder}')
            model = model[:-5]
        elif kind == 'overnight_moe':
            data = json.loads((folder / 'summary.json').read_text(encoding='utf-8-sig'))
            model = str(data.get('model', ''))
            if not model:
                raise RuntimeError(f'Cannot determine model for {folder}')
        else:
            data = json.loads((folder / 'queue.json').read_text(encoding='utf-8-sig'))
            models = data.get('models', [])
            indices = {int(m.group(1)) for f in folder.glob('*__runner.*.log')
                       if (m := re.match(r'^(\d+)_\d+__runner\.', f.name))}
            if len(indices) == 1 and next(iter(indices)) < len(models):
                selected = models[next(iter(indices))]
                model = selected['model'] + '-' + selected['quantization']
            elif len(models) == 1:
                model = models[0]['model'] + '-' + models[0]['quantization']
            else:
                model = 'multi-model'
        label = re.sub(r'[^A-Za-z0-9._-]+', '-', model).strip('._-')[:120]
        if not label:
            raise RuntimeError(f'Empty model label for {folder}')
        new_name = folder.name[:-(len(kind) + 2)] + '__' + label + '__' + kind
        target = RUNS / new_name
        if target.exists():
            raise RuntimeError(f'Target already exists: {target}')
        plan[folder.name] = new_name
    if len(set(plan.values())) != len(plan):
        raise RuntimeError('Duplicate rename target')
    return plan


def files():
    for root, dirs, names in os.walk(PROJECT, followlinks=False):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS and not (Path(root) / d).is_symlink()]
        for name in names:
            path = Path(root) / name
            if path.is_symlink() or path.suffix.lower() in SKIP_EXTS:
                continue
            yield path


def replacements(raw, plan):
    # Folder names are ASCII; replacing only exact names preserves byte encoding.
    for old, new in plan.items():
        raw = raw.replace(old.encode('ascii'), new.encode('ascii'))
        raw = raw.replace(old.encode('utf-16-le'), new.encode('utf-16-le'))
        raw = raw.replace(old.encode('utf-16-be'), new.encode('utf-16-be'))
    return raw


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    action = parser.add_mutually_exclusive_group()
    action.add_argument('--apply', action='store_true')
    action.add_argument('--rollback', type=Path, metavar='MANIFEST')
    args = parser.parse_args()
    if args.rollback:
        manifest_path = args.rollback.resolve()
        if not manifest_path.is_relative_to(BACKUPS.resolve()):
            raise RuntimeError('Manifest must be inside the project traceability backup directory')
        manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
        for old, new in manifest['renames'].items():
            src, dst = RUNS / new, RUNS / old
            if src.is_symlink() or not src.is_dir() or src.resolve().parent != RUNS.resolve() or dst.exists():
                raise RuntimeError(f'Rollback directory preflight failed: {src} -> {dst}')
        for old, new in manifest['renames'].items():
            (RUNS / new).rename(RUNS / old)
        for entry in manifest['files']:
            destination = PROJECT / entry['path']
            backup = manifest_path.parent / entry['backup']
            if not destination.resolve().is_relative_to(PROJECT.resolve()) or not backup.resolve().is_relative_to(manifest_path.parent.resolve()):
                raise RuntimeError('Unsafe rollback file')
            destination.write_bytes(backup.read_bytes())
        print(f"Restored {len(manifest['renames'])} folders and {len(manifest['files'])} files")
        return
    plan = make_plan()
    changes = []
    for path in files():
        raw = path.read_bytes()
        # Skip binary data except recognized UTF-16 text with BOM.
        if b'\0' in raw[:4096] and not raw.startswith((b'\xff\xfe', b'\xfe\xff')):
            continue
        updated = replacements(raw, plan)
        if updated != raw:
            changes.append((path, raw, updated))
    print(f'{len(plan)} folder renames; {len(changes)} text files with references')
    for old, new in plan.items():
        print(f'{old} -> {new}')
    if not args.apply or not plan:
        return
    backup_dir = BACKUPS / datetime.now().strftime('%Y_%m_%d__%H_%M_%S_%f')
    backup_dir.mkdir(parents=True)
    manifest = {'renames': plan, 'files': []}
    for i, (path, raw, updated) in enumerate(changes):
        backup = f'{i:06d}.bak'
        (backup_dir / backup).write_bytes(raw)
        manifest['files'].append({'path': str(path.relative_to(PROJECT)), 'backup': backup})
    manifest_path = backup_dir / 'manifest.json'
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding='utf-8')
    # Replace references before rename; paths in manifest remain the original ones.
    for path, raw, updated in changes:
        path.write_bytes(updated)
    for old, new in plan.items():
        src, dst = RUNS / old, RUNS / new
        if src.is_symlink() or src.resolve().parent != RUNS.resolve() or dst.exists():
            raise RuntimeError(f'Unsafe move: {src} -> {dst}; restore using {manifest_path}')
        src.rename(dst)
    print(f'Applied. Rollback manifest: {manifest_path}')


if __name__ == '__main__':
    main()
