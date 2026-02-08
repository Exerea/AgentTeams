#!/usr/bin/env python3
from __future__ import annotations

from argparse import ArgumentParser, Namespace
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
import re
import subprocess
import sys


GLOBAL_KICKOFF = "殿のご命令と各AGENTS.mdに忠実に従う家臣たちが集まりました。──家臣たちが動きます！"
KOUJO_TOKEN = "【稼働口上】"
DECLARATION_PATTERN = re.compile(
    r"^DECLARATION\s+team=(?P<team>\S+)\s+role=(?P<role>\S+)\s+task=(?P<task>(?:T-\d+|N/A))\s+action=(?P<action>\S+)(?:\s+\|\s+.*)?$"
)
KOUJO_PATTERN = re.compile(
    r"^【稼働口上】殿、ただいま\s+(?P<honorific>家老|足軽)\s+の\s+(?P<team>[^/\s]+)/(?P<role>\S+)\s+が「(?P<title>[^」]+)」を務めます。(?P<summary>.*)$"
)
TASK_FILE_NAME_PATTERN = re.compile(r"^TASK-\d{5}-[a-z0-9]+(?:-[a-z0-9]+)*\.yaml$")
TASK_VALUE_PATTERN = re.compile(r"^(?:T-\d+|N/A)$")
TASK_ID_ONLY_TITLE_PATTERN = re.compile(r"^(?:T-\d+|N/A)$")


@dataclass
class GuardError(Exception):
    code: str
    message: str
    action_hint: str = "guard_chat_send"


def fail(code: str, message: str) -> int:
    print(f"ERROR [{code}] {message}", file=sys.stderr)
    return 1


def warn(code: str, message: str) -> None:
    print(f"WARN [{code}] {message}", file=sys.stderr)


def now_utc_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8").lstrip("\ufeff")


def write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as fh:
        fh.write(content)


def parse_args(argv: list[str]) -> Namespace:
    parser = ArgumentParser(description="Guard chat declaration protocol before log send.")
    parser.add_argument(
        "--event",
        required=True,
        choices=("task_start", "role_switch", "gate"),
        help="guard event type",
    )
    parser.add_argument("--team", required=True, help="team name")
    parser.add_argument("--role", required=True, help="role name")
    parser.add_argument("--task", required=True, help="task id or N/A")
    parser.add_argument("--task-title", required=True, help="human-readable task title")
    parser.add_argument("--message-file", required=True, help="message body file path")
    parser.add_argument("--task-file", required=True, help="TASK-*.yaml path")
    parser.add_argument("--log", default="logs/e2e-ai-log.md", help="chat log path")
    parser.add_argument(
        "--emit-fixed-file",
        default="",
        help="optional output path for generated fixed declaration message",
    )
    parser.add_argument("--verbose", action="store_true", help="verbose logging")
    return parser.parse_args(argv)


def expected_honorific(team: str, role: str) -> str:
    if team == "coordinator" and role == "coordinator":
        return "家老"
    return "足軽"


def parse_message_lines(message_path: Path) -> list[str]:
    if not message_path.exists():
        raise GuardError("MESSAGE_FILE_MISSING", f"missing message file: {message_path.as_posix()}")

    lines = [line.strip() for line in read_text(message_path).splitlines()]
    lines = [line for line in lines if line]
    if not lines:
        raise GuardError(
            "CHAT_ENTRY_FORMAT_INVALID",
            f"message file is empty: {message_path.as_posix()}",
        )
    return lines


def extract_action_hint(lines: list[str]) -> str:
    for line in lines:
        match = DECLARATION_PATTERN.fullmatch(line.strip())
        if match:
            return match.group("action")
    return "guard_chat_send"


def parse_koujo_line(line: str, team: str, role: str, task_title: str, task_value: str) -> None:
    if KOUJO_TOKEN not in line:
        raise GuardError("CHAT_KOUJO_MISSING", "required 稼働口上 line is missing")

    match = KOUJO_PATTERN.fullmatch(line.strip())
    if not match:
        raise GuardError("CHAT_KOUJO_FORMAT_INVALID", "稼働口上 format is invalid")

    honorific = match.group("honorific")
    expected = expected_honorific(team, role)
    if honorific != expected:
        raise GuardError(
            "CHAT_HONORIFIC_MISMATCH",
            f"expected honorific '{expected}' for {team}/{role}, got '{honorific}'",
        )

    declared_team = match.group("team")
    declared_role = match.group("role")
    if declared_team != team or declared_role != role:
        raise GuardError(
            "CHAT_KOUJO_ROLE_MISMATCH",
            f"koujo team/role must be {team}/{role}, got {declared_team}/{declared_role}",
        )

    title = match.group("title").strip()
    if title != task_title:
        raise GuardError(
            "CHAT_KOUJO_TITLE_MISMATCH",
            f"koujo title must be '{task_title}', got '{title}'",
        )
    if TASK_ID_ONLY_TITLE_PATTERN.fullmatch(title) or title == task_value:
        raise GuardError(
            "CHAT_KOUJO_TITLE_INVALID",
            "koujo title must be a human-readable task title, not task_id only",
        )


def parse_declaration_line(line: str, team: str, role: str, task_value: str) -> str:
    stripped = line.strip()
    if not stripped.startswith("DECLARATION "):
        raise GuardError("CHAT_DECLARATION_MISSING", "required DECLARATION line is missing")

    match = DECLARATION_PATTERN.fullmatch(stripped)
    if not match:
        raise GuardError("CHAT_DECLARATION_FORMAT_INVALID", "DECLARATION format is invalid")

    if match.group("team") != team:
        raise GuardError(
            "CHAT_DECLARATION_TEAM_MISMATCH",
            f"DECLARATION team must be '{team}'",
            action_hint=match.group("action"),
        )
    if match.group("role") != role:
        raise GuardError(
            "CHAT_DECLARATION_ROLE_MISMATCH",
            f"DECLARATION role must be '{role}'",
            action_hint=match.group("action"),
        )
    if match.group("task") != task_value:
        raise GuardError(
            "CHAT_DECLARATION_TASK_MISMATCH",
            f"DECLARATION task must be '{task_value}'",
            action_hint=match.group("action"),
        )
    return match.group("action")


def validate_message_contract(
    event: str,
    lines: list[str],
    team: str,
    role: str,
    task_value: str,
    task_title: str,
) -> str:
    if event == "task_start":
        if len(lines) < 3:
            raise GuardError(
                "CHAT_ENTRY_FORMAT_INVALID",
                "task_start requires at least 3 lines: kickoff -> 稼働口上 -> DECLARATION",
            )
        kickoff = lines[0].strip()
        if kickoff != GLOBAL_KICKOFF:
            if "殿のご命令" in kickoff:
                raise GuardError(
                    "CHAT_GLOBAL_KICKOFF_FORMAT_INVALID",
                    "fixed kickoff declaration must exactly match the required sentence",
                )
            raise GuardError(
                "CHAT_GLOBAL_KICKOFF_MISSING",
                "task_start requires the fixed kickoff declaration as first line",
            )

        parse_koujo_line(lines[1], team, role, task_title, task_value)
        return parse_declaration_line(lines[2], team, role, task_value)

    if len(lines) < 2:
        raise GuardError(
            "CHAT_ENTRY_FORMAT_INVALID",
            f"{event} requires at least 2 lines: 稼働口上 -> DECLARATION",
        )

    parse_koujo_line(lines[0], team, role, task_title, task_value)
    return parse_declaration_line(lines[1], team, role, task_value)


def resolve_repo_root(cwd: Path) -> Path:
    try:
        proc = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            cwd=str(cwd),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )
    except OSError:
        return cwd.resolve()

    if proc.returncode != 0:
        return cwd.resolve()

    out = proc.stdout.strip()
    if not out:
        return cwd.resolve()
    return Path(out.splitlines()[-1]).resolve()


def append_guard_log_entries(
    log_path: Path,
    event: str,
    team: str,
    role: str,
    task_value: str,
    message_lines: list[str],
) -> str:
    if not log_path.exists():
        raise GuardError("CHAT_LOG_MISSING", f"missing chat log file: {log_path.as_posix()}")

    original = read_text(log_path)
    if "## Entries" not in original:
        raise GuardError(
            "CHAT_ENTRY_FORMAT_INVALID",
            f"log file missing required section '## Entries': {log_path.as_posix()}",
        )

    entries: list[str] = []
    entries.append(
        f"- {now_utc_iso()} GUARD_SEND_OK event={event} team={team} role={role} task={task_value}"
    )
    for line in message_lines:
        entries.append(f"- {now_utc_iso()} {line}")

    new_text = original if original.endswith("\n") else original + "\n"
    new_text += "\n".join(entries) + "\n"
    write_text(log_path, new_text)
    return original


def run_chat_validator(repo_root: Path, log_path: Path) -> tuple[int, str]:
    script_path = repo_root / "scripts" / "validate-chat-declaration.py"
    if not script_path.exists():
        raise GuardError(
            "VALIDATOR_MISSING",
            f"missing validator script: {script_path.as_posix()}",
        )

    proc = subprocess.run(
        [sys.executable, str(script_path), "--log", str(log_path)],
        cwd=str(repo_root),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    return proc.returncode, proc.stdout.strip()


def report_protocol_incident(
    repo_root: Path,
    task_file_path: Path,
    code: str,
    message: str,
    verbose: bool,
) -> None:
    at_script = repo_root / "scripts" / "at.py"
    if not at_script.exists():
        warn(
            "GUARD_REPORT_INCIDENT_SKIPPED",
            f"missing at.py for report-incident call: {at_script.as_posix()}",
        )
        return

    summary = f"guard-chat blocked ({code}): {message}"
    summary = " ".join(summary.replace("\r", " ").replace("\n", " ").split())
    if len(summary) > 220:
        summary = summary[:217].rstrip() + "..."

    command = [
        sys.executable,
        str(at_script),
        "report-incident",
        "--task-file",
        str(task_file_path),
        "--code",
        "PROTO_REQUIRED_FIELD_MISSING",
        "--summary",
        summary,
        "--project",
        repo_root.name or "agentteams-project",
    ]
    if verbose:
        command.append("--verbose")

    proc = subprocess.run(
        command,
        cwd=str(repo_root),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    if proc.returncode == 0:
        if verbose:
            print(proc.stdout.strip())
        return

    detail = proc.stdout.strip()
    if detail:
        warn("GUARD_REPORT_INCIDENT_FAILED", detail)
        return
    warn("GUARD_REPORT_INCIDENT_FAILED", "report-incident returned non-zero exit code")


def emit_fixed_message(
    target: Path,
    event: str,
    team: str,
    role: str,
    task_value: str,
    task_title: str,
    action: str,
) -> None:
    honorific = expected_honorific(team, role)
    koujo = (
        f"{KOUJO_TOKEN}殿、ただいま {honorific} の {team}/{role} が「{task_title}」を務めます。"
        "送信前ガード要件に合わせて再生成しました。"
    )
    declaration = f"DECLARATION team={team} role={role} task={task_value} action={action}"

    lines: list[str] = []
    if event == "task_start":
        lines.append(GLOBAL_KICKOFF)
    lines.append(koujo)
    lines.append(declaration)
    write_text(target, "\n".join(lines) + "\n")


def main(argv: list[str]) -> int:
    args = parse_args(argv)

    if not TASK_VALUE_PATTERN.fullmatch(args.task):
        return fail("PATH_LAYOUT_INVALID", f"invalid --task value: {args.task}")
    if not args.team.strip():
        return fail("PATH_LAYOUT_INVALID", "--team must not be empty")
    if not args.role.strip():
        return fail("PATH_LAYOUT_INVALID", "--role must not be empty")
    if not args.task_title.strip():
        return fail("PATH_LAYOUT_INVALID", "--task-title must not be empty")

    cwd = Path.cwd().resolve()
    repo_root = resolve_repo_root(cwd)
    task_path = Path(args.task_file).expanduser()
    if not task_path.is_absolute():
        task_path = (cwd / task_path).resolve()

    if not task_path.exists():
        return fail("TASK_FILE_MISSING", f"missing task file: {task_path.as_posix()}")
    if not TASK_FILE_NAME_PATTERN.fullmatch(task_path.name):
        return fail("TASK_FILENAME_INVALID", f"invalid task filename: {task_path.name}")

    log_path = Path(args.log).expanduser()
    if not log_path.is_absolute():
        log_path = (cwd / log_path).resolve()

    message_path = Path(args.message_file).expanduser()
    if not message_path.is_absolute():
        message_path = (cwd / message_path).resolve()

    action_hint = "guard_chat_send"
    original_log_text = ""
    try:
        message_lines = parse_message_lines(message_path)
        action_hint = extract_action_hint(message_lines)
        action = validate_message_contract(
            args.event,
            message_lines,
            args.team.strip(),
            args.role.strip(),
            args.task.strip(),
            args.task_title.strip(),
        )
        action_hint = action or action_hint

        original_log_text = append_guard_log_entries(
            log_path,
            args.event,
            args.team.strip(),
            args.role.strip(),
            args.task.strip(),
            message_lines,
        )
        validator_code, validator_output = run_chat_validator(repo_root, log_path)
        if validator_code != 0:
            write_text(log_path, original_log_text)
            raise GuardError(
                "CHAT_DECLARATION_VALIDATION_FAILED",
                validator_output or "validate-chat-declaration failed after guard append",
                action_hint=action_hint,
            )
    except GuardError as exc:
        if args.emit_fixed_file:
            fixed_target = Path(args.emit_fixed_file).expanduser()
            if not fixed_target.is_absolute():
                fixed_target = (cwd / fixed_target).resolve()
            try:
                emit_fixed_message(
                    fixed_target,
                    args.event,
                    args.team.strip(),
                    args.role.strip(),
                    args.task.strip(),
                    args.task_title.strip(),
                    exc.action_hint or action_hint,
                )
                print(f"fixed template emitted: {fixed_target.as_posix()}")
            except OSError as file_error:
                warn(
                    "GUARD_FIXED_TEMPLATE_WRITE_FAILED",
                    f"failed to write fixed template: {file_error}",
                )

        report_protocol_incident(repo_root, task_path, exc.code, exc.message, args.verbose)
        return fail(exc.code, exc.message)

    print(
        "OK [GUARD_SEND_OK] "
        f"event={args.event} team={args.team} role={args.role} task={args.task} "
        f"log={log_path.as_posix()}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
