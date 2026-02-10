#!/usr/bin/env python3
from __future__ import annotations

import argparse
from datetime import date, datetime, timezone
from pathlib import Path
import re
import sys

try:
    import yaml  # type: ignore
except Exception as exc:  # pragma: no cover
    print(f"ERROR [PYTHON_DEP_MISSING] PyYAML is required: {exc}")
    sys.exit(1)

ALLOWED_STATUS = {"todo", "in_progress", "in_review", "blocked", "done"}
ID_PATTERN = re.compile(r"^T-\d{5}$")
TIMESTAMP_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")
REQUIRED_KEYS = [
    "id",
    "title",
    "status",
    "task",
    "goal",
    "constraints",
    "acceptance",
    "warnings",
    "declarations",
    "handoffs",
    "notes",
    "updated_at",
]
FLAG_KEYS = [
    "qa_required",
    "security_required",
    "ux_required",
    "docs_required",
    "research_required",
]
DECLARATION_KEYS = ["at", "team", "role", "action", "what", "controlled_by"]
ROUTING_KEYS = ["required_teams", "capability_tags"]
FLAGS_COMPAT_END = date(2026, 6, 30)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate .takt/tasks schema")
    parser.add_argument("--path", default=".takt/tasks", help="task directory")
    parser.add_argument("--file", default="", help="single task file")
    parser.add_argument(
        "--effective-date",
        default="",
        help="override validation date (YYYY-MM-DD) for compatibility checks",
    )
    return parser.parse_args()


def load_yaml(path: Path) -> dict:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    return data if isinstance(data, dict) else {}


def parse_effective_date(value: str) -> date | None:
    text = value.strip()
    if not text:
        return None
    try:
        return date.fromisoformat(text)
    except ValueError:
        return None


def parse_teams(values: object) -> list[str]:
    if not isinstance(values, list):
        return []
    teams: list[str] = []
    for item in values:
        team = str(item or "").strip()
        if team:
            teams.append(team)
    return teams


def validate_routing(path: Path, task: dict, errors: list[str]) -> bool:
    if "routing" not in task or task.get("routing") is None:
        return False

    routing = task.get("routing")
    if not isinstance(routing, dict):
        errors.append(f"{path.as_posix()}: routing must be a map")
        return False

    for key in ROUTING_KEYS:
        if key not in routing:
            errors.append(f"{path.as_posix()}: routing.{key} is required")

    required_teams = parse_teams(routing.get("required_teams"))
    if not required_teams:
        errors.append(f"{path.as_posix()}: routing.required_teams must be a non-empty list of strings")

    capability_tags = routing.get("capability_tags")
    if not isinstance(capability_tags, list):
        errors.append(f"{path.as_posix()}: routing.capability_tags must be a list")
    else:
        for idx, tag in enumerate(capability_tags):
            if not isinstance(tag, str) or not tag.strip():
                errors.append(f"{path.as_posix()}: routing.capability_tags[{idx}] must be a non-empty string")
    return True


def validate_flags(path: Path, task: dict, errors: list[str]) -> bool:
    if "flags" not in task or task.get("flags") is None:
        return False
    flags = task.get("flags")
    if not isinstance(flags, dict):
        errors.append(f"{path.as_posix()}: flags must be a map")
        return False
    for flag in FLAG_KEYS:
        if flag not in flags:
            errors.append(f"{path.as_posix()}: flags.{flag} is required")
            continue
        if not isinstance(flags[flag], bool):
            errors.append(f"{path.as_posix()}: flags.{flag} must be boolean")
    return True


def validate_task(path: Path, effective_date: date) -> list[str]:
    task = load_yaml(path)
    errors: list[str] = []

    for key in REQUIRED_KEYS:
        if key not in task:
            errors.append(f"{path.as_posix()}: missing key '{key}'")

    if errors:
        return errors

    task_id = str(task["id"])
    if not ID_PATTERN.fullmatch(task_id):
        errors.append(f"{path.as_posix()}: invalid id '{task_id}' (expected T-00000)")

    status = str(task["status"])
    if status not in ALLOWED_STATUS:
        errors.append(f"{path.as_posix()}: invalid status '{status}'")

    if not isinstance(task["title"], str) or not str(task["title"]).strip():
        errors.append(f"{path.as_posix()}: title must be a non-empty string")

    if not isinstance(task["task"], str) or not str(task["task"]).strip():
        errors.append(f"{path.as_posix()}: task must be a non-empty string")

    if not isinstance(task["goal"], str):
        errors.append(f"{path.as_posix()}: goal must be a string")

    for list_key in ["constraints", "acceptance", "warnings", "declarations", "handoffs"]:
        if not isinstance(task[list_key], list):
            errors.append(f"{path.as_posix()}: {list_key} must be a list")

    has_routing = validate_routing(path, task, errors)
    has_flags = validate_flags(path, task, errors)

    if not has_routing and not has_flags:
        errors.append(f"{path.as_posix()}: either routing or flags must be defined")

    # Compatibility gate:
    # - Until 2026-06-30: flags-only is allowed
    # - From 2026-07-01: routing is required (flags-only invalid)
    if has_flags and not has_routing and effective_date > FLAGS_COMPAT_END:
        errors.append(
            f"{path.as_posix()}: flags-only tasks are no longer allowed after {FLAGS_COMPAT_END.isoformat()}; add routing"
        )

    updated_at = str(task["updated_at"])
    if not TIMESTAMP_PATTERN.fullmatch(updated_at):
        errors.append(f"{path.as_posix()}: updated_at must match YYYY-MM-DDTHH:MM:SSZ")

    declarations = task["declarations"]
    if isinstance(declarations, list):
        for index, declaration in enumerate(declarations):
            if not isinstance(declaration, dict):
                errors.append(f"{path.as_posix()}: declarations[{index}] must be a map")
                continue

            for key in DECLARATION_KEYS:
                if key not in declaration:
                    errors.append(f"{path.as_posix()}: declarations[{index}].{key} is required")

            if "at" in declaration:
                at = str(declaration["at"])
                if not TIMESTAMP_PATTERN.fullmatch(at):
                    errors.append(
                        f"{path.as_posix()}: declarations[{index}].at must match YYYY-MM-DDTHH:MM:SSZ"
                    )

            for key in ["team", "role", "action", "what"]:
                if key in declaration and (
                    not isinstance(declaration[key], str) or not str(declaration[key]).strip()
                ):
                    errors.append(
                        f"{path.as_posix()}: declarations[{index}].{key} must be a non-empty string"
                    )

            if "controlled_by" in declaration:
                controls = declaration["controlled_by"]
                if not isinstance(controls, list) or len(controls) == 0:
                    errors.append(
                        f"{path.as_posix()}: declarations[{index}].controlled_by must be a non-empty list"
                    )
                else:
                    for ctrl_idx, control in enumerate(controls):
                        if not isinstance(control, str) or not control.strip():
                            errors.append(
                                f"{path.as_posix()}: declarations[{index}].controlled_by[{ctrl_idx}] must be a non-empty string"
                            )

    return errors


def main() -> int:
    args = parse_args()
    override_date = parse_effective_date(args.effective_date)
    if args.effective_date and override_date is None:
        print(f"ERROR [TASK_CONFIG_INVALID] --effective-date must be YYYY-MM-DD: {args.effective_date}")
        return 1
    effective_date = override_date or datetime.now(timezone.utc).date()

    files: list[Path]
    if args.file:
        files = [Path(args.file).resolve()]
    else:
        task_dir = Path(args.path).resolve()
        if not task_dir.exists():
            print(f"ERROR [TASK_DIR_MISSING] {task_dir.as_posix()}")
            return 1
        files = sorted(task_dir.glob("TASK-*.yaml"))

    if not files:
        print("ERROR [TASK_FILES_EMPTY] no task files found")
        return 1

    all_errors: list[str] = []
    for file in files:
        if not file.exists():
            all_errors.append(f"{file.as_posix()}: file not found")
            continue
        all_errors.extend(validate_task(file, effective_date))

    if all_errors:
        for err in all_errors:
            print(f"ERROR [TAKT_TASK_INVALID] {err}")
        return 1

    print(f"OK [TAKT_TASK_VALID] files={len(files)} effective_date={effective_date.isoformat()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
