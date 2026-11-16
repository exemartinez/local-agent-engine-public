#!/usr/bin/env bash
# Dry-run by default; use --apply or --rollback PATH. Run from any directory.
set -euo pipefail
project_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
exec "$project_root/.venv/Scripts/python.exe" "$project_root/scripts/rename_model_runs.py" "$@"
