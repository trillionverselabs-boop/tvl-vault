from pathlib import Path

from vault import index, review


def _seed(tmp_path: Path):
    (tmp_path / "a.pdf").write_bytes(b"%PDF-1.4 identical")
    (tmp_path / "b.pdf").write_bytes(b"%PDF-1.4 identical")
    (tmp_path / "c.md").write_text("# Alpha\n\nbody one\n")
    (tmp_path / "d.md").write_text("# Beta\n\nbody two\n")
    return index.rebuild(tmp_path, tmp_path / "vault.db")


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
