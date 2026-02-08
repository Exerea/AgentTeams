#!/usr/bin/env python3
from __future__ import annotations

from argparse import ArgumentParser, Namespace
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
import re
import sys


GLOBAL_KICKOFF = "殿のご命令と各AGENTS.mdに忠実に従う家臣たちが集まりました。──家臣たちが動きます！"
KOUJO_TOKEN = "【稼働口上】"
TIMESTAMP_PREFIX_PATTERN = re.compile(r"^(?P<ts>\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z)\s+(?P<body>.+)$")
GUARD_ENTRY_PATTERN = re.compile(
    r"^GUARD_SEND_OK\s+event=(?:task_start|role_switch|gate)\s+team=\S+\s+role=\S+\s+task=(?:T-\d+|N/A)$"
)


@dataclass
class Policy:
    enabled: bool
    enabled_at: datetime
    transport: str
    strict_mode: bool


@dataclass
class Entry:
    line_no: int
    timestamp: datetime | None
    body: str


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


def parse_bool(value: str, default: bool) -> bool:
    normalized = normalize_scalar(value).lower()
    if normalized in {"true", "yes", "1"}:
        return True
    if normalized in {"false", "no", "0"}:
        return False
    return default


def parse_utc_timestamp(value: str) -> datetime:
    normalized = normalize_scalar(value)
    try:
        return datetime.strptime(normalized, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    except ValueError as exc:
        raise ValueError(f"invalid UTC timestamp '{normalized}' (expected YYYY-MM-DDTHH:MM:SSZ)") from exc


def parse_args(argv: list[str]) -> Namespace:
    parser = ArgumentParser(description="Validate chat guard usage evidence.")
    parser.add_argument("--log", default="logs/e2e-ai-log.md", help="chat log path")
    parser.add_argument(
        "--policy",
        default=".codex/runtime-policy.yaml",
        help="runtime policy path (default: .codex/runtime-policy.yaml)",
    )
    return parser.parse_args(argv)


def parse_policy(policy_path: Path) -> Policy:
    if not policy_path.exists():
        raise ValueError(f"missing runtime policy file: {policy_path.as_posix()}")

    lines = read_text(policy_path).splitlines()
    section = ""
    values: dict[str, str] = {}

    for line in lines:
        top = re.match(r"^([A-Za-z_][A-Za-z0-9_-]*)\s*:\s*(.*)$", line)
        if top and not line.startswith("  "):
            section = top.group(1)
            continue

        if section != "chat_guard":
            continue

        child = re.match(r"^\s{2}([A-Za-z_][A-Za-z0-9_-]*)\s*:\s*(.*)$", line)
        if child:
            values[child.group(1)] = normalize_scalar(child.group(2))

    if not values:
        raise ValueError("runtime policy is missing 'chat_guard' section")

    enabled = parse_bool(values.get("enabled", "false"), default=False)
    enabled_at_raw = values.get("enabled_at", "")
    transport = normalize_scalar(values.get("transport", ""))
    strict_mode = parse_bool(values.get("strict_mode", "true"), default=True)

    if enabled and not enabled_at_raw:
        raise ValueError("chat_guard.enabled=true requires chat_guard.enabled_at")
    if enabled and not transport:
        raise ValueError("chat_guard.enabled=true requires chat_guard.transport")

    enabled_at = (
        parse_utc_timestamp(enabled_at_raw)
        if enabled
        else datetime.fromtimestamp(0, tz=timezone.utc)
    )
    return Policy(
        enabled=enabled,
        enabled_at=enabled_at,
        transport=transport,
        strict_mode=strict_mode,
    )


def entry_payload(line: str) -> str:
    trimmed = line.strip()
    if trimmed.startswith("- "):
        return trimmed[2:].strip()
    return trimmed


def parse_entries(log_path: Path) -> tuple[list[Entry], str | None]:
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

    entries: list[Entry] = []
    for idx, line in enumerate(lines[entries_index + 1 :], start=entries_index + 2):
        if not line.strip().startswith("- "):
            continue
        payload = entry_payload(line)
        m_ts = TIMESTAMP_PREFIX_PATTERN.match(payload)
        if m_ts:
            ts = datetime.strptime(m_ts.group("ts"), "%Y-%m-%dT%H:%M:%SZ").replace(
                tzinfo=timezone.utc
            )
            body = m_ts.group("body").strip()
            entries.append(Entry(line_no=idx, timestamp=ts, body=body))
            continue
        entries.append(Entry(line_no=idx, timestamp=None, body=payload.strip()))
    return entries, None


def is_declaration_target(body: str) -> bool:
    stripped = body.strip()
    return (
        stripped == GLOBAL_KICKOFF
        or stripped.startswith(KOUJO_TOKEN)
        or stripped.startswith("DECLARATION ")
    )


def is_guard_entry(body: str) -> bool:
    return bool(GUARD_ENTRY_PATTERN.fullmatch(body.strip()))


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    policy_path = Path(args.policy)
    log_path = Path(args.log)

    try:
        policy = parse_policy(policy_path)
    except ValueError as exc:
        return fail("CHAT_GUARD_POLICY_INVALID", str(exc))

    if not policy.enabled:
        print(
            "chat guard usage validation skipped: "
            f"chat_guard.enabled=false policy={policy_path.as_posix()}"
        )
        return 0

    entries, parse_error = parse_entries(log_path)
    if parse_error:
        return fail("CHAT_LOG_INVALID", parse_error)

    if not entries:
        return fail("CHAT_GUARD_USAGE_MISSING", "chat log has no entries to validate")

    for idx, entry in enumerate(entries):
        if not is_declaration_target(entry.body):
            continue
        if entry.timestamp is None:
            return fail(
                "CHAT_GUARD_TIMESTAMP_MISSING",
                f"declaration target entry at line {entry.line_no} is missing timestamp",
            )
        if entry.timestamp < policy.enabled_at:
            continue

        previous = entries[idx - 1] if idx > 0 else None
        previous_is_declaration_target = previous is not None and is_declaration_target(previous.body)
        if previous_is_declaration_target:
            continue

        if previous is None or not is_guard_entry(previous.body):
            if not policy.strict_mode:
                continue
            return fail(
                "CHAT_GUARD_USAGE_MISSING",
                f"declaration target at line {entry.line_no} must be preceded by GUARD_SEND_OK",
            )

        if previous.timestamp is None:
            return fail(
                "CHAT_GUARD_TIMESTAMP_MISSING",
                f"GUARD_SEND_OK entry at line {previous.line_no} is missing timestamp",
            )
        if previous.timestamp < policy.enabled_at:
            return fail(
                "CHAT_GUARD_USAGE_MISSING",
                f"GUARD_SEND_OK at line {previous.line_no} is older than enabled_at",
            )

    print(
        "chat guard usage validation passed: "
        f"log={log_path.as_posix()} policy={policy_path.as_posix()} "
        f"enabled_at={policy.enabled_at.strftime('%Y-%m-%dT%H:%M:%SZ')} transport={policy.transport}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
