#!/usr/bin/env python3
from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path
import sys

try:
    import yaml  # type: ignore
except Exception as exc:  # pragma: no cover
    print(f"ERROR [PYTHON_DEP_MISSING] PyYAML is required: {exc}")
    sys.exit(1)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Detect recurring incidents across projects")
    parser.add_argument("--signals", default=".takt/control-plane/signals/latest.yaml", help="signals file")
    parser.add_argument(
        "--min-projects",
        type=int,
        default=3,
        help="minimum distinct projects sharing a fingerprint",
    )
    parser.add_argument(
        "--output",
        default=".takt/control-plane/signals/incidents-detected.yaml",
        help="output path",
    )
    return parser.parse_args()


def load_yaml(path: Path) -> dict:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    return data if isinstance(data, dict) else {}


def now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def main() -> int:
    args = parse_args()
    signals_path = Path(args.signals).resolve()
    output_path = Path(args.output).resolve()

    if not signals_path.exists():
        print(f"ERROR [FLEET_INCIDENTS_SIGNALS_MISSING] {signals_path.as_posix()}")
        return 1

    if args.min_projects < 1:
        print("ERROR [FLEET_INCIDENTS_CONFIG_INVALID] --min-projects must be >= 1")
        return 1

    signals = load_yaml(signals_path)
    counts = signals.get("fingerprint_project_counts")
    if not isinstance(counts, dict):
        print(f"ERROR [FLEET_INCIDENTS_SIGNALS_INVALID] missing fingerprint_project_counts in {signals_path.as_posix()}")
        return 1

    recurring: list[dict] = []
    for fingerprint, project_count in sorted(counts.items(), key=lambda x: str(x[0])):
        if not isinstance(project_count, int):
            continue
        if project_count >= args.min_projects:
            recurring.append(
                {
                    "fingerprint": str(fingerprint),
                    "project_count": int(project_count),
                    "threshold": args.min_projects,
                    "status": "recurring",
                }
            )

    result = {
        "detected_at": now_iso(),
        "min_projects": args.min_projects,
        "recurring_incidents": recurring,
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(yaml.safe_dump(result, allow_unicode=True, sort_keys=False), encoding="utf-8")

    if recurring:
        print(f"OK [FLEET_INCIDENTS_DETECTED] recurring={len(recurring)} output={output_path.as_posix()}")
    else:
        print(f"OK [FLEET_INCIDENTS_NONE] output={output_path.as_posix()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
