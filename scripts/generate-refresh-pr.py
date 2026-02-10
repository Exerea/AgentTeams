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


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate control-plane refresh queue/proposal artifacts")
    parser.add_argument("--control-plane", default=".takt/control-plane", help="control-plane root")
    parser.add_argument(
        "--incidents",
        default=".takt/control-plane/signals/incidents-detected.yaml",
        help="incident detection output",
    )
    parser.add_argument(
        "--overload",
        default=".takt/control-plane/signals/overload-detected.yaml",
        help="overload detection output",
    )
    parser.add_argument("--apply-catalog-updates", action="store_true", help="apply generated updates to catalogs")
    return parser.parse_args()


def load_yaml(path: Path) -> dict:
    if not path.exists():
        return {}
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    return data if isinstance(data, dict) else {}


def dump_yaml(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(data, allow_unicode=True, sort_keys=False), encoding="utf-8")


def now_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")


def ensure_list_map(data: dict, key: str) -> list[dict]:
    value = data.get(key)
    if isinstance(value, list):
        return [item for item in value if isinstance(item, dict)]
    return []


def append_unique_by_id(items: list[dict], id_key: str, candidate: dict) -> bool:
    candidate_id = str(candidate.get(id_key) or "").strip()
    if not candidate_id:
        return False
    for item in items:
        if str(item.get(id_key) or "").strip() == candidate_id:
            return False
    items.append(candidate)
    return True


def main() -> int:
    args = parse_args()
    cp_root = Path(args.control_plane).resolve()
    incidents_path = Path(args.incidents).resolve()
    overload_path = Path(args.overload).resolve()

    if not cp_root.exists():
        print(f"ERROR [REFRESH_CONTROL_PLANE_MISSING] {cp_root.as_posix()}")
        return 1

    incidents_data = load_yaml(incidents_path)
    overload_data = load_yaml(overload_path)

    recurring = ensure_list_map(incidents_data, "recurring_incidents")
    split_candidates = ensure_list_map(overload_data, "split_candidates")

    stamp = now_stamp()
    refresh_id = f"R-{stamp}"

    team_updates: list[dict] = []
    rule_updates: list[dict] = []
    skill_updates: list[dict] = []

    for candidate in split_candidates:
        project_id = str(candidate.get("project_id") or "").strip()
        capabilities = candidate.get("capabilities_for_new_team")
        caps = [str(v).strip() for v in capabilities] if isinstance(capabilities, list) else []
        caps = [cap for cap in caps if cap]
        if not caps:
            continue
        top_name = "-".join(slug(cap) for cap in caps[:2]) or "split"
        team_id = f"team-{slug(project_id)}-{top_name}"
        skill_id = f"skill-{slug(project_id)}-{top_name}"

        team_updates.append(
            {
                "team_id": team_id,
                "mission": f"specialized team carved out from overload candidate {project_id}",
                "owned_capabilities": caps[:2],
                "slo_targets": {"queue_p95_hours": 24, "lead_time_p50_hours": 48},
                "persona_ref": ".takt/personas/implementer.md",
                "policy_refs": [".takt/policies/governance.md", ".takt/policies/quality.md"],
                "skill_refs": [skill_id],
                "active": False,
                "source_refresh_id": refresh_id,
            }
        )

        skill_updates.append(
            {
                "skill_id": skill_id,
                "description": f"specialized execution skill for {project_id} overload split",
                "applies_to_teams": [team_id],
                "trigger": {"capability_tags": caps[:2]},
                "instruction_ref": f".takt/skills/{skill_id}.md",
                "policy_refs": [".takt/policies/governance.md", ".takt/policies/quality.md"],
                "evidence_requirements": [f"declarations controlled_by must include skill:{skill_id}"],
                "enabled": False,
                "source_refresh_id": refresh_id,
            }
        )

    for incident in recurring:
        fingerprint = str(incident.get("fingerprint") or "").strip()
        if not fingerprint:
            continue
        rule_id = f"incident-{slug(fingerprint)}"
        rule_updates.append(
            {
                "rule_id": rule_id,
                "when": {"incident_fingerprint": fingerprint},
                "require_teams": ["coordinator", "qa-review-guild"],
                "require_skills": ["skill-qa-regression-trace"],
                "priority": 70,
                "enabled": False,
                "source_refresh_id": refresh_id,
            }
        )

    refresh_queue = {
        "refresh_id": refresh_id,
        "created_at": now_iso(),
        "source": "auto-detect",
        "status": "pending_review",
        "findings": {"incidents": recurring, "overload_candidates": split_candidates},
        "actions": {
            "team_catalog_updates": team_updates,
            "routing_rule_updates": rule_updates,
            "skill_updates": skill_updates,
        },
    }

    queue_path = cp_root / "refresh-queue" / f"{refresh_id}.yaml"
    dump_yaml(queue_path, refresh_queue)

    proposal_path = cp_root / "refresh-proposals" / f"RP-{stamp}.md"
    proposal_lines = [
        f"# Refresh Proposal RP-{stamp}",
        "",
        "## Context",
        f"- refresh_id: `{refresh_id}`",
        f"- generated_at: `{now_iso()}`",
        f"- recurring_incidents: `{len(recurring)}`",
        f"- split_candidates: `{len(split_candidates)}`",
        "",
        "## Proposed Team Updates",
    ]
    if team_updates:
        proposal_lines.extend([f"- `{item['team_id']}` capabilities={item['owned_capabilities']}" for item in team_updates])
    else:
        proposal_lines.append("- none")

    proposal_lines.append("")
    proposal_lines.append("## Proposed Rule Updates")
    if rule_updates:
        proposal_lines.extend([f"- `{item['rule_id']}` incident={item['when'].get('incident_fingerprint')}" for item in rule_updates])
    else:
        proposal_lines.append("- none")

    proposal_lines.append("")
    proposal_lines.append("## Proposed Skill Updates")
    if skill_updates:
        proposal_lines.extend([f"- `{item['skill_id']}` applies_to={item['applies_to_teams']}" for item in skill_updates])
    else:
        proposal_lines.append("- none")

    proposal_lines.append("")
    proposal_lines.append("## Required Gates")
    proposal_lines.append("- qa_review")
    proposal_lines.append("- leader_gate")
    proposal_path.parent.mkdir(parents=True, exist_ok=True)
    proposal_path.write_text("\n".join(proposal_lines).strip() + "\n", encoding="utf-8")

    updated_files: list[str] = []
    if args.apply_catalog_updates:
        teams_path = cp_root / "team-catalog" / "teams.yaml"
        rules_path = cp_root / "rule-catalog" / "routing-rules.yaml"
        skills_path = cp_root / "skill-catalog" / "skills.yaml"

        teams_data = load_yaml(teams_path) or {"version": 1, "teams": []}
        rules_data = load_yaml(rules_path) or {"version": 1, "rules": []}
        skills_data = load_yaml(skills_path) or {"version": 1, "skills": []}

        teams_list = ensure_list_map(teams_data, "teams")
        rules_list = ensure_list_map(rules_data, "rules")
        skills_list = ensure_list_map(skills_data, "skills")

        team_changed = False
        for item in team_updates:
            if append_unique_by_id(teams_list, "team_id", item):
                team_changed = True

        rule_changed = False
        for item in rule_updates:
            if append_unique_by_id(rules_list, "rule_id", item):
                rule_changed = True

        skill_changed = False
        for item in skill_updates:
            if append_unique_by_id(skills_list, "skill_id", item):
                skill_changed = True

        if team_changed:
            teams_data["teams"] = teams_list
            dump_yaml(teams_path, teams_data)
            updated_files.append(teams_path.as_posix())
        if rule_changed:
            rules_data["rules"] = rules_list
            dump_yaml(rules_path, rules_data)
            updated_files.append(rules_path.as_posix())
        if skill_changed:
            skills_data["skills"] = skills_list
            dump_yaml(skills_path, skills_data)
            updated_files.append(skills_path.as_posix())

        for skill in skill_updates:
            skill_id = str(skill.get("skill_id") or "").strip()
            if not skill_id:
                continue
            skill_doc = cp_root.parent / "skills" / f"{skill_id}.md"
            if skill_doc.exists():
                continue
            skill_doc.parent.mkdir(parents=True, exist_ok=True)
            skill_doc.write_text(
                "\n".join(
                    [
                        f"# Skill: {skill_id}",
                        "",
                        "Generated by auto refresh proposal.",
                        "",
                        "Checklist:",
                        "- verify proposed scope",
                        "- validate evidence collection requirements",
                        f"- include `skill:{skill_id}` in declarations",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            updated_files.append(skill_doc.as_posix())

    print(
        "OK [REFRESH_PROPOSAL_GENERATED] "
        f"refresh_id={refresh_id} queue={queue_path.as_posix()} proposal={proposal_path.as_posix()} "
        f"catalog_updates={len(updated_files)}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
