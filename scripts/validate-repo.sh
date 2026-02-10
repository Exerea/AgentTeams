#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repo_root"

if command -v python3 >/dev/null 2>&1; then
  py_bin="python3"
elif command -v python >/dev/null 2>&1; then
  py_bin="python"
else
  echo "ERROR: python or python3 is required." >&2
  exit 1
fi

"$py_bin" ./scripts/validate-takt-task.py --path .takt/tasks
"$py_bin" ./scripts/validate-takt-evidence.py --allow-empty-logs
"$py_bin" ./scripts/validate-doc-consistency.py
"$py_bin" ./scripts/validate-scenarios-structure.py
bash ./scripts/validate-secrets.sh

echo "repository validation passed"
