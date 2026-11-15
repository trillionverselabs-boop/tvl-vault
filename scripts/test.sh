#!/usr/bin/env bash
# Run the suite whatever the checkout folder is called.
#
# The repository is `the-vault`, which is not a valid Python package name, so
# pytest would try to import the repository root as a module and die on the
# relative imports inside src/vault. Copy the tree to a valid name and run
# pytest there.
set -euo pipefail

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
tmp="$(mktemp -d "${TMPDIR:-/tmp}/vault-tests.XXXXXX")"
trap 'rm -rf "$tmp"' EXIT
mkdir -p "$tmp/vault"
cp -al "$root"/. "$tmp/vault/"

cd "$tmp/vault"
PYTHON="${PYTHON:-python3}"
exec "$PYTHON" -m pytest "$@"
