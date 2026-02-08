#!/usr/bin/env python3
from __future__ import annotations

from argparse import ArgumentParser, Namespace
from datetime import datetime, timedelta, timezone
from pathlib import Path
import os
import re
import sys


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


def parse_meta(path: Path) -> dict[str, str]:
    out = {"version": "", "source": "", "ref": "", "commit": "", "synced_at": ""}
    for line in read_text(path).splitlines():
        m = re.match(r"^([A-Za-z_][A-Za-z0-9_]*)\s*:\s*(.*)$", line)
        if not m:
            continue
        key = m.group(1)
        if key not in out:
            continue
        out[key] = normalize(m.group(2))
    return out


def parse_args(argv: list[str]) -> Namespace:
    parser = ArgumentParser(description="Validate incident registry cache freshness.")
    parser.add_argument(
        "--meta",
        default=".codex/cache/incident-registry.meta.yaml",
        help="meta file path (default: .codex/cache/incident-registry.meta.yaml)",
    )
    parser.add_argument(
        "--registry",
        default=".codex/cache/incident-registry.yaml",
        help="registry cache file path (default: .codex/cache/incident-registry.yaml)",
    )
    parser.add_argument(
        "--max-age-hours",
        type=int,
        default=24,
        help="max allowed sync age in hours before stale (default: 24)",
    )
    parser.add_argument(
        "--ci",
        action="store_true",
        help="force CI mode (stale/missing becomes hard failure)",
    )
    return parser.parse_args(argv)


def is_ci_mode(args: Namespace) -> bool:
    if args.ci:
        return True
    return os.environ.get("CI", "").lower() in {"1", "true", "yes"} or os.environ.get(
        "GITHUB_ACTIONS", ""
    ).lower() in {"1", "true", "yes"}


def report(code: str, message: str, is_error: bool) -> int:
    level = "ERROR" if is_error else "WARN"
    stream = sys.stderr if is_error else sys.stdout
    print(f"{level} [{code}] {message}", file=stream)
    return 1 if is_error else 0


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    ci_mode = is_ci_mode(args)
    meta_path = Path(args.meta)
    registry_path = Path(args.registry)

    if not registry_path.exists():
        return report(
            "INCIDENT_REGISTRY_MISSING",
            f"missing incident registry cache: {registry_path.as_posix()}",
            ci_mode,
        )

    if not meta_path.exists():
        return report(
            "INCIDENT_REGISTRY_META_MISSING",
            f"missing incident registry meta: {meta_path.as_posix()}",
            ci_mode,
        )

    meta = parse_meta(meta_path)
    missing = [key for key in ("source", "ref", "commit", "synced_at") if not meta.get(key)]
    if missing:
        return report(
            "INCIDENT_REGISTRY_META_INVALID",
            f"meta file missing keys: {', '.join(missing)}",
            ci_mode,
        )

    synced_at = parse_dt(meta["synced_at"])
    if synced_at is None:
        return report(
            "INCIDENT_REGISTRY_META_INVALID",
            f"meta synced_at is invalid ISO-8601: {meta['synced_at']}",
            ci_mode,
        )

    now = datetime.now(timezone.utc)
    max_age = timedelta(hours=max(1, args.max_age_hours))
    age = now - synced_at
    if age > max_age:
        return report(
            "INCIDENT_REGISTRY_STALE",
            f"incident registry cache is stale: age_hours={age.total_seconds()/3600:.1f}, max={max_age.total_seconds()/3600:.1f}",
            ci_mode,
        )

    print(
        f"incident sync freshness is valid: meta={meta_path.as_posix()}, age_hours={age.total_seconds()/3600:.1f}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
