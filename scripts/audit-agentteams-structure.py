#!/usr/bin/env python3
from __future__ import annotations

from argparse import ArgumentParser, Namespace
from dataclasses import dataclass
from pathlib import Path
import re
import sys


TASK_FILE_PATTERN = re.compile(r"^TASK-\d{5}-[a-z0-9]+(?:-[a-z0-9]+)*\.yaml$")
DECLARATION_PATTERN = re.compile(
    r"^DECLARATION\s+team=\S+\s+role=\S+\s+task=(?:T-\d+|N/A)\s+action=\S+(?:\s+\|\s+.*)?$"
)
BOOL_TRUE = {"true", "yes", "1"}


@dataclass
class TaskSnapshot:
    path: Path
    task_id: str
    title: str
    status: str
    assignee: str
    teams: set[str]
    roles: set[str]
    handoff_memos: list[str]
    warnings_open: int
    qa_required: bool
    backend_security_required: bool
    ux_required: bool


@dataclass
class Finding:
    code: str
    task_id: str
    severity: str
    message: str


def normalize(value: str) -> str:
    v = (value or "").strip()
    if (v.startswith('"') and v.endswith('"')) or (v.startswith("'") and v.endswith("'")):
        v = v[1:-1]
    return v.strip()


def parse_bool(value: str) -> bool:
    return normalize(value).lower() in BOOL_TRUE


def parse_args(argv: list[str]) -> Namespace:
    parser = ArgumentParser(description="Audit AgentTeams task distribution and rule evidence.")
    parser.add_argument(
        "--states-dir",
        default=".codex/states",
        help="directory containing TASK-*.yaml files (default: .codex/states)",
    )
    parser.add_argument("--log", default="logs/e2e-ai-log.md", help="chat log path")
    parser.add_argument("--min-teams", type=int, default=3, help="minimum unique teams per task")
    parser.add_argument("--min-roles", type=int, default=5, help="minimum unique roles per task")
    parser.add_argument("--output", default="", help="optional markdown output path")
    parser.add_argument(
        "--strict",
        action="store_true",
        help="return non-zero when findings exist",
    )
    return parser.parse_args(argv)


def parse_task(path: Path) -> TaskSnapshot:
    lines = path.read_text(encoding="utf-8").lstrip("\ufeff").splitlines()
    section = ""
    in_handoff = False

    task_id = path.stem
    title = path.name
    status = ""
    assignee = ""
    warnings_open = 0
    teams: set[str] = set()
    roles: set[str] = set()
    handoff_memos: list[str] = []

    qa_required = False
    backend_security_required = False
    ux_required = False

    for line in lines:
        m_top = re.match(r"^([A-Za-z_][A-Za-z0-9_]*)\s*:\s*(.*)$", line)
        if m_top:
            section = m_top.group(1)
            value = normalize(m_top.group(2))
            in_handoff = False
            if section == "id":
                task_id = value or task_id
            elif section == "title":
                title = value or title
            elif section == "status":
                status = value
            elif section == "assignee":
                assignee = value
                if assignee:
                    roles.add(assignee)
                    teams.add(assignee.split("/", 1)[0] if "/" in assignee else assignee)
            continue

        if section == "warnings":
            m_warn_status = re.match(r"^\s{4}status\s*:\s*(.+)$", line)
            if m_warn_status and normalize(m_warn_status.group(1)) == "open":
                warnings_open += 1
            continue

        if section == "local_flags":
            m_flag = re.match(
                r"^\s{2}(qa_review_required|backend_security_required|ux_review_required)\s*:\s*(.+)$",
                line,
            )
            if m_flag:
                key = m_flag.group(1)
                value = m_flag.group(2)
                if key == "qa_review_required":
                    qa_required = parse_bool(value)
                elif key == "backend_security_required":
                    backend_security_required = parse_bool(value)
                elif key == "ux_review_required":
                    ux_required = parse_bool(value)
            continue

        if section == "handoffs":
            m_item = re.match(r"^\s{2}-\s*(.*)$", line)
            if m_item:
                in_handoff = True
                inline = m_item.group(1).strip()
                if inline:
                    m_inline = re.match(r"^([A-Za-z_][A-Za-z0-9_]*)\s*:\s*(.*)$", inline)
                    if m_inline:
                        key = m_inline.group(1)
                        value = normalize(m_inline.group(2))
                        if key in {"from", "to"} and value:
                            roles.add(value)
                            teams.add(value.split("/", 1)[0] if "/" in value else value)
                        if key == "memo":
                            handoff_memos.append(value)
                continue
            if in_handoff:
                m_kv = re.match(r"^\s{4}([A-Za-z_][A-Za-z0-9_]*)\s*:\s*(.*)$", line)
                if m_kv:
                    key = m_kv.group(1)
                    value = normalize(m_kv.group(2))
                    if key in {"from", "to"} and value:
                        roles.add(value)
                        teams.add(value.split("/", 1)[0] if "/" in value else value)
                    if key == "memo":
                        handoff_memos.append(value)
            continue

    return TaskSnapshot(
        path=path,
        task_id=task_id,
        title=title,
        status=status,
        assignee=assignee,
        teams=teams,
        roles=roles,
        handoff_memos=handoff_memos,
        warnings_open=warnings_open,
        qa_required=qa_required,
        backend_security_required=backend_security_required,
        ux_required=ux_required,
    )


def audit_tasks(tasks: list[TaskSnapshot], min_teams: int, min_roles: int) -> list[Finding]:
    findings: list[Finding] = []
    qa_roles = {"qa-review-guild/code-critic", "qa-review-guild/test-architect"}
    backend_security_role = "backend/security-expert"
    ux_role = "frontend/ux-specialist"

    for task in tasks:
        if len(task.teams) < min_teams:
            findings.append(
                Finding(
                    code="TEAM_DISTRIBUTION_LOW",
                    task_id=task.task_id,
                    severity="warning",
                    message=f"unique teams={len(task.teams)} < min-teams={min_teams}",
                )
            )
        if len(task.roles) < min_roles:
            findings.append(
                Finding(
                    code="ROLE_DISTRIBUTION_LOW",
                    task_id=task.task_id,
                    severity="warning",
                    message=f"unique roles={len(task.roles)} < min-roles={min_roles}",
                )
            )

        has_declaration = any(DECLARATION_PATTERN.match(memo) for memo in task.handoff_memos)
        if task.status in {"in_progress", "in_review", "done"} and not has_declaration:
            findings.append(
                Finding(
                    code="DECLARATION_EVIDENCE_MISSING",
                    task_id=task.task_id,
                    severity="error",
                    message="status requires at least one handoff DECLARATION evidence",
                )
            )

        if task.qa_required and not qa_roles.issubset(task.roles):
            findings.append(
                Finding(
                    code="QA_EVIDENCE_MISSING",
                    task_id=task.task_id,
                    severity="error",
                    message="qa_review_required=true but code-critic/test-architect evidence is incomplete",
                )
            )
        if task.backend_security_required and backend_security_role not in task.roles:
            findings.append(
                Finding(
                    code="BACKEND_SECURITY_EVIDENCE_MISSING",
                    task_id=task.task_id,
                    severity="error",
                    message="backend_security_required=true but backend/security-expert evidence is missing",
                )
            )
        if task.ux_required and ux_role not in task.roles:
            findings.append(
                Finding(
                    code="UX_EVIDENCE_MISSING",
                    task_id=task.task_id,
                    severity="error",
                    message="ux_review_required=true but frontend/ux-specialist evidence is missing",
                )
            )
        if task.status == "done" and task.warnings_open > 0:
            findings.append(
                Finding(
                    code="OPEN_WARNING_AT_DONE",
                    task_id=task.task_id,
                    severity="error",
                    message=f"done status has {task.warnings_open} open warning(s)",
                )
            )

    return findings


def audit_log(log_path: Path) -> tuple[bool, bool, bool]:
    if not log_path.exists():
        return False, False, False

    text = log_path.read_text(encoding="utf-8").lstrip("\ufeff")
    has_agents_read = ".codex/AGENTS.md" in text
    has_adr_read = "docs/adr/" in text
    has_guard = "GUARD_SEND_OK" in text
    return has_agents_read, has_adr_read, has_guard


def render_report(
    tasks: list[TaskSnapshot],
    findings: list[Finding],
    has_agents_read: bool,
    has_adr_read: bool,
    has_guard: bool,
) -> str:
    lines: list[str] = []
    lines.append("# AgentTeams Structure Audit")
    lines.append("")
    lines.append("## Summary")
    lines.append(f"- tasks scanned: {len(tasks)}")
    lines.append(f"- findings: {len(findings)}")
    lines.append(f"- log has AGENTS read evidence: {'yes' if has_agents_read else 'no'}")
    lines.append(f"- log has ADR read evidence: {'yes' if has_adr_read else 'no'}")
    lines.append(f"- log has guard usage evidence: {'yes' if has_guard else 'no'}")
    lines.append("")

    if findings:
        lines.append("## Findings")
        for finding in findings:
            lines.append(
                f"- [{finding.severity}] {finding.task_id} {finding.code}: {finding.message}"
            )
    else:
        lines.append("## Findings")
        lines.append("- no structural findings detected")
    lines.append("")

    lines.append("## Task Matrix")
    for task in tasks:
        lines.append(
            f"- {task.task_id} | status={task.status or 'N/A'} | teams={len(task.teams)} | roles={len(task.roles)} | open_warnings={task.warnings_open}"
        )
    lines.append("")
    return "\n".join(lines)


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    if args.min_teams < 1:
        print("ERROR: --min-teams must be >= 1", file=sys.stderr)
        return 1
    if args.min_roles < 1:
        print("ERROR: --min-roles must be >= 1", file=sys.stderr)
        return 1

    states_dir = Path(args.states_dir)
    if not states_dir.exists():
        print(f"ERROR: states directory not found: {states_dir.as_posix()}", file=sys.stderr)
        return 1

    task_files = sorted(
        path
        for path in states_dir.glob("TASK-*.yaml")
        if path.is_file() and TASK_FILE_PATTERN.fullmatch(path.name)
    )
    tasks = [parse_task(path) for path in task_files]
    findings = audit_tasks(tasks, args.min_teams, args.min_roles)

    has_agents_read, has_adr_read, has_guard = audit_log(Path(args.log))
    report = render_report(tasks, findings, has_agents_read, has_adr_read, has_guard)

    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(report, encoding="utf-8")
        print(f"audit report written: {output_path.as_posix()}")
    else:
        print(report)

    if args.strict and findings:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
