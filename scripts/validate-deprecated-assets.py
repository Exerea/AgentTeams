#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
import re
import sys


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8").lstrip("\ufeff")


def parse_rules(path: Path) -> tuple[list[str], list[str]]:
    retired_roles: list[str] = []
    retired_paths: list[str] = []
    section = ""

    for line in read_text(path).splitlines():
        raw = line.rstrip()
        stripped = raw.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if re.match(r"^[A-Za-z_][A-Za-z0-9_]*\s*:", stripped):
            key = stripped.split(":", 1)[0].strip()
            section = key
            continue
        m_item = re.match(r"^\s*-\s*(.+)\s*$", raw)
        if not m_item:
            continue
        value = m_item.group(1).strip().strip('"').strip("'")
        if section == "retired_roles":
            retired_roles.append(value)
        elif section == "retired_paths":
            retired_paths.append(value)

    return retired_roles, retired_paths


def main() -> int:
    repo_root = Path(__file__).resolve().parent.parent
    rules_path = repo_root / ".codex" / "deprecation-rules.yaml"
    states_dir = repo_root / ".codex" / "states"

    if not rules_path.exists():
        print(f"ERROR: missing required file: {rules_path.as_posix()}", file=sys.stderr)
        return 1

    retired_roles, retired_paths = parse_rules(rules_path)
    errors: list[str] = []

    if not retired_roles:
        errors.append("deprecation-rules.yaml must declare at least one retired_roles item")
    if not retired_paths:
        errors.append("deprecation-rules.yaml must declare at least one retired_paths item")

    for rel in retired_paths:
        target = repo_root / rel
        if target.exists():
            errors.append(f"retired path still exists: {rel}")

    task_files = sorted(states_dir.glob("TASK-*.yaml"))
    for task_file in task_files:
        text = read_text(task_file)
        lines = text.splitlines()
        for role in retired_roles:
            role_re = re.escape(role)
            if re.search(rf"^assignee\s*:\s*{role_re}\s*$", text, flags=re.MULTILINE):
                errors.append(f"{task_file.as_posix()} assigns retired role '{role}'")

            section = ""
            for ln in lines:
                m_top = re.match(r"^([A-Za-z_][A-Za-z0-9_]*)\s*:", ln)
                if m_top:
                    section = m_top.group(1)
                    continue
                if section == "handoffs":
                    if re.match(rf"^\s{{4}}from\s*:\s*{role_re}\s*$", ln) or re.match(
                        rf"^\s{{4}}to\s*:\s*{role_re}\s*$", ln
                    ):
                        errors.append(f"{task_file.as_posix()} handoff uses retired role '{role}'")
                        break

    if errors:
        for err in errors:
            print(f"ERROR: {err}", file=sys.stderr)
        return 1

    print("deprecated assets are valid")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
