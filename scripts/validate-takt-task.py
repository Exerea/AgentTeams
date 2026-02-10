#!/usr/bin/env python3
from __future__ import annotations

import argparse
from datetime import datetime, timezone
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
APPROVAL_STATUS = {"pending", "approved", "rejected"}
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
    "approvals",
    "notes",
    "updated_at",
]
DECLARATION_KEYS = ["at", "team", "role", "action", "what", "controlled_by"]
ROUTING_KEYS = ["required_teams", "capability_tags"]
TEAM_LEADER_GATE_KEYS = ["team", "leader_role", "status", "at", "note", "controlled_by"]
SINGLE_GATE_KEYS = ["by", "status", "at", "note", "controlled_by"]
LEGACY_REVIEW_KEY = "fl" + "ags"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate .takt/tasks schema")
    parser.add_argument("--path", default=".takt/tasks", help="task directory")
    parser.add_argument("--file", default="", help="single task file")
    return parser.parse_args()


def load_yaml(path: Path) -> dict:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    return data if isinstance(data, dict) else {}


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


def validate_legacy_review_absent(path: Path, task: dict, errors: list[str]) -> None:
    if LEGACY_REVIEW_KEY in task:
        errors.append(f"{path.as_posix()}: legacy review field is no longer supported; use routing only")


def required_teams_for_approval(task: dict) -> list[str]:
    routing = task.get("routing")
    if isinstance(routing, dict) and isinstance(routing.get("required_teams"), list):
        teams = parse_teams(routing.get("required_teams"))
        if teams:
            if "coordinator" not in teams:
                teams.append("coordinator")
            return teams
    return ["coordinator"]


def parse_iso_utc(value: object) -> datetime | None:
    raw = str(value or "").strip()
    if not raw:
        return None
    if not TIMESTAMP_PATTERN.fullmatch(raw):
        return None
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00")).astimezone(timezone.utc)
    except ValueError:
        return None


def validate_controlled_by(path: Path, pointer: str, controls: object, errors: list[str]) -> None:
    if not isinstance(controls, list) or len(controls) == 0:
        errors.append(f"{path.as_posix()}: {pointer}.controlled_by must be a non-empty list")
        return
    for ctrl_idx, control in enumerate(controls):
        if not isinstance(control, str) or not control.strip():
            errors.append(
                f"{path.as_posix()}: {pointer}.controlled_by[{ctrl_idx}] must be a non-empty string"
            )


def validate_single_gate(
    path: Path,
    pointer: str,
    gate: object,
    actor_key: str,
    errors: list[str],
) -> tuple[str, datetime | None]:
    if not isinstance(gate, dict):
        errors.append(f"{path.as_posix()}: {pointer} must be a map")
        return "", None

    required_keys = SINGLE_GATE_KEYS
    for key in required_keys:
        if key not in gate:
            errors.append(f"{path.as_posix()}: {pointer}.{key} is required")

    actor = str(gate.get(actor_key) or "").strip()
    if not actor:
        errors.append(f"{path.as_posix()}: {pointer}.{actor_key} must be a non-empty string")

    status = str(gate.get("status") or "").strip()
    if status not in APPROVAL_STATUS:
        errors.append(
            f"{path.as_posix()}: {pointer}.status must be one of {sorted(APPROVAL_STATUS)}"
        )

    at_raw = str(gate.get("at") or "").strip()
    if not TIMESTAMP_PATTERN.fullmatch(at_raw):
        errors.append(f"{path.as_posix()}: {pointer}.at must match YYYY-MM-DDTHH:MM:SSZ")

    note = gate.get("note")
    if not isinstance(note, str):
        errors.append(f"{path.as_posix()}: {pointer}.note must be a string")

    validate_controlled_by(path, pointer, gate.get("controlled_by"), errors)
    return status, parse_iso_utc(at_raw)


def validate_approvals(path: Path, task: dict, errors: list[str], status: str) -> None:
    approvals = task.get("approvals")
    if not isinstance(approvals, dict):
        errors.append(f"{path.as_posix()}: approvals must be a map")
        return

    for key in ["team_leader_gates", "qa_gate", "leader_gate"]:
        if key not in approvals:
            errors.append(f"{path.as_posix()}: approvals.{key} is required")

    team_leader_gates = approvals.get("team_leader_gates")
    if not isinstance(team_leader_gates, list):
        errors.append(f"{path.as_posix()}: approvals.team_leader_gates must be a list")
        team_leader_gates = []

    latest_team_state: dict[str, tuple[datetime, str]] = {}
    latest_team_state_any: dict[str, str] = {}
    for idx, gate in enumerate(team_leader_gates):
        pointer = f"approvals.team_leader_gates[{idx}]"
        if not isinstance(gate, dict):
            errors.append(f"{path.as_posix()}: {pointer} must be a map")
            continue
        for key in TEAM_LEADER_GATE_KEYS:
            if key not in gate:
                errors.append(f"{path.as_posix()}: {pointer}.{key} is required")

        team = str(gate.get("team") or "").strip()
        if not team:
            errors.append(f"{path.as_posix()}: {pointer}.team must be a non-empty string")

        leader_role = str(gate.get("leader_role") or "").strip()
        if not leader_role:
            errors.append(f"{path.as_posix()}: {pointer}.leader_role must be a non-empty string")

        gate_status = str(gate.get("status") or "").strip()
        if gate_status not in APPROVAL_STATUS:
            errors.append(
                f"{path.as_posix()}: {pointer}.status must be one of {sorted(APPROVAL_STATUS)}"
            )

        at_raw = str(gate.get("at") or "").strip()
        if not TIMESTAMP_PATTERN.fullmatch(at_raw):
            errors.append(f"{path.as_posix()}: {pointer}.at must match YYYY-MM-DDTHH:MM:SSZ")
        at_dt = parse_iso_utc(at_raw)

        note = gate.get("note")
        if not isinstance(note, str):
            errors.append(f"{path.as_posix()}: {pointer}.note must be a string")

        validate_controlled_by(path, pointer, gate.get("controlled_by"), errors)

        if team:
            latest_team_state_any[team] = gate_status
        if team and at_dt is not None:
            existing = latest_team_state.get(team)
            if existing is None or at_dt >= existing[0]:
                latest_team_state[team] = (at_dt, gate_status)

    qa_status, qa_at = validate_single_gate(path, "approvals.qa_gate", approvals.get("qa_gate"), "by", errors)
    leader_status, leader_at = validate_single_gate(
        path,
        "approvals.leader_gate",
        approvals.get("leader_gate"),
        "by",
        errors,
    )

    required_teams = required_teams_for_approval(task)
    expected_team_leaders = [team for team in required_teams if team != "qa-review-guild"]

    if status in {"in_review", "done"}:
        missing_teams = sorted(team for team in expected_team_leaders if team not in latest_team_state_any)
        if missing_teams:
            errors.append(
                f"{path.as_posix()}: approvals.team_leader_gates missing teams for status={status}: {','.join(missing_teams)}"
            )

        not_approved_teams = sorted(
            team
            for team in expected_team_leaders
            if latest_team_state.get(team, (datetime.min.replace(tzinfo=timezone.utc), "pending"))[1] != "approved"
        )
        if not_approved_teams:
            errors.append(
                f"{path.as_posix()}: team leader approvals must be approved before QA for status={status}: {','.join(not_approved_teams)}"
            )

        if qa_status != "approved":
            errors.append(f"{path.as_posix()}: approvals.qa_gate.status must be approved for status={status}")

    if status == "done" and leader_status != "approved":
        errors.append(f"{path.as_posix()}: approvals.leader_gate.status must be approved for status=done")

    if qa_status == "approved" and qa_at is not None:
        for team in expected_team_leaders:
            team_at = latest_team_state.get(team, (None, ""))[0] if team in latest_team_state else None
            if team_at is not None and team_at > qa_at:
                errors.append(
                    f"{path.as_posix()}: team leader approval for {team} must occur before qa_gate approval"
                )

    if leader_status == "approved":
        if qa_status != "approved":
            errors.append(
                f"{path.as_posix()}: approvals.leader_gate cannot be approved before qa_gate approval"
            )
        if qa_at is not None and leader_at is not None and leader_at < qa_at:
            errors.append(
                f"{path.as_posix()}: approvals.leader_gate.at must be later than approvals.qa_gate.at"
            )

    if status == "done":
        has_rejection = any(state[1] == "rejected" for state in latest_team_state.values()) or qa_status == "rejected" or leader_status == "rejected"
        if has_rejection:
            errors.append(f"{path.as_posix()}: status=done cannot include rejected approvals")


def validate_task(path: Path) -> list[str]:
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
    validate_legacy_review_absent(path, task, errors)
    if not has_routing:
        errors.append(f"{path.as_posix()}: routing must be defined")

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

    validate_approvals(path, task, errors, status)

    return errors


def main() -> int:
    args = parse_args()
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
        all_errors.extend(validate_task(file))

    if all_errors:
        for err in all_errors:
            print(f"ERROR [TAKT_TASK_INVALID] {err}")
        return 1

    print(f"OK [TAKT_TASK_VALID] files={len(files)} effective_date={datetime.now(timezone.utc).date().isoformat()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
