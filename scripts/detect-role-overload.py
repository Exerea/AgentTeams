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
    parser = argparse.ArgumentParser(description="Detect role overload candidates from intake metadata")
    parser.add_argument("--intake", default=".takt/control-plane/intake", help="intake root")
    parser.add_argument("--window-days", type=int, default=14, help="analysis window days")
    parser.add_argument("--output", default=".takt/control-plane/signals/overload-detected.yaml", help="output path")
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


def threshold_hits(entry: dict) -> list[str]:
    hits: list[str] = []
    queue = entry.get("queue_p95_hours")
    lead = entry.get("lead_time_p50_hours")
    rework = entry.get("rework_rate")
    blocked = entry.get("blocked_ratio")

    if isinstance(queue, (int, float)) and float(queue) > 24:
        hits.append("queue_p95_hours>24")
    if isinstance(lead, (int, float)) and float(lead) > 48:
        hits.append("lead_time_p50_hours>48")
    if isinstance(rework, (int, float)) and float(rework) > 0.25:
        hits.append("rework_rate>0.25")
    if isinstance(blocked, (int, float)) and float(blocked) > 0.20:
        hits.append("blocked_ratio>0.20")
    return hits


def overlap_ratio(item: object) -> float:
    if not isinstance(item, dict):
        return 0.0
    ratio = item.get("responsibility_overlap_ratio")
    if isinstance(ratio, (int, float)):
        return float(ratio)
    return 0.0


def top_two_capabilities(items: list[dict]) -> list[str]:
    sorted_items = sorted(items, key=lambda x: overlap_ratio(x), reverse=True)
    capabilities: list[str] = []
    for item in sorted_items[:2]:
        capability = str(item.get("capability") or "").strip()
        if capability:
            capabilities.append(capability)
    return capabilities


def now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def main() -> int:
    args = parse_args()
    intake_root = Path(args.intake).resolve()
    output_path = Path(args.output).resolve()

    if not intake_root.exists():
        print(f"ERROR [ROLE_OVERLOAD_INTAKE_MISSING] {intake_root.as_posix()}")
        return 1
    if args.window_days < 1:
        print("ERROR [ROLE_OVERLOAD_CONFIG_INVALID] --window-days must be >= 1")
        return 1

    cutoff = datetime.now(timezone.utc) - timedelta(days=args.window_days)
    latest_by_project: dict[str, dict] = {}

    for intake_file in sorted(intake_root.glob("*/*.yaml")):
        data = load_yaml(intake_file)
        project_id = str(data.get("project_id") or "").strip()
        captured_at = parse_utc(data.get("captured_at"))
        if not project_id or captured_at is None or captured_at < cutoff:
            continue
        prev = latest_by_project.get(project_id)
        prev_time = parse_utc(prev.get("captured_at")) if isinstance(prev, dict) else None
        if prev is None or prev_time is None or captured_at > prev_time:
            latest_by_project[project_id] = data

    overload_candidates: list[dict] = []
    split_candidates: list[dict] = []

    for project_id, data in sorted(latest_by_project.items(), key=lambda x: x[0]):
        hits = threshold_hits(data)
        overlaps = data.get("top_overlaps") if isinstance(data.get("top_overlaps"), list) else []
        max_ratio = max((overlap_ratio(item) for item in overlaps), default=0.0)
        candidate = {
            "project_id": project_id,
            "repo": str(data.get("repo") or ""),
            "captured_at": str(data.get("captured_at") or ""),
            "threshold_hits": hits,
            "hit_count": len(hits),
            "max_responsibility_overlap_ratio": round(max_ratio, 4),
            "top_overlaps": overlaps,
            "is_overload_candidate": len(hits) >= 2,
            "is_split_triggered": len(hits) >= 2 and max_ratio >= 0.35,
        }
        if candidate["is_overload_candidate"]:
            overload_candidates.append(candidate)
        if candidate["is_split_triggered"]:
            capabilities = top_two_capabilities(overlaps)
            split_candidates.append(
                {
                    "project_id": project_id,
                    "repo": str(data.get("repo") or ""),
                    "max_responsibility_overlap_ratio": round(max_ratio, 4),
                    "capabilities_for_new_team": capabilities,
                    "proposed_transfer_from_existing": capabilities,
                }
            )

    result = {
        "detected_at": now_iso(),
        "window_days": args.window_days,
        "overload_candidates": overload_candidates,
        "split_candidates": split_candidates,
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(yaml.safe_dump(result, allow_unicode=True, sort_keys=False), encoding="utf-8")

    print(
        "OK [ROLE_OVERLOAD_ANALYZED] "
        f"overload_candidates={len(overload_candidates)} split_candidates={len(split_candidates)} "
        f"output={output_path.as_posix()}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
