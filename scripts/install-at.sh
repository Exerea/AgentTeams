#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo_root="$(cd "$script_dir/.." && pwd)"
source_at="$repo_root/at"
target_dir="${HOME}/.local/bin"
target_at="${target_dir}/at"

if [[ ! -f "$source_at" ]]; then
  echo "ERROR: missing launcher: $source_at" >&2
  exit 1
fi

mkdir -p "$target_dir"

if [[ -L "$target_at" || -f "$target_at" ]]; then
  rm -f "$target_at"
fi

ln -s "$source_at" "$target_at"

echo "Installed: $target_at -> $source_at"

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

echo "Try: at init"
