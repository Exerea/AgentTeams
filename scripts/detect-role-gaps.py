#!/usr/bin/env python3
from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
import re


SIGNAL_TYPES = {
    "warning_code_hotspot",
    "role_pair_hotspot",
    "handoff_ping_pong",
    "blocked_stall",
    "gate_repeat_block",
    "ux_psychology_hotspot",
}
SUGGESTED_ACTIONS = {"no_change", "skill_update", "role_split", "new_role"}


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


def iso_utc(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def parse_rules(path: Path) -> dict:
    defaults = {
        "version": "v1",
        "recency_days": 14,
        "blocked_stall_hours": 48,
        "open_review_max_days": 7,
        "warning_code_hotspot_count": 3,
        "warning_code_hotspot_tasks": 2,
        "role_pair_hotspot_count": 3,
        "handoff_ping_pong_count": 4,
        "gate_repeat_block_count": 3,
        "ux_psychology_hotspot_count": 3,
        "ux_psychology_hotspot_tasks": 2,
        "blocked_stall_keywords": ["担当外", "role boundary", "再割当"],
        "gate_keywords": [
            "ADR Gate",
            "Documentation Sync Gate",
            "Protocol Gate",
            "Tech Gate",
            "QA Gate",
            "Backend Security Gate",
            "Research Gate",
            "Secret Scan Gate",
            "UX Gate",
        ],
        "ux_psychology_keywords": [
            "ux",
            "ユーザー体験",
            "認知負荷",
            "決断疲れ",
            "オンボーディング",
            "導線",
            "摩擦",
            "離脱",
            "ダークパターン",
            "dark pattern",
            "nudge",
        ],
        "actions": {
            "warning_code_hotspot": "skill_update",
            "role_pair_hotspot": "role_split",
            "handoff_ping_pong": "role_split",
            "blocked_stall": "new_role",
            "gate_repeat_block": "skill_update",
            "ux_psychology_hotspot": "skill_update",
        },
    }
    if not path.exists():
        return defaults

    for ln in read_text(path).splitlines():
        s = ln.strip()
        if not s or s.startswith("#"):
            continue
        m = re.match(r"^([A-Za-z_][A-Za-z0-9_]*)\s*:\s*(.*)$", s)
        if not m:
            continue
        key, value = m.group(1), normalize(m.group(2))
        if key in {
            "recency_days",
            "blocked_stall_hours",
            "open_review_max_days",
            "warning_code_hotspot_count",
            "warning_code_hotspot_tasks",
            "role_pair_hotspot_count",
            "handoff_ping_pong_count",
            "gate_repeat_block_count",
            "ux_psychology_hotspot_count",
            "ux_psychology_hotspot_tasks",
        }:
            try:
                defaults[key] = int(value)
            except ValueError:
                pass
            continue
        if key == "version":
            defaults["version"] = value or defaults["version"]
            continue
        if key == "blocked_stall_keywords":
            defaults["blocked_stall_keywords"] = [x.strip() for x in value.split("|") if x.strip()]
            continue
        if key == "gate_keywords":
            defaults["gate_keywords"] = [x.strip() for x in value.split("|") if x.strip()]
            continue
        if key == "ux_psychology_keywords":
            defaults["ux_psychology_keywords"] = [x.strip().lower() for x in value.split("|") if x.strip()]
            continue
        m_action = re.match(
            r"^action_(warning_code_hotspot|role_pair_hotspot|handoff_ping_pong|blocked_stall|gate_repeat_block|ux_psychology_hotspot)$",
            key,
        )
        if m_action and value in SUGGESTED_ACTIONS:
            defaults["actions"][m_action.group(1)] = value

    return defaults


def parse_task(path: Path) -> dict:
    lines = read_text(path).splitlines()
    out = {
        "id": "",
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
        nonlocal warning, in_warning
        if in_warning and warning:
            out["warnings"].append(warning.copy())
        warning = {}
        in_warning = False

    def flush_handoff() -> None:
        nonlocal handoff, in_handoff
        if in_handoff and handoff:
            out["handoffs"].append(handoff.copy())
        handoff = {}
        in_handoff = False

    for ln in lines:
        m_top = re.match(r"^([A-Za-z_][A-Za-z0-9_]*)\s*:\s*(.*)$", ln)
        if m_top:
            flush_warning()
            flush_handoff()
            section = m_top.group(1)
            val = normalize(m_top.group(2))
            if section in {"id", "status", "notes", "updated_at"}:
                out[section] = val
            continue

        if section == "warnings":
            m_item = re.match(r"^\s{2}-\s*(.*)$", ln)
            if m_item:
                flush_warning()
                in_warning = True
                warning = {}
                inline = m_item.group(1).strip()
                if inline:
                    m_inline = re.match(r"^([A-Za-z_][A-Za-z0-9_]*)\s*:\s*(.*)$", inline)
                    if m_inline:
                        warning[m_inline.group(1)] = normalize(m_inline.group(2))
                continue
            m_key = re.match(r"^\s{4}([A-Za-z_][A-Za-z0-9_]*)\s*:\s*(.*)$", ln)
            if in_warning and m_key:
                warning[m_key.group(1)] = normalize(m_key.group(2))
            continue

        if section == "handoffs":
            m_item = re.match(r"^\s{2}-\s*(.*)$", ln)
            if m_item:
                flush_handoff()
                in_handoff = True
                handoff = {}
                inline = m_item.group(1).strip()
                if inline:
                    m_inline = re.match(r"^([A-Za-z_][A-Za-z0-9_]*)\s*:\s*(.*)$", inline)
                    if m_inline:
                        handoff[m_inline.group(1)] = normalize(m_inline.group(2))
                continue
            m_key = re.match(r"^\s{4}([A-Za-z_][A-Za-z0-9_]*)\s*:\s*(.*)$", ln)
            if in_handoff and m_key:
                handoff[m_key.group(1)] = normalize(m_key.group(2))
            continue

    flush_warning()
    flush_handoff()

    out["id"] = out["id"] or path.name
    out["updated_dt"] = parse_dt(out["updated_at"])
    return out


def parse_role_gap_index(path: Path) -> dict:
    out = {"version": "v1", "updated_at": "", "candidates": []}
    if not path.exists():
        return out

    section = ""
    in_candidate = False
    in_evidence = False
    candidate: dict[str, object] = {}

    def flush_candidate() -> None:
        nonlocal candidate, in_candidate, in_evidence
        if in_candidate:
            candidate.setdefault("evidence_task_ids", [])
            out["candidates"].append(candidate.copy())
        candidate = {}
        in_candidate = False
        in_evidence = False

    for ln in read_text(path).splitlines():
        m_top = re.match(r"^([A-Za-z_][A-Za-z0-9_]*)\s*:\s*(.*)$", ln)
        if m_top:
            flush_candidate()
            section = m_top.group(1)
            val = normalize(m_top.group(2))
            if section in {"version", "updated_at"}:
                out[section] = val
            if section == "candidates" and val == "[]":
                section = ""
            continue

        if section != "candidates":
            continue

        m_item = re.match(r"^\s{2}-\s*(.*)$", ln)
        if m_item:
            flush_candidate()
            in_candidate = True
            candidate = {"evidence_task_ids": []}
            inline = m_item.group(1).strip()
            if inline:
                m_inline = re.match(r"^([A-Za-z_][A-Za-z0-9_]*)\s*:\s*(.*)$", inline)
                if m_inline:
                    candidate[m_inline.group(1)] = normalize(m_inline.group(2))
            continue

        if not in_candidate:
            continue

        m_ev_head = re.match(r"^\s{4}evidence_task_ids\s*:\s*(.*)$", ln)
        if m_ev_head:
            in_evidence = True
            inline = normalize(m_ev_head.group(1))
            if inline == "[]":
                candidate["evidence_task_ids"] = []
                in_evidence = False
            continue

        if in_evidence:
            m_ev_item = re.match(r"^\s{6}-\s*(.+)$", ln)
            if m_ev_item:
                candidate.setdefault("evidence_task_ids", []).append(normalize(m_ev_item.group(1)))
                continue
            in_evidence = False

        m_key = re.match(r"^\s{4}([A-Za-z_][A-Za-z0-9_]*)\s*:\s*(.*)$", ln)
        if m_key:
            candidate[m_key.group(1)] = normalize(m_key.group(2))

    flush_candidate()
    return out


def quote(value: str) -> str:
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'


def write_role_gap_index(path: Path, data: dict) -> None:
    candidates = data.get("candidates", [])
    lines = [
        f"version: {data.get('version', 'v1')}",
        f"updated_at: {data.get('updated_at', '')}",
    ]
    if not candidates:
        lines.append("candidates: []")
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return

    lines.append("candidates:")
    for c in candidates:
        lines.append(f"  - id: {normalize(str(c.get('id', '')))}")
        lines.append(f"    signal_type: {normalize(str(c.get('signal_type', '')))}")
        lines.append(f"    summary: {quote(normalize(str(c.get('summary', ''))))}")
        evidence = c.get("evidence_task_ids", [])
        if not isinstance(evidence, list):
            evidence = []
        if evidence:
            lines.append("    evidence_task_ids:")
            for task_id in evidence:
                lines.append(f"      - {normalize(str(task_id))}")
        else:
            lines.append("    evidence_task_ids: []")
        lines.append(f"    suggested_actions: {normalize(str(c.get('suggested_actions', 'no_change')))}")
        lines.append(f"    owner: {normalize(str(c.get('owner', 'coordinator')))}")
        lines.append(f"    status: {normalize(str(c.get('status', 'open')))}")
        lines.append(f"    decision_note: {quote(normalize(str(c.get('decision_note', ''))))}")
        lines.append(f"    adr_ref: {quote(normalize(str(c.get('adr_ref', ''))))}")
        lines.append(f"    updated_at: {normalize(str(c.get('updated_at', '')))}")

    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def build_candidate(signal_type: str, summary: str, evidence_task_ids: list[str], suggested_action: str, now_iso: str) -> dict:
    return {
        "id": "",
        "signal_type": signal_type,
        "summary": summary,
        "evidence_task_ids": sorted(set(evidence_task_ids)),
        "suggested_actions": suggested_action if suggested_action in SUGGESTED_ACTIONS else "no_change",
        "owner": "coordinator",
        "status": "open",
        "decision_note": "",
        "adr_ref": "",
        "updated_at": now_iso,
    }


def candidate_key(candidate: dict) -> tuple:
    evidence = candidate.get("evidence_task_ids", [])
    if not isinstance(evidence, list):
        evidence = []
    return (
        normalize(str(candidate.get("signal_type", ""))),
        normalize(str(candidate.get("summary", ""))),
        tuple(sorted(normalize(str(x)) for x in evidence)),
    )


def next_candidate_id(existing_ids: list[str], now_dt: datetime) -> str:
    prefix = f"RG-{now_dt.strftime('%Y%m%d')}-"
    max_no = 0
    for cid in existing_ids:
        if not cid.startswith(prefix):
            continue
        tail = cid[len(prefix) :]
        if tail.isdigit():
            max_no = max(max_no, int(tail))
    return f"{prefix}{max_no + 1:03d}"


def main() -> int:
    repo_root = Path(__file__).resolve().parent.parent
    rules_path = repo_root / ".codex" / "role-gap-rules.yaml"
    index_path = repo_root / ".codex" / "states" / "_role-gap-index.yaml"
    states_dir = repo_root / ".codex" / "states"
    archive_dir = states_dir / "archive"

    rules = parse_rules(rules_path)
    recency_days = int(rules["recency_days"])
    blocked_stall_hours = int(rules["blocked_stall_hours"])
    warning_code_hotspot_count = int(rules["warning_code_hotspot_count"])
    warning_code_hotspot_tasks = int(rules["warning_code_hotspot_tasks"])
    role_pair_hotspot_count = int(rules["role_pair_hotspot_count"])
    handoff_ping_pong_count = int(rules["handoff_ping_pong_count"])
    gate_repeat_block_count = int(rules["gate_repeat_block_count"])
    ux_psychology_hotspot_count = int(rules["ux_psychology_hotspot_count"])
    ux_psychology_hotspot_tasks = int(rules["ux_psychology_hotspot_tasks"])

    now_dt = now_utc()
    now_iso = iso_utc(now_dt)
    recency_cutoff = now_dt - timedelta(days=recency_days)

    task_files = sorted(states_dir.glob("TASK-*.yaml"))
    if archive_dir.exists():
        task_files += sorted(archive_dir.glob("*.yaml"))
    tasks = [parse_task(p) for p in task_files]

    warnings_by_code: dict[str, list[str]] = defaultdict(list)
    warnings_by_pair: dict[tuple[str, str], list[str]] = defaultdict(list)
    ping_pong_candidates: list[dict] = []
    blocked_stall_task_ids: list[str] = []
    gate_hits: dict[str, list[str]] = defaultdict(list)
    ux_psychology_hits: list[str] = []

    blocked_keywords = [k.lower() for k in rules.get("blocked_stall_keywords", [])]
    gate_keywords = list(rules.get("gate_keywords", []))
    ux_psychology_keywords = [k.lower() for k in rules.get("ux_psychology_keywords", [])]
    actions = rules.get("actions", {})

    for task in tasks:
        task_id = normalize(str(task.get("id", ""))) or "UNKNOWN"
        task_status = normalize(str(task.get("status", "")))
        task_notes = normalize(str(task.get("notes", "")))
        task_updated_dt = task.get("updated_dt")

        for w in task.get("warnings", []):
            code = normalize(str(w.get("code", "")))
            source = normalize(str(w.get("source_role", "")))
            target = normalize(str(w.get("target_role", "")))
            warning_dt = parse_dt(str(w.get("detected_at", ""))) or parse_dt(str(w.get("updated_at", ""))) or task_updated_dt
            if warning_dt is None or warning_dt < recency_cutoff:
                continue
            if code:
                warnings_by_code[code].append(task_id)
            if source and target:
                warnings_by_pair[(source, target)].append(task_id)

        if task_status == "blocked" and task_updated_dt is not None:
            age_hours = (now_dt - task_updated_dt).total_seconds() / 3600
            if age_hours >= blocked_stall_hours and any(k in task_notes.lower() for k in blocked_keywords):
                blocked_stall_task_ids.append(task_id)

        if task_updated_dt is not None and task_updated_dt >= recency_cutoff:
            for gate in gate_keywords:
                if gate.lower() in task_notes.lower():
                    gate_hits[gate].append(task_id)

            text_parts = [task_notes]
            for w in task.get("warnings", []):
                text_parts.append(normalize(str(w.get("summary", ""))))
                text_parts.append(normalize(str(w.get("code", ""))))
            for h in task.get("handoffs", []):
                text_parts.append(normalize(str(h.get("memo", ""))))
            searchable = " ".join(text_parts).lower()
            if any(k in searchable for k in ux_psychology_keywords):
                ux_psychology_hits.append(task_id)

        handoff_counts: dict[tuple[str, str], int] = defaultdict(int)
        for h in task.get("handoffs", []):
            src = normalize(str(h.get("from", "")))
            dst = normalize(str(h.get("to", "")))
            if not src or not dst:
                continue
            key = tuple(sorted((src, dst)))
            handoff_counts[key] += 1
        for pair, count in handoff_counts.items():
            if count >= handoff_ping_pong_count:
                ping_pong_candidates.append(
                    build_candidate(
                        "handoff_ping_pong",
                        f"task {task_id} has handoff ping-pong {pair[0]} <-> {pair[1]} ({count} times).",
                        [task_id],
                        actions.get("handoff_ping_pong", "role_split"),
                        now_iso,
                    )
                )

    generated: list[dict] = []

    for code, task_ids in warnings_by_code.items():
        if len(task_ids) >= warning_code_hotspot_count and len(set(task_ids)) >= warning_code_hotspot_tasks:
            generated.append(
                build_candidate(
                    "warning_code_hotspot",
                    f"warning code {code} occurred {len(task_ids)} times across {len(set(task_ids))} tasks in last {recency_days} days.",
                    task_ids,
                    actions.get("warning_code_hotspot", "skill_update"),
                    now_iso,
                )
            )

    for (src, dst), task_ids in warnings_by_pair.items():
        if len(task_ids) >= role_pair_hotspot_count:
            generated.append(
                build_candidate(
                    "role_pair_hotspot",
                    f"warning role pair {src} -> {dst} occurred {len(task_ids)} times in last {recency_days} days.",
                    task_ids,
                    actions.get("role_pair_hotspot", "role_split"),
                    now_iso,
                )
            )

    generated.extend(ping_pong_candidates)

    if blocked_stall_task_ids:
        generated.append(
            build_candidate(
                "blocked_stall",
                f"{len(set(blocked_stall_task_ids))} blocked tasks exceeded {blocked_stall_hours} hours with role-boundary keywords.",
                blocked_stall_task_ids,
                actions.get("blocked_stall", "new_role"),
                now_iso,
            )
        )

    for gate, task_ids in gate_hits.items():
        if len(task_ids) >= gate_repeat_block_count:
            generated.append(
                build_candidate(
                    "gate_repeat_block",
                    f"{gate} related remand appeared {len(task_ids)} times in last {recency_days} days.",
                    task_ids,
                    actions.get("gate_repeat_block", "skill_update"),
                    now_iso,
                )
            )

    if len(ux_psychology_hits) >= ux_psychology_hotspot_count and len(set(ux_psychology_hits)) >= ux_psychology_hotspot_tasks:
        generated.append(
            build_candidate(
                "ux_psychology_hotspot",
                f"UX psychology friction keywords appeared {len(ux_psychology_hits)} times across {len(set(ux_psychology_hits))} tasks in last {recency_days} days.",
                ux_psychology_hits,
                actions.get("ux_psychology_hotspot", "skill_update"),
                now_iso,
            )
        )

    index = parse_role_gap_index(index_path)
    existing = index.get("candidates", [])
    if not isinstance(existing, list):
        existing = []
    existing_keys = {candidate_key(c) for c in existing}
    existing_ids = [normalize(str(c.get("id", ""))) for c in existing]

    added = 0
    for candidate in generated:
        key = candidate_key(candidate)
        if key in existing_keys:
            continue
        cid = next_candidate_id(existing_ids, now_dt)
        candidate["id"] = cid
        existing_ids.append(cid)
        existing_keys.add(key)
        existing.append(candidate)
        added += 1

    index["version"] = normalize(str(index.get("version", rules.get("version", "v1")))) or "v1"
    index["updated_at"] = now_iso
    index["candidates"] = existing
    write_role_gap_index(index_path, index)

    open_count = sum(1 for c in existing if normalize(str(c.get("status", ""))) == "open")
    print(f"role gap detection completed: candidates_total={len(existing)}, candidates_open={open_count}, added={added}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

