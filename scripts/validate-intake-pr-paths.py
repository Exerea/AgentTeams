#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path
import subprocess
import sys

ALLOWED_PREFIX = ".takt/control-plane/intake/"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate intake PR path restrictions")
    parser.add_argument("--base-ref", default="", help="git base ref (commit/branch)")
    parser.add_argument("--head-ref", default="HEAD", help="git head ref (commit/branch)")
    parser.add_argument(
        "--allow-no-intake-changes",
        action="store_true",
        help="allow PRs that do not touch intake paths",
    )
    return parser.parse_args()


def git_changed_files(base_ref: str, head_ref: str) -> list[str]:
    if not base_ref:
        return []
    proc = subprocess.run(
        ["git", "diff", "--name-only", f"{base_ref}...{head_ref}"],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if proc.returncode != 0:
        raise RuntimeError(proc.stdout.strip() or "git diff failed")
    return [line.strip().replace("\\", "/") for line in proc.stdout.splitlines() if line.strip()]


def main() -> int:
    args = parse_args()

    if not args.base_ref:
        print("OK [INTAKE_PATH_GUARD_SKIPPED] base ref is empty")
        return 0

    try:
        changed = git_changed_files(args.base_ref, args.head_ref)
    except RuntimeError as exc:
        print(f"ERROR [INTAKE_PATH_GUARD_FAILED] {exc}")
        return 1

    if not changed:
        print("OK [INTAKE_PATH_GUARD_SKIPPED] no changed files")
        return 0

    intake_changed = [f for f in changed if f.startswith(ALLOWED_PREFIX)]
    non_intake_changed = [f for f in changed if not f.startswith(ALLOWED_PREFIX)]

    if intake_changed and non_intake_changed:
        print("ERROR [INTAKE_PATH_GUARD_FAILED] intake PR must only modify intake paths")
        for path in non_intake_changed:
            print(f"ERROR [INTAKE_PATH_GUARD_FAILED] disallowed path: {path}")
        return 1

    if not intake_changed and not args.allow_no_intake_changes:
        print("ERROR [INTAKE_PATH_GUARD_FAILED] no intake path changes detected")
        return 1

    if intake_changed:
        print(f"OK [INTAKE_PATH_GUARD_VALID] intake_files={len(intake_changed)}")
        return 0

    print("OK [INTAKE_PATH_GUARD_VALID] no intake changes (allowed)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
