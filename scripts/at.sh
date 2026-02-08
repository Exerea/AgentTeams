#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
script_path="$script_dir/at.py"

if [[ ! -f "$script_path" ]]; then
  echo "ERROR [PATH_LAYOUT_INVALID] missing script: $script_path"
  exit 1
fi

if command -v python3 >/dev/null 2>&1; then
  exec python3 "$script_path" "$@"
fi

if command -v python >/dev/null 2>&1; then
  exec python "$script_path" "$@"
fi

echo "ERROR [PATH_LAYOUT_INVALID] python runtime not found (python3 or python required)."
echo "Next: Install python, then retry: agentteams init <git-url>"
echo "Compat: ./at init <git-url>"
exit 1
