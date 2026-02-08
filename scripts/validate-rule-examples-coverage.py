#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
import re
import sys


REQUIRED_SECTION_HEADINGS = [
    "### Rule",
    "### Intent",
    "### Good Example",
    "### Bad Example",
    "### Why Bad",
    "### Detection",
    "### Related Files",
]


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8").lstrip("\ufeff")


def extract_non_negotiable_rules(agents_text: str) -> list[str]:
    pattern = re.compile(r"^(?:##\s*)?\d+\.\s+")
    return [ln.strip() for ln in agents_text.splitlines() if pattern.match(ln.strip())]


def extract_rule_sections(examples_text: str) -> dict[str, str]:
    lines = examples_text.splitlines()
    section_start_indices: list[tuple[str, int]] = []

    for idx, ln in enumerate(lines):
        m = re.match(r"^##\s+(R-\d{2})\b", ln.strip())
        if m:
            section_start_indices.append((m.group(1), idx))

    sections: dict[str, str] = {}
    for i, (section_id, start_idx) in enumerate(section_start_indices):
        end_idx = section_start_indices[i + 1][1] if i + 1 < len(section_start_indices) else len(lines)
        sections[section_id] = "\n".join(lines[start_idx:end_idx])
    return sections


def content_between(section_text: str, heading: str, next_heading: str | None) -> str:
    pattern = re.escape(heading) + r"\n"
    start = re.search(pattern, section_text)
    if not start:
        return ""
    begin = start.end()

    if next_heading:
        next_pattern = r"\n" + re.escape(next_heading) + r"\n"
        end_m = re.search(next_pattern, section_text[begin:])
        if end_m:
            return section_text[begin : begin + end_m.start()].strip()
    return section_text[begin:].strip()


def main() -> int:
    repo_root = Path(__file__).resolve().parent.parent
    agents_path = repo_root / ".codex" / "AGENTS.md"
    examples_path = repo_root / "docs" / "guides" / "rule-examples.md"

    errors: list[str] = []

    if not agents_path.exists():
        errors.append(f"missing file: {agents_path.as_posix()}")
    if not examples_path.exists():
        errors.append(f"missing file: {examples_path.as_posix()}")
    if errors:
        for err in errors:
            print(f"ERROR: {err}", file=sys.stderr)
        return 1

    agents_text = read_text(agents_path)
    examples_text = read_text(examples_path)

    rules = extract_non_negotiable_rules(agents_text)
    if len(rules) != 23:
        errors.append(f"expected 23 non-negotiable rules in .codex/AGENTS.md (found {len(rules)})")

    expected_ids = [f"R-{i:02d}" for i in range(1, 24)]
    sections = extract_rule_sections(examples_text)
    found_ids = sorted(sections.keys())

    missing_ids = [sid for sid in expected_ids if sid not in sections]
    extra_ids = [sid for sid in found_ids if sid not in expected_ids]
    if missing_ids:
        errors.append(f"missing rule sections: {', '.join(missing_ids)}")
    if extra_ids:
        errors.append(f"unexpected rule sections: {', '.join(extra_ids)}")

    for sid in expected_ids:
        sec = sections.get(sid, "")
        if not sec:
            continue

        for i, heading in enumerate(REQUIRED_SECTION_HEADINGS):
            if heading not in sec:
                errors.append(f"{sid} missing heading: {heading}")
                continue
            next_heading = REQUIRED_SECTION_HEADINGS[i + 1] if i + 1 < len(REQUIRED_SECTION_HEADINGS) else None
            content = content_between(sec, heading, next_heading)
            if not content:
                errors.append(f"{sid} heading has empty content: {heading}")

        detection_content = content_between(sec, "### Detection", "### Related Files")
        if detection_content and "manual review" not in detection_content.lower():
            has_validate = re.search(r"validate-[a-z0-9\-]+", detection_content) is not None
            has_detect = "detect-role-gaps" in detection_content
            if not (has_validate or has_detect):
                errors.append(f"{sid} Detection must mention a validator, detect-role-gaps, or 'manual review'")

        related_files_content = content_between(sec, "### Related Files", None)
        if related_files_content and "`" not in related_files_content:
            errors.append(f"{sid} Related Files must include at least one backticked file path")

    if errors:
        for err in errors:
            print(f"ERROR: {err}", file=sys.stderr)
        return 1

    print("rule examples coverage is valid")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
