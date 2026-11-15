#!/usr/bin/env bash
# Rebuild The Vault: index every corpus root, then recompute the flags.
#
# One command, no arguments needed. It writes the index the desktop reads
# (paths.vault_db_path()); pass --db to write somewhere else, and --root to
# limit it to one corpus root (repeatable).
#
#   ./scripts/rebuild.sh
#   ./scripts/rebuild.sh --db /tmp/vault.db
#   ./scripts/rebuild.sh --root /home/lisacore/work
#
# The corpus is only read. Nothing here writes to a source file.
set -euo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")/.."

# `vault` lives under src/, which is not on the path by default. PYTHONPATH, not
# a sys.path hack inside the package: the same interpreter and the same module
# are used either way, and the tests import `vault` the same way.
export PYTHONPATH="$PWD/src${PYTHONPATH:+:$PYTHONPATH}"

# The Hermes environment (it carries pytest and the FastAPI stack the dashboard
# imports). Falls back to whatever python3 is on PATH.
PYTHON="${PYTHON:-}"
if [ -z "$PYTHON" ]; then
  if [ -x "$PWD/.venv/bin/python" ]; then
    PYTHON="$PWD/.venv/bin/python"
  else
    PYTHON="python3"
  fi
fi

exec "$PYTHON" -m vault rebuild "$@"
