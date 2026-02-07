#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repo_root"

gitleaks_version="${GITLEAKS_VERSION:-8.24.2}"

resolve_gitleaks_bin() {
  if command -v gitleaks >/dev/null 2>&1; then
    command -v gitleaks
    return 0
  fi

  local tool_dir="$repo_root/.tools/gitleaks"
  local local_bin="$tool_dir/gitleaks"
  if [[ -x "$local_bin" ]]; then
    echo "$local_bin"
    return 0
  fi

  local os
  case "$(uname -s)" in
    Linux) os="linux" ;;
    Darwin) os="darwin" ;;
    *)
      echo "ERROR: unsupported OS for gitleaks bootstrap: $(uname -s)" >&2
      return 1
      ;;
  esac

  local arch
  case "$(uname -m)" in
    x86_64|amd64) arch="x64" ;;
    aarch64|arm64) arch="arm64" ;;
    *)
      echo "ERROR: unsupported architecture for gitleaks bootstrap: $(uname -m)" >&2
      return 1
      ;;
  esac

  if ! command -v curl >/dev/null 2>&1 && ! command -v wget >/dev/null 2>&1; then
    echo "ERROR: curl or wget is required to download gitleaks." >&2
    return 1
  fi

  mkdir -p "$tool_dir"

  local asset="gitleaks_${gitleaks_version}_${os}_${arch}.tar.gz"
  local url="https://github.com/gitleaks/gitleaks/releases/download/v${gitleaks_version}/${asset}"
  local tmp_dir
  tmp_dir="$(mktemp -d)"

  echo "gitleaks command not found. Downloading v${gitleaks_version} (${os}/${arch}) ..." >&2
  if command -v curl >/dev/null 2>&1; then
    curl -fsSL "$url" -o "$tmp_dir/gitleaks.tar.gz"
  else
    wget -qO "$tmp_dir/gitleaks.tar.gz" "$url"
  fi

  tar -xzf "$tmp_dir/gitleaks.tar.gz" -C "$tmp_dir" gitleaks
  install -m 0755 "$tmp_dir/gitleaks" "$local_bin"
  rm -rf "$tmp_dir"

  echo "$local_bin"
}

gitleaks_bin="$(resolve_gitleaks_bin)"
"$gitleaks_bin" detect --source . --no-git --config .gitleaks.toml --redact

echo "secret scan is valid"
