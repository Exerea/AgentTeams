#!/usr/bin/env python3
from __future__ import annotations

from argparse import ArgumentParser, Namespace
from pathlib import Path
import re
import subprocess
import sys


TASK_FILE_PATTERN = re.compile(r"^TASK-\d{5}-[a-z0-9]+(?:-[a-z0-9]+)*\.yaml$")
TASK_ID_PATTERN = re.compile(r"^id\s*:\s*(.+?)\s*$")
TASK_STATUS_PATTERN = re.compile(r"^status\s*:\s*(.+?)\s*$")
DECLARATION_PATTERN = re.compile(
    r"^DECLARATION\s+team=coordinator\s+role=coordinator\s+task=(?P<task>T-\d+|N/A)\s+action=self_update_commit_push(?:\s+\|\s+.*)?$"
)


def fail(code: str, message: str) -> int:
    print(f"ERROR [{code}] {message}", file=sys.stderr)
    return 1


def run_git(args: list[str], repo_root: Path) -> tuple[int, str]:
    proc = subprocess.run(
        ["git", *args],
        cwd=str(repo_root),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    return proc.returncode, proc.stdout


def parse_args(argv: list[str]) -> Namespace:
    parser = ArgumentParser(description="Validate self-update evidence before commit.")
    parser.add_argument("--task-file", default="", help="Path to TASK-xxxxx-*.yaml")
    parser.add_argument(
        "--log",
        default="logs/e2e-ai-log.md",
        help="Chat log path (default: logs/e2e-ai-log.md)",
    )
    return parser.parse_args(argv)


def normalize_path(path_arg: str, repo_root: Path) -> Path:
    raw = Path(path_arg).expanduser()
    if raw.is_absolute():
        return raw.resolve()
    return (repo_root / raw).resolve()


def parse_task_metadata(task_path: Path) -> tuple[str, str]:
    text = task_path.read_text(encoding="utf-8").lstrip("\ufeff")
    task_id = ""
    status = ""
    for line in text.splitlines():
        if not task_id:
            m_id = TASK_ID_PATTERN.match(line)
            if m_id:
                task_id = m_id.group(1).strip()
        if not status:
            m_status = TASK_STATUS_PATTERN.match(line)
            if m_status:
                status = m_status.group(1).strip()
        if task_id and status:
            break
    return task_id, status


def rel_posix(path: Path, repo_root: Path) -> str:
    return path.relative_to(repo_root).as_posix()


def extract_declaration(payload: str) -> str | None:
    idx = payload.find("DECLARATION ")
    if idx < 0:
        return None
    return payload[idx:].strip()


def parse_added_lines_from_staged_diff(diff_text: str) -> list[str]:
    added: list[str] = []
    for line in diff_text.splitlines():
        if not line.startswith("+"):
            continue
        if line.startswith("+++"):
            continue
        added.append(line[1:].strip())
    return added


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    repo_root = Path(__file__).resolve().parent.parent

    if not args.task_file:
        return fail(
            "SELF_UPDATE_TASK_REQUIRED",
            "--task-file is required",
        )

    task_path = normalize_path(args.task_file, repo_root)
    states_dir = (repo_root / ".codex" / "states").resolve()

    if not task_path.exists() or not task_path.is_file():
        return fail(
            "SELF_UPDATE_TASK_PATH_INVALID",
            f"task file not found: {task_path.as_posix()}",
        )
    if task_path.parent != states_dir or not TASK_FILE_PATTERN.fullmatch(task_path.name):
        return fail(
            "SELF_UPDATE_TASK_PATH_INVALID",
            "task file must be under .codex/states and named TASK-xxxxx-slug.yaml",
        )

    task_id, status = parse_task_metadata(task_path)
    if not task_id:
        return fail("SELF_UPDATE_TASK_PATH_INVALID", "task id is missing in task file")
    if status != "done":
        return fail(
            "SELF_UPDATE_TASK_STATUS_INVALID",
            f"task status must be done for self-update: {task_id} (current: {status or 'N/A'})",
        )

    log_path = normalize_path(args.log, repo_root)
    if not log_path.exists() or not log_path.is_file():
        return fail("SELF_UPDATE_LOG_NOT_STAGED", f"log file not found: {log_path.as_posix()}")

    if not task_path.is_relative_to(repo_root):
        return fail("SELF_UPDATE_TASK_PATH_INVALID", "task file must be inside repository")
    if not log_path.is_relative_to(repo_root):
        return fail("SELF_UPDATE_LOG_NOT_STAGED", "log file must be inside repository")

    task_rel = rel_posix(task_path, repo_root)
    log_rel = rel_posix(log_path, repo_root)

    code, staged_out = run_git(["diff", "--cached", "--name-only"], repo_root)
    if code != 0:
        return fail("SELF_UPDATE_TASK_SCOPE_INVALID", "failed to read staged files")
    staged_files = [line.strip().replace("\\", "/") for line in staged_out.splitlines() if line.strip()]
    staged_set = set(staged_files)

    if task_rel not in staged_set:
        return fail(
            "SELF_UPDATE_TASK_SCOPE_INVALID",
            f"target task file is not staged: {task_rel}",
        )

    other_staged_tasks = []
    for path in staged_set:
        if not path.startswith(".codex/states/TASK-"):
            continue
        if path == task_rel:
            continue
        other_staged_tasks.append(path)
    if other_staged_tasks:
        return fail(
            "SELF_UPDATE_TASK_SCOPE_INVALID",
            "only the target task file may be staged under .codex/states/TASK-*.yaml",
        )

    if log_rel not in staged_set:
        return fail(
            "SELF_UPDATE_LOG_NOT_STAGED",
            f"log file is not staged: {log_rel}",
        )

    code, diff_out = run_git(["diff", "--cached", "--unified=0", "--", log_rel], repo_root)
    if code != 0:
        return fail("SELF_UPDATE_LOG_NOT_STAGED", "failed to read staged log diff")

    added_lines = parse_added_lines_from_staged_diff(diff_out)
    if not any("【稼働口上】" in line for line in added_lines):
        return fail(
            "SELF_UPDATE_LOG_KOUJO_MISSING",
            "staged log additions must include a line with 【稼働口上】",
        )

    declaration_lines = []
    for line in added_lines:
        declaration = extract_declaration(line)
        if declaration is not None:
            declaration_lines.append(declaration)

    if not declaration_lines:
        return fail(
            "SELF_UPDATE_LOG_DECLARATION_MISSING",
            "staged log additions must include DECLARATION ... action=self_update_commit_push",
        )

    valid_for_action = []
    for declaration in declaration_lines:
        m_decl = DECLARATION_PATTERN.fullmatch(declaration)
        if m_decl:
            valid_for_action.append(m_decl.group("task"))

    if not valid_for_action:
        return fail(
            "SELF_UPDATE_LOG_DECLARATION_MISSING",
            "required DECLARATION for coordinator/coordinator self_update_commit_push is missing",
        )

    if task_id not in valid_for_action:
        return fail(
            "SELF_UPDATE_LOG_DECLARATION_TASK_MISMATCH",
            f"DECLARATION task must match task file id ({task_id})",
        )

    print(f"self-update evidence validation passed: task={task_id}, log={log_rel}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
