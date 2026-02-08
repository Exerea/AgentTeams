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

bash ./scripts/validate-states-index.sh ./.codex/states/_index.yaml

for f in ./.codex/states/TASK-*.yaml; do
  bash ./scripts/validate-task-state.sh "$f"
done

"$py_bin" ./scripts/validate-doc-consistency.py
"$py_bin" ./scripts/validate-self-update-evidence.py --help >/dev/null
"$py_bin" ./scripts/validate-scenarios-structure.py
"$py_bin" ./scripts/validate-rule-examples-coverage.py
"$py_bin" ./scripts/detect-role-gaps.py
"$py_bin" ./scripts/validate-role-gap-review.py
"$py_bin" ./scripts/validate-deprecated-assets.py
"$py_bin" ./scripts/validate-chat-declaration.py
if [[ -f ./knowledge/incidents/_index.yaml ]]; then
  "$py_bin" ./scripts/validate-incident-registry.py
else
  echo "WARN [INCIDENT_REGISTRY_MISSING] knowledge/incidents/_index.yaml not found; registry validation skipped."
fi
"$py_bin" ./scripts/validate-incident-sync-freshness.py
"$py_bin" ./scripts/detect-recurring-incident.py
bash ./scripts/validate-secrets.sh

echo "repository validation passed"
