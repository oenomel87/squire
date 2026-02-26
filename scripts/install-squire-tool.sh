#!/usr/bin/env bash
set -euo pipefail

if ! command -v uv >/dev/null 2>&1; then
  echo "uv is required. Install uv first: https://docs.astral.sh/uv/" >&2
  exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
ENGINE_DIR="${PROJECT_ROOT}/squire-engine"

if [[ ! -f "${ENGINE_DIR}/pyproject.toml" ]]; then
  echo "Could not find squire-engine/pyproject.toml" >&2
  exit 1
fi

echo "Installing squire CLI as a global uv tool..."
uv tool install --editable "${ENGINE_DIR}" --force

echo "Ensuring uv tool bin directory is on PATH..."
uv tool update-shell

echo "Done."
echo "If this is your first setup, restart your terminal."
echo "Verify with: squire --help"

