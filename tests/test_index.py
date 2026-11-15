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
    # FTS5 would read a bare `rag OR 1=1` as a boolean query and match everything;
    # every term must be quoted so it is a literal.
    assert index.search(db, "rag OR 1=1 --") == []
    assert index.search(db, "!!!") == []
    # a lone operator is a literal word, not a switch
    assert index.search(db, "OR") == []


def test_broken_source_is_recorded_not_fatal(tmp_path):
    (tmp_path / "bad.pdf").write_bytes(b"%PDF-1.4 not really a pdf")
    db = index.rebuild(tmp_path, tmp_path / "vault.db")
    row = db.execute("SELECT title FROM documents").fetchone()
    assert row is not None


def test_a_word_in_the_section_title_outranks_the_same_word_in_a_body(tmp_path):
    """A section *named* Chunking is the answer to "chunking"; a section that
    merely mentions chunking in passing is not. FTS5's bm25 weights the title
    and body columns equally, which ties them — so the title is weighted here."""
    _doc(tmp_path, "doctrine.md", "Chunking", "split a document into sections")
    _doc(tmp_path, "notes.md", "Meeting notes", "we talked about chunking and other things " * 3)
    db = index.rebuild(tmp_path, tmp_path / "vault.db")
    rows = index.search(db, "chunking")
    assert rows[0]["doc_title"] == "Chunking", [r["doc_title"] for r in rows]
    assert rows[0]["section_title"] == "Chunking"


def test_a_distinctive_term_beats_a_term_common_across_the_corpus(tmp_path):
    """BM25 as FTS5 computes it has no IDF across a one-file corpus the way a
    retriever needs: a word that appears everywhere ranks like a rare one. The
    title match is the tiebreak that matters."""
    _doc(tmp_path, "doctrine.md", "Budget", "the budget figure")
    for i in range(6):
        _doc(tmp_path, f"n{i}.md", f"Note {i}", "budget " * 4)
    db = index.rebuild(tmp_path, tmp_path / "vault.db")
    assert index.search(db, "budget")[0]["doc_title"] == "Budget"


def test_the_same_document_does_not_take_every_slot(tmp_path):
    """A document split into overlapping sections otherwise floods the context:
    six copies of one doc leaves no room for the document that answers."""
    body = "chunking must happen at the section header level. " * 40
    _doc(tmp_path, "a.md", "One", body)
    _doc(tmp_path, "b.md", "Two", body)
    _doc(tmp_path, "c.md", "Three", body)
    db = index.rebuild(tmp_path, tmp_path / "vault.db")
    rows = index.search(db, "chunking", limit=25)
    per_doc = {}
    for r in rows:
        per_doc[r["doc_id"]] = per_doc.get(r["doc_id"], 0) + 1
    assert per_doc and max(per_doc.values()) <= index.PER_DOCUMENT_SECTIONS, per_doc
    assert len(per_doc) > 1, "one document crowded out the others"


def test_a_title_match_with_an_empty_body_is_not_offered_as_evidence(tmp_path):
    """A separator line can be a section title; its body is nothing."""
    _doc(tmp_path, "a.md", "Chunking", "")
    db = index.rebuild(tmp_path, tmp_path / "vault.db")
    assert [r for r in index.search(db, "chunking") if (r["body"] or "").strip()] == []
