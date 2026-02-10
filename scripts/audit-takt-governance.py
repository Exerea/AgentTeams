#!/usr/bin/env python3
from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path
import sys

try:
    import yaml  # type: ignore
except Exception as exc:  # pragma: no cover
    print(f"ERROR [PYTHON_DEP_MISSING] PyYAML is required: {exc}")
    sys.exit(1)


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


def required_teams_from_flags(flags: object) -> set[str]:
    required = {"coordinator"}
    if not isinstance(flags, dict):
        return required
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


def required_teams(task: dict) -> set[str]:
    routing = task.get("routing")
    if isinstance(routing, dict) and isinstance(routing.get("required_teams"), list):
        teams = {str(v).strip() for v in routing.get("required_teams") if str(v).strip()}
        if teams:
            teams.add("coordinator")
            return teams
    return required_teams_from_flags(task.get("flags"))


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
    declarations = task.get("declarations") if isinstance(task.get("declarations"), list) else []
    for entry in declarations:
        if not isinstance(entry, dict):
            continue
        controls = entry.get("controlled_by")
        if not isinstance(controls, list):
            continue
        for value in controls:
            text = str(value or "").strip()
            if text.startswith("rule:"):
                rules.add(text.removeprefix("rule:"))
            if text.startswith("skill:"):
                skills.add(text.removeprefix("skill:"))
    return rules, skills


def rule_matches_task(rule: dict, task: dict) -> bool:
    when = rule.get("when") if isinstance(rule.get("when"), dict) else {}
    status = str(task.get("status") or "")
    flags = task.get("flags") if isinstance(task.get("flags"), dict) else {}
    tags = capability_tags(task)

    if isinstance(when.get("any_status"), list):
        statuses = {str(v).strip() for v in when.get("any_status") if str(v).strip()}
        if statuses and status not in statuses:
            return False

    flag_clause = when.get("flag")
    if isinstance(flag_clause, dict):
        key = str(flag_clause.get("key") or "").strip()
        expected = flag_clause.get("equals")
        if key and bool(flags.get(key, False)) != bool(expected):
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

    return sorted(entries, key=lambda item: item[0])


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
