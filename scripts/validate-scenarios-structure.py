#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
import sys

REQUIRED_HEADINGS = [
    "## Scenario 1",
    "## Scenario 2",
    "## Scenario 3",
    "## Scenario 4",
]

REQUIRED_TOKENS = [
    "agentteams orchestrate",
    ".takt/tasks/",
    "routing.required_teams",
    "capability_tags",
    "qa-review-guild",
    "team leaders -> QA -> overall leader",
]


def main() -> int:
    repo_root = Path(__file__).resolve().parent.parent
    target = repo_root / "docs" / "guides" / "request-routing-scenarios.md"

    if not target.exists():
        print(f"ERROR [SCENARIO_DOC_MISSING] {target.as_posix()}")
        return 1

    content = target.read_text(encoding="utf-8")

    errors: list[str] = []
    for heading in REQUIRED_HEADINGS:
        if heading not in content:
            errors.append(f"missing heading: {heading}")

    for token in REQUIRED_TOKENS:
        if token not in content:
            errors.append(f"missing token: {token}")

    if errors:
        for err in errors:
            print(f"ERROR [SCENARIO_STRUCTURE_INVALID] {err}")
        return 1

    print("OK [SCENARIO_STRUCTURE_VALID]")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
