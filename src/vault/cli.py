"""`python -m vault rebuild` — the one command that rebuilds the index.

Everything the desktop shows comes from one SQLite file, and this is the only
thing that writes it. Two jobs, in this order:

1. **Rebuild** the index from the corpus roots (`index.rebuild`). One pass over
   every root, one DB. The pass deletes first, so calling it twice over the
   same corpus gives the same rows, not double rows.
2. **Compute and store the flags** (`review.compute_flags` + `write_flags`).
   Without this the `flags` table is empty and the Review tab shows nothing —
   the queue is not derived on read, it is written here.

The corpus is only ever read. No source file is opened for writing anywhere in
this module.

Usage:
    python -m vault rebuild                       # the configured corpus roots
    python -m vault rebuild --root ~/work         # extra roots, repeatable
    python -m vault rebuild --db /tmp/vault.db    # somewhere other than the default
    python -m vault rebuild --no-flags            # index only, leave flags alone
    python -m vault stats                         # read the index without writing
"""

from __future__ import annotations

import argparse
import sqlite3
import sys
from collections import Counter
from pathlib import Path

from . import index, paths, review


def _flags(db: sqlite3.Connection) -> dict[str, int]:
    """Flag -> count, in the order the UI lists them."""
    out = {f: 0 for f in review.FLAG_ORDER}
    for flag, n in db.execute("SELECT flag, COUNT(*) FROM flags GROUP BY flag"):
        out[flag] = n
    return out


def _counts(db: sqlite3.Connection) -> dict[str, int]:
    return {
        "documents": db.execute("SELECT COUNT(*) FROM documents").fetchone()[0],
        "sections": db.execute("SELECT COUNT(*) FROM sections").fetchone()[0],
        "duplicates": db.execute("SELECT COUNT(*) FROM duplicates").fetchone()[0],
        "images": db.execute("SELECT COUNT(*) FROM documents WHERE kind='image'").fetchone()[0],
    }


def _summary(db: sqlite3.Connection, roots: list[Path], db_path: Path) -> str:
    """The human-readable line the command prints.

    Every number is a count from the DB, so what is printed and what the UI
    reads are the same numbers. The path printed is the one actually written,
    which is not always `paths.vault_db_path()` (`--db` overrides it).
    """
    c = _counts(db)
    parts = [f"documents {c['documents']}", f"sections {c['sections']}",
             f"duplicates {c['duplicates']}", f"images {c['images']}"]
    flags = _flags(db)
    if flags:
        parts.append("flags: " + ", ".join(f"{k}={v}" for k, v in flags.items() if v))
    return f"vault: {len(roots)} root{'s' if len(roots) != 1 else ''} → {db_path}\n  " \
        + " · ".join(parts)


def rebuild(roots: list[Path] | None = None, db_path: Path | None = None,
            with_flags: bool = True) -> sqlite3.Connection:
    """Rebuild the index and return the open connection.

    The single public entry point, so a test (or the desktop) can drive it
    without parsing argv.
    """
    roots = [Path(r) for r in (roots if roots is not None else paths.corpus_roots())]
    if not roots:
        raise SystemExit("vault: no corpus roots found — pass --root")
    db = index.rebuild(roots, db_path or paths.vault_db_path())
    if with_flags:
        review.write_flags(db, review.compute_flags(db))
    return db


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        prog="vault",
        description="Rebuild The Vault's index from the corpus. The corpus is read-only.",
        epilog="examples:\n"
               "  vault rebuild                     index every corpus root\n"
               "  vault rebuild --root ~/work       index one root (repeatable)\n"
               "  vault rebuild --db /tmp/v.db      write somewhere else\n"
               "  vault stats                       read the index without writing\n",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    sub = ap.add_subparsers(dest="cmd", required=True)

    r = sub.add_parser("rebuild", help="rebuild the index and recompute the flags")
    r.add_argument("--root", action="append", default=None,
                   help="a corpus root; repeatable. Default: the configured roots")
    r.add_argument("--db", default=None,
                   help="where to write the index. Default: the profile's vault.db")
    r.add_argument("--no-flags", action="store_true",
                   help="index only; leave the flags table as it is")

    s = sub.add_parser("stats", help="print the counts already in the index (no rebuild)")
    s.add_argument("--db", default=None, help="which index to read")

    # `rebuild.sh` forwards its own `--help` here, and a caller typing
    # `vault --help` wants the flags of the command they will actually run.
    args = list(sys.argv[1:] if argv is None else argv)
    if args[:1] in (["-h"], ["--help"]):
        args = ["rebuild", *args]
    a = ap.parse_args(args)

    if a.cmd == "stats":
        p = Path(a.db) if a.db else paths.vault_db_path()
        if not p.exists():
            print(f"vault: no index at {p} — run `python -m vault rebuild`", file=sys.stderr)
            return 1
        db = sqlite3.connect(p)
        db.row_factory = sqlite3.Row
        c = _counts(db)
        flags = _flags(db) if db.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='flags'").fetchone() else {}
        print(f"vault: {p}")
        print("  " + " · ".join(f"{k} {v}" for k, v in c.items()))
        if flags:
            print("  flags: " + ", ".join(f"{k}={v}" for k, v in flags.items() if v))
        return 0

    roots = [Path(x) for x in (a.root or [])] or paths.corpus_roots()
    db_path = Path(a.db) if a.db else None
    db = rebuild(roots, db_path, with_flags=not a.no_flags)
    print(_summary(db, roots, db_path or paths.vault_db_path()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
