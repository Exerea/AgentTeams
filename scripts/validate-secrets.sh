#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repo_root"

if ! command -v gitleaks >/dev/null 2>&1; then
  echo "ERROR: gitleaks is required." >&2
  exit 1
fi

gitleaks detect --source . --no-git --config .gitleaks.toml --redact

echo "secret scan is valid"
