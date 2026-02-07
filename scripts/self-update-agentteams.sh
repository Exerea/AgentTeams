#!/usr/bin/env bash
set -euo pipefail

message="chore(agentteams): self-update by coordinator"
remote="origin"
branch=""
skip_validate=0
no_push=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --message)
      [[ $# -ge 2 ]] || { echo "ERROR: --message requires a value" >&2; exit 1; }
      message="$2"
      shift 2
      ;;
    --remote)
      [[ $# -ge 2 ]] || { echo "ERROR: --remote requires a value" >&2; exit 1; }
      remote="$2"
      shift 2
      ;;
    --branch)
      [[ $# -ge 2 ]] || { echo "ERROR: --branch requires a value" >&2; exit 1; }
      branch="$2"
      shift 2
      ;;
    --skip-validate)
      skip_validate=1
      shift
      ;;
    --no-push)
      no_push=1
      shift
      ;;
    *)
      echo "ERROR: unknown argument: $1" >&2
      echo "Usage: self-update-agentteams.sh [--message <msg>] [--remote <name>] [--branch <name>] [--skip-validate] [--no-push]" >&2
      exit 1
      ;;
  esac
done

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repo_root"

git rev-parse --is-inside-work-tree >/dev/null

if [[ -z "$branch" ]]; then
  branch="$(git rev-parse --abbrev-ref HEAD)"
fi

if [[ "$branch" == "HEAD" ]]; then
  echo "ERROR: detached HEAD is not allowed for self-update. checkout a branch first." >&2
  exit 1
fi

git remote get-url "$remote" >/dev/null

if [[ "$skip_validate" -eq 0 ]]; then
  if command -v powershell >/dev/null 2>&1; then
    powershell -NoProfile -ExecutionPolicy Bypass -File ./scripts/validate-repo.ps1
  else
    bash ./scripts/validate-repo.sh
  fi
fi

git add -A

if git diff --cached --quiet; then
  echo "No staged changes detected. Nothing to commit."
  exit 0
fi

git commit -m "$message"
echo "Committed with message: $message"

if [[ "$no_push" -eq 1 ]]; then
  echo "NoPush mode enabled. Commit created locally only."
  exit 0
fi

if git rev-parse --abbrev-ref --symbolic-full-name '@{u}' >/dev/null 2>&1; then
  git push "$remote" "$branch"
else
  git push -u "$remote" "$branch"
fi

echo "Pushed to $remote/$branch"
