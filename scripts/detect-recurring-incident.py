#!/usr/bin/env python3
from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
import re
import sys


IMPROVEMENT_PATTERN = re.compile(
    r"IMPROVEMENT_PROPOSAL\s+type=(?:process|role|tool|rule|cleanup)\s+priority=(?:high|medium|low)\s+owner=coordinator\s+summary=.+"
)


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8").lstrip("\ufeff")


def normalize(value: str) -> str:
    v = (value or "").strip()
    if (v.startswith('"') and v.endswith('"')) or (v.startswith("'") and v.endswith("'")):
        v = v[1:-1]
    return v.strip()


def parse_dt(value: str) -> datetime | None:
    raw = normalize(value)
    if not raw:
        return None
    if raw.endswith("Z"):
        raw = raw[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(raw)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def parse_rules(path: Path) -> dict[str, int]:
    out = {
        "recency_days": 14,
        "warning_code_hotspot_count": 3,
        "warning_code_hotspot_tasks": 2,
    }
    if not path.exists():
        return out
    for ln in read_text(path).splitlines():
        m = re.match(
            r"^(recency_days|warning_code_hotspot_count|warning_code_hotspot_tasks)\s*:\s*(\d+)\s*$",
            ln.strip(),
        )
        if not m:
            continue
        out[m.group(1)] = int(m.group(2))
    return out


def parse_cache_registry(path: Path) -> list[dict[str, str]]:
    incidents: list[dict[str, str]] = []
    if not path.exists():
        return incidents

    section = ""
    in_item = False
    item: dict[str, str] = {}

    def flush_item() -> None:
        nonlocal in_item, item
        if in_item and item:
            incidents.append(item.copy())
        in_item = False
        item = {}

    for ln in read_text(path).splitlines():
        m_top = re.match(r"^([A-Za-z_][A-Za-z0-9_]*)\s*:\s*(.*)$", ln)
        if m_top:
            flush_item()
            section = m_top.group(1)
            continue
        if section != "incidents":
            continue
        m_item = re.match(r"^\s{2}-\s*(.*)$", ln)
        if m_item:
            flush_item()
            in_item = True
            inline = m_item.group(1).strip()
            if inline:
                m_inline = re.match(r"^([A-Za-z_][A-Za-z0-9_]*)\s*:\s*(.*)$", inline)
                if m_inline:
                    item[m_inline.group(1)] = normalize(m_inline.group(2))
            continue
        if in_item:
            m_key = re.match(r"^\s{4}([A-Za-z_][A-Za-z0-9_]*)\s*:\s*(.*)$", ln)
            if m_key:
                item[m_key.group(1)] = normalize(m_key.group(2))

    flush_item()
    return incidents


def parse_task(path: Path) -> dict:
    lines = read_text(path).splitlines()
    task = {
        "id": "",
        "assignee": "",
        "status": "",
        "notes": "",
        "updated_at": "",
        "warnings": [],
        "handoffs": [],
    }
    section = ""
    in_warning = False
    warning: dict[str, str] = {}
    in_handoff = False
    handoff: dict[str, str] = {}

    def flush_warning() -> None:
        nonlocal in_warning, warning
        if in_warning and warning:
            task["warnings"].append(warning.copy())
        in_warning = False
        warning = {}

    def flush_handoff() -> None:
        nonlocal in_handoff, handoff
        if in_handoff and handoff:
            task["handoffs"].append(handoff.copy())
        in_handoff = False
        handoff = {}

    for ln in lines:
        m_top = re.match(r"^([A-Za-z_][A-Za-z0-9_]*)\s*:\s*(.*)$", ln)
        if m_top:
            flush_warning()
            flush_handoff()
            section = m_top.group(1)
            val = normalize(m_top.group(2))
            if section in {"id", "assignee", "status", "notes", "updated_at"}:
                task[section] = val
            continue

        if section == "warnings":
            m_item = re.match(r"^\s{2}-\s*(.*)$", ln)
            if m_item:
                flush_warning()
                in_warning = True
                inline = m_item.group(1).strip()
                if inline:
                    m_inline = re.match(r"^([A-Za-z_][A-Za-z0-9_]*)\s*:\s*(.*)$", inline)
                    if m_inline:
                        warning[m_inline.group(1)] = normalize(m_inline.group(2))
                continue
            if in_warning:
                m_key = re.match(r"^\s{4}([A-Za-z_][A-Za-z0-9_]*)\s*:\s*(.*)$", ln)
                if m_key:
                    warning[m_key.group(1)] = normalize(m_key.group(2))
            continue

        if section == "handoffs":
            m_item = re.match(r"^\s{2}-\s*(.*)$", ln)
            if m_item:
                flush_handoff()
                in_handoff = True
                inline = m_item.group(1).strip()
                if inline:
                    m_inline = re.match(r"^([A-Za-z_][A-Za-z0-9_]*)\s*:\s*(.*)$", inline)
                    if m_inline:
                        handoff[m_inline.group(1)] = normalize(m_inline.group(2))
                continue
            if in_handoff:
                m_key = re.match(r"^\s{4}([A-Za-z_][A-Za-z0-9_]*)\s*:\s*(.*)$", ln)
                if m_key:
                    handoff[m_key.group(1)] = normalize(m_key.group(2))
            continue

    flush_warning()
    flush_handoff()
    task["updated_dt"] = parse_dt(str(task["updated_at"]))
    return task


def has_improvement_evidence(task: dict) -> bool:
    notes = normalize(str(task.get("notes", "")))
    if IMPROVEMENT_PATTERN.search(notes):
        return True
    for handoff in task.get("handoffs", []):
        memo = normalize(str(handoff.get("memo", "")))
        if IMPROVEMENT_PATTERN.search(memo):
            return True
    return False


def has_interaction_auditor_handoff(task: dict) -> bool:
    for handoff in task.get("handoffs", []):
        from_role = normalize(str(handoff.get("from", "")))
        to_role = normalize(str(handoff.get("to", "")))
        if from_role == "protocol-team/interaction-auditor" or to_role == "protocol-team/interaction-auditor":
            return True
    return False


def has_coordinator_triage(task: dict) -> bool:
    if normalize(str(task.get("assignee", ""))) == "coordinator":
        return True
    for handoff in task.get("handoffs", []):
        from_role = normalize(str(handoff.get("from", "")))
        to_role = normalize(str(handoff.get("to", "")))
        if from_role == "coordinator/coordinator" or to_role == "coordinator/coordinator":
            return True
    return False


def main() -> int:
    repo_root = Path(__file__).resolve().parent.parent
    rules = parse_rules(repo_root / ".codex" / "role-gap-rules.yaml")
    cache_path = repo_root / ".codex" / "cache" / "incident-registry.yaml"
    states_dir = repo_root / ".codex" / "states"
    archive_dir = states_dir / "archive"

    registry_incidents = parse_cache_registry(cache_path)
    if not registry_incidents:
        print(
            f"WARN [INCIDENT_REGISTRY_MISSING] recurring-incident detection skipped because cache is missing or empty: {cache_path.as_posix()}"
        )
        return 0

    registry_map: dict[tuple[str, str], dict[str, str]] = {}
    for item in registry_incidents:
        warning_code = normalize(str(item.get("fingerprint_warning_code", "")))
        role_pair = normalize(str(item.get("fingerprint_role_pair", "")))
        non_malicious = normalize(str(item.get("classification_non_malicious", ""))).lower()
        status = normalize(str(item.get("status", ""))).lower()
        if not warning_code or not role_pair:
            continue
        if non_malicious != "true":
            continue
        if status not in {"open", "monitoring"}:
            continue
        registry_map[(warning_code, role_pair)] = item

    now = datetime.now(timezone.utc)
    recency_cutoff = now - timedelta(days=rules["recency_days"])
    threshold_count = rules["warning_code_hotspot_count"]
    threshold_tasks = rules["warning_code_hotspot_tasks"]

    task_files = sorted(states_dir.glob("TASK-*.yaml"))
    if archive_dir.exists():
        task_files.extend(sorted(archive_dir.glob("*.yaml")))
    tasks: dict[str, dict] = {}
    for path in task_files:
        task = parse_task(path)
        task_id = normalize(str(task.get("id", ""))) or path.name
        tasks[task_id] = task

    occurrences: dict[tuple[str, str], list[str]] = defaultdict(list)
    for task_id, task in tasks.items():
        for warning in task.get("warnings", []):
            warning_code = normalize(str(warning.get("code", "")))
            source_role = normalize(str(warning.get("source_role", "")))
            target_role = normalize(str(warning.get("target_role", "")))
            role_pair = f"{source_role}->{target_role}" if source_role and target_role else ""
            detected_at = parse_dt(str(warning.get("detected_at", "")))
            if detected_at is None:
                detected_at = task.get("updated_dt")
            if detected_at is None or detected_at < recency_cutoff:
                continue
            if not warning_code or not role_pair:
                continue
            occurrences[(warning_code, role_pair)].append(task_id)

    recurring_keys = [
        key
        for key, task_ids in occurrences.items()
        if len(task_ids) >= threshold_count and len(set(task_ids)) >= threshold_tasks
    ]

    if not recurring_keys:
        print("recurring incident detection passed: no recurring keys matched threshold")
        return 0

    errors: list[str] = []
    matched = 0
    for key in recurring_keys:
        if key not in registry_map:
            continue
        matched += 1
        task_ids = sorted(set(occurrences[key]))
        relevant_tasks = [tasks[task_id] for task_id in task_ids if task_id in tasks]

        has_improvement = any(has_improvement_evidence(task) for task in relevant_tasks)
        has_auditor = any(has_interaction_auditor_handoff(task) for task in relevant_tasks)
        has_triage = any(has_coordinator_triage(task) for task in relevant_tasks)

        if not has_improvement:
            errors.append(
                f"RECURRING_INCIDENT_ROOT_CAUSE_MISSING key={key[0]}|{key[1]} missing IMPROVEMENT_PROPOSAL evidence"
            )
        if not has_auditor:
            errors.append(
                f"RECURRING_INCIDENT_AUDIT_HANDOFF_MISSING key={key[0]}|{key[1]} missing protocol-team/interaction-auditor handoff"
            )
        if not has_triage:
            errors.append(
                f"RECURRING_INCIDENT_TRIAGE_MISSING key={key[0]}|{key[1]} missing coordinator triage evidence"
            )

    if matched == 0:
        print("recurring incident detection passed: no recurring keys matched incident registry")
        return 0

    if errors:
        for error in errors:
            print(f"ERROR [{error.split()[0]}] {' '.join(error.split()[1:])}", file=sys.stderr)
        return 1

    print(f"recurring incident detection passed: matched_keys={matched}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
