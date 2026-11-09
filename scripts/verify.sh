#!/usr/bin/env bash
# End-of-task checks from README. Not a hook.
# Does not start the API, set ARS_DATA_ROOT, or read source recordings.
# pnpm build writes gitignored frontend/dist only.
set -euo pipefail

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

(
  cd "$root/backend"
  uv run ruff check .
  uv run pytest -q
)

(
  cd "$root/frontend"
  pnpm typecheck
  pnpm test
  pnpm build
)
