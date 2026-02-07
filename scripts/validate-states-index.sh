#!/usr/bin/env bash
set -euo pipefail

index_file="${1:-./.codex/states/_index.yaml}"

if [[ ! -f "$index_file" ]]; then
  echo "ERROR: index file not found: $index_file" >&2
  exit 1
fi

if command -v python3 >/dev/null 2>&1; then
  py_bin="python3"
elif command -v python >/dev/null 2>&1; then
  py_bin="python"
else
  echo "ERROR: python or python3 is required." >&2
  exit 1
fi

"$py_bin" - "$index_file" <<'PY'
import re
import sys
from pathlib import Path

index_path = Path(sys.argv[1])
text = index_path.read_text(encoding="utf-8").lstrip("\ufeff")
lines = text.splitlines()

required_top = ["version", "project", "tasks", "updated_at"]
allowed_status = {"todo", "in_progress", "in_review", "blocked", "done"}
required_task = ["id", "title", "status", "assignee", "file", "updated_at"]
errors = []

keys = []
for ln in lines:
    m = re.match(r"^([A-Za-z_][A-Za-z0-9_]*)\s*:", ln)
    if m:
        k = m.group(1)
        if k not in keys:
            keys.append(k)

missing_top = [k for k in required_top if k not in keys]
extra_top = [k for k in keys if k not in required_top]
if missing_top:
    errors.append(f"missing top-level keys: {', '.join(missing_top)}")
if extra_top:
    errors.append(f"unexpected top-level keys: {', '.join(extra_top)}")

section = None
project_keys = set()
in_task = False
task_idx = 0
task_keys = set()
status = ""
file_name = ""
base_dir = index_path.parent

def validate_task(i: int, keys_: set, status_: str, file_: str):
    miss = [k for k in required_task if k not in keys_]
    if miss:
        errors.append(f"tasks[{i}] missing keys: {', '.join(miss)}")
    if status_ and status_ not in allowed_status:
        errors.append(f"tasks[{i}].status invalid: '{status_}'")
    if file_:
        if not re.match(r"^TASK-\d{5}-[a-z0-9]+(?:-[a-z0-9]+)*\.yaml$", file_):
            errors.append(f"tasks[{i}].file invalid naming: '{file_}'")
        elif not (base_dir / file_).exists():
            errors.append(f"tasks[{i}].file not found: '{file_}'")

for ln in lines:
    m_top = re.match(r"^([A-Za-z_][A-Za-z0-9_]*)\s*:", ln)
    if m_top:
        if section == "tasks" and in_task:
            validate_task(task_idx, task_keys, status, file_name)
        section = m_top.group(1)
        in_task = False
        task_keys = set()
        status = ""
        file_name = ""
        continue

    if section == "project":
        m_proj = re.match(r"^\s{2}([A-Za-z_][A-Za-z0-9_]*)\s*:", ln)
        if m_proj:
            project_keys.add(m_proj.group(1))
        continue

    if section != "tasks":
        continue

    if re.match(r"^\s{2}-\s", ln):
        if in_task:
            validate_task(task_idx, task_keys, status, file_name)
        task_idx += 1
        in_task = True
        task_keys = set()
        status = ""
        file_name = ""

        m_inline = re.match(r"^\s{2}-\s*([A-Za-z_][A-Za-z0-9_]*)\s*:\s*(.+)?$", ln)
        if m_inline:
            k = m_inline.group(1)
            v = (m_inline.group(2) or "").strip()
            task_keys.add(k)
            if k == "status":
                status = v
            if k == "file":
                file_name = v
        continue

    m_task = re.match(r"^\s{4}([A-Za-z_][A-Za-z0-9_]*)\s*:\s*(.+)?$", ln)
    if in_task and m_task:
        k = m_task.group(1)
        v = (m_task.group(2) or "").strip()
        task_keys.add(k)
        if k == "status":
            status = v
        if k == "file":
            file_name = v

if section == "tasks" and in_task:
    validate_task(task_idx, task_keys, status, file_name)

for k in ["name", "repository", "default_branch"]:
    if k not in project_keys:
        errors.append(f"project missing key: {k}")

if errors:
    for e in errors:
        print(f"ERROR: {e}", file=sys.stderr)
    sys.exit(1)

print(f"states index is valid: {index_path}")
sys.exit(0)
PY
