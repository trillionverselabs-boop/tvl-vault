from pathlib import Path

from vault import paths


def test_data_root_is_profile_scoped(tmp_path, monkeypatch):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    root = paths.data_root()
    assert root.name == "tvl-vault"
    assert str(root).startswith(str(tmp_path))


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
