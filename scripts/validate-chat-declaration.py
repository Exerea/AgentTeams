#!/usr/bin/env python3
from __future__ import annotations

from argparse import ArgumentParser, Namespace
from pathlib import Path
import re
import sys


GLOBAL_KICKOFF = "殿のご命令と各AGENTS.mdに忠実に従う家臣たちが集まりました。──家臣たちが動きます！"
KOUJO_TOKEN = "【稼働口上】"
DECLARATION_PATTERN = re.compile(
    r"^DECLARATION\s+team=\S+\s+role=\S+\s+task=(?:T-\d+|N/A)\s+action=\S+(?:\s+\|\s+.*)?$"
)
TIMESTAMP_PREFIX_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z\s+")
ACTION_PATTERNS = ("実行 ", "調べました", "Ran ")
DECLARATION_WINDOW = 6


def fail(code: str, message: str) -> int:
    print(f"ERROR [{code}] {message}", file=sys.stderr)
    return 1


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8").lstrip("\ufeff")


def entry_payload(line: str) -> str:
    trimmed = line.strip()
    if not trimmed.startswith("- "):
        return trimmed
    return trimmed[2:].strip()


def strip_timestamp_prefix(payload: str) -> str:
    return TIMESTAMP_PREFIX_PATTERN.sub("", payload, count=1).strip()


def extract_declaration(payload: str) -> str | None:
    idx = payload.find("DECLARATION ")
    if idx < 0:
        return None
    return payload[idx:].strip()


def is_action_payload(payload: str) -> bool:
    return any(token in payload for token in ACTION_PATTERNS)


def is_valid_declaration_payload(payload: str) -> bool:
    declaration = extract_declaration(payload)
    if declaration is None:
        return False
    return bool(DECLARATION_PATTERN.fullmatch(declaration))


def parse_args(argv: list[str]) -> Namespace:
    parser = ArgumentParser(description="Validate chat declaration protocol log.")
    parser.add_argument(
        "--log",
        default="logs/e2e-ai-log.md",
        help="chat log path (default: logs/e2e-ai-log.md)",
    )
    return parser.parse_args(argv)


def validate_global_kickoff(first_entry: str) -> tuple[str, str | None]:
    entry_body = strip_timestamp_prefix(first_entry)
    if entry_body == GLOBAL_KICKOFF:
        return "", None

    kickoff_keywords = ("殿のご命令", "AGENTS.md", "家臣たち", "動きます")
    if any(keyword in entry_body for keyword in kickoff_keywords):
        return (
            "CHAT_GLOBAL_KICKOFF_FORMAT_INVALID",
            "first entry kickoff declaration must exactly match the fixed sentence",
        )

    return (
        "CHAT_GLOBAL_KICKOFF_MISSING",
        "first entry must include the fixed global kickoff declaration",
    )


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    log_path = Path(args.log)

    if not log_path.exists():
        return fail("CHAT_LOG_MISSING", f"missing log file: {log_path.as_posix()}")

    text = read_text(log_path)
    lines = text.splitlines()

    entries_index = -1
    for idx, line in enumerate(lines):
        if line.strip() == "## Entries":
            entries_index = idx
            break
    if entries_index < 0:
        return fail("CHAT_ENTRY_FORMAT_INVALID", "missing required section: ## Entries")

    entries: list[str] = []
    for line in lines[entries_index + 1 :]:
        if line.strip().startswith("- "):
            entries.append(entry_payload(line))
    if len(entries) < 3:
        return fail(
            "CHAT_ENTRY_FORMAT_INVALID",
            "at least three entry lines are required after ## Entries",
        )

    first_entry = entries[0]
    second_entry = entries[1]
    third_entry = entries[2]

    kickoff_error_code, kickoff_message = validate_global_kickoff(first_entry)
    if kickoff_error_code:
        return fail(kickoff_error_code, kickoff_message or "invalid kickoff declaration")

    if KOUJO_TOKEN not in second_entry:
        return fail("CHAT_KOUJO_MISSING", "second entry must include 稼働口上")

    third_declaration = extract_declaration(third_entry)
    if third_declaration is None:
        return fail("CHAT_DECLARATION_MISSING", "third entry must include DECLARATION")
    if not DECLARATION_PATTERN.fullmatch(third_declaration):
        return fail("CHAT_DECLARATION_FORMAT_INVALID", "third entry has invalid DECLARATION format")

    for idx, payload in enumerate(entries):
        declaration = extract_declaration(payload)
        if declaration is not None and not DECLARATION_PATTERN.fullmatch(declaration):
            return fail("CHAT_DECLARATION_FORMAT_INVALID", f"invalid DECLARATION at entry index {idx}")

        if not is_action_payload(payload):
            continue

        start = max(0, idx - DECLARATION_WINDOW)
        window = entries[start:idx]
        has_preceding_declaration = any(is_valid_declaration_payload(candidate) for candidate in window)
        if not has_preceding_declaration:
            return fail(
                "CHAT_DECLARATION_MISSING",
                "action entry requires a preceding DECLARATION within the last 6 entries",
            )

    print(f"chat declaration validation passed: {log_path.as_posix()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
