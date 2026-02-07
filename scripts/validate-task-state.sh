#!/usr/bin/env bash
set -euo pipefail

task_file="${1:-}"

if [[ -z "$task_file" ]]; then
  echo "ERROR: task file path is required. Usage: validate-task-state.sh <TASK-xxxxx-slug.yaml>" >&2
  exit 1
fi

if [[ ! -f "$task_file" ]]; then
  echo "ERROR: task file not found: $task_file" >&2
  exit 1
fi

if command -v python3 >/dev/null 2>&1; then
  py_bin="python3"
elif command -v python >/dev/null 2>&1; then
  py_bin="python"
else
  echo "ERROR: python or python3 is required." >&2
  exit 1
fi

"$py_bin" - "$task_file" <<'PY'
import re
import sys
from pathlib import Path

task_path = Path(sys.argv[1])
text = task_path.read_text(encoding="utf-8").lstrip("\ufeff")
lines = text.splitlines()

allowed_status = {"todo", "in_progress", "in_review", "blocked", "done"}
required_top = {
    "id",
    "title",
    "owner",
    "assignee",
    "status",
    "target_stack",
    "depends_on",
    "adr_refs",
    "local_flags",
    "warnings",
    "handoffs",
    "notes",
    "updated_at",
}
required_target_stack = {"language", "framework", "infra"}
required_flags = {
    "major_decision_required",
    "documentation_sync_required",
    "tech_specialist_required",
    "qa_review_required",
    "research_track_enabled",
    "backend_security_required",
    "ux_review_required",
}
required_warning_keys = {
    "id",
    "level",
    "code",
    "detected_by",
    "source_role",
    "target_role",
    "detected_at",
    "summary",
    "status",
    "resolution_task_ids",
    "updated_at",
}
allowed_warning_levels = {"warning", "error"}
allowed_warning_statuses = {"open", "triaged", "resolved"}
allowed_warning_codes = {
    "PROTO_SCHEMA_MISMATCH",
    "PROTO_FIELD_CASE_MISMATCH",
    "PROTO_REQUIRED_FIELD_MISSING",
    "PROTO_UNEXPECTED_FIELD",
    "PROTO_HANDOFF_CONTEXT_MISSING",
}
qa_roles = {"qa-review-guild/code-critic", "qa-review-guild/test-architect"}
backend_security_role = "backend/security-expert"
ux_specialist_role = "frontend/ux-specialist"
removed_reviewer_role = "frontend/code-reviewer"
research_roles = {"innovation-research-guild/trend-researcher", "innovation-research-guild/poc-agent"}
tech_prefix = "tech-specialist-guild/"
declaration_pattern = re.compile(r"^DECLARATION\s+team=\S+\s+role=\S+\s+task=(?:T-\d+|N/A)\s+action=\S+(?:\s+\|\s+.*)?$")
improvement_pattern = re.compile(
    r"IMPROVEMENT_PROPOSAL\s+type=(?:process|role|tool|rule|cleanup)\s+priority=(?:high|medium|low)\s+owner=coordinator\s+summary=.+"
)
statuses_require_declaration = {"in_progress", "in_review", "done"}

errors = []

if not re.match(r"^TASK-\d{5}-[a-z0-9]+(?:-[a-z0-9]+)*\.yaml$", task_path.name):
    errors.append(f"invalid task filename: {task_path.name}")

top_keys = []
for ln in lines:
    m = re.match(r"^([A-Za-z_][A-Za-z0-9_]*)\s*:", ln)
    if m:
        k = m.group(1)
        if k not in top_keys:
            top_keys.append(k)

missing_top = sorted(required_top - set(top_keys))
extra_top = sorted(set(top_keys) - required_top)
if missing_top:
    errors.append(f"missing top-level keys: {', '.join(missing_top)}")
if extra_top:
    errors.append(f"unexpected top-level keys: {', '.join(extra_top)}")

section = None
status = ""
task_id = ""
assignee = ""
notes = ""
adr_ref_count = 0
target_stack = {}
flags = {}

handoff_idx = 0
in_handoff = False
handoff_keys = set()
handoff_from_values = []
handoff_to_values = []
handoff_memo_values = []

warning_idx = 0
in_warning = False
warning = {}
warning_open_count = 0

def validate_handoff(idx: int, keys: set) -> None:
    missing = sorted({"from", "to", "at", "memo"} - keys)
    if missing:
        errors.append(f"handoffs[{idx}] missing keys: {', '.join(missing)}")

def validate_warning(idx: int, obj: dict) -> None:
    nonlocal_warning_open = obj.get("status", "")
    missing = sorted(required_warning_keys - set(obj.keys()))
    if missing:
        errors.append(f"warnings[{idx}] missing keys: {', '.join(missing)}")

    level = obj.get("level", "")
    warn_status = obj.get("status", "")
    code = obj.get("code", "")
    if level and level not in allowed_warning_levels:
        errors.append(f"warnings[{idx}].level invalid: '{level}'")
    if warn_status and warn_status not in allowed_warning_statuses:
        errors.append(f"warnings[{idx}].status invalid: '{warn_status}'")
    if code and code not in allowed_warning_codes:
        errors.append(f"warnings[{idx}].code invalid: '{code}'")
    return 1 if nonlocal_warning_open == "open" else 0

for ln in lines:
    m_top = re.match(r"^([A-Za-z_][A-Za-z0-9_]*)\s*:", ln)
    if m_top:
        key = m_top.group(1)
        if key == "status":
            m = re.match(r"^status\s*:\s*(.+)$", ln)
            if m:
                status = m.group(1).strip()
        elif key == "id":
            m = re.match(r"^id\s*:\s*(.+)$", ln)
            if m:
                task_id = m.group(1).strip()
        elif key == "assignee":
            m = re.match(r"^assignee\s*:\s*(.+)$", ln)
            if m:
                assignee = m.group(1).strip()
        elif key == "notes":
            m = re.match(r"^notes\s*:\s*(.+)$", ln)
            if m:
                notes = m.group(1).strip()

        if section == "handoffs" and in_handoff:
            validate_handoff(handoff_idx, handoff_keys)
        if section == "warnings" and in_warning:
            warning_open_count += validate_warning(warning_idx, warning)

        section = key
        in_handoff = False
        handoff_keys = set()
        in_warning = False
        warning = {}
        continue

    if section == "target_stack":
        m = re.match(r"^\s{2}(language|framework|infra)\s*:\s*(.+)\s*$", ln)
        if m:
            target_stack[m.group(1)] = m.group(2).strip()
        continue

    if section == "local_flags":
        m = re.match(r"^\s{2}(major_decision_required|documentation_sync_required|tech_specialist_required|qa_review_required|research_track_enabled|backend_security_required|ux_review_required)\s*:\s*(.+)\s*$", ln)
        if m:
            k = m.group(1)
            v = m.group(2).strip().lower()
            if v not in {"true", "false"}:
                errors.append(f"local_flags.{k} must be true or false")
            else:
                flags[k] = v
        continue

    if section == "adr_refs":
        if re.match(r"^\s{2}-\s+.+$", ln):
            adr_ref_count += 1
        continue

    if section == "warnings":
        if re.match(r"^\s{2}-\s", ln):
            if in_warning:
                warning_open_count += validate_warning(warning_idx, warning)
            warning_idx += 1
            in_warning = True
            warning = {}
            m_inline = re.match(r"^\s{2}-\s*([A-Za-z_][A-Za-z0-9_]*)\s*:\s*(.*)$", ln)
            if m_inline:
                warning[m_inline.group(1)] = (m_inline.group(2) or "").strip()
            continue
        m_warn = re.match(r"^\s{4}([A-Za-z_][A-Za-z0-9_]*)\s*:\s*(.*)$", ln)
        if in_warning and m_warn:
            warning[m_warn.group(1)] = (m_warn.group(2) or "").strip()
        continue

    if section == "handoffs":
        if re.match(r"^\s{2}-\s", ln):
            if in_handoff:
                validate_handoff(handoff_idx, handoff_keys)
            handoff_idx += 1
            in_handoff = True
            handoff_keys = set()
            m_inline = re.match(r"^\s{2}-\s*([A-Za-z_][A-Za-z0-9_]*)\s*:\s*(.+)$", ln)
            if m_inline:
                hk = m_inline.group(1)
                hv = m_inline.group(2).strip()
                handoff_keys.add(hk)
                if hk == "from":
                    handoff_from_values.append(hv)
                if hk == "to":
                    handoff_to_values.append(hv)
                if hk == "memo":
                    handoff_memo_values.append(hv)
            continue
        m_h = re.match(r"^\s{4}([A-Za-z_][A-Za-z0-9_]*)\s*:\s*(.+)$", ln)
        if in_handoff and m_h:
            hk = m_h.group(1)
            hv = m_h.group(2).strip()
            handoff_keys.add(hk)
            if hk == "from":
                handoff_from_values.append(hv)
            if hk == "to":
                handoff_to_values.append(hv)
            if hk == "memo":
                handoff_memo_values.append(hv)
        continue

if section == "handoffs" and in_handoff:
    validate_handoff(handoff_idx, handoff_keys)
if section == "warnings" and in_warning:
    warning_open_count += validate_warning(warning_idx, warning)

if status and status not in allowed_status:
    errors.append(f"status invalid: '{status}'")

for k in sorted(required_target_stack):
    if k not in target_stack or not target_stack[k]:
        errors.append(f"missing required target_stack key: {k}")

for k in sorted(required_flags):
    if k not in flags:
        errors.append(f"missing required local_flags key: {k}")

all_handoff_roles = set(handoff_from_values + handoff_to_values)
has_code_critic = "qa-review-guild/code-critic" in all_handoff_roles
has_test_arch = "qa-review-guild/test-architect" in all_handoff_roles
has_removed_reviewer_role = assignee == removed_reviewer_role or removed_reviewer_role in all_handoff_roles
has_backend_security = assignee == backend_security_role or backend_security_role in all_handoff_roles
has_ux_specialist = assignee == ux_specialist_role or ux_specialist_role in all_handoff_roles
has_tech_specialist = assignee.startswith(tech_prefix) or any(r.startswith(tech_prefix) for r in all_handoff_roles)
has_research_role = assignee in research_roles or any(r in research_roles for r in all_handoff_roles)
has_declaration_evidence = any(declaration_pattern.match(memo) for memo in handoff_memo_values)
invalid_declarations = [memo for memo in handoff_memo_values if memo.startswith("DECLARATION") and not declaration_pattern.match(memo)]
has_improvement_evidence = bool(improvement_pattern.search(notes)) or any(
    bool(improvement_pattern.search(memo)) for memo in handoff_memo_values
)
invalid_improvement_entries = [memo for memo in handoff_memo_values if "IMPROVEMENT_PROPOSAL" in memo and not improvement_pattern.search(memo)]
if "IMPROVEMENT_PROPOSAL" in notes and not improvement_pattern.search(notes):
    invalid_improvement_entries.append("notes")
needs_improvement_proposal = status == "blocked" or (warning_open_count > 0 and status in {"blocked", "in_review", "done"})

if invalid_declarations:
    errors.append("handoff memo contains invalid DECLARATION format")

if invalid_improvement_entries:
    errors.append(
        "IMPROVEMENT_PROPOSAL format is invalid. expected: "
        "IMPROVEMENT_PROPOSAL type=<process|role|tool|rule|cleanup> "
        "priority=<high|medium|low> owner=coordinator summary=<text>"
    )

if status in statuses_require_declaration and not has_declaration_evidence:
    errors.append(
        f"task '{task_id or 'N/A'}' with status '{status}' requires at least one handoff memo declaration"
    )

if needs_improvement_proposal and not has_improvement_evidence:
    errors.append(
        f"task '{task_id or 'N/A'}' requires IMPROVEMENT_PROPOSAL evidence "
        "when blocked or unresolved warnings are present"
    )

if has_removed_reviewer_role:
    errors.append("frontend/code-reviewer is removed and cannot be assigned or used in handoffs; use qa-review-guild/code-critic")

if status == "done" and warning_open_count > 0:
    errors.append("task cannot be done while warnings.status=open exists")

if status == "done" and flags.get("qa_review_required") == "true":
    if not (assignee in qa_roles or (has_code_critic and has_test_arch)):
        errors.append("qa_review_required=true requires code-critic and test-architect evidence before done")

if status == "done" and flags.get("backend_security_required") == "true" and not has_backend_security:
    errors.append("backend_security_required=true requires backend/security-expert evidence before done")

if status == "done" and flags.get("ux_review_required") == "true" and not has_ux_specialist:
    errors.append("ux_review_required=true requires frontend/ux-specialist evidence before done")

if status == "done" and flags.get("tech_specialist_required") == "true" and not has_tech_specialist:
    errors.append("tech_specialist_required=true requires tech-specialist-guild evidence before done")

if status == "done" and flags.get("research_track_enabled") == "true":
    if "poc_result" not in notes:
        errors.append("research_track_enabled=true requires notes to include 'poc_result' before done")
    if adr_ref_count < 1:
        errors.append("research_track_enabled=true requires adr_refs before done")
    if not has_research_role:
        errors.append("research_track_enabled=true requires trend-researcher/poc-agent evidence before done")

if errors:
    for e in errors:
        print(f"ERROR: {e}", file=sys.stderr)
    sys.exit(1)

print(f"task state is valid: {task_path}")
sys.exit(0)
PY
