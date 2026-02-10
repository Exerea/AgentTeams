#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path
import re
import sys

try:
    import yaml  # type: ignore
except Exception as exc:  # pragma: no cover
    print(f"ERROR [PYTHON_DEP_MISSING] PyYAML is required: {exc}")
    sys.exit(1)

TIMESTAMP_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")
INTAKE_REQUIRED_KEYS = [
    "project_id",
    "repo",
    "captured_at",
    "window_days",
    "task_counts",
    "lead_time_p50_hours",
    "queue_p95_hours",
    "rework_rate",
    "blocked_ratio",
    "incident_fingerprints",
    "policy_failures",
    "top_overlaps",
]
TEAM_REQUIRED_KEYS = [
    "team_id",
    "mission",
    "owned_capabilities",
    "slo_targets",
    "persona_ref",
    "policy_refs",
    "skill_refs",
    "active",
]
RULE_REQUIRED_KEYS = [
    "rule_id",
    "when",
    "require_teams",
    "require_skills",
    "priority",
    "enabled",
]
SKILL_REQUIRED_KEYS = [
    "skill_id",
    "description",
    "applies_to_teams",
    "trigger",
    "instruction_ref",
    "policy_refs",
    "evidence_requirements",
    "enabled",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate .takt/control-plane schema")
    parser.add_argument("--path", default=".takt/control-plane", help="control-plane root")
    return parser.parse_args()


def load_yaml(path: Path) -> dict:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    return data if isinstance(data, dict) else {}


def as_list(value: object) -> list:
    return value if isinstance(value, list) else []


def validate_registry(path: Path, errors: list[str]) -> set[str]:
    if not path.exists():
        errors.append(f"missing file: {path.as_posix()}")
        return set()

    data = load_yaml(path)
    projects = as_list(data.get("projects"))
    if not projects:
        errors.append(f"{path.as_posix()}: projects must be a non-empty list")
        return set()

    project_ids: set[str] = set()
    for idx, item in enumerate(projects):
        if not isinstance(item, dict):
            errors.append(f"{path.as_posix()}: projects[{idx}] must be a map")
            continue
        project_id = str(item.get("project_id") or "").strip()
        repo = str(item.get("repo") or "").strip()
        active = item.get("active")
        if not project_id:
            errors.append(f"{path.as_posix()}: projects[{idx}].project_id is required")
            continue
        if project_id in project_ids:
            errors.append(f"{path.as_posix()}: duplicate project_id '{project_id}'")
        project_ids.add(project_id)
        if not repo:
            errors.append(f"{path.as_posix()}: projects[{idx}].repo is required")
        if not isinstance(active, bool):
            errors.append(f"{path.as_posix()}: projects[{idx}].active must be boolean")
    return project_ids


def validate_intake_file(path: Path, project_ids: set[str], errors: list[str]) -> None:
    data = load_yaml(path)
    for key in INTAKE_REQUIRED_KEYS:
        if key not in data:
            errors.append(f"{path.as_posix()}: missing key '{key}'")

    if not data:
        return

    project_id = str(data.get("project_id") or "").strip()
    if project_ids and project_id not in project_ids:
        errors.append(f"{path.as_posix()}: unknown project_id '{project_id}'")

    captured_at = str(data.get("captured_at") or "")
    if not TIMESTAMP_PATTERN.fullmatch(captured_at):
        errors.append(f"{path.as_posix()}: captured_at must match YYYY-MM-DDTHH:MM:SSZ")

    window_days = data.get("window_days")
    if not isinstance(window_days, int) or window_days <= 0:
        errors.append(f"{path.as_posix()}: window_days must be a positive integer")

    task_counts = data.get("task_counts")
    if not isinstance(task_counts, dict):
        errors.append(f"{path.as_posix()}: task_counts must be a map")
    else:
        for key in ["todo", "in_progress", "in_review", "blocked", "done"]:
            value = task_counts.get(key)
            if not isinstance(value, int) or value < 0:
                errors.append(f"{path.as_posix()}: task_counts.{key} must be an integer >= 0")

    for metric in ["lead_time_p50_hours", "queue_p95_hours", "rework_rate", "blocked_ratio"]:
        value = data.get(metric)
        if not isinstance(value, (int, float)):
            errors.append(f"{path.as_posix()}: {metric} must be numeric")
            continue
        if metric in {"rework_rate", "blocked_ratio"} and not (0 <= float(value) <= 1):
            errors.append(f"{path.as_posix()}: {metric} must be between 0 and 1")

    incident_fingerprints = data.get("incident_fingerprints")
    if not isinstance(incident_fingerprints, list):
        errors.append(f"{path.as_posix()}: incident_fingerprints must be a list")
    else:
        for idx, item in enumerate(incident_fingerprints):
            if not isinstance(item, dict):
                errors.append(f"{path.as_posix()}: incident_fingerprints[{idx}] must be a map")
                continue
            for key in ["hash", "error_class", "failing_step", "policy", "rule_id"]:
                if not str(item.get(key) or "").strip():
                    errors.append(f"{path.as_posix()}: incident_fingerprints[{idx}].{key} is required")

    policy_failures = data.get("policy_failures")
    if not isinstance(policy_failures, list):
        errors.append(f"{path.as_posix()}: policy_failures must be a list")

    top_overlaps = data.get("top_overlaps")
    if not isinstance(top_overlaps, list):
        errors.append(f"{path.as_posix()}: top_overlaps must be a list")
    else:
        for idx, item in enumerate(top_overlaps):
            if not isinstance(item, dict):
                errors.append(f"{path.as_posix()}: top_overlaps[{idx}] must be a map")
                continue
            capability = str(item.get("capability") or "").strip()
            ratio = item.get("responsibility_overlap_ratio")
            if not capability:
                errors.append(f"{path.as_posix()}: top_overlaps[{idx}].capability is required")
            if not isinstance(ratio, (int, float)) or not (0 <= float(ratio) <= 1):
                errors.append(
                    f"{path.as_posix()}: top_overlaps[{idx}].responsibility_overlap_ratio must be between 0 and 1"
                )


def validate_catalog(
    path: Path, list_key: str, required_keys: list[str], id_key: str, errors: list[str]
) -> set[str]:
    if not path.exists():
        errors.append(f"missing file: {path.as_posix()}")
        return set()

    data = load_yaml(path)
    items = as_list(data.get(list_key))
    if not items:
        errors.append(f"{path.as_posix()}: {list_key} must be a non-empty list")
        return set()

    ids: set[str] = set()
    for idx, item in enumerate(items):
        if not isinstance(item, dict):
            errors.append(f"{path.as_posix()}: {list_key}[{idx}] must be a map")
            continue
        for key in required_keys:
            if key not in item:
                errors.append(f"{path.as_posix()}: {list_key}[{idx}].{key} is required")

        item_id = str(item.get(id_key) or "").strip()
        if item_id:
            if item_id in ids:
                errors.append(f"{path.as_posix()}: duplicate {id_key} '{item_id}'")
            ids.add(item_id)
    return ids


def validate_signals_latest(path: Path, errors: list[str]) -> None:
    if not path.exists():
        errors.append(f"missing file: {path.as_posix()}")
        return

    data = load_yaml(path)
    for key in ["generated_at", "window_days", "projects", "fingerprint_project_counts", "overload_candidates"]:
        if key not in data:
            errors.append(f"{path.as_posix()}: missing key '{key}'")


def main() -> int:
    args = parse_args()
    root = Path(args.path).resolve()

    if not root.exists():
        print(f"ERROR [CONTROL_PLANE_MISSING] {root.as_posix()}")
        return 1

    errors: list[str] = []
    project_ids = validate_registry(root / "registry" / "projects.yaml", errors)

    intake_dir = root / "intake"
    if not intake_dir.exists():
        errors.append(f"missing directory: {intake_dir.as_posix()}")
    else:
        intake_files = sorted(intake_dir.glob("*/*.yaml"))
        if not intake_files:
            errors.append(f"{intake_dir.as_posix()}: no intake YAML files found")
        for file in intake_files:
            validate_intake_file(file, project_ids, errors)

    validate_signals_latest(root / "signals" / "latest.yaml", errors)

    team_ids = validate_catalog(
        root / "team-catalog" / "teams.yaml", "teams", TEAM_REQUIRED_KEYS, "team_id", errors
    )
    rule_ids = validate_catalog(
        root / "rule-catalog" / "routing-rules.yaml", "rules", RULE_REQUIRED_KEYS, "rule_id", errors
    )
    skill_ids = validate_catalog(
        root / "skill-catalog" / "skills.yaml", "skills", SKILL_REQUIRED_KEYS, "skill_id", errors
    )

    skills_dir = root.parent / "skills"
    if not skills_dir.exists():
        errors.append(f"missing directory: {skills_dir.as_posix()}")
    else:
        for skill_id in skill_ids:
            expected = skills_dir / f"{skill_id}.md"
            if not expected.exists():
                errors.append(f"missing skill file: {expected.as_posix()}")

    # Lightweight cross-reference checks
    teams_file = root / "team-catalog" / "teams.yaml"
    if teams_file.exists():
        data = load_yaml(teams_file)
        for idx, team in enumerate(as_list(data.get("teams"))):
            if not isinstance(team, dict):
                continue
            for skill_ref in as_list(team.get("skill_refs")):
                skill_text = str(skill_ref).strip()
                if skill_text and skill_text not in skill_ids:
                    errors.append(
                        f"{teams_file.as_posix()}: teams[{idx}].skill_refs references unknown skill '{skill_text}'"
                    )

    rules_file = root / "rule-catalog" / "routing-rules.yaml"
    if rules_file.exists():
        data = load_yaml(rules_file)
        for idx, rule in enumerate(as_list(data.get("rules"))):
            if not isinstance(rule, dict):
                continue
            for team in as_list(rule.get("require_teams")):
                team_text = str(team).strip()
                if team_text and team_text not in team_ids:
                    errors.append(
                        f"{rules_file.as_posix()}: rules[{idx}].require_teams references unknown team '{team_text}'"
                    )
            for skill in as_list(rule.get("require_skills")):
                skill_text = str(skill).strip()
                if skill_text and skill_text not in skill_ids:
                    errors.append(
                        f"{rules_file.as_posix()}: rules[{idx}].require_skills references unknown skill '{skill_text}'"
                    )

    if errors:
        for err in errors:
            print(f"ERROR [CONTROL_PLANE_INVALID] {err}")
        return 1

    intake_count = len(list((root / "intake").glob("*/*.yaml")))
    print(
        "OK [CONTROL_PLANE_VALID] "
        f"projects={len(project_ids)} intake_files={intake_count} teams={len(team_ids)} "
        f"rules={len(rule_ids)} skills={len(skill_ids)}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
