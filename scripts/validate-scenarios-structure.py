#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
import re
import sys


SCENARIO_HEADING = re.compile(r"^## Scenario \d+:")
REQUIRED_SUBHEADINGS = [
    "### User Request",
    "### Coordinator Decomposition",
    "### Task File Blueprint",
    "### Handoff Timeline",
    "### Gate Checks",
    "### Completion Criteria",
    "### Validation Commands",
]


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8").lstrip("\ufeff")


def main() -> int:
    repo_root = Path(__file__).resolve().parent.parent
    scenario_path = repo_root / "docs" / "guides" / "request-routing-scenarios.md"

    if not scenario_path.exists():
        print(f"ERROR: missing file: {scenario_path.as_posix()}", file=sys.stderr)
        return 1

    text = read_text(scenario_path)
    lines = text.splitlines()

    errors: list[str] = []

    if "task_file_path" not in text:
        errors.append(f"{scenario_path.as_posix()} must include task_file_path rule")
    if "_index.yaml" not in text:
        errors.append(f"{scenario_path.as_posix()} must include _index.yaml ownership rule")

    indices = [idx for idx, line in enumerate(lines) if SCENARIO_HEADING.match(line)]
    if len(indices) != 6:
        errors.append(
            f"{scenario_path.as_posix()} must include exactly 6 scenarios (found {len(indices)})"
        )

    for i, start in enumerate(indices, 1):
        end = indices[i] if i < len(indices) else len(lines)
        block = "\n".join(lines[start:end])
        for heading in REQUIRED_SUBHEADINGS:
            if heading not in block:
                errors.append(f"Scenario {i} missing section: {heading}")

    if errors:
        for err in errors:
            print(f"ERROR: {err}", file=sys.stderr)
        return 1

    print("request routing scenarios structure is valid")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
