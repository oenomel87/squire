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

exec uv run --project "${ENGINE_DIR}" squire "$@"
