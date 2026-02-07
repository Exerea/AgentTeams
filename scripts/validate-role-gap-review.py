#!/usr/bin/env python3
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
import re
import sys


SIGNAL_TYPES = {
    "warning_code_hotspot",
    "role_pair_hotspot",
    "handoff_ping_pong",
    "blocked_stall",
    "gate_repeat_block",
    "ux_psychology_hotspot",
}
SUGGESTED_ACTIONS = {"no_change", "skill_update", "role_split", "new_role"}
CANDIDATE_STATUSES = {"open", "triaged", "accepted", "rejected", "implemented"}
REQUIRED_KEYS = {
    "id",
    "signal_type",
    "summary",
    "evidence_task_ids",
    "suggested_actions",
    "owner",
    "status",
    "decision_note",
    "adr_ref",
    "updated_at",
}


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


def parse_rules(path: Path) -> dict:
    out = {"open_review_max_days": 7}
    if not path.exists():
        return out

    for ln in read_text(path).splitlines():
        s = ln.strip()
        if not s or s.startswith("#"):
            continue
        m = re.match(r"^open_review_max_days\s*:\s*(\d+)\s*$", s)
        if m:
            out["open_review_max_days"] = int(m.group(1))
    return out


def parse_role_gap_index(path: Path) -> dict:
    out = {"version": "", "updated_at": "", "candidates": []}
    if not path.exists():
        return out

    lines = read_text(path).splitlines()
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

    for ln in lines:
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


def main() -> int:
    repo_root = Path(__file__).resolve().parent.parent
    rules_path = repo_root / ".codex" / "role-gap-rules.yaml"
    index_path = repo_root / ".codex" / "states" / "_role-gap-index.yaml"

    if not index_path.exists():
        print(f"ERROR: missing file: {index_path.as_posix()}", file=sys.stderr)
        return 1

    rules = parse_rules(rules_path)
    open_review_max_days = int(rules.get("open_review_max_days", 7))
    index = parse_role_gap_index(index_path)

    errors: list[str] = []
    if not normalize(index.get("version", "")):
        errors.append("missing top-level key: version")
    if not normalize(index.get("updated_at", "")):
        errors.append("missing top-level key: updated_at")
    candidates = index.get("candidates", [])
    if not isinstance(candidates, list):
        errors.append("top-level key 'candidates' must be a list")
        candidates = []

    now_dt = datetime.now(timezone.utc)
    open_cutoff = now_dt - timedelta(days=open_review_max_days)

    for i, c in enumerate(candidates):
        if not isinstance(c, dict):
            errors.append(f"candidates[{i}] must be an object")
            continue
        missing = sorted(REQUIRED_KEYS - set(c.keys()))
        if missing:
            errors.append(f"candidates[{i}] missing keys: {', '.join(missing)}")

        signal_type = normalize(str(c.get("signal_type", "")))
        suggested = normalize(str(c.get("suggested_actions", "")))
        status = normalize(str(c.get("status", "")))
        owner = normalize(str(c.get("owner", "")))
        decision_note = normalize(str(c.get("decision_note", "")))
        adr_ref = normalize(str(c.get("adr_ref", "")))
        updated_dt = parse_dt(str(c.get("updated_at", "")))

        if signal_type and signal_type not in SIGNAL_TYPES:
            errors.append(f"candidates[{i}].signal_type invalid: '{signal_type}'")
        if suggested and suggested not in SUGGESTED_ACTIONS:
            errors.append(f"candidates[{i}].suggested_actions invalid: '{suggested}'")
        if status and status not in CANDIDATE_STATUSES:
            errors.append(f"candidates[{i}].status invalid: '{status}'")
        if owner and owner != "coordinator":
            errors.append(f"candidates[{i}].owner must be 'coordinator'")

        evidence = c.get("evidence_task_ids", [])
        if not isinstance(evidence, list):
            errors.append(f"candidates[{i}].evidence_task_ids must be a list")

        if status == "open":
            if updated_dt is None:
                errors.append(f"candidates[{i}] open status requires valid updated_at")
            elif updated_dt < open_cutoff:
                errors.append(
                    f"candidates[{i}] open for more than {open_review_max_days} days"
                )

        if status == "accepted" and not adr_ref:
            errors.append(f"candidates[{i}] accepted requires adr_ref")

        if status == "rejected" and not decision_note:
            errors.append(f"candidates[{i}] rejected requires decision_note")

        if status == "implemented" and suggested in {"role_split", "new_role"}:
            required_traces = [
                ".codex/roles/",
                ".codex/coordinator.md",
                ".codex/AGENTS.md",
                "docs/specs/0001-agentteams-as-is-operations.md",
                "docs/guides/request-routing-scenarios.md",
            ]
            for trace in required_traces:
                if trace not in decision_note:
                    errors.append(
                        f"candidates[{i}] implemented requires change trace in decision_note: {trace}"
                    )

    if errors:
        for err in errors:
            print(f"ERROR: {err}", file=sys.stderr)
        return 1

    print("role gap review is valid")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
