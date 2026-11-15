from pathlib import Path

from vault import paths


def test_data_root_is_profile_scoped(tmp_path, monkeypatch):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    root = paths.data_root()
    assert root.name == "tvl-vault"
    assert str(root).startswith(str(tmp_path))


def test_the_vaults_own_repo_is_not_part_of_the_corpus(tmp_path):
    """`tvl-vault` lives inside ~/work, which IS a corpus root. Indexing it would
    rank this project's own plan and handoff above the doctrine they describe."""
    vault_dir = tmp_path / "work" / "tvl-vault"
    vault_dir.mkdir(parents=True)
    (vault_dir / "HANDOFF.md").write_text("# The Vault — handoff\n")
    other = tmp_path / "work" / "tvl-brand"
    other.mkdir(parents=True)
    (other / "NOTES.md").write_text("# Brand notes\n")

    from vault import sources
    found = [d.path for d in sources.scan(tmp_path / "work")]
    assert other / "NOTES.md" in found
    assert vault_dir / "HANDOFF.md" not in found, "the Vault indexed itself"


def test_a_download_suffix_is_not_a_different_document(tmp_path):
    """`doc (1).pdf` / `doc-2.pdf` are the same file saved twice by a browser.
    They are byte-different (metadata), so sha256 does not catch them; the
    version-stripped name does."""
    data = b"%PDF-1.4 same document bytes"
    (tmp_path / "TVL — CIA of AI — Canonical Logic (v1.0).pdf").write_bytes(data)
    (tmp_path / "TVL — CIA of AI — Canonical Logic (v1.0) (1).pdf").write_bytes(data + b" ")
    (tmp_path / "TVL — CIA of AI — Canonical Logic (v1.0)-2.pdf").write_bytes(data + b"  ")
    from vault import sources
    pdfs = [d for d in sources.scan(tmp_path) if d.kind == "pdf"]
    assert len(pdfs) == 1, [str(d.path) for d in pdfs]
    assert len(pdfs[0].duplicates) == 2, [str(p) for p in pdfs[0].duplicates]


def test_corpus_roots_are_absolute_and_exist():
    roots = paths.corpus_roots()
    assert roots, "no corpus roots configured"
    for r in roots:
        assert r.is_absolute()
        assert r.exists(), r


def test_vault_db_path_is_inside_data_root(tmp_path, monkeypatch):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    assert paths.vault_db_path() == paths.data_root() / "vault.db"


def test_excluded_dirs_are_recognised():
    assert paths.is_excluded_dir(".venv")
    assert paths.is_excluded_dir("node_modules")
    assert not paths.is_excluded_dir("documents")
