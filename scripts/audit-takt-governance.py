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

TIMESTAMP_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")
APPROVAL_STATUS = {"pending", "approved", "rejected"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Audit TAKT governance distribution and evidence")
    parser.add_argument("--path", default=".takt/tasks", help="task directory path")
    parser.add_argument("--logs", default=".takt/logs", help="logs directory path")
    parser.add_argument("--min-teams", type=int, default=3, help="minimum distinct teams expected")
    parser.add_argument("--strict", action="store_true", help="fail when warnings are found")
    parser.add_argument("--verbose", action="store_true", help="verbose output")
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


def to_sortable_iso(value: object) -> str:
    raw = str(value or "").strip()
    if not raw:
        return "9999-12-31T23:59:59Z"
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    except ValueError:
        return raw


def parse_iso_utc(value: object) -> datetime | None:
    raw = str(value or "").strip()
    if not TIMESTAMP_PATTERN.fullmatch(raw):
        return None
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
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


def observed_teams(task: dict) -> set[str]:
    observed: set[str] = {"coordinator"}
    declarations = task.get("declarations") if isinstance(task.get("declarations"), list) else []
    for entry in declarations:
        if not isinstance(entry, dict):
            continue
        team = team_of(entry.get("team"))
        if team:
            observed.add(team)

    handoffs = task.get("handoffs") if isinstance(task.get("handoffs"), list) else []
    for entry in handoffs:
        if not isinstance(entry, dict):
            continue
        src = team_of(entry.get("from"))
        dst = team_of(entry.get("to"))
        if src:
            observed.add(src)
        if dst:
            observed.add(dst)
    return observed


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


def timeline_entries(task: dict) -> list[tuple[str, str]]:
    entries: list[tuple[str, str]] = []

    declarations = task.get("declarations") if isinstance(task.get("declarations"), list) else []
    for entry in declarations:
        if not isinstance(entry, dict):
            continue
        at = str(entry.get("at") or "")
        team = str(entry.get("team") or "").strip()
        role = str(entry.get("role") or "").strip()
        action = str(entry.get("action") or "").strip()
        what = str(entry.get("what") or "").strip()
        controls = entry.get("controlled_by") if isinstance(entry.get("controlled_by"), list) else []
        controls_text = ",".join(str(v) for v in controls) if controls else "-"
        entries.append(
            (
                to_sortable_iso(at),
                f"DECLARE team={team} role={role} action={action} what={what} controlled_by={controls_text}",
            )
        )

    handoffs = task.get("handoffs") if isinstance(task.get("handoffs"), list) else []
    for entry in handoffs:
        if not isinstance(entry, dict):
            continue
        at = str(entry.get("at") or "")
        src = str(entry.get("from") or "").strip()
        dst = str(entry.get("to") or "").strip()
        memo = str(entry.get("memo") or "").strip()
        entries.append((to_sortable_iso(at), f"HANDOFF from={src} to={dst} memo={memo}"))

    approvals = task.get("approvals") if isinstance(task.get("approvals"), dict) else {}
    team_leader_gates = approvals.get("team_leader_gates")
    if isinstance(team_leader_gates, list):
        for gate in team_leader_gates:
            if not isinstance(gate, dict):
                continue
            at = str(gate.get("at") or "")
            team = str(gate.get("team") or "").strip()
            role = str(gate.get("leader_role") or "").strip()
            status = str(gate.get("status") or "").strip()
            note = str(gate.get("note") or "").strip()
            entries.append(
                (to_sortable_iso(at), f"TEAM_LEADER_GATE team={team} role={role} status={status} note={note}")
            )

    qa_gate = approvals.get("qa_gate")
    if isinstance(qa_gate, dict):
        at = str(qa_gate.get("at") or "")
        by = str(qa_gate.get("by") or "").strip()
        status = str(qa_gate.get("status") or "").strip()
        note = str(qa_gate.get("note") or "").strip()
        entries.append((to_sortable_iso(at), f"QA_GATE by={by} status={status} note={note}"))

    leader_gate = approvals.get("leader_gate")
    if isinstance(leader_gate, dict):
        at = str(leader_gate.get("at") or "")
        by = str(leader_gate.get("by") or "").strip()
        status = str(leader_gate.get("status") or "").strip()
        note = str(leader_gate.get("note") or "").strip()
        entries.append((to_sortable_iso(at), f"LEADER_GATE by={by} status={status} note={note}"))

    return sorted(entries, key=lambda item: item[0])


def approval_chain_warnings(task_id: str, task: dict, status: str) -> list[str]:
    warnings: list[str] = []
    approvals = task.get("approvals")
    if not isinstance(approvals, dict):
        warnings.append(f"WARN [AUDIT_APPROVALS_MISSING] task={task_id} approvals map is missing")
        return warnings

    required_team_leaders = sorted(team for team in required_teams(task) if team != "qa-review-guild")
    team_leader_gates = approvals.get("team_leader_gates")
    if not isinstance(team_leader_gates, list):
        warnings.append(
            f"WARN [AUDIT_TEAM_LEADER_GATE_INVALID] task={task_id} approvals.team_leader_gates must be a list"
        )
        team_leader_gates = []

    latest_team_state: dict[str, tuple[datetime, str]] = {}
    latest_team_state_any: dict[str, str] = {}
    for gate in team_leader_gates:
        if not isinstance(gate, dict):
            continue
        team = str(gate.get("team") or "").strip()
        gate_status = str(gate.get("status") or "").strip()
        gate_at = parse_iso_utc(gate.get("at"))
        if gate_status not in APPROVAL_STATUS:
            warnings.append(
                f"WARN [AUDIT_TEAM_LEADER_GATE_STATUS_INVALID] task={task_id} team={team or '-'} status={gate_status or '-'}"
            )
        if team:
            latest_team_state_any[team] = gate_status
        if team and gate_at is not None:
            existing = latest_team_state.get(team)
            if existing is None or gate_at >= existing[0]:
                latest_team_state[team] = (gate_at, gate_status)

    qa_gate = approvals.get("qa_gate")
    qa_status = ""
    qa_at: datetime | None = None
    if isinstance(qa_gate, dict):
        qa_status = str(qa_gate.get("status") or "").strip()
        qa_at = parse_iso_utc(qa_gate.get("at"))
    else:
        warnings.append(f"WARN [AUDIT_QA_GATE_MISSING] task={task_id} approvals.qa_gate is missing")

    leader_gate = approvals.get("leader_gate")
    leader_status = ""
    leader_at: datetime | None = None
    if isinstance(leader_gate, dict):
        leader_status = str(leader_gate.get("status") or "").strip()
        leader_at = parse_iso_utc(leader_gate.get("at"))
    else:
        warnings.append(f"WARN [AUDIT_LEADER_GATE_MISSING] task={task_id} approvals.leader_gate is missing")

    if qa_status and qa_status not in APPROVAL_STATUS:
        warnings.append(f"WARN [AUDIT_QA_GATE_STATUS_INVALID] task={task_id} status={qa_status}")
    if leader_status and leader_status not in APPROVAL_STATUS:
        warnings.append(f"WARN [AUDIT_LEADER_GATE_STATUS_INVALID] task={task_id} status={leader_status}")

    if status in {"in_review", "done"}:
        missing = sorted(team for team in required_team_leaders if team not in latest_team_state_any)
        if missing:
            warnings.append(
                f"WARN [AUDIT_TEAM_LEADER_GATE_MISSING] task={task_id} missing={','.join(missing)}"
            )

        not_approved = sorted(
            team
            for team in required_team_leaders
            if latest_team_state.get(team, (datetime.min.replace(tzinfo=timezone.utc), "pending"))[1] != "approved"
        )
        if not_approved:
            warnings.append(
                f"WARN [AUDIT_TEAM_LEADER_GATE_NOT_APPROVED] task={task_id} teams={','.join(not_approved)}"
            )

        if qa_status != "approved":
            warnings.append(
                f"WARN [AUDIT_QA_GATE_NOT_APPROVED] task={task_id} qa_status={qa_status or '-'}"
            )

    if status == "done" and leader_status != "approved":
        warnings.append(
            f"WARN [AUDIT_LEADER_GATE_NOT_APPROVED] task={task_id} leader_status={leader_status or '-'}"
        )

    if qa_status == "approved" and qa_at is not None:
        for team in required_team_leaders:
            state = latest_team_state.get(team)
            if state is None:
                continue
            if state[0] > qa_at:
                warnings.append(
                    f"WARN [AUDIT_APPROVAL_ORDER_INVALID] task={task_id} team={team} approved_after_qa=true"
                )

    if leader_status == "approved":
        if qa_status != "approved":
            warnings.append(f"WARN [AUDIT_APPROVAL_ORDER_INVALID] task={task_id} leader_before_qa=true")
        if leader_at is not None and qa_at is not None and leader_at < qa_at:
            warnings.append(
                f"WARN [AUDIT_APPROVAL_ORDER_INVALID] task={task_id} leader_gate_before_qa_gate=true"
            )

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
            warnings.append(f"WARN [AUDIT_REJECTED_DONE_INVALID] task={task_id} rejected_gate_present=true")
        latest_rejection = max(rejection_times)
        declarations = task.get("declarations") if isinstance(task.get("declarations"), list) else []
        has_rework = False
        for entry in declarations:
            if not isinstance(entry, dict):
                continue
            action = str(entry.get("action") or "").strip().lower()
            if "rework" not in action and "fix" not in action and "address_rejection" not in action:
                continue
            at = parse_iso_utc(entry.get("at"))
            if at is not None and at >= latest_rejection:
                has_rework = True
                break
        if not has_rework:
            warnings.append(
                f"WARN [AUDIT_REWORK_EVIDENCE_MISSING] task={task_id} rejected_gate_requires_rework=true"
            )

    return warnings


def main() -> int:
    args = parse_args()
    if args.min_teams < 1:
        print("ERROR [AUDIT_CONFIG_INVALID] --min-teams must be >= 1")
        return 1

    root = Path.cwd()
    task_dir = Path(args.path).resolve()
    logs_dir = Path(args.logs).resolve()

    if not task_dir.exists():
        print(f"ERROR [AUDIT_TASK_DIR_MISSING] {task_dir.as_posix()}")
        return 1

    files = sorted(task_dir.glob("TASK-*.yaml"))
    if not files:
        print(f"ERROR [AUDIT_TASKS_EMPTY] no TASK-*.yaml under {task_dir.as_posix()}")
        return 1

    warnings: list[str] = []
    for task_file in files:
        task = load_yaml(task_file)
        task_id = str(task.get("id") or task_file.stem)
        status = str(task.get("status") or "")
        declarations = task.get("declarations") if isinstance(task.get("declarations"), list) else []

        if len(declarations) == 0:
            warnings.append(f"WARN [AUDIT_DECLARATION_MISSING] task={task_id} declarations are empty")

        expected_teams = required_teams(task)
        observed = observed_teams(task)
        missing_teams = sorted(expected_teams - observed)
        if missing_teams:
            warnings.append(
                f"WARN [AUDIT_TEAM_COVERAGE_MISSING] task={task_id} missing_required_teams={','.join(missing_teams)}"
            )

        if len(observed) < args.min_teams:
            warnings.append(
                f"WARN [AUDIT_DISTRIBUTION_LOW] task={task_id} observed_teams={len(observed)} min={args.min_teams}"
            )

        observed_rules, observed_skills = extract_rule_skill_evidence(task)
        expected_rules, expected_skills = expected_rule_and_skill_ids(task, root)
        if status in {"in_review", "done"}:
            missing_rules = sorted(expected_rules - observed_rules)
            if missing_rules:
                warnings.append(
                    f"WARN [AUDIT_RULE_EVIDENCE_MISSING] task={task_id} missing_rules={','.join(missing_rules)}"
                )
            missing_skills = sorted(expected_skills - observed_skills)
            if missing_skills:
                warnings.append(
                    f"WARN [AUDIT_SKILL_EVIDENCE_MISSING] task={task_id} missing_skills={','.join(missing_skills)}"
                )

        warnings.extend(approval_chain_warnings(task_id, task, status))

        if args.verbose:
            print(
                f"INFO [AUDIT_TASK] task={task_id} expected={sorted(expected_teams)} observed={sorted(observed)} "
                f"expected_rules={sorted(expected_rules)} observed_rules={sorted(observed_rules)} "
                f"expected_skills={sorted(expected_skills)} observed_skills={sorted(observed_skills)}"
            )
            for at, detail in timeline_entries(task):
                print(f"INFO [AUDIT_TIMELINE] task={task_id} at={at} {detail}")

    log_files = [p for p in logs_dir.glob("*") if p.is_file()]
    if not log_files:
        warnings.append(f"WARN [AUDIT_EVIDENCE_LOGS_EMPTY] no log files under {logs_dir.as_posix()}")

    if warnings:
        for warning in warnings:
            print(warning)
        if args.strict:
            print("ERROR [AUDIT_FAILED] strict mode enabled and warnings detected")
            return 1
        print(f"OK [AUDIT_DONE_WITH_WARNINGS] warnings={len(warnings)}")
        return 0

    print(f"OK [AUDIT_DONE] tasks={len(files)} logs={len(log_files)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
