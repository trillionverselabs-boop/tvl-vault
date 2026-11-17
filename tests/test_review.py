from pathlib import Path

import pytest

from vault import index, review


def _seed(tmp_path: Path):
    (tmp_path / "a.pdf").write_bytes(b"%PDF-1.4 identical")
    (tmp_path / "b.pdf").write_bytes(b"%PDF-1.4 identical")
    (tmp_path / "c.md").write_text("# Alpha\n\nbody one\n")
    (tmp_path / "d.md").write_text("# Beta\n\nbody two\n")
    return index.rebuild(tmp_path, tmp_path / "vault.db")


@pytest.fixture(autouse=True)
def _keep_the_real_data_root(tmp_path, monkeypatch):
    """The DB this module writes is in the test's own tmp tree.

    The data root itself is redirected for the whole suite by
    `tests/conftest.py`; this module only needs its own index file.
    """
    monkeypatch.setenv("HERMES_VAULT_DB", str(tmp_path / "vault.db"))


def test_byte_duplicate_gets_duplicate_flag(tmp_path):
    (tmp_path / "a.pdf").write_bytes(b"%PDF-1.4 identical")
    (tmp_path / "b.pdf").write_bytes(b"%PDF-1.4 identical")
    db = index.rebuild(tmp_path, tmp_path / "vault.db")
    assert "duplicate" in [f["flag"] for f in review.compute_flags(db)]


def test_a_doc_with_no_sections_gets_unclear(tmp_path):
    (tmp_path / "empty.pdf").write_bytes(b"%PDF-1.4 no text at all")
    db = index.rebuild(tmp_path, tmp_path / "vault.db")
    assert any(f["flag"] == "unclear" for f in review.compute_flags(db))


def test_version_regress_is_flagged(tmp_path):
    (tmp_path / "x.md").write_text("# TVL — Same\n\nVersion:\nv1.0\n")
    (tmp_path / "y.md").write_text("# TVL — Same\n\nVersion:\nv1.2\n")
    db = index.rebuild(tmp_path, tmp_path / "vault.db")
    flags = [f for f in review.compute_flags(db) if f["flag"] == "outdated"]
    assert flags, "expected the v1.0 copy to be flagged outdated"


def test_validity_tag_not_active_is_outdated(tmp_path):
    (tmp_path / "z.pdf").write_bytes(b"%PDF-1.4 z")
    db = index.rebuild(tmp_path, tmp_path / "vault.db")
    db.execute("UPDATE documents SET rag_json=? WHERE doc_id=?",
               ('{"validity": "Frozen (v0.9)"}', db.execute("SELECT doc_id FROM documents").fetchone()[0]))
    db.commit()
    assert any(f["flag"] == "outdated" for f in review.compute_flags(db))


def test_write_flags_round_trips(tmp_path):
    db = _seed(tmp_path)
    flags = review.compute_flags(db)
    review.write_flags(db, flags)
    n = db.execute("SELECT COUNT(*) FROM flags").fetchone()[0]
    assert n == len(flags)
    assert db.execute("SELECT COUNT(DISTINCT flag) FROM flags").fetchone()[0] >= 2


# ── the corrections queue ────────────────────────────────────────────────

def test_a_confirmation_leaves_the_queue_and_a_keep_stays(tmp_path):
    db = _seed(tmp_path)
    review.write_flags(db, review.compute_flags(db))
    dup = db.execute("SELECT doc_id FROM flags WHERE flag='duplicate'").fetchone()[0]
    assert "duplicate" in {f["flag"] for f in review.queue(db) if f["doc_id"] == dup}

    review.write_correction(db, dup, "duplicate", "confirm")
    assert "duplicate" not in {f["flag"] for f in review.queue(db) if f["doc_id"] == dup}

    # a `keep` on another flag of the same document leaves that flag queued
    db.execute("INSERT OR REPLACE INTO flags(doc_id,section_id,flag,reason,evidence) "
               "VALUES(?,NULL,'unclear','no text','e')", (dup,))
    db.commit()
    review.write_correction(db, dup, "unclear", "keep")
    assert "unclear" in {f["flag"] for f in review.queue(db) if f["doc_id"] == dup}


def test_corrections_are_recorded_without_touching_the_source(tmp_path):
    src = tmp_path / "a.md"
    src.write_text("# Alpha\n\nbody\n")
    db = index.rebuild(tmp_path, tmp_path / "vault.db")
    review.write_flags(db, review.compute_flags(db))
    doc_id = db.execute("SELECT doc_id FROM documents").fetchone()[0]
    before = src.read_bytes()

    row = review.write_correction(db, doc_id, "unclear", "edit", "needs a rewrite")
    assert row["action"] == "edit"
    assert row["note"] == "needs a rewrite"
    assert src.read_bytes() == before, "the source file must never be rewritten"
    assert review.corrections(db)[0]["doc_id"] == doc_id


def test_a_decision_on_one_flag_leaves_the_other_on_the_queue(tmp_path):
    """Confirming a duplicate must not erase the unclear flag.

    Four doctrine PDFs on the real corpus carried both flags at once (a
    `tvl-ingest` copy, and no numbered headings). The old document-level key
    cleared both, so the reading was never reviewed.
    """
    (tmp_path / "a.pdf").write_bytes(b"%PDF-1.4 no extractable text")
    (tmp_path / "b.pdf").write_bytes(b"%PDF-1.4 no extractable text")
    db = index.rebuild(tmp_path, tmp_path / "vault.db")
    review.write_flags(db, review.compute_flags(db))
    doc = db.execute("SELECT doc_id FROM flags WHERE flag='duplicate'").fetchone()[0]
    assert {f["flag"] for f in review.queue(db) if f["doc_id"] == doc} == {"duplicate", "unclear"}

    review.write_correction(db, doc, "duplicate", "confirm")
    assert {f["flag"] for f in review.queue(db) if f["doc_id"] == doc} == {"unclear"}


def test_a_decision_is_idempotent_per_flag(tmp_path):
    """One status per (document, flag). A second decision replaces the first."""
    db = _seed(tmp_path)
    review.write_flags(db, review.compute_flags(db))
    doc_id = db.execute("SELECT doc_id FROM flags WHERE flag='duplicate'").fetchone()[0]
    review.write_correction(db, doc_id, "duplicate", "keep")
    review.write_correction(db, doc_id, "duplicate", "confirm")
    rows = db.execute("SELECT * FROM corrections WHERE doc_id=?", (doc_id,)).fetchall()
    assert len(rows) == 1
    assert rows[0]["action"] == "confirm"


def test_queue_orders_a_disagreement_first(tmp_path):
    db = _seed(tmp_path)
    review.write_flags(db, review.compute_flags(db))
    first = db.execute("SELECT doc_id FROM documents LIMIT 1").fetchone()[0]
    db.execute("INSERT OR REPLACE INTO flags(doc_id,section_id,flag,reason,evidence) "
               "VALUES(? ,NULL,'conflict','two budgets','e')", (first,))
    db.commit()
    assert review.queue(db)[0]["flag"] == "conflict"


def test_the_conflict_pass_needs_a_model_and_is_not_part_of_the_flags(tmp_path):
    """Task 10 shipped the model-assisted pass; it is on demand, so the
    deterministic flag table never claims a conflict it cannot prove."""
    db = _seed(tmp_path)
    assert review.conflicts(db, None) == []
    assert [f for f in review.compute_flags(db) if f["flag"] == "conflict"] == []
