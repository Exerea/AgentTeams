#!/usr/bin/env bash
set -euo pipefail

message="chore(agentteams): self-update by coordinator"
remote="origin"
branch=""
task_file=""
no_push=0

print_usage() {
  echo "Usage: self-update-agentteams.sh --task-file <path> [--message <msg>] [--remote <name>] [--branch <name>] [--no-push]" >&2
}

fail() {
  local code="$1"
  local message_text="$2"
  local next_command="${3:-}"
  echo "ERROR [$code] $message_text" >&2
  if [[ -n "$next_command" ]]; then
    echo "Next: $next_command" >&2
  fi
  exit 1
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --task-file)
      [[ $# -ge 2 ]] || fail "SELF_UPDATE_TASK_REQUIRED" "--task-file requires a value" "bash ./scripts/self-update-agentteams.sh --task-file ./.codex/states/TASK-xxxxx-your-task.yaml --no-push"
      task_file="$2"
      shift 2
      ;;
    --message)
      [[ $# -ge 2 ]] || fail "SELF_UPDATE_TASK_PATH_INVALID" "--message requires a value"
      message="$2"
      shift 2
      ;;
    --remote)
      [[ $# -ge 2 ]] || fail "SELF_UPDATE_TASK_PATH_INVALID" "--remote requires a value"
      remote="$2"
      shift 2
      ;;
    --branch)
      [[ $# -ge 2 ]] || fail "SELF_UPDATE_TASK_PATH_INVALID" "--branch requires a value"
      branch="$2"
      shift 2
      ;;
    --skip-validate)
      fail "SELF_UPDATE_TASK_PATH_INVALID" "--skip-validate is removed. self-update always runs validation." "bash ./scripts/self-update-agentteams.sh --task-file ./.codex/states/TASK-xxxxx-your-task.yaml --no-push"
      ;;
    --no-push)
      no_push=1
      shift
      ;;
    --help|-h)
      print_usage
      exit 0
      ;;
    *)
      print_usage
      fail "SELF_UPDATE_TASK_PATH_INVALID" "unknown argument: $1"
      ;;
  esac
done

if [[ -z "$task_file" ]]; then
  print_usage
  fail "SELF_UPDATE_TASK_REQUIRED" "--task-file is required" "bash ./scripts/self-update-agentteams.sh --task-file ./.codex/states/TASK-xxxxx-your-task.yaml --no-push"
fi

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repo_root"

if [[ ! -f "$task_file" ]]; then
  fail "SELF_UPDATE_TASK_PATH_INVALID" "task file not found: $task_file"
fi

task_file_name="$(basename "$task_file")"
if [[ ! "$task_file_name" =~ ^TASK-[0-9]{5}-[a-z0-9]+(-[a-z0-9]+)*\.yaml$ ]]; then
  fail "SELF_UPDATE_TASK_PATH_INVALID" "task file name must follow TASK-xxxxx-slug.yaml: $task_file_name"
fi

git rev-parse --is-inside-work-tree >/dev/null

if [[ -z "$branch" ]]; then
  branch="$(git rev-parse --abbrev-ref HEAD)"
fi

if [[ "$branch" == "HEAD" ]]; then
  echo "ERROR: detached HEAD is not allowed for self-update. checkout a branch first." >&2
  exit 1
fi

git remote get-url "$remote" >/dev/null

if command -v powershell >/dev/null 2>&1; then
  powershell -NoProfile -ExecutionPolicy Bypass -File ./scripts/validate-repo.ps1
else
  bash ./scripts/validate-repo.sh
fi

if command -v powershell >/dev/null 2>&1; then
  powershell -NoProfile -ExecutionPolicy Bypass -File ./scripts/validate-task-state.ps1 -Path "$task_file"
else
  bash ./scripts/validate-task-state.sh "$task_file"
fi

git add -A

if git diff --cached --quiet; then
  echo "No staged changes detected. Nothing to commit."
  exit 0
fi

if command -v python3 >/dev/null 2>&1; then
  py_bin="python3"
elif command -v python >/dev/null 2>&1; then
  py_bin="python"
else
  fail "SELF_UPDATE_TASK_PATH_INVALID" "python runtime not found (python3/python required)"
fi

"$py_bin" ./scripts/validate-self-update-evidence.py --task-file "$task_file" --log logs/e2e-ai-log.md

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
