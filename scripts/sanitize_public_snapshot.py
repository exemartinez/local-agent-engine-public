"""Mask sensitive machine-specific diagnostics in a publishable repository copy.

This intentionally targets diagnostic artifacts, not model-generated source or
benchmark measurements. Run on a copy; retain private originals separately.
"""
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / 'benchmarks' / 'results'
DOCS = ROOT / 'documentation' / 'archive' / 'system-investigations'
PATH_PATTERN = re.compile(r'(?i)\b[A-Z]:[\\/][^\r\n`|";]*')
IDENTIFIERS = re.compile(r'(?i)\b(?:GPU-REDACTED|REDACTED-SID|GPU-[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}|S-1-5-21-(?:\d+-){2,}\d+)\b')


def mask(value):
    if isinstance(value, str):
        value = PATH_PATTERN.sub('***', value)
        value = IDENTIFIERS.sub('***', value)
        return value
    if isinstance(value, list):
        return [mask(x) for x in value]
    if isinstance(value, dict):
        return {k: mask(v) for k, v in value.items()}
    return value


def main():
    changed = []
    json_files = list(RESULTS.glob('*__disk_inventory.json')) + [RESULTS / 'hardware_inventory.json']
    for path in json_files:
        if not path.is_file():
            continue
        obj = json.loads(path.read_text(encoding='utf-8-sig'))
        sanitized = mask(obj)
        if obj != sanitized:
            path.write_text(json.dumps(sanitized, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
            changed.append(path)
    for path in [*DOCS.glob('*disk_inventory.md'), *DOCS.glob('*disk_space_investigation.md'),
                 ROOT / 'benchmarks/logs/nvidia-smi.txt', RESULTS / 'ollama-install.stderr.log']:
        if not path.is_file():
            continue
        original = path.read_text(encoding='utf-8-sig')
        sanitized = mask(original)
        if original != sanitized:
            path.write_text(sanitized, encoding='utf-8')
            changed.append(path)
    print(f'Sanitized {len(changed)} diagnostic files; redacted paths and identifiers are marked ***.')


if __name__ == '__main__':
    main()
