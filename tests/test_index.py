import sqlite3
from pathlib import Path

from vault import index


def _doc(tmp_path: Path, name: str, title: str, body: str) -> Path:
    p = tmp_path / name
    p.write_text(f"# {title}\n\n{body}\n")
    return p


def _db(tmp_path: Path) -> sqlite3.Connection:
    return index._connect(tmp_path / "vault.db")


def test_rebuild_creates_documents_and_sections(tmp_path):
    _doc(tmp_path, "a.md", "Alpha", "the sabotage contest logic")
    db = index.rebuild(tmp_path, tmp_path / "vault.db")
    assert db.execute("SELECT COUNT(*) FROM documents").fetchone()[0] == 1
    assert db.execute("SELECT COUNT(*) FROM sections").fetchone()[0] == 1


def test_fts_finds_a_section_by_word(tmp_path):
    _doc(tmp_path, "a.md", "Alpha", "the sabotage contest logic")
    _doc(tmp_path, "b.md", "Beta", "unrelated gardening text")
    db = index.rebuild(tmp_path, tmp_path / "vault.db")
    rows = index.search(db, "sabotage")
    assert rows and rows[0]["doc_title"] == "Alpha"


def test_bm25_orders_the_best_section_first(tmp_path):
    _doc(tmp_path, "a.md", "Alpha", "sabotage " * 20)
    _doc(tmp_path, "b.md", "Beta", "sabotage once")
    db = index.rebuild(tmp_path, tmp_path / "vault.db")
    assert index.search(db, "sabotage")[0]["doc_title"] == "Alpha"


def test_rebuild_is_idempotent(tmp_path):
    _doc(tmp_path, "a.md", "Alpha", "body")
    db1 = index.rebuild(tmp_path, tmp_path / "vault.db")
    n1 = db1.execute("SELECT COUNT(*) FROM sections").fetchone()[0]
    db2 = index.rebuild(tmp_path, tmp_path / "vault.db")
    assert db2.execute("SELECT COUNT(*) FROM sections").fetchone()[0] == n1


def test_duplicate_documents_are_recorded_not_reindexed(tmp_path):
    (tmp_path / "a.pdf").write_bytes(b"%PDF-1.4 same")
    (tmp_path / "b.pdf").write_bytes(b"%PDF-1.4 same")
    db = index.rebuild(tmp_path, tmp_path / "vault.db")
    assert db.execute("SELECT COUNT(*) FROM documents").fetchone()[0] == 1
    assert db.execute("SELECT COUNT(*) FROM duplicates").fetchone()[0] == 1


def test_search_never_raises_on_punctuation(tmp_path):
    _doc(tmp_path, "a.md", "Alpha", "body text")
    db = index.rebuild(tmp_path, tmp_path / "vault.db")
    assert index.search(db, "rag OR 1=1 --") == []
    assert index.search(db, "!!!") == []


def test_broken_source_is_recorded_not_fatal(tmp_path):
    (tmp_path / "bad.pdf").write_bytes(b"%PDF-1.4 not really a pdf")
    db = index.rebuild(tmp_path, tmp_path / "vault.db")
    row = db.execute("SELECT title FROM documents").fetchone()
    assert row is not None
