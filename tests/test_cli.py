"""`python -m vault rebuild` — the one command that rebuilds the index.

The CLI is the only way a human (or the cron job) refreshes the Vault: it is
what the Review walkthrough and the desktop's "rebuild" affordance end up
calling. These tests pin the three things it must do and one thing it must not.

It must not swallow a bad flag: `raise SystemExit(main([...]))` propagates,
and pytest catches it. So `main()` is called directly and its return code is
asserted, never wrapped.
"""

from __future__ import annotations

import importlib.util
import json
import os
import sqlite3
import sys
from collections import Counter
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent

sys.path.insert(0, str(ROOT / "src"))

from vault import index, paths, review  # noqa: E402


def _load_cli():
    """Import `vault.cli` as a module *of the package*, exactly as `python -m vault`
    does.

    A standalone `spec_from_file_location` fails: `cli.py` uses relative imports
    (`from . import index`), and a file loaded outside its package has no parent
    to resolve them against. The package itself is already importable (conftest
    puts `src/` on `sys.path`), so the real module object is the honest one.
    """
    import vault

    return importlib.import_module("vault.cli")


@pytest.fixture(autouse=True)
def _isolated_home(tmp_path, monkeypatch):
    """No test may write the profile's real vault.db, and none may read the real
    corpus: `HERMES_VAULT_ROOTS` pins the roots to the folder each test makes."""
    monkeypatch.setenv("HERMES_HOME", str(tmp_path / "hermes"))
    monkeypatch.delenv("HERMES_VAULT_DB", raising=False)
    monkeypatch.setenv("HERMES_VAULT_ROOTS", os.pathsep.join(
        [str(tmp_path / "hermes" / "attachments"), str(tmp_path / "roots")]))


def _seed(root: Path) -> None:
    (root / "alpha.md").write_text("# Alpha Doctrine\n\nsabotage contest logic\n")
    (root / "beta.pdf").write_bytes(b"%PDF-1.4 empty")


def _read_flags(db_path: Path) -> dict[str, int]:
    """Flag counts, read from a fresh connection.

    A separate connection is deliberate: the CLI's connection is still open when
    it prints, and SQLite keeps the last commit in the WAL until that handle
    closes — a second handle can then see a stale snapshot and report the
    pre-commit counts.
    """
    db = sqlite3.connect(db_path)
    try:
        return dict(db.execute("SELECT flag, COUNT(*) FROM flags GROUP BY flag"))
    finally:
        db.close()


def _flags(db: sqlite3.Connection) -> dict[str, int]:
    return dict(db.execute("SELECT flag, COUNT(*) FROM flags GROUP BY flag"))


def test_rebuild_writes_the_index_and_a_flag_summary(tmp_path, capsys):
    root = tmp_path / "corpus"
    root.mkdir()
    _seed(root)
    db_path = tmp_path / "vault.db"
    cli = _load_cli()

    rc = cli.main(["rebuild", "--root", str(root), "--db", str(db_path)])

    out = capsys.readouterr().out
    assert rc == 0
    assert db_path.exists(), "the index file was not written"
    assert "documents 2" in out, out
    assert "sections 1" in out, out
    assert "flags:" in out and "unclear=1" in out, out
    db = sqlite3.connect(db_path)
    assert db.execute("SELECT COUNT(*) FROM documents").fetchone()[0] == 2
    assert _flags(db) == {"unclear": 1, "current": 1}


def test_rebuild_accepts_several_roots_and_counts_the_union(tmp_path, capsys):
    """The CLI is called per corpus root by the wrapper script; three roots must
    end up in one index, not three."""
    a, b = tmp_path / "a", tmp_path / "b"
    a.mkdir()
    b.mkdir()
    (a / "one.md").write_text("# One\n\nbody\n")
    (b / "two.md").write_text("# Two\n\nbody\n")
    db_path = tmp_path / "vault.db"
    cli = _load_cli()

    rc = cli.main(["rebuild", "--root", str(a), "--root", str(b), "--db", str(db_path)])

    assert rc == 0
    out = capsys.readouterr().out
    assert "documents 2" in out, out
    db = sqlite3.connect(db_path)
    assert db.execute("SELECT COUNT(*) FROM documents").fetchone()[0] == 2


def test_rebuild_summarises_duplicate_and_outdated_flags(tmp_path, capsys):
    root = tmp_path / "corpus"
    root.mkdir()
    body = b"%PDF-1.4 identical bytes"
    (root / "a.pdf").write_bytes(body)
    (root / "b.pdf").write_bytes(body)                    # byte-identical copy
    (root / "old.md").write_text("# TVL — Same\n\nVersion:\nv1.0\n")
    (root / "new.md").write_text("# TVL — Same\n\nVersion:\nv1.2\n")
    cli = _load_cli()

    cli.main(["rebuild", "--root", str(root), "--db", str(tmp_path / "v.db")])
    out = capsys.readouterr().out

    assert "duplicate=1" in out, out
    assert "outdated=1" in out, out


def test_rebuild_with_no_root_uses_the_configured_corpus_roots(tmp_path, capsys):
    """With no `--root`, the roots come from `paths.corpus_roots()` — the same
    three the desktop uses. Pointed at a throwaway home here, so the test reads
    only the folder it made."""
    home = tmp_path / "hermes"
    att = home / "attachments"
    att.mkdir(parents=True)
    (att / "a.md").write_text("# Only\n\nbody\n")
    cli = _load_cli()

    rc = cli.main(["rebuild", "--db", str(tmp_path / "v.db")])

    assert rc == 0
    out = capsys.readouterr().out
    assert "documents 1" in out, out
    db = sqlite3.connect(tmp_path / "v.db")
    assert db.execute("SELECT COUNT(*) FROM documents").fetchone()[0] == 1


def test_rebuild_without_a_db_argument_writes_the_profile_index(tmp_path, capsys):
    """The default target is `paths.vault_db_path()` — the desktop reads that
    file. The test points HERMES_HOME at a throwaway tree."""
    home = tmp_path / "hermes"
    att = home / "attachments"
    att.mkdir(parents=True)
    (att / "a.md").write_text("# Only\n\nbody\n")
    cli = _load_cli()

    cli.main(["rebuild"])

    out = capsys.readouterr().out
    expected = home / "tvl-vault" / "vault.db"
    assert expected.exists(), f"expected the index at {expected}; output was {out!r}"
    assert "tvl-vault" in out, out


def test_rebuild_is_idempotent(tmp_path):
    """Run it twice over the same corpus: the second pass must not double the
    rows or leave the first pass's documents behind."""
    root = tmp_path / "corpus"
    root.mkdir()
    _seed(root)
    db_path = tmp_path / "vault.db"
    cli = _load_cli()

    cli.main(["rebuild", "--root", str(root), "--db", str(db_path)])
    first = sqlite3.connect(db_path).execute("SELECT COUNT(*) FROM documents").fetchone()[0]
    cli.main(["rebuild", "--root", str(root), "--db", str(db_path)])
    db = sqlite3.connect(db_path)

    assert db.execute("SELECT COUNT(*) FROM documents").fetchone()[0] == first == 2
    assert db.execute("SELECT COUNT(*) FROM sections").fetchone()[0] == 1
    assert _flags(db) == {"unclear": 1, "current": 1}


def test_rebuild_never_writes_to_a_source_file(tmp_path):
    """Rule 4: the index is derived, the corpus is read-only."""
    root = tmp_path / "corpus"
    root.mkdir()
    src = root / "alpha.md"
    src.write_text("# Alpha\n\nsabotage contest logic\n")
    before = src.read_bytes()
    cli = _load_cli()

    cli.main(["rebuild", "--root", str(root), "--db", str(tmp_path / "v.db")])

    assert src.read_bytes() == before, "a source file was rewritten"


def test_rebuild_with_no_roots_at_all_is_a_clear_error(tmp_path, monkeypatch):
    """The honest failure: no corpus roots configured. A rebuild that silently
    wrote an empty index would look like a clean corpus."""
    monkeypatch.setenv("HERMES_VAULT_ROOTS", str(tmp_path / "nowhere"))
    db_path = tmp_path / "v.db"
    cli = _load_cli()
    with pytest.raises(SystemExit) as exc:
        cli.main(["rebuild", "--db", str(db_path)])
    assert "no corpus roots" in str(exc.value)
    assert not db_path.exists(), "an empty index was written anyway"


def test_stats_on_a_missing_index_says_so(tmp_path, capsys):
    """`stats` is read-only: it must not create the file it is asked about."""
    cli = _load_cli()
    rc = cli.main(["stats", "--db", str(tmp_path / "absent.db")])
    assert rc == 1
    err = capsys.readouterr().err
    assert "no index" in err, err
    assert not (tmp_path / "absent.db").exists()


def test_the_roots_override_replaces_the_default_three(tmp_path, capsys):
    """`HERMES_VAULT_ROOTS` is the seam a second machine (or a test) uses; the
    command must read exactly the roots it is given, not the default three."""
    mine = tmp_path / "mine"
    mine.mkdir()
    (mine / "a.md").write_text("# A\n\nbody\n")
    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setenv("HERMES_VAULT_ROOTS", str(mine))
    try:
        rc = _load_cli().main(["rebuild", "--db", str(tmp_path / "v.db")])
    finally:
        monkeypatch.undo()
    assert rc == 0
    out = capsys.readouterr().out
    assert "1 root" in out, out
    assert "documents 1" in out, out


def test_module_entrypoint_runs_the_cli():
    """`python -m vault --help` must dispatch, not just define main().

    The interpreter is this repo's `.venv` one (the Hermes environment), which
    is the interpreter `scripts/rebuild.sh` uses; `sys.executable` under pytest
    is the same interpreter, but saying it explicitly keeps the test honest if
    the suite is ever run from the system python.
    """
    venv = ROOT / ".venv" / "bin" / "python"
    interp = str(venv) if venv.exists() else sys.executable
    proc = __import__("subprocess").run(
        [interp, "-m", "vault", "--help"],
        cwd=str(ROOT / "src"), capture_output=True, text=True,
    )
    assert proc.returncode == 0, proc.stderr
    assert "rebuild" in proc.stdout


def test_the_wrapper_script_is_executable_and_points_at_the_package():
    script = ROOT / "scripts" / "rebuild.sh"
    assert script.exists(), "scripts/rebuild.sh is missing"
    assert script.stat().st_mode & 0o111, "scripts/rebuild.sh is not executable"
    text = script.read_text()
    assert "python -m vault rebuild" in text or "-m vault rebuild" in text, text


def test_rebuild_writes_flags_the_review_queue_reads(tmp_path):
    """The CLI's flags table is the one `review.queue()` reads — the command
    that refreshes the index is also the one that fills the queue."""
    root = tmp_path / "corpus"
    root.mkdir()
    _seed(root)
    db_path = tmp_path / "vault.db"
    cli = _load_cli()
    cli.main(["rebuild", "--root", str(root), "--db", str(db_path)])

    db = sqlite3.connect(db_path)
    db.row_factory = sqlite3.Row
    queue = review.queue(db)
    assert queue, "the queue is empty after a rebuild"
    assert all(q["flag"] != "current" for q in queue)


def test_flag_counts_match_the_table(tmp_path, capsys):
    """The printed summary and the flags table must agree — the number a human
    reads is the number the UI shows."""
    root = tmp_path / "corpus"
    root.mkdir()
    _seed(root)
    db_path = tmp_path / "vault.db"
    cli = _load_cli()
    cli.main(["rebuild", "--root", str(root), "--db", str(db_path)])
    out = capsys.readouterr().out
    counts = _read_flags(db_path)
    for flag, n in counts.items():
        assert f"{flag}={n}" in out, f"{flag}={n} missing from {out!r}"


def test_the_desktop_docs_point_at_the_rebuild_command():
    """The handoff and the plan tell the next reader to run it; the command they
    name must be the one that exists."""
    for doc in (ROOT / "HANDOFF.md", ROOT / "docs" / "PLAN.md"):
        if doc.exists():
            assert "rebuild" in doc.read_text().lower()
