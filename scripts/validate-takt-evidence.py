#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path
import subprocess
import sys

try:
    import yaml  # type: ignore
except Exception as exc:  # pragma: no cover
    print(f"ERROR [PYTHON_DEP_MISSING] PyYAML is required: {exc}")
    sys.exit(1)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate TAKT execution evidence")
    parser.add_argument("--tasks", default=".takt/tasks", help="task directory")
    parser.add_argument("--logs", default=".takt/logs", help="logs directory")
    parser.add_argument("--allow-empty-logs", action="store_true", help="do not fail on empty logs")
    return parser.parse_args()


def load_yaml(path: Path) -> dict:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    return data if isinstance(data, dict) else {}


def main() -> int:
    args = parse_args()
    root = Path.cwd()

    task_dir = (root / args.tasks).resolve()
    logs_dir = (root / args.logs).resolve()

    if not task_dir.exists():
        print(f"ERROR [EVIDENCE_TASK_DIR_MISSING] {task_dir.as_posix()}")
        return 1

    tasks = sorted(task_dir.glob("TASK-*.yaml"))
    if not tasks:
        print(f"ERROR [EVIDENCE_TASKS_EMPTY] no TASK-*.yaml under {task_dir.as_posix()}")
        return 1

    evidence_errors: list[str] = []
    for task_file in tasks:
        task = load_yaml(task_file)
        status = str(task.get("status") or "")
        handoffs = task.get("handoffs") if isinstance(task.get("handoffs"), list) else []
        if status in {"in_review", "done"} and len(handoffs) == 0:
            evidence_errors.append(
                f"{task_file.as_posix()}: status={status} requires at least one handoff evidence"
            )

    log_files = [p for p in logs_dir.glob("*") if p.is_file()] if logs_dir.exists() else []
    if not log_files and not args.allow_empty_logs:
        evidence_errors.append(f"{logs_dir.as_posix()}: no evidence log files found")

    audit_script = root / "scripts" / "audit-takt-governance.py"
    if not audit_script.exists():
        evidence_errors.append(f"missing script: {audit_script.as_posix()}")
    else:
        proc = subprocess.run(
            [sys.executable, str(audit_script), "--strict"],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        out = proc.stdout.strip()
        if out:
            print(out)
        if proc.returncode != 0:
            evidence_errors.append("strict governance audit failed")

    if evidence_errors:
        for err in evidence_errors:
            print(f"ERROR [TAKT_EVIDENCE_INVALID] {err}")
        return 1

    print(f"OK [TAKT_EVIDENCE_VALID] tasks={len(tasks)} logs={len(log_files)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
