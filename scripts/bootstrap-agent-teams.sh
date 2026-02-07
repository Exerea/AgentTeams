#!/usr/bin/env bash
set -euo pipefail

target=""
force=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --target)
      if [[ $# -lt 2 ]]; then
        echo "ERROR: --target requires a path value." >&2
        echo "Usage: bootstrap-agent-teams.sh --target <path> [--force]" >&2
        exit 1
      fi
      target="$2"
      shift 2
      ;;
    --force)
      force=1
      shift
      ;;
    *)
      echo "ERROR: Unknown argument: $1" >&2
      echo "Usage: bootstrap-agent-teams.sh --target <path> [--force]" >&2
      exit 1
      ;;
  esac
done

if [[ -z "$target" ]]; then
  echo "ERROR: Missing required argument: --target <path>" >&2
  echo "Usage: bootstrap-agent-teams.sh --target <path> [--force]" >&2
  exit 1
fi

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
template_root="$(cd "$script_dir/.." && pwd)"
mkdir -p "$target"
target_root="$(cd "$target" && pwd)"

if [[ "$target_root" == "$template_root" ]]; then
  echo "ERROR: Target path must be different from template root." >&2
  exit 1
fi

paths_to_copy=(
  "AGENTS.md"
  "README.md"
  ".gitleaks.toml"
  ".github"
  ".codex"
  "docs"
  "shared"
  "scripts"
)

copied=0
skipped=0
overwritten=0

copy_entry() {
  local source_path="$1"
  local destination_path="$2"
  local source_name
  source_name="$(basename "$source_path")"

  if [[ "$source_name" == "__pycache__" || "$source_name" == *.pyc ]]; then
    return
  fi

  if [[ -d "$source_path" ]]; then
    mkdir -p "$destination_path"
    shopt -s dotglob nullglob
    local child
    for child in "$source_path"/*; do
      copy_entry "$child" "$destination_path/$(basename "$child")"
    done
    shopt -u dotglob nullglob
    return
  fi

  if [[ -e "$destination_path" ]]; then
    if [[ "$force" -eq 1 ]]; then
      cp "$source_path" "$destination_path"
      overwritten=$((overwritten + 1))
      echo "OVERWRITE $destination_path"
    else
      skipped=$((skipped + 1))
      echo "SKIP $destination_path"
    fi
  else
    mkdir -p "$(dirname "$destination_path")"
    cp "$source_path" "$destination_path"
    copied=$((copied + 1))
    echo "COPY $destination_path"
  fi
}

for relative_path in "${paths_to_copy[@]}"; do
  source_path="$template_root/$relative_path"
  destination_path="$target_root/$relative_path"

  if [[ ! -e "$source_path" ]]; then
    echo "WARN: Source path not found: $source_path" >&2
    continue
  fi

  copy_entry "$source_path" "$destination_path"
done

echo
echo "Completed bootstrap to: $target_root"
echo "Copied: $copied"
echo "Skipped: $skipped"
echo "Overwritten: $overwritten"
