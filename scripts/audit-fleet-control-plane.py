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
    parser = argparse.ArgumentParser(description="Audit fleet-level control-plane health")
    parser.add_argument("--control-plane", default=".takt/control-plane", help="control-plane root")
    parser.add_argument("--strict", action="store_true", help="fail when warnings exist")
    parser.add_argument("--verbose", action="store_true", help="verbose output")
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


def main() -> int:
    args = parse_args()
    cp_root = Path(args.control_plane).resolve()
    warnings: list[str] = []

    registry_path = cp_root / "registry" / "projects.yaml"
    signals_path = cp_root / "signals" / "latest.yaml"

    if not cp_root.exists():
        print(f"ERROR [FLEET_AUDIT_MISSING] {cp_root.as_posix()}")
        return 1
    if not registry_path.exists():
        print(f"ERROR [FLEET_AUDIT_MISSING] {registry_path.as_posix()}")
        return 1
    if not signals_path.exists():
        print(f"ERROR [FLEET_AUDIT_MISSING] {signals_path.as_posix()}")
        return 1

    registry = load_yaml(registry_path)
    signals = load_yaml(signals_path)
    projects = registry.get("projects") if isinstance(registry.get("projects"), list) else []
    signal_projects = signals.get("projects") if isinstance(signals.get("projects"), list) else []
    fp_counts = (
        signals.get("fingerprint_project_counts")
        if isinstance(signals.get("fingerprint_project_counts"), dict)
        else {}
    )
    overload_candidates = (
        signals.get("overload_candidates") if isinstance(signals.get("overload_candidates"), list) else []
    )

    if not projects:
        warnings.append("WARN [FLEET_AUDIT_PROJECTS_EMPTY] no registered projects")
    if not signal_projects:
        warnings.append("WARN [FLEET_AUDIT_SIGNALS_EMPTY] no aggregated project signals")

    now = datetime.now(timezone.utc)
    stale_cutoff = now - timedelta(days=14)
    for item in signal_projects:
        if not isinstance(item, dict):
            continue
        project_id = str(item.get("project_id") or "").strip()
        captured_at = parse_utc(item.get("captured_at"))
        if captured_at is None:
            warnings.append(
                f"WARN [FLEET_AUDIT_CAPTURE_INVALID] project={project_id} captured_at is invalid"
            )
            continue
        if captured_at < stale_cutoff:
            warnings.append(
                f"WARN [FLEET_AUDIT_STALE_INTAKE] project={project_id} captured_at={captured_at.strftime('%Y-%m-%dT%H:%M:%SZ')}"
            )

    recurring = [k for k, v in fp_counts.items() if isinstance(v, int) and v >= 3]
    if recurring:
        warnings.append(
            f"WARN [FLEET_AUDIT_RECURRING_INCIDENTS] recurring_fingerprints={','.join(sorted(recurring))}"
        )

    if args.verbose:
        print(
            "INFO [FLEET_AUDIT_SUMMARY] "
            f"registered_projects={len(projects)} signal_projects={len(signal_projects)} "
            f"fingerprints={len(fp_counts)} overload_candidates={len(overload_candidates)}"
        )
        for item in signal_projects:
            if not isinstance(item, dict):
                continue
            print(
                "INFO [FLEET_AUDIT_PROJECT] "
                f"project={item.get('project_id')} queue_p95={item.get('queue_p95_hours')} "
                f"lead_p50={item.get('lead_time_p50_hours')} rework_rate={item.get('rework_rate')} "
                f"blocked_ratio={item.get('blocked_ratio')}"
            )

    if warnings:
        for warning in warnings:
            print(warning)
        if args.strict:
            print("ERROR [FLEET_AUDIT_FAILED] strict mode enabled and warnings detected")
            return 1
        print(f"OK [FLEET_AUDIT_DONE_WITH_WARNINGS] warnings={len(warnings)}")
        return 0

    print(
        "OK [FLEET_AUDIT_DONE] "
        f"registered_projects={len(projects)} signal_projects={len(signal_projects)} overload_candidates={len(overload_candidates)}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
