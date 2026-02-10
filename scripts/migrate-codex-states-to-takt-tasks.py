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

STATUS_MAP = {
    "todo": "todo",
    "in_progress": "in_progress",
    "in_review": "in_review",
    "blocked": "blocked",
    "done": "done",
}

ID_RE = re.compile(r"T-(\d+)$")


def to_iso(value: str | None) -> str:
    raw = (value or "").strip()
    if not raw:
        return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    except ValueError:
        return raw


def normalize_id(old_id: str, file_stem: str) -> str:
    candidate = (old_id or "").strip()
    match = ID_RE.match(candidate)
    if match:
        return f"T-{int(match.group(1)):05d}"

    fallback = re.search(r"TASK-(\d{5})", file_stem)
    if fallback:
        return f"T-{int(fallback.group(1)):05d}"

    return "T-00000"


def build_task_prompt(title: str, notes: str, flags: dict[str, bool]) -> str:
    lines = [
        f"Title: {title.strip()}",
        "",
        "Execution instruction:",
        (notes or "Implement the requested work and produce review-ready evidence.").strip(),
        "",
        "Required review flags:",
        f"- qa_required: {str(flags.get('qa_required', True)).lower()}",
        f"- security_required: {str(flags.get('security_required', False)).lower()}",
        f"- ux_required: {str(flags.get('ux_required', False)).lower()}",
        f"- docs_required: {str(flags.get('docs_required', True)).lower()}",
        f"- research_required: {str(flags.get('research_required', False)).lower()}",
    ]
    return "\n".join(lines).strip()


def convert(src_file: Path) -> dict:
    raw = yaml.safe_load(src_file.read_text(encoding="utf-8")) or {}

    local_flags = raw.get("local_flags") or {}
    flags = {
        "qa_required": bool(local_flags.get("qa_review_required", True)),
        "security_required": bool(local_flags.get("backend_security_required", False)),
        "ux_required": bool(local_flags.get("ux_review_required", False)),
        "docs_required": bool(local_flags.get("documentation_sync_required", True)),
        "research_required": bool(local_flags.get("research_track_enabled", False)),
    }

    title = str(raw.get("title") or src_file.stem)
    notes = str(raw.get("notes") or "")
    status = str(raw.get("status") or "todo")

    return {
        "id": normalize_id(str(raw.get("id") or ""), src_file.stem),
        "title": title,
        "status": STATUS_MAP.get(status, "todo"),
        "task": build_task_prompt(title, notes, flags),
        "goal": str(raw.get("goal") or ""),
        "constraints": list(raw.get("constraints") or []),
        "acceptance": list(raw.get("acceptance") or []),
        "flags": flags,
        "warnings": list(raw.get("warnings") or []),
        "handoffs": list(raw.get("handoffs") or []),
        "notes": notes,
        "updated_at": to_iso(str(raw.get("updated_at") or "")),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Migrate legacy codex task states to .takt/tasks schema")
    parser.add_argument(
        "--source",
        default=str(Path(".") / (".cod" + "ex") / "states"),
        help="source directory containing TASK-*.yaml",
    )
    parser.add_argument(
        "--target",
        default=str(Path(".takt") / "tasks"),
        help="target directory for migrated TASK-*.yaml",
    )
    args = parser.parse_args()

    source = Path(args.source).resolve()
    target = Path(args.target).resolve()

    if not source.exists():
        print(f"ERROR [MIGRATE_SOURCE_MISSING] {source.as_posix()}")
        return 1

    target.mkdir(parents=True, exist_ok=True)

    files = sorted(source.glob("TASK-*.yaml"))
    if not files:
        print(f"ERROR [MIGRATE_SOURCE_EMPTY] no TASK-*.yaml under {source.as_posix()}")
        return 1

    migrated = 0
    for src_file in files:
        converted = convert(src_file)
        dest_file = target / src_file.name
        text = yaml.safe_dump(converted, allow_unicode=True, sort_keys=False)
        dest_file.write_text(text, encoding="utf-8")
        migrated += 1

    print(f"OK [MIGRATE_DONE] migrated={migrated} source={source.as_posix()} target={target.as_posix()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
