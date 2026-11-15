"""Where The Vault reads and writes.

Reads are absolute and come from three places: the profile's own attachments
folder (where the desktop puts anything you hand me), the note trees under
~/work and ~/Projects, and the ingest drop zone under ~/work/tvl-ingest.

Writes go ONLY to `plugin_data_dir("tvl-vault")` — the profile-scoped data root
that survives `plugins update` and `plugins remove`. This module is the only
place that knows those paths.
"""

from __future__ import annotations

import os
from pathlib import Path

PLUGIN_ID = "tvl-vault"

# Directories that are build output, not source. Skipped by the scanner.
EXCLUDED_DIR_NAMES = {
    "node_modules", "__pycache__", ".venv", "venv", ".mypy_cache",
    ".ruff_cache", ".pytest_cache", "dist", "build", ".cache",
}

# The plugin's own repository. It lives inside ~/work, which is a corpus root,
# so without this the Vault indexes its own plan, handoff and tests — and its
# notes about the doctrine then outrank the doctrine itself.
SELF_DIR_NAMES = {PLUGIN_ID}


def _hermes_home() -> Path:
    try:
        from hermes_constants import get_hermes_home

        return Path(get_hermes_home())
    except Exception:
        return Path(os.environ.get("HERMES_HOME") or (Path.home() / ".hermes"))


def data_root() -> Path:
    home = _hermes_home()
    try:
        from plugins.plugin_storage import plugin_data_dir  # type: ignore

        p = Path(plugin_data_dir(PLUGIN_ID))
        if str(p).startswith(str(home)):
            return p
    except Exception:
        pass
    return home / PLUGIN_ID


def vault_db_path() -> Path:
    """The index file. `HERMES_VAULT_DB` overrides it — tests point it elsewhere."""
    override = os.environ.get("HERMES_VAULT_DB")
    if override:
        return Path(override)
    return data_root() / "vault.db"


def _home_note_root() -> Path | None:
    """The ingest drop zone, if it exists.

    It is a *sibling* of the corpus roots, not a replacement: it holds the
    `Trillionverselabs vision/` PDFs that landed on 2026-11-14. Optional, and
    only when it is really there — a test that points HERMES_HOME at a throwaway
    tree must not inherit the real one.
    """
    p = Path("/home/lisacore/work/tvl-ingest")
    return p if p.is_dir() else None


def corpus_roots() -> list[Path]:
    """Existing source directories, in priority order. Missing ones are skipped.

    The first root is the profile's own attachments (where the desktop puts
    anything you hand it). The note trees are pinned to this machine's home
    because they are Lisa's real folders; `HERMES_VAULT_ROOTS` overrides them
    wholesale for a test or a second machine, and `HERMES_HOME` replaces the
    attachments root.
    """
    home = _hermes_home()
    override = os.environ.get("HERMES_VAULT_ROOTS")
    if override:
        return [Path(x) for x in override.split(os.pathsep) if x and Path(x).is_dir()]
    candidates = [home / "attachments", Path("/home/lisacore/work"),
                  Path("/home/lisacore/Projects")]
    note = _home_note_root()
    if note is not None:
        candidates.append(note)
    return [c for c in candidates if c.is_dir()]


def is_excluded_dir(name: str) -> bool:
    """Build output, dot-directories, and the plugin's own repository."""
    return name in EXCLUDED_DIR_NAMES or name in SELF_DIR_NAMES or name.startswith(".")
