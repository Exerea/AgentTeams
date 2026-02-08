#!/usr/bin/env python3
from __future__ import annotations

from argparse import ArgumentParser, Namespace
from datetime import datetime, timezone
from pathlib import Path
import re
import sys


ALLOWED_STATUSES = {"open", "monitoring", "resolved"}
ALLOWED_ROOT_ACTIONS = {"process", "role", "tool", "rule", "cleanup"}


def fail(message: str) -> int:
    print(f"ERROR: {message}", file=sys.stderr)
    return 1


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


def parse_index(path: Path) -> dict:
    data: dict[str, object] = {"version": "", "updated_at": "", "incidents": []}
    lines = read_text(path).splitlines()
    section = ""
    in_item = False
    item: dict[str, str] = {}

    def flush_item() -> None:
        nonlocal in_item, item
        if in_item and item:
            data["incidents"].append(item.copy())  # type: ignore[arg-type]
        in_item = False
        item = {}

    for ln in lines:
        m_top = re.match(r"^([A-Za-z_][A-Za-z0-9_]*)\s*:\s*(.*)$", ln)
        if m_top:
            flush_item()
            key = m_top.group(1)
            val = normalize(m_top.group(2))
            section = key
            if key in {"version", "updated_at"}:
                data[key] = val
            if key == "incidents" and val == "[]":
                section = ""
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

        if not in_item:
            continue

        m_key = re.match(r"^\s{4}([A-Za-z_][A-Za-z0-9_]*)\s*:\s*(.*)$", ln)
        if m_key:
            item[m_key.group(1)] = normalize(m_key.group(2))

    flush_item()
    return data


def parse_incident(path: Path) -> dict:
    data: dict[str, object] = {
        "id": "",
        "title": "",
        "fingerprint": {},
        "classification": {},
        "first_seen_at": "",
        "last_seen_at": "",
        "occurrence_count_global": "",
        "projects_seen": [],
        "source_tasks": [],
        "suggested_root_actions": "",
        "status": "",
        "updated_at": "",
    }

    section = ""
    in_projects = False
    in_tasks = False
    for ln in read_text(path).splitlines():
        m_top = re.match(r"^([A-Za-z_][A-Za-z0-9_]*)\s*:\s*(.*)$", ln)
        if m_top:
            key = m_top.group(1)
            val = normalize(m_top.group(2))
            section = key
            in_projects = False
            in_tasks = False

            if key in {
                "id",
                "title",
                "first_seen_at",
                "last_seen_at",
                "occurrence_count_global",
                "suggested_root_actions",
                "status",
                "updated_at",
            }:
                data[key] = val
                continue
            if key == "projects_seen":
                if val == "[]":
                    data["projects_seen"] = []
                    section = ""
                else:
                    in_projects = True
                continue
            if key == "source_tasks":
                if val == "[]":
                    data["source_tasks"] = []
                    section = ""
                else:
                    in_tasks = True
                continue
            continue

        if section == "fingerprint":
            m = re.match(r"^\s{2}([A-Za-z_][A-Za-z0-9_]*)\s*:\s*(.*)$", ln)
            if m:
                fp = data["fingerprint"]  # type: ignore[assignment]
                assert isinstance(fp, dict)
                fp[m.group(1)] = normalize(m.group(2))
            continue

        if section == "classification":
            m = re.match(r"^\s{2}([A-Za-z_][A-Za-z0-9_]*)\s*:\s*(.*)$", ln)
            if m:
                cl = data["classification"]  # type: ignore[assignment]
                assert isinstance(cl, dict)
                cl[m.group(1)] = normalize(m.group(2))
            continue

        if section == "projects_seen":
            if in_projects:
                m = re.match(r"^\s{2}-\s*(.+)$", ln)
                if m:
                    projects = data["projects_seen"]  # type: ignore[assignment]
                    assert isinstance(projects, list)
                    projects.append(normalize(m.group(1)))
                    continue
            in_projects = False
            continue

        if section == "source_tasks":
            if in_tasks:
                m = re.match(r"^\s{2}-\s*(.+)$", ln)
                if m:
                    tasks = data["source_tasks"]  # type: ignore[assignment]
                    assert isinstance(tasks, list)
                    tasks.append(normalize(m.group(1)))
                    continue
            in_tasks = False
            continue

    return data


def parse_args(argv: list[str]) -> Namespace:
    parser = ArgumentParser(description="Validate incident registry schema and consistency.")
    parser.add_argument(
        "--root",
        default="knowledge/incidents",
        help="incident registry root directory (default: knowledge/incidents)",
    )
    return parser.parse_args(argv)


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    root = Path(args.root)
    index_path = root / "_index.yaml"
    if not index_path.exists():
        return fail(f"missing index file: {index_path.as_posix()}")

    index = parse_index(index_path)
    errors: list[str] = []
    version = normalize(str(index.get("version", "")))
    updated_at = normalize(str(index.get("updated_at", "")))
    incidents = index.get("incidents", [])

    if not version:
        errors.append("index.version is required")
    if parse_dt(updated_at) is None:
        errors.append("index.updated_at must be ISO-8601 timestamp")
    if not isinstance(incidents, list):
        errors.append("index.incidents must be a list")
        incidents = []

    index_map: dict[str, dict[str, str]] = {}
    for i, item in enumerate(incidents):
        if not isinstance(item, dict):
            errors.append(f"index.incidents[{i}] must be an object")
            continue
        item_id = normalize(str(item.get("id", "")))
        item_file = normalize(str(item.get("file", "")))
        item_warning = normalize(str(item.get("fingerprint_warning_code", "")))
        item_role_pair = normalize(str(item.get("fingerprint_role_pair", "")))
        item_non_malicious = normalize(str(item.get("classification_non_malicious", ""))).lower()
        item_status = normalize(str(item.get("status", "")))
        item_updated = normalize(str(item.get("updated_at", "")))
        missing = [
            key
            for key in (
                "id",
                "file",
                "fingerprint_warning_code",
                "fingerprint_role_pair",
                "classification_non_malicious",
                "status",
                "updated_at",
            )
            if not normalize(str(item.get(key, "")))
        ]
        if missing:
            errors.append(f"index entry missing keys for id={item_id or 'N/A'}: {', '.join(missing)}")
            continue
        if item_status not in ALLOWED_STATUSES:
            errors.append(f"index entry invalid status for id={item_id}: {item_status}")
        if item_non_malicious not in {"true", "false"}:
            errors.append(f"index entry classification_non_malicious must be true/false for id={item_id}")
        if parse_dt(item_updated) is None:
            errors.append(f"index entry updated_at is invalid for id={item_id}")
        if item_id in index_map:
            errors.append(f"duplicate incident id in index: {item_id}")
            continue
        index_map[item_id] = {
            "file": item_file,
            "warning_code": item_warning,
            "role_pair": item_role_pair,
            "classification_non_malicious": item_non_malicious,
            "status": item_status,
        }

    for incident_id, meta in index_map.items():
        incident_path = Path(meta["file"])
        if not incident_path.is_absolute():
            candidates = [
                (root / incident_path).resolve(),
                (root.parent.parent / incident_path).resolve(),
                (Path(".") / incident_path).resolve(),
            ]
            resolved_path = None
            for candidate in candidates:
                if candidate.exists():
                    resolved_path = candidate
                    break
            if resolved_path is None:
                resolved_path = candidates[0]
            incident_path = resolved_path
        if not incident_path.exists():
            errors.append(f"incident file does not exist for id={incident_id}: {meta['file']}")
            continue

        incident = parse_incident(incident_path)
        incident_id_file = normalize(str(incident.get("id", "")))
        title = normalize(str(incident.get("title", "")))
        first_seen_at = normalize(str(incident.get("first_seen_at", "")))
        last_seen_at = normalize(str(incident.get("last_seen_at", "")))
        updated = normalize(str(incident.get("updated_at", "")))
        status = normalize(str(incident.get("status", "")))
        suggested = normalize(str(incident.get("suggested_root_actions", "")))
        occurrence = normalize(str(incident.get("occurrence_count_global", "")))
        projects = incident.get("projects_seen", [])
        tasks = incident.get("source_tasks", [])
        fingerprint = incident.get("fingerprint", {})
        classification = incident.get("classification", {})

        if incident_id_file != incident_id:
            errors.append(f"id mismatch between index and file: {incident_id} vs {incident_id_file}")
        if not title:
            errors.append(f"incident title is required: {incident_id}")

        fp_warning = ""
        fp_role_pair = ""
        fp_gate = ""
        fp_keywords = ""
        if not isinstance(fingerprint, dict):
            errors.append(f"fingerprint must be object: {incident_id}")
        else:
            fp_warning = normalize(str(fingerprint.get("warning_code", "")))
            fp_role_pair = normalize(str(fingerprint.get("role_pair", "")))
            fp_gate = normalize(str(fingerprint.get("gate", "")))
            fp_keywords = normalize(str(fingerprint.get("keywords", "")))
            for key, value in (
                ("warning_code", fp_warning),
                ("role_pair", fp_role_pair),
                ("gate", fp_gate),
                ("keywords", fp_keywords),
            ):
                if not value:
                    errors.append(f"fingerprint.{key} is required: {incident_id}")

        if not isinstance(classification, dict):
            errors.append(f"classification must be object: {incident_id}")
            non_malicious = ""
        else:
            non_malicious = normalize(str(classification.get("non_malicious", ""))).lower()
            if non_malicious not in {"true", "false"}:
                errors.append(f"classification.non_malicious must be true/false: {incident_id}")

        dt_first = parse_dt(first_seen_at)
        dt_last = parse_dt(last_seen_at)
        dt_updated = parse_dt(updated)
        if dt_first is None:
            errors.append(f"first_seen_at must be ISO-8601: {incident_id}")
        if dt_last is None:
            errors.append(f"last_seen_at must be ISO-8601: {incident_id}")
        if dt_updated is None:
            errors.append(f"updated_at must be ISO-8601: {incident_id}")
        if dt_first and dt_last and dt_first > dt_last:
            errors.append(f"first_seen_at must be <= last_seen_at: {incident_id}")
        if dt_last and dt_updated and dt_last > dt_updated:
            errors.append(f"last_seen_at must be <= updated_at: {incident_id}")

        if not occurrence.isdigit() or int(occurrence) < 1:
            errors.append(f"occurrence_count_global must be integer >=1: {incident_id}")
        if suggested not in ALLOWED_ROOT_ACTIONS:
            errors.append(f"suggested_root_actions is invalid: {incident_id} -> {suggested}")
        if status not in ALLOWED_STATUSES:
            errors.append(f"status is invalid: {incident_id} -> {status}")
        if not isinstance(projects, list) or len(projects) == 0:
            errors.append(f"projects_seen must be non-empty list: {incident_id}")
        if not isinstance(tasks, list) or len(tasks) == 0:
            errors.append(f"source_tasks must be non-empty list: {incident_id}")

        if meta["warning_code"] != fp_warning:
            errors.append(f"index warning code mismatch for id={incident_id}")
        if meta["role_pair"] != fp_role_pair:
            errors.append(f"index role_pair mismatch for id={incident_id}")
        if meta["classification_non_malicious"] != non_malicious:
            errors.append(f"index classification_non_malicious mismatch for id={incident_id}")
        if meta["status"] != status:
            errors.append(f"index status mismatch for id={incident_id}")

    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1

    print(f"incident registry is valid: {root.as_posix()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
