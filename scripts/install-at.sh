#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo_root="$(cd "$script_dir/.." && pwd)"
source_at="$repo_root/at"
source_agentteams="$repo_root/agentteams"
target_dir="${HOME}/.local/bin"
target_at="${target_dir}/at"
target_agentteams="${target_dir}/agentteams"

if [[ ! -f "$source_at" ]]; then
  echo "ERROR: missing launcher: $source_at" >&2
  exit 1
fi
if [[ ! -f "$source_agentteams" ]]; then
  echo "ERROR: missing launcher: $source_agentteams" >&2
  exit 1
fi

mkdir -p "$target_dir"

if [[ -L "$target_at" || -f "$target_at" ]]; then
  rm -f "$target_at"
fi
if [[ -L "$target_agentteams" || -f "$target_agentteams" ]]; then
  rm -f "$target_agentteams"
fi

ln -s "$source_at" "$target_at"
ln -s "$source_agentteams" "$target_agentteams"

echo "Installed: $target_at -> $source_at"
echo "Installed: $target_agentteams -> $source_agentteams"

case ":$PATH:" in
  *":$target_dir:"*)
    echo "PATH already contains $target_dir"
    ;;
  *)
    echo "PATH does not include $target_dir"
    echo "Run one of the following and re-open shell:"
    echo "  echo 'export PATH=\"$target_dir:\$PATH\"' >> ~/.bashrc && source ~/.bashrc"
    echo "  echo 'export PATH=\"$target_dir:\$PATH\"' >> ~/.zshrc && source ~/.zshrc"
    ;;
esac

resolved_at="$(command -v at || true)"
if [[ -n "$resolved_at" && "$resolved_at" != "$target_at" ]]; then
  echo "WARN: 'at' currently resolves to: $resolved_at"
  echo "To prioritize AgentTeams launcher, prepend $target_dir in PATH."
fi

resolved_agentteams="$(command -v agentteams || true)"
if [[ -n "$resolved_agentteams" && "$resolved_agentteams" != "$target_agentteams" ]]; then
  echo "WARN: 'agentteams' currently resolves to: $resolved_agentteams"
  echo "To prioritize AgentTeams launcher, prepend $target_dir in PATH."
fi

echo "Try: agentteams init"
echo "Compat: at init"
