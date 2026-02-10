#!/usr/bin/env python3
from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path
import re
import subprocess
import sys

try:
    import yaml  # type: ignore
except Exception as exc:  # pragma: no cover
    print(f"ERROR [PYTHON_DEP_MISSING] PyYAML is required: {exc}")
    sys.exit(1)

TIMESTAMP_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")
APPROVAL_STATUS = {"pending", "approved", "rejected"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate TAKT execution evidence")
    parser.add_argument("--tasks", default=".takt/tasks", help="task directory")
    parser.add_argument("--logs", default=".takt/logs", help="logs directory")
    parser.add_argument("--allow-empty-logs", action="store_true", help="do not fail on empty logs")
    return parser.parse_args()


def load_yaml(path: Path) -> dict:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    return data if isinstance(data, dict) else {}


def load_yaml_if_exists(path: Path) -> dict:
    if not path.exists():
        return {}
    return load_yaml(path)


def as_list(value: object) -> list:
    return value if isinstance(value, list) else []


def team_of(role_ref: object) -> str:
    value = str(role_ref or "").strip()
    if "/" in value:
        return value.split("/", 1)[0].strip()
    return value


def parse_iso_utc(value: object) -> datetime | None:
    raw = str(value or "").strip()
    if not TIMESTAMP_PATTERN.fullmatch(raw):
        return None
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00")).astimezone(timezone.utc)
    except ValueError:
        return None


def required_teams(task: dict) -> set[str]:
    routing = task.get("routing")
    if isinstance(routing, dict) and isinstance(routing.get("required_teams"), list):
        teams = {str(v).strip() for v in routing.get("required_teams") if str(v).strip()}
        if teams:
            teams.add("coordinator")
            return teams
    return {"coordinator"}


def capability_tags(task: dict) -> set[str]:
    routing = task.get("routing")
    if not isinstance(routing, dict):
        return set()
    tags = routing.get("capability_tags")
    if not isinstance(tags, list):
        return set()
    return {str(v).strip() for v in tags if str(v).strip()}


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


def extract_rule_skill_evidence(task: dict) -> tuple[set[str], set[str]]:
    rules: set[str] = set()
    skills: set[str] = set()

    def collect_controls(controls: object) -> None:
        if not isinstance(controls, list):
            return
        for value in controls:
            text = str(value or "").strip()
            if text.startswith("rule:"):
                rules.add(text.removeprefix("rule:"))
            if text.startswith("skill:"):
                skills.add(text.removeprefix("skill:"))

    declarations = task.get("declarations") if isinstance(task.get("declarations"), list) else []
    for entry in declarations:
        if not isinstance(entry, dict):
            continue
        collect_controls(entry.get("controlled_by"))

    approvals = task.get("approvals") if isinstance(task.get("approvals"), dict) else {}
    team_leader_gates = approvals.get("team_leader_gates")
    if isinstance(team_leader_gates, list):
        for gate in team_leader_gates:
            if isinstance(gate, dict):
                collect_controls(gate.get("controlled_by"))

    qa_gate = approvals.get("qa_gate")
    if isinstance(qa_gate, dict):
        collect_controls(qa_gate.get("controlled_by"))
    leader_gate = approvals.get("leader_gate")
    if isinstance(leader_gate, dict):
        collect_controls(leader_gate.get("controlled_by"))

    return rules, skills


def approval_chain_errors(task_file: Path, task: dict, status: str) -> list[str]:
    errors: list[str] = []
    approvals = task.get("approvals")
    if not isinstance(approvals, dict):
        errors.append(f"{task_file.as_posix()}: approvals map is required")
        return errors

    required_team_leaders = sorted(team for team in required_teams(task) if team != "qa-review-guild")
    team_leader_gates = approvals.get("team_leader_gates")
    if not isinstance(team_leader_gates, list):
        errors.append(f"{task_file.as_posix()}: approvals.team_leader_gates must be a list")
        team_leader_gates = []

    latest_team_state: dict[str, tuple[datetime, str]] = {}
    latest_team_state_any: dict[str, str] = {}
    for gate in team_leader_gates:
        if not isinstance(gate, dict):
            continue
        team = str(gate.get("team") or "").strip()
        gate_status = str(gate.get("status") or "").strip()
        gate_at = parse_iso_utc(gate.get("at"))
        if team:
            latest_team_state_any[team] = gate_status
        if team and gate_at is not None:
            existing = latest_team_state.get(team)
            if existing is None or gate_at >= existing[0]:
                latest_team_state[team] = (gate_at, gate_status)

    qa_gate = approvals.get("qa_gate") if isinstance(approvals.get("qa_gate"), dict) else {}
    qa_status = str(qa_gate.get("status") or "").strip()
    qa_at = parse_iso_utc(qa_gate.get("at"))

    leader_gate = approvals.get("leader_gate") if isinstance(approvals.get("leader_gate"), dict) else {}
    leader_status = str(leader_gate.get("status") or "").strip()
    leader_at = parse_iso_utc(leader_gate.get("at"))

    if qa_status not in APPROVAL_STATUS:
        errors.append(f"{task_file.as_posix()}: approvals.qa_gate.status is invalid")
    if leader_status not in APPROVAL_STATUS:
        errors.append(f"{task_file.as_posix()}: approvals.leader_gate.status is invalid")

    if status in {"in_review", "done"}:
        missing = sorted(team for team in required_team_leaders if team not in latest_team_state_any)
        if missing:
            errors.append(
                f"{task_file.as_posix()}: missing team leader gate entries: {','.join(missing)}"
            )

        not_approved = sorted(
            team
            for team in required_team_leaders
            if latest_team_state.get(team, (datetime.min.replace(tzinfo=timezone.utc), "pending"))[1] != "approved"
        )
        if not_approved:
            errors.append(
                f"{task_file.as_posix()}: team leader approvals must be approved before QA: {','.join(not_approved)}"
            )

        if qa_status != "approved":
            errors.append(f"{task_file.as_posix()}: qa_gate must be approved for status={status}")

    if status == "done" and leader_status != "approved":
        errors.append(f"{task_file.as_posix()}: leader_gate must be approved for status=done")

    if qa_status == "approved" and qa_at is not None:
        for team in required_team_leaders:
            state = latest_team_state.get(team)
            if state is None:
                continue
            if state[0] > qa_at:
                errors.append(
                    f"{task_file.as_posix()}: team leader approval for {team} occurs after QA approval"
                )

    if leader_status == "approved":
        if qa_status != "approved":
            errors.append(f"{task_file.as_posix()}: leader_gate approved before qa_gate approval")
        if leader_at is not None and qa_at is not None and leader_at < qa_at:
            errors.append(f"{task_file.as_posix()}: leader_gate.at must be later than qa_gate.at")

    rejection_times: list[datetime] = []
    for team in required_team_leaders:
        state = latest_team_state.get(team)
        if state and state[1] == "rejected":
            rejection_times.append(state[0])
    if qa_status == "rejected" and qa_at is not None:
        rejection_times.append(qa_at)
    if leader_status == "rejected" and leader_at is not None:
        rejection_times.append(leader_at)

    if rejection_times:
        if status == "done":
            errors.append(f"{task_file.as_posix()}: status=done cannot contain rejected gate results")
        latest_rejection = max(rejection_times)
        declarations = task.get("declarations") if isinstance(task.get("declarations"), list) else []
        has_rework = False
        for entry in declarations:
            if not isinstance(entry, dict):
                continue
            action = str(entry.get("action") or "").strip().lower()
            if not action:
                continue
            if "rework" not in action and "fix" not in action and "address_rejection" not in action:
                continue
            at = parse_iso_utc(entry.get("at"))
            if at is not None and at >= latest_rejection:
                has_rework = True
                break
        if not has_rework:
            errors.append(
                f"{task_file.as_posix()}: rejected gate requires rework declaration by AI team after rejection"
            )

    return errors


def rule_matches_task(rule: dict, task: dict) -> bool:
    when = rule.get("when") if isinstance(rule.get("when"), dict) else {}
    status = str(task.get("status") or "")
    tags = capability_tags(task)

    if isinstance(when.get("any_status"), list):
        statuses = {str(v).strip() for v in when.get("any_status") if str(v).strip()}
        if statuses and status not in statuses:
            return False

    trigger_tags = when.get("capability_tags")
    if isinstance(trigger_tags, list):
        required_tags = {str(v).strip() for v in trigger_tags if str(v).strip()}
        if required_tags and not tags.intersection(required_tags):
            return False

    return True


def expected_rule_and_skill_ids(task: dict, root: Path) -> tuple[set[str], set[str]]:
    expected_rules: set[str] = set()
    expected_skills: set[str] = set()

    required = required_teams(task)
    tags = capability_tags(task)

    rules_data = load_yaml_if_exists(root / ".takt" / "control-plane" / "rule-catalog" / "routing-rules.yaml")
    rules = rules_data.get("rules") if isinstance(rules_data.get("rules"), list) else []
    for rule in rules:
        if not isinstance(rule, dict):
            continue
        if not bool(rule.get("enabled", False)):
            continue
        rule_id = str(rule.get("rule_id") or "").strip()
        if not rule_id:
            continue
        if not rule_matches_task(rule, task):
            continue
        expected_rules.add(rule_id)
        for skill in as_list(rule.get("require_skills")):
            skill_text = str(skill).strip()
            if skill_text:
                expected_skills.add(skill_text)

    skills_data = load_yaml_if_exists(root / ".takt" / "control-plane" / "skill-catalog" / "skills.yaml")
    skills = skills_data.get("skills") if isinstance(skills_data.get("skills"), list) else []
    for skill in skills:
        if not isinstance(skill, dict):
            continue
        if not bool(skill.get("enabled", False)):
            continue
        skill_id = str(skill.get("skill_id") or "").strip()
        if not skill_id:
            continue
        applies = {str(v).strip() for v in as_list(skill.get("applies_to_teams")) if str(v).strip()}
        if applies and not required.intersection(applies):
            continue
        trigger = skill.get("trigger") if isinstance(skill.get("trigger"), dict) else {}
        trigger_tags = {str(v).strip() for v in as_list(trigger.get("capability_tags")) if str(v).strip()}
        if trigger_tags and tags and not tags.intersection(trigger_tags):
            continue
        expected_skills.add(skill_id)

    return expected_rules, expected_skills


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
        expected_teams = required_teams(task)
        observed_teams = declared_teams(task)
        observed_rules, observed_skills = extract_rule_skill_evidence(task)
        expected_rules, expected_skills = expected_rule_and_skill_ids(task, root)

        if status in {"in_progress", "in_review", "blocked", "done"} and len(declarations) == 0:
            evidence_errors.append(
                f"{task_file.as_posix()}: status={status} requires at least one declaration"
            )

        if status in {"in_review", "done"}:
            missing_teams = sorted(expected_teams - observed_teams)
            if missing_teams:
                evidence_errors.append(
                    f"{task_file.as_posix()}: missing declared teams for status={status}: {','.join(missing_teams)}"
                )

            if len(handoffs) == 0:
                evidence_errors.append(
                    f"{task_file.as_posix()}: status={status} requires at least one handoff evidence"
                )

            missing_rules = sorted(expected_rules - observed_rules)
            if missing_rules:
                evidence_errors.append(
                    f"{task_file.as_posix()}: missing rule evidence for status={status}: {','.join(missing_rules)}"
                )

            missing_skills = sorted(expected_skills - observed_skills)
            if missing_skills:
                evidence_errors.append(
                    f"{task_file.as_posix()}: missing skill evidence for status={status}: {','.join(missing_skills)}"
                )

        evidence_errors.extend(approval_chain_errors(task_file, task, status))

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
