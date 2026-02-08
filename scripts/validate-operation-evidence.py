#!/usr/bin/env python3
from __future__ import annotations

from argparse import ArgumentParser, Namespace
from pathlib import Path
import re
import sys


TASK_FILE_NAME_PATTERN = re.compile(r"^TASK-\d{5}-[a-z0-9]+(?:-[a-z0-9]+)*\.yaml$")
DECLARATION_PATTERN = re.compile(
    r"^DECLARATION\s+team=\S+\s+role=\S+\s+task=(?:T-\d+|N/A)\s+action=\S+(?:\s+\|\s+.*)?$"
)
TIMESTAMP_PREFIX_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z\s+")
DECLARATION_WINDOW = 6
DEFAULT_REQUIRE_READ = [".codex/AGENTS.md", "docs/adr/"]


def fail(code: str, message: str) -> int:
    print(f"ERROR [{code}] {message}", file=sys.stderr)
    return 1


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8").lstrip("\ufeff")


def normalize_scalar(value: str) -> str:
    v = (value or "").strip()
    if (v.startswith('"') and v.endswith('"')) or (v.startswith("'") and v.endswith("'")):
        v = v[1:-1]
    return v.strip()


def entry_payload(line: str) -> str:
    trimmed = line.strip()
    if trimmed.startswith("- "):
        return trimmed[2:].strip()
    return trimmed


def strip_timestamp_prefix(payload: str) -> str:
    return TIMESTAMP_PREFIX_PATTERN.sub("", payload, count=1).strip()


def extract_declaration(payload: str) -> str | None:
    idx = payload.find("DECLARATION ")
    if idx < 0:
        return None
    return payload[idx:].strip()


def declaration_at_start(payload: str) -> str | None:
    stripped = payload.strip()
    if not stripped.startswith("DECLARATION "):
        return None
    return stripped


def is_valid_declaration(payload: str) -> bool:
    declaration = extract_declaration(payload)
    if declaration is None:
        return False
    return bool(DECLARATION_PATTERN.fullmatch(declaration))


def parse_args(argv: list[str]) -> Namespace:
    parser = ArgumentParser(description="Validate AgentTeams operation evidence.")
    parser.add_argument("--task-file", required=True, help="TASK-*.yaml path")
    parser.add_argument("--log", default="logs/e2e-ai-log.md", help="chat log path")
    parser.add_argument("--min-teams", type=int, default=3, help="minimum unique team count")
    parser.add_argument("--min-roles", type=int, default=5, help="minimum unique role count")
    parser.add_argument(
        "--require-read",
        action="append",
        default=[],
        help="required read evidence pattern (repeatable)",
    )
    return parser.parse_args(argv)


def parse_entries(log_path: Path) -> tuple[list[str], str | None]:
    if not log_path.exists():
        return [], f"missing log file: {log_path.as_posix()}"

    lines = read_text(log_path).splitlines()
    entries_index = -1
    for idx, line in enumerate(lines):
        if line.strip() == "## Entries":
            entries_index = idx
            break
    if entries_index < 0:
        return [], f"missing required section in chat log: {log_path.as_posix()}#Entries"

    entries: list[str] = []
    for line in lines[entries_index + 1 :]:
        if line.strip().startswith("- "):
            entries.append(entry_payload(line))
    if not entries:
        return [], "chat log has no entry lines after ## Entries"

    return entries, None


def has_preceding_declaration(entries: list[str], idx: int) -> bool:
    start = max(0, idx - DECLARATION_WINDOW)
    window = entries[start : idx + 1]
    return any(is_valid_declaration(candidate) for candidate in window)


def parse_handoffs(task_path: Path) -> list[dict[str, str]]:
    lines = read_text(task_path).splitlines()
    section = ""
    in_handoff = False
    handoff: dict[str, str] = {}
    handoffs: list[dict[str, str]] = []

    def flush_handoff() -> None:
        nonlocal in_handoff, handoff
        if in_handoff and handoff:
            handoffs.append(handoff.copy())
        in_handoff = False
        handoff = {}

    for line in lines:
        m_top = re.match(r"^([A-Za-z_][A-Za-z0-9_]*)\s*:", line)
        if m_top:
            if section == "handoffs":
                flush_handoff()
            section = m_top.group(1)
            continue

        if section != "handoffs":
            continue

        m_item = re.match(r"^\s{2}-\s*(.*)$", line)
        if m_item:
            flush_handoff()
            in_handoff = True
            inline = m_item.group(1).strip()
            if inline:
                m_inline = re.match(r"^([A-Za-z_][A-Za-z0-9_]*)\s*:\s*(.*)$", inline)
                if m_inline:
                    handoff[m_inline.group(1)] = normalize_scalar(m_inline.group(2))
            continue

        if in_handoff:
            m_key = re.match(r"^\s{4}([A-Za-z_][A-Za-z0-9_]*)\s*:\s*(.*)$", line)
            if m_key:
                handoff[m_key.group(1)] = normalize_scalar(m_key.group(2))

    if section == "handoffs":
        flush_handoff()

    return handoffs


def team_name(role_path: str) -> str:
    cleaned = normalize_scalar(role_path)
    if not cleaned:
        return ""
    if "/" in cleaned:
        return cleaned.split("/", 1)[0]
    return cleaned


def main(argv: list[str]) -> int:
    args = parse_args(argv)

    if args.min_teams < 1:
        return fail("INVALID_THRESHOLD", "--min-teams must be >= 1")
    if args.min_roles < 1:
        return fail("INVALID_THRESHOLD", "--min-roles must be >= 1")

    task_path = Path(args.task_file)
    if not task_path.exists():
        return fail("TASK_FILE_MISSING", f"missing task file: {task_path.as_posix()}")
    if not TASK_FILE_NAME_PATTERN.fullmatch(task_path.name):
        return fail("TASK_FILENAME_INVALID", f"invalid task filename: {task_path.name}")

    log_path = Path(args.log)
    entries, entries_error = parse_entries(log_path)
    if entries_error:
        return fail("CHAT_LOG_INVALID", entries_error)

    require_reads = [p for p in args.require_read if p.strip()]
    if not require_reads:
        require_reads = DEFAULT_REQUIRE_READ.copy()

    for pattern in require_reads:
        has_match = False
        has_match_with_declaration = False
        for idx, payload in enumerate(entries):
            body = strip_timestamp_prefix(payload)
            if pattern not in body:
                continue
            has_match = True
            if has_preceding_declaration(entries, idx):
                has_match_with_declaration = True
                break

        if not has_match:
            return fail("READ_EVIDENCE_MISSING", f"missing read evidence for pattern: {pattern}")
        if not has_match_with_declaration:
            return fail(
                "READ_EVIDENCE_DECLARATION_MISSING",
                f"read evidence for pattern '{pattern}' must have preceding DECLARATION within last {DECLARATION_WINDOW} entries",
            )

    handoffs = parse_handoffs(task_path)
    if not handoffs:
        return fail("HANDOFFS_MISSING", f"task has no handoffs: {task_path.as_posix()}")

    unique_teams: set[str] = set()
    unique_roles: set[str] = set()
    has_cross_team_handoff = False

    for idx, handoff in enumerate(handoffs):
        missing = [k for k in ("from", "to", "memo") if not normalize_scalar(handoff.get(k, ""))]
        if missing:
            return fail(
                "HANDOFF_REQUIRED_FIELD_MISSING",
                f"handoffs[{idx}] missing required fields: {', '.join(missing)}",
            )

        from_role = normalize_scalar(handoff["from"])
        to_role = normalize_scalar(handoff["to"])
        memo = normalize_scalar(handoff["memo"])
        declaration = declaration_at_start(memo)
        if declaration is None or not DECLARATION_PATTERN.fullmatch(declaration):
            return fail(
                "HANDOFF_DECLARATION_FORMAT_INVALID",
                f"handoffs[{idx}].memo must start with valid DECLARATION",
            )

        unique_roles.add(from_role)
        unique_roles.add(to_role)
        from_team = team_name(from_role)
        to_team = team_name(to_role)
        if from_team:
            unique_teams.add(from_team)
        if to_team:
            unique_teams.add(to_team)
        if from_team and to_team and from_team != to_team:
            has_cross_team_handoff = True

    if len(unique_teams) < args.min_teams:
        return fail(
            "TEAM_DISTRIBUTION_INSUFFICIENT",
            f"unique teams={len(unique_teams)} is below --min-teams={args.min_teams}",
        )
    if len(unique_roles) < args.min_roles:
        return fail(
            "ROLE_DISTRIBUTION_INSUFFICIENT",
            f"unique roles={len(unique_roles)} is below --min-roles={args.min_roles}",
        )
    if not has_cross_team_handoff:
        return fail("HANDOFF_CROSS_TEAM_MISSING", "at least one cross-team handoff is required")

    print(
        "operation evidence validation passed: "
        f"task={task_path.as_posix()} log={log_path.as_posix()} "
        f"teams={len(unique_teams)} roles={len(unique_roles)} cross_team=yes"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
