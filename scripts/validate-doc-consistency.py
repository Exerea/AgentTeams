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


def main() -> int:
    repo_root = Path(__file__).resolve().parent.parent
    files = {
        "agents": repo_root / ".codex" / "AGENTS.md",
        "coordinator": repo_root / ".codex" / "coordinator.md",
        "spec": repo_root / "docs" / "specs" / "0001-agentteams-as-is-operations.md",
        "readme": repo_root / "README.md",
        "workflow": repo_root / ".github" / "workflows" / "agentteams-validate.yml",
        "role_gap_rules": repo_root / ".codex" / "role-gap-rules.yaml",
        "role_gap_index": repo_root / ".codex" / "states" / "_role-gap-index.yaml",
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

    # Spec heading check
    if "Task 契約（v2.6a）" not in content["spec"]:
        errors.append(f"{files['spec'].as_posix()} must include heading: Task 契約（v2.6a）")

    if errors:
        for err in errors:
            print(f"ERROR: {err}", file=sys.stderr)
        return 1

    print("documentation consistency is valid")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

