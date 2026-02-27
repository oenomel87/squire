#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Usage:
  install_squire_cli.sh <squire-repo-or-engine-path>

Examples:
  install_squire_cli.sh /Users/me/workspace/squire
  install_squire_cli.sh /Users/me/workspace/squire/squire-engine
EOF
}

if ! command -v uv >/dev/null 2>&1; then
  echo "uv is required. Install from https://docs.astral.sh/uv/" >&2
  exit 1
fi

if [[ $# -ne 1 ]]; then
  usage >&2
  exit 1
fi

input_path="$(cd "$1" && pwd)"
engine_path=""

if [[ -f "${input_path}/pyproject.toml" && -f "${input_path}/src/squire/cli.py" ]]; then
  engine_path="${input_path}"
elif [[ -f "${input_path}/squire-engine/pyproject.toml" ]]; then
  engine_path="${input_path}/squire-engine"
else
  echo "Could not find squire-engine from: ${input_path}" >&2
  usage >&2
  exit 1
fi

echo "Installing squire from: ${engine_path}"
uv tool install --editable "${engine_path}" --force
uv tool update-shell
echo "Installed. Open a new shell and run: squire --help"
