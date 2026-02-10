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


def team_of(role_ref: object) -> str:
    value = str(role_ref or "").strip()
    if "/" in value:
        return value.split("/", 1)[0].strip()
    return value


def required_teams(task: dict) -> set[str]:
    flags = task.get("flags") if isinstance(task.get("flags"), dict) else {}
    required = {"coordinator"}
    if bool(flags.get("qa_required", False)):
        required.add("qa-review-guild")
    if bool(flags.get("security_required", False)):
        required.add("backend")
    if bool(flags.get("ux_required", False)):
        required.add("frontend")
    if bool(flags.get("docs_required", False)):
        required.add("documentation-guild")
    if bool(flags.get("research_required", False)):
        required.add("innovation-research-guild")
    return required


def declared_teams(task: dict) -> set[str]:
    teams: set[str] = set()

    declarations = task.get("declarations") if isinstance(task.get("declarations"), list) else []
    for entry in declarations:
        if not isinstance(entry, dict):
            continue
        team = team_of(entry.get("team"))
        if team:
            teams.add(team)

    handoffs = task.get("handoffs") if isinstance(task.get("handoffs"), list) else []
    for entry in handoffs:
        if not isinstance(entry, dict):
            continue
        src = team_of(entry.get("from"))
        dst = team_of(entry.get("to"))
        if src:
            teams.add(src)
        if dst:
            teams.add(dst)

    return teams


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
        declarations = task.get("declarations") if isinstance(task.get("declarations"), list) else []
        expected = required_teams(task)
        observed = declared_teams(task)

        if status in {"in_progress", "in_review", "blocked", "done"} and len(declarations) == 0:
            evidence_errors.append(
                f"{task_file.as_posix()}: status={status} requires at least one declaration"
            )

        if status in {"in_review", "done"}:
            missing = sorted(expected - observed)
            if missing:
                evidence_errors.append(
                    f"{task_file.as_posix()}: missing declared teams for status={status}: {','.join(missing)}"
                )

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
