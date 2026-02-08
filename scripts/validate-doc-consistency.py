#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
import sys


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8").lstrip("\ufeff")


def require_all(src: str, needles: list[str], path: Path, errors: list[str]) -> None:
    for needle in needles:
        if needle not in src:
            errors.append(f"{path.as_posix()} must include '{needle}'")


def require_none(src: str, needles: list[str], path: Path, errors: list[str]) -> None:
    for needle in needles:
        if needle in src:
            errors.append(f"{path.as_posix()} must not include '{needle}'")


def main() -> int:
    repo_root = Path(__file__).resolve().parent.parent
    files = {
        "agents": repo_root / ".codex" / "AGENTS.md",
        "coordinator": repo_root / ".codex" / "coordinator.md",
        "common_ops": repo_root / "shared" / "skills" / "common-ops.md",
        "spec": repo_root / "docs" / "specs" / "0001-agentteams-as-is-operations.md",
        "readme": repo_root / "README.md",
        "protocol": repo_root / "docs" / "guides" / "communication-protocol.md",
        "scenarios": repo_root / "docs" / "guides" / "request-routing-scenarios.md",
        "rule_examples": repo_root / "docs" / "guides" / "rule-examples.md",
        "workflow": repo_root / ".github" / "workflows" / "agentteams-validate.yml",
        "role_gap_rules": repo_root / ".codex" / "role-gap-rules.yaml",
        "role_gap_index": repo_root / ".codex" / "states" / "_role-gap-index.yaml",
        "deprecation_rules": repo_root / ".codex" / "deprecation-rules.yaml",
        "self_update_ps1": repo_root / "scripts" / "self-update-agentteams.ps1",
        "self_update_sh": repo_root / "scripts" / "self-update-agentteams.sh",
        "self_update_evidence": repo_root / "scripts" / "validate-self-update-evidence.py",
    }

    errors: list[str] = []
    content: dict[str, str] = {}
    for key, path in files.items():
        if not path.exists():
            errors.append(f"missing required file: {path.as_posix()}")
            continue
        content[key] = read_text(path)

    if errors:
        for err in errors:
            print(f"ERROR: {err}", file=sys.stderr)
        return 1

    # Core flags consistency
    for key in ("agents", "coordinator", "spec"):
        src = content[key]
        path = files[key]
        require_all(
            src,
            ["backend_security_required", "ux_review_required"],
            path,
            errors,
        )

    # Gate names consistency (coordinator/spec)
    required_gates = [
        "ADR Gate",
        "Documentation Sync Gate",
        "Protocol Gate",
        "Tech Gate",
        "QA Gate",
        "Backend Security Gate",
        "UX Gate",
        "Research Gate",
        "Secret Scan Gate",
        "Role Gap Review Gate",
    ]
    for gate in required_gates:
        if gate not in content["coordinator"]:
            errors.append(f"{files['coordinator'].as_posix()} missing gate heading: {gate}")
        if gate not in content["spec"]:
            errors.append(f"{files['spec'].as_posix()} missing gate heading: {gate}")

    # Ownership rules
    for key in ("agents", "coordinator", "spec"):
        src = content[key]
        path = files[key]
        require_all(src, ["task_file_path", "_index.yaml"], path, errors)

    # Declaration protocol references
    declaration_refs = {
        "agents": ["DECLARATION", "team=", "role=", "task=", "action="],
        "coordinator": ["DECLARATION", "team=", "role=", "task=", "action="],
        "common_ops": ["DECLARATION", "team=", "role=", "task=", "action="],
        "spec": ["DECLARATION", "team=", "role=", "task=", "action="],
        "readme": ["DECLARATION", "team=", "role=", "task=", "action="],
        "protocol": ["DECLARATION", "team=", "role=", "task=", "action="],
        "scenarios": ["DECLARATION", "team=", "role=", "task=", "action="],
    }
    for key, needles in declaration_refs.items():
        require_all(content[key], needles, files[key], errors)

    # Roleplay declaration vocabulary consistency
    roleplay_refs = {
        "agents": ["殿様", "家老", "足軽"],
        "coordinator": ["殿様", "家老", "足軽"],
        "common_ops": ["殿様", "家老", "足軽"],
        "spec": ["殿様", "家老", "足軽"],
        "readme": ["殿様", "家老", "足軽"],
        "protocol": ["殿様", "家老", "足軽"],
        "scenarios": ["殿様", "家老", "足軽"],
    }
    for key, needles in roleplay_refs.items():
        require_all(content[key], needles, files[key], errors)

    # Roleplay declaration must be title-first, not task-id-only
    title_first_refs = {
        "agents": ["task_id", "「<task_title>」"],
        "coordinator": ["「<task_title>」", "task_id"],
        "common_ops": ["「<task_title>」", "task_id"],
        "spec": ["「<task_title>」", "task_id"],
        "readme": ["「<task_title>」", "task_id"],
        "protocol": ["「<task_title>」", "task_id"],
        "scenarios": ["「<task_title>」", "task_id"],
    }
    for key, needles in title_first_refs.items():
        require_all(content[key], needles, files[key], errors)

    # Proactive recommendation rule consistency
    proactive_refs = {
        "agents": ["必要性判断", "進言"],
        "coordinator": ["必要性判断", "進言"],
        "common_ops": ["必要性判断", "進言"],
        "spec": ["必要性判断", "進言"],
        "readme": ["必要性判断", "進言"],
        "protocol": ["必要性判断", "進言"],
        "scenarios": ["必要性判断", "進言"],
        "rule_examples": ["必要性判断", "進言"],
    }
    for key, needles in proactive_refs.items():
        require_all(content[key], needles, files[key], errors)

    # MCP policy consistency
    mcp_refs = {
        "coordinator": ["DevTools MCP", "mcp_evidence"],
        "common_ops": ["mcp_evidence"],
        "spec": ["MCP運用契約", "DevTools MCP", "mcp_evidence"],
        "readme": ["MCP運用", "DevTools MCP", "mcp_evidence"],
        "protocol": ["MCP Usage Pattern", "DevTools MCP", "mcp_evidence"],
        "scenarios": ["mcp_evidence"],
        "rule_examples": ["DevTools MCP"],
    }
    for key, needles in mcp_refs.items():
        require_all(content[key], needles, files[key], errors)

    # Secret scan references
    secret_refs = {
        "agents": ["validate-secrets"],
        "coordinator": ["validate-secrets", "Secret Scan Gate"],
        "spec": ["validate-secrets.ps1", "validate-secrets.sh", "Secret Scan Gate"],
        "readme": ["validate-secrets.ps1", "validate-secrets.sh", "validate-secrets-linux"],
        "workflow": ["validate-secrets-linux"],
    }
    for key, needles in secret_refs.items():
        require_all(content[key], needles, files[key], errors)

    # Role gap references
    role_gap_refs = {
        "agents": ["role gap", "_role-gap-index.yaml", "detect-role-gaps"],
        "coordinator": ["Role Gap Triage Flow", "_role-gap-index.yaml", "detect-role-gaps"],
        "spec": ["detect-role-gaps.py", "validate-role-gap-review.py", "_role-gap-index.yaml", "Role Gap Review Gate"],
        "readme": ["detect-role-gaps", "validate-role-gap-review", "_role-gap-index.yaml"],
        "workflow": ["detect-role-gaps", "validate-role-gap-review"],
        "role_gap_rules": ["recency_days", "open_review_max_days", "ux_psychology_keywords"],
        "role_gap_index": ["version", "candidates"],
    }
    for key, needles in role_gap_refs.items():
        src = content[key]
        src_lower = src.lower()
        path = files[key]
        for needle in needles:
            if needle.lower() not in src_lower:
                errors.append(f"{path.as_posix()} must include '{needle}'")

    # Rule examples references
    rule_example_refs = {
        "agents": ["docs/guides/rule-examples.md"],
        "coordinator": ["docs/guides/rule-examples.md"],
        "spec": ["docs/guides/rule-examples.md"],
        "readme": ["docs/guides/rule-examples.md"],
        "scenarios": ["docs/guides/rule-examples.md"],
        "workflow": ["validate-rule-examples-coverage"],
        "rule_examples": ["## R-01", "## R-23", "### Good Example", "### Bad Example"],
    }
    for key, needles in rule_example_refs.items():
        require_all(content[key], needles, files[key], errors)

    # Reviewer ownership consistency
    reviewer_ownership_refs = {
        "agents": ["frontend/code-reviewer", "廃止済み", "qa-review-guild/code-critic"],
        "coordinator": ["frontend/code-reviewer", "新規割当禁止", "qa-review-guild/code-critic"],
        "readme": ["frontend/code-reviewer", "廃止済み", "qa-review-guild/code-critic"],
        "spec": ["frontend/code-reviewer", "qa-review-guild/code-critic"],
        "scenarios": ["frontend/code-reviewer", "qa-review-guild/code-critic"],
        "rule_examples": ["frontend/code-reviewer", "qa-review-guild/code-critic"],
    }
    for key, needles in reviewer_ownership_refs.items():
        require_all(content[key], needles, files[key], errors)

    # Improvement proposal protocol consistency
    improvement_refs = {
        "agents": ["IMPROVEMENT_PROPOSAL", "type=", "priority=", "owner=coordinator", "summary="],
        "coordinator": ["IMPROVEMENT_PROPOSAL", "type=", "priority=", "owner=coordinator", "summary="],
        "common_ops": ["IMPROVEMENT_PROPOSAL", "type=", "priority=", "owner=coordinator", "summary="],
        "readme": ["IMPROVEMENT_PROPOSAL", "type=", "priority=", "owner=coordinator", "summary="],
        "spec": ["IMPROVEMENT_PROPOSAL", "type=", "priority=", "owner=coordinator", "summary="],
        "protocol": ["IMPROVEMENT_PROPOSAL", "type=", "priority=", "owner=coordinator", "summary="],
        "scenarios": ["IMPROVEMENT_PROPOSAL", "type=", "priority=", "owner=coordinator", "summary="],
        "rule_examples": ["IMPROVEMENT_PROPOSAL", "type=", "priority=", "owner=coordinator", "summary="],
    }
    for key, needles in improvement_refs.items():
        require_all(content[key], needles, files[key], errors)

    # Deprecation cleanup consistency
    deprecation_refs = {
        "agents": ["validate-deprecated-assets.py", "deprecation-rules.yaml"],
        "coordinator": ["validate-deprecated-assets.py", "deprecation-rules.yaml"],
        "readme": ["validate-deprecated-assets.py", "deprecation-rules.yaml"],
        "spec": ["validate-deprecated-assets.py", "deprecation-rules.yaml"],
        "workflow": ["validate-deprecated-assets"],
        "deprecation_rules": ["retired_roles", "retired_paths"],
    }
    for key, needles in deprecation_refs.items():
        require_all(content[key], needles, files[key], errors)

    # Self-update policy consistency
    self_update_refs = {
        "agents": ["self-update-agentteams.ps1", "self-update-agentteams.sh"],
        "coordinator": ["self-update-agentteams.ps1", "self-update-agentteams.sh"],
        "common_ops": ["self-update-agentteams.ps1", "self-update-agentteams.sh"],
        "readme": ["self-update-agentteams.ps1", "self-update-agentteams.sh", "validate-repo"],
        "spec": ["self-update-agentteams.ps1", "self-update-agentteams.sh", "validate-repo"],
        "protocol": ["self_update_commit_push"],
        "self_update_ps1": ["TaskFile", "validate-task-state.ps1", "validate-self-update-evidence.py"],
        "self_update_sh": ["--task-file", "validate-task-state.sh", "validate-self-update-evidence.py"],
        "self_update_evidence": [
            "SELF_UPDATE_TASK_REQUIRED",
            "SELF_UPDATE_TASK_PATH_INVALID",
            "SELF_UPDATE_TASK_STATUS_INVALID",
            "SELF_UPDATE_TASK_SCOPE_INVALID",
            "SELF_UPDATE_LOG_NOT_STAGED",
            "SELF_UPDATE_LOG_KOUJO_MISSING",
            "SELF_UPDATE_LOG_DECLARATION_MISSING",
            "SELF_UPDATE_LOG_DECLARATION_TASK_MISMATCH",
        ],
    }
    for key, needles in self_update_refs.items():
        require_all(content[key], needles, files[key], errors)

    self_update_task_file_doc_refs = {
        "readme": ["--task-file", "-TaskFile", "self_update_commit_push"],
        "coordinator": ["--task-file", "-TaskFile", "self_update_commit_push", "logs/e2e-ai-log.md"],
        "spec": ["--task-file", "-TaskFile", "self_update_commit_push", "logs/e2e-ai-log.md"],
        "protocol": ["self_update_commit_push", "logs/e2e-ai-log.md"],
    }
    for key, needles in self_update_task_file_doc_refs.items():
        require_all(content[key], needles, files[key], errors)

    self_update_skip_validate_forbidden = {
        "readme": ["--skip-validate", "-SkipValidate"],
        "coordinator": ["--skip-validate", "-SkipValidate"],
        "spec": ["--skip-validate", "-SkipValidate"],
        "protocol": ["--skip-validate", "-SkipValidate"],
    }
    for key, needles in self_update_skip_validate_forbidden.items():
        require_none(content[key], needles, files[key], errors)

    # Spec heading check
    if "Task 契約（v2.8）" not in content["spec"]:
        errors.append(f"{files['spec'].as_posix()} must include heading: Task 契約（v2.8）")

    if errors:
        for err in errors:
            print(f"ERROR: {err}", file=sys.stderr)
        return 1

    print("documentation consistency is valid")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
