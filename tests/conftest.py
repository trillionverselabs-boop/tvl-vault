import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from vault import paths  # noqa: E402


@pytest.fixture(autouse=True)
def _keep_the_real_profile_out_of_the_tests(tmp_path, monkeypatch):
    """Every test gets a throwaway data root, whatever the module forgot to set.

    The profile's real data root holds Lisa's review decisions. A module that
    sets `HERMES_VAULT_DB` but not `HERMES_HOME` still resolves
    `correction_path()` through `data_root()`, which follows the *unset*
    `HERMES_HOME` and lands on the real profile — so its test decisions were
    appended to her log. This fixture is the backstop: no module can forget
    it, because it applies to every test in the tree.
    """
    monkeypatch.setenv("HERMES_HOME", str(tmp_path / "hermes-home"))
    monkeypatch.delenv("HERMES_VAULT_ROOTS", raising=False)
    yield


def test_the_real_profile_data_root_is_never_a_test_target():
    """The real root must not be derivable from the environment a test runs in.

    Read from disk, not from the environment: this asserts about the tree on
    this machine, so a suite that silently points `HERMES_HOME` at the real
    profile cannot pass by agreeing with itself.
    """
    real_root = Path.home() / ".hermes" / "profiles" / "charlene" / "tvl-vault"
    here = paths.data_root()
    assert here != real_root, (
        f"the suite is running against the real profile data root: {here}"
    )
    assert "hermes-home" in str(here), here


def test_the_backstop_applies_even_when_a_module_sets_only_the_db(tmp_path, monkeypatch):
    """The leak this fixture exists to stop.

    `test_api.py` sets `HERMES_VAULT_DB` and — until this fixture — nothing
    else. `vault_db_path()` followed the override, but `correction_path()` goes
    through `data_root()`, which followed the *unset* `HERMES_HOME` and
    resolved to the real profile. So every API test appended a row to Lisa's
    real review log (measured: 237 → 241, then 245 → 249, 249 → 253). This
    test reproduces that exact module shape: the module sets the DB and
    leaves the data root to the environment. It fails if the autouse fixture
    is removed, because then `correction_path()` is the real file.
    """
    monkeypatch.setenv("HERMES_VAULT_DB", str(tmp_path / "vault.db"))

    from vault import review

    assert review.correction_path() != (
        Path.home() / ".hermes" / "profiles" / "charlene" / "tvl-vault" / "corrections.jsonl"
    )
    assert "hermes-home" in str(review.correction_path()), review.correction_path()
