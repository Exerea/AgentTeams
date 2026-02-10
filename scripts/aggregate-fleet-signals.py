#!/usr/bin/env python3
from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
from pathlib import Path
import sys

try:
    import yaml  # type: ignore
except Exception as exc:  # pragma: no cover
    print(f"ERROR [PYTHON_DEP_MISSING] PyYAML is required: {exc}")
    sys.exit(1)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Aggregate fleet intake metadata into control-plane signals")
    parser.add_argument("--control-plane", default=".takt/control-plane", help="control-plane root path")
    parser.add_argument("--window-days", type=int, default=14, help="window days for overload aggregation")
    parser.add_argument("--incident-window-days", type=int, default=7, help="window days for incident aggregation")
    parser.add_argument("--write-history", action="store_true", help="write signals history snapshot")
    return parser.parse_args()


def load_yaml(path: Path) -> dict:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    return data if isinstance(data, dict) else {}


def parse_utc(value: object) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
    except ValueError:
        return None


def iso_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def overlap_ratio(entry: object) -> float:
    if not isinstance(entry, dict):
        return 0.0
    value = entry.get("responsibility_overlap_ratio")
    if isinstance(value, (int, float)):
        return float(value)
    return 0.0


def threshold_hits(item: dict) -> list[str]:
    hits: list[str] = []
    queue_p95 = item.get("queue_p95_hours")
    lead_p50 = item.get("lead_time_p50_hours")
    rework = item.get("rework_rate")
    blocked = item.get("blocked_ratio")

    if isinstance(queue_p95, (int, float)) and float(queue_p95) > 24:
        hits.append("queue_p95_hours>24")
    if isinstance(lead_p50, (int, float)) and float(lead_p50) > 48:
        hits.append("lead_time_p50_hours>48")
    if isinstance(rework, (int, float)) and float(rework) > 0.25:
        hits.append("rework_rate>0.25")
    if isinstance(blocked, (int, float)) and float(blocked) > 0.20:
        hits.append("blocked_ratio>0.20")
    return hits


def main() -> int:
    args = parse_args()
    cp_root = Path(args.control_plane).resolve()
    intake_root = cp_root / "intake"
    signals_root = cp_root / "signals"
    latest_file = signals_root / "latest.yaml"
    history_root = signals_root / "history"

    if not intake_root.exists():
        print(f"ERROR [FLEET_AGGREGATE_INTAKE_MISSING] {intake_root.as_posix()}")
        return 1

    now = datetime.now(timezone.utc)
    overload_cutoff = now - timedelta(days=max(args.window_days, 1))
    incident_cutoff = now - timedelta(days=max(args.incident_window_days, 1))

    latest_by_project: dict[str, dict] = {}
    fingerprint_projects: dict[str, set[str]] = {}
    intake_files = sorted(intake_root.glob("*/*.yaml"))

    for intake_file in intake_files:
        data = load_yaml(intake_file)
        project_id = str(data.get("project_id") or "").strip()
        captured_at = parse_utc(data.get("captured_at"))
        if not project_id or captured_at is None:
            continue

        record = {
            "project_id": project_id,
            "repo": str(data.get("repo") or "").strip(),
            "captured_at": captured_at.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "window_days": int(data.get("window_days") or 0),
            "task_counts": data.get("task_counts") if isinstance(data.get("task_counts"), dict) else {},
            "lead_time_p50_hours": float(data.get("lead_time_p50_hours") or 0),
            "queue_p95_hours": float(data.get("queue_p95_hours") or 0),
            "rework_rate": float(data.get("rework_rate") or 0),
            "blocked_ratio": float(data.get("blocked_ratio") or 0),
            "incident_fingerprints": data.get("incident_fingerprints")
            if isinstance(data.get("incident_fingerprints"), list)
            else [],
            "policy_failures": data.get("policy_failures") if isinstance(data.get("policy_failures"), list) else [],
            "top_overlaps": data.get("top_overlaps") if isinstance(data.get("top_overlaps"), list) else [],
        }

        existing = latest_by_project.get(project_id)
        if existing is None or parse_utc(existing.get("captured_at")) < captured_at:
            latest_by_project[project_id] = record

        if captured_at >= incident_cutoff:
            for incident in record["incident_fingerprints"]:
                if not isinstance(incident, dict):
                    continue
                fp_hash = str(incident.get("hash") or "").strip()
                if not fp_hash:
                    continue
                fingerprint_projects.setdefault(fp_hash, set()).add(project_id)

    projects: list[dict] = []
    overload_candidates: list[dict] = []
    for record in sorted(latest_by_project.values(), key=lambda x: x["project_id"]):
        captured_at = parse_utc(record.get("captured_at"))
        if captured_at is None or captured_at < overload_cutoff:
            continue

        hits = threshold_hits(record)
        overlaps = record["top_overlaps"] if isinstance(record["top_overlaps"], list) else []
        max_overlap = max((overlap_ratio(item) for item in overlaps), default=0.0)

        enriched = dict(record)
        enriched["threshold_hits"] = hits
        enriched["max_responsibility_overlap_ratio"] = round(max_overlap, 4)
        projects.append(enriched)

        if len(hits) >= 2:
            overload_candidates.append(
                {
                    "project_id": record["project_id"],
                    "repo": record["repo"],
                    "threshold_hits": hits,
                    "max_responsibility_overlap_ratio": round(max_overlap, 4),
                    "top_overlaps": overlaps,
                }
            )

    fingerprint_project_counts = {
        key: len(value) for key, value in sorted(fingerprint_projects.items(), key=lambda x: x[0])
    }

    signals = {
        "generated_at": iso_now(),
        "window_days": args.window_days,
        "incident_window_days": args.incident_window_days,
        "projects": projects,
        "fingerprint_project_counts": fingerprint_project_counts,
        "overload_candidates": overload_candidates,
        "notes": ["event-driven refresh: no periodic schedule required"],
    }

    signals_root.mkdir(parents=True, exist_ok=True)
    latest_file.write_text(yaml.safe_dump(signals, allow_unicode=True, sort_keys=False), encoding="utf-8")

    if args.write_history:
        history_root.mkdir(parents=True, exist_ok=True)
        stamp = now.strftime("%Y%m%dT%H%M%SZ")
        history_file = history_root / f"{stamp}.yaml"
        history_file.write_text(yaml.safe_dump(signals, allow_unicode=True, sort_keys=False), encoding="utf-8")

    print(
        "OK [FLEET_SIGNALS_AGGREGATED] "
        f"projects={len(projects)} fingerprints={len(fingerprint_project_counts)} overload_candidates={len(overload_candidates)}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
