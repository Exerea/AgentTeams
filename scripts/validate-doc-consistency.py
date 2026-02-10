#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
import sys

REQUIRED_FILES = [
    Path("README.md"),
    Path("docs/guides/architecture.md"),
    Path("docs/guides/request-routing-scenarios.md"),
    Path("docs/guides/takt-orchestration.md"),
]

REQUIRED_README_TOKENS = [
    "agentteams init",
    "agentteams doctor",
    "agentteams orchestrate",
    "agentteams audit",
    "agentteams audit --scope fleet",
    ".takt/tasks",
    ".takt/control-plane",
    "TAKT",
]

FORBIDDEN_TOKEN = ".co" + "dex"
SCAN_PATHS = [
    Path("README.md"),
    Path("docs/guides"),
    Path("scripts"),
]


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def main() -> int:
    repo_root = Path(__file__).resolve().parent.parent
    errors: list[str] = []

    for rel in REQUIRED_FILES:
        full = repo_root / rel
        if not full.exists():
            errors.append(f"missing required document: {rel.as_posix()}")

    readme = repo_root / "README.md"
    if readme.exists():
        content = read_text(readme)
        for token in REQUIRED_README_TOKENS:
            if token not in content:
                errors.append(f"README.md missing token: {token}")

    for rel in SCAN_PATHS:
        full = repo_root / rel
        if not full.exists():
            continue

        files: list[Path] = []
        if full.is_file():
            files = [full]
        else:
            files = [p for p in full.rglob("*") if p.is_file()]

        for file in files:
            if file.suffix.lower() in {".png", ".jpg", ".jpeg", ".gif", ".exe", ".tar", ".gz", ".zip", ".pyc"}:
                continue
            text = read_text(file)
            if FORBIDDEN_TOKEN in text:
                relpath = file.relative_to(repo_root).as_posix()
                errors.append(f"forbidden token '{FORBIDDEN_TOKEN}' found in {relpath}")

    if errors:
        for err in errors:
            print(f"ERROR [DOC_CONSISTENCY_INVALID] {err}")
        return 1

    print("OK [DOC_CONSISTENCY_VALID]")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
