"""The model-assisted conflict pass (`review.conflicts`, Task 10).

The deterministic pass (Task 5) can prove a byte-identical copy and a version
regress. It cannot see that two documents *disagree* — that needs the model.
This pass is therefore **on demand only**: it is never part of `rebuild`
(every rebuild would spend model calls), and the caller supplies the model.

The rules these tests pin are the plan's guardrails:

* at most 200 candidate pairs per run;
* `temperature=0` (the same corpus gives the same verdicts);
* every `conflict` flag carries non-empty `evidence`;
* a model failure degrades to no flags, never to a crash;
* a pair already decided by a human is never asked again.

The fixtures use the real shape of a disagreement — two sections of two
different documents that state a claim (a full sentence, well past
`MIN_CLAIM_WORDS`) and give the same subject different values. A three-word
fixture would never be a candidate at all.
"""

from __future__ import annotations

import importlib.util
import json
import sqlite3
import sys
import types
from pathlib import Path

import pytest

from vault import index, review

ROOT = Path(__file__).resolve().parent.parent
API = ROOT / "dashboard" / "plugin_api.py"
JS = ROOT / "desktop" / "plugin.js"

# The real shape: two sections, each stating a claim about the same subject.
_BUDGET_A = ("# Budget Doctrine\n\n"
             "SECTION 1 — The Operating Budget\n\n"
             "The monthly operating budget for the studio is three hundred "
             "dollars, and that figure is the ceiling for every recurring "
             "cost the business carries while it is being built.\n")
_BUDGET_B = ("# Budget Review\n\n"
             "SECTION 1 — Revised Operating Budget\n\n"
             "The monthly operating budget for the studio is eighty dollars, "
             "which is the number the current plan actually assumes for every "
             "recurring cost the business carries.\n")
_GARDEN = ("# Gardening Notes\n\n"
           "SECTION 1 — Tomatoes\n\n"
           "Tomatoes need full sun, frequent water and a stake before the "
           "fruit sets, or the branches break under the weight of the crop.\n")


@pytest.fixture(autouse=True)
def _keep_the_real_data_root(tmp_path, monkeypatch):
    """No test may read the real corpus or write the profile's data root."""
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    monkeypatch.delenv("HERMES_VAULT_DB", raising=False)
    monkeypatch.setenv("HERMES_VAULT_ROOTS", str(tmp_path / "corpus"))


class FakeLlm:
    """Stands in for `ctx.llm`. Returns one verdict per call, in order.

    `verdicts` is a list; when it runs out the last one repeats. A verdict may
    be a dict (the `parsed` JSON `complete_structured` returns when it can) or
    a string of JSON (the raw text it returns otherwise) — the pass must accept
    both. Each call is recorded with the exact kwargs, so the guardrails can be
    asserted against what was really sent.
    """

    def __init__(self, verdicts):
        self.verdicts = list(verdicts)
        self.calls = []

    def complete_structured(self, **kw):
        self.calls.append(kw)
        v = self.verdicts[min(len(self.calls) - 1, len(self.verdicts) - 1)]
        return types.SimpleNamespace(**({"parsed": v} if isinstance(v, dict) else {"text": v}))


def _seed(tmp_path: Path, docs: dict[str, str]) -> sqlite3.Connection:
    root = tmp_path / "corpus"
    root.mkdir(parents=True, exist_ok=True)
    for name, body in docs.items():
        (root / name).write_text(body)
    return index.rebuild([root], tmp_path / "vault.db")


def _seed_budget(tmp_path: Path) -> sqlite3.Connection:
    return _seed(tmp_path, {"a.md": _BUDGET_A, "b.md": _BUDGET_B})


def _conflict_rows(db: sqlite3.Connection) -> list[dict]:
    """Conflict flags, or `[]` when the flags table does not exist yet."""
    if not db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='flags'").fetchone():
        return []
    return [dict(r) for r in db.execute("SELECT * FROM flags WHERE flag='conflict'")]


# ── the pass is real, and it is on demand ───────────────────────────────────

def test_a_model_reported_conflict_becomes_a_conflict_flag(tmp_path):
    db = _seed_budget(tmp_path)
    llm = FakeLlm([{"contradicts": True, "reason": "two different monthly budgets"}])

    out = review.conflicts(db, llm)

    assert out, "the model's verdict produced no flag"
    assert all(f["flag"] == "conflict" for f in out)
    assert any("budget" in f["evidence"].lower() for f in out), out
    # the verdicts are written, so the Review tab reads them without re-asking
    assert _conflict_rows(db), "conflict flags were not written to the flags table"


def test_the_same_pair_is_not_asked_twice(tmp_path):
    """A pair already flagged conflict is settled; a rerun must not re-ask."""
    db = _seed_budget(tmp_path)
    llm = FakeLlm([{"contradicts": True, "reason": "two budgets"}])
    assert review.conflicts(db, llm)
    calls_after_first = len(llm.calls)

    assert review.conflicts(db, llm) == [], "a settled pair was reported again"
    assert len(llm.calls) == calls_after_first, "a settled pair was asked again"


def test_a_rebuild_never_calls_the_model(tmp_path):
    """Conflict detection is on demand. `rebuild` is the $0, offline command;
    a model call inside it would make every refresh cost money and break when
    the free model is throttled. Nothing here supplies a model at all — the
    pass must therefore not run."""
    db = _seed_budget(tmp_path)
    review.compute_flags(db)
    review.write_flags(db, review.compute_flags(db))
    assert _conflict_rows(db) == []


def test_the_pass_runs_at_temperature_zero(tmp_path):
    """The same corpus must give the same verdicts; a drift would make the
    review queue change between two identical rebuilds."""
    db = _seed_budget(tmp_path)
    llm = FakeLlm([{"contradicts": True, "reason": "two budgets"}])
    review.conflicts(db, llm)
    assert llm.calls, "the model was never called"
    for call in llm.calls:
        assert call.get("temperature") == 0, call
        assert call.get("model") in (None, "") and call.get("provider") in (None, ""), call


def test_a_model_failure_is_no_flags_not_a_crash(tmp_path):
    class Boom:
        def complete_structured(self, **kw):
            raise RuntimeError("the free model timed out")

    assert review.conflicts(_seed_budget(tmp_path), Boom()) == []


def test_no_model_no_pass(tmp_path):
    """Without a bound model the pass says nothing rather than guessing."""
    assert review.conflicts(_seed_budget(tmp_path), None) == []


# ── the guardrails ─────────────────────────────────────────────────────────

def test_a_conflict_flag_always_carries_evidence(tmp_path):
    """The plan's guardrail: a conflict a reviewer cannot read is not
    reviewable, so the flag must always carry a reason."""
    db = _seed_budget(tmp_path)
    review.conflicts(db, FakeLlm([{"contradicts": True, "reason": ""}]))
    rows = _conflict_rows(db)
    assert rows, "an empty-reason verdict must still be recorded for a human"
    for f in rows:
        assert (f["evidence"] or "").strip(), f


def test_the_pass_is_capped_at_two_hundred_pairs(tmp_path):
    """200 model calls is the ceiling; a bigger corpus must not exceed it."""
    docs = {f"d{i:02d}.md": f"# Doctrine {i}\n\nSECTION 1 — Budget\n\n"
                    f"The monthly operating budget figure for the studio is {i} "
                    f"dollars and that number is the ceiling for recurring costs.\n"
            for i in range(80)}
    db = _seed(tmp_path, docs)
    llm = FakeLlm([{"contradicts": False, "reason": ""}])
    review.conflicts(db, llm)
    assert review.MAX_CONFLICT_PAIRS == 200
    assert len(llm.calls) <= review.MAX_CONFLICT_PAIRS, len(llm.calls)


def test_a_verdict_of_no_is_not_recorded(tmp_path):
    db = _seed_budget(tmp_path)
    review.conflicts(db, FakeLlm([{"contradicts": False, "reason": "different topics"}]))
    assert _conflict_rows(db) == []


def test_a_json_string_verdict_is_accepted(tmp_path):
    """`complete_structured` may return parsed JSON or raw text; both must work."""
    db = _seed_budget(tmp_path)
    review.conflicts(db, FakeLlm(['{"contradicts": true, "reason": "two budgets"}']))
    assert _conflict_rows(db), "a JSON string verdict was dropped"


def test_an_unparseable_verdict_is_ignored(tmp_path):
    db = _seed_budget(tmp_path)
    review.conflicts(db, FakeLlm(["I cannot tell."]))
    assert _conflict_rows(db) == []


# ── what counts as a candidate pair ────────────────────────────────────────

def test_only_sections_that_share_a_salient_word_are_compared(tmp_path):
    """A pair with no shared subject is not a disagreement; asking about one
    would spend the cap on noise."""
    db = _seed(tmp_path, {"a.md": _BUDGET_A, "b.md": _GARDEN})
    llm = FakeLlm([{"contradicts": True, "reason": "whatever"}])
    review.conflicts(db, llm)
    assert llm.calls == [], "a pair with no shared subject was asked about"


def test_a_section_is_never_compared_with_itself(tmp_path):
    db = _seed(tmp_path, {"a.md": _BUDGET_A + "\n# Budget Again\n\nSECTION 2 — Budget\n\n"
                                      "The monthly operating budget is three hundred dollars, "
                                      "the same ceiling as before.\n"})
    llm = FakeLlm([{"contradicts": True, "reason": "self"}])
    review.conflicts(db, llm)
    assert llm.calls == []


def test_short_sections_are_not_candidates(tmp_path):
    """A heading with no claim in it cannot contradict anything."""
    db = _seed(tmp_path, {"a.md": "# Budget\n\nBudget\n\n# Other\n\nBudget\n"})
    llm = FakeLlm([{"contradicts": True, "reason": "short"}])
    review.conflicts(db, llm)
    assert llm.calls == []


def test_the_model_is_shown_both_passages(tmp_path):
    """The verdict is only auditable if the model was shown the two claims."""
    db = _seed_budget(tmp_path)
    llm = FakeLlm([{"contradicts": True, "reason": "two budgets"}])
    review.conflicts(db, llm)
    text = json.dumps(llm.calls[0]["input"])
    assert "three hundred" in text and "eighty dollars" in text, text


def test_a_human_decision_on_a_conflict_stands(tmp_path):
    """A pair the human has already resolved is not re-asked."""
    db = _seed_budget(tmp_path)
    review.write_flags(db, review.compute_flags(db))
    doc_id = db.execute("SELECT doc_id FROM documents LIMIT 1").fetchone()[0]
    review.write_correction(db, doc_id, "conflict", "confirm", "the $80 figure is the current one")
    llm = FakeLlm([{"contradicts": True, "reason": "two budgets"}])
    assert review.conflicts(db, llm) == []
    assert llm.calls == []


# ── the queue and the surfaces read it ─────────────────────────────────────

def test_a_conflict_is_on_the_review_queue_first(tmp_path):
    """The queue's severity order puts a disagreement ahead of a duplicate."""
    db = _seed_budget(tmp_path)
    review.write_flags(db, review.compute_flags(db))
    review.conflicts(db, FakeLlm([{"contradicts": True, "reason": "two budgets"}]))
    q = review.queue(db)
    assert q and q[0]["flag"] == "conflict", q


def _load_api(tmp_path, monkeypatch):
    """Import the router the way the dashboard loader does — standalone, by spec."""
    monkeypatch.setenv("HERMES_VAULT_DB", str(tmp_path / "vault.db"))
    spec = importlib.util.spec_from_file_location("_test_conflicts_api", API)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    sys.modules["_test_conflicts_api"] = mod
    spec.loader.exec_module(mod)
    return mod


def _client(mod):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    app = FastAPI()
    app.include_router(mod.router)
    return TestClient(app)


def test_the_backend_route_runs_the_pass_on_demand(tmp_path, monkeypatch):
    """`POST /conflicts` is the one place the model is asked. It is a POST
    because it writes flags and spends model calls — never a GET, never a
    rebuild."""
    mod = _load_api(tmp_path, monkeypatch)
    _seed_budget(tmp_path)
    llm = FakeLlm([{"contradicts": True, "reason": "two budgets"}])
    monkeypatch.setattr(mod, "get_llm", lambda: llm)

    client = _client(mod)
    r = client.post("/conflicts")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["conflicts"], body
    assert body["pairs"] >= 1
    assert client.get("/conflicts").status_code in (405, 404)
    assert len(llm.calls) >= 1


def test_the_route_reports_when_the_pass_finds_nothing(tmp_path, monkeypatch):
    mod = _load_api(tmp_path, monkeypatch)
    _seed(tmp_path, {"a.md": _BUDGET_A, "b.md": _GARDEN})
    llm = FakeLlm([{"contradicts": False, "reason": ""}])
    monkeypatch.setattr(mod, "get_llm", lambda: llm)

    r = _client(mod).post("/conflicts")
    assert r.status_code == 200, r.text
    assert r.json()["conflicts"] == []
    assert r.json()["pairs"] == 0


def test_the_route_without_a_model_says_so(tmp_path, monkeypatch):
    mod = _load_api(tmp_path, monkeypatch)
    _seed_budget(tmp_path)
    monkeypatch.setattr(mod, "get_llm", lambda: None)
    r = _client(mod).post("/conflicts")
    assert r.status_code == 503
    assert "model" in r.json()["detail"].lower()


def test_the_route_never_writes_to_the_corpus(tmp_path, monkeypatch):
    """The conflict pass reads the corpus and writes flags. It must not touch
    a source file."""
    mod = _load_api(tmp_path, monkeypatch)
    _seed_budget(tmp_path)
    corpus = tmp_path / "corpus"
    src = {p.name: p.read_bytes() for p in corpus.iterdir()}
    monkeypatch.setattr(mod, "get_llm", lambda: FakeLlm([{"contradicts": True, "reason": "x"}]))
    _client(mod).post("/conflicts")
    assert src == {p.name: p.read_bytes() for p in corpus.iterdir()}


def test_the_desktop_page_offers_the_pass():
    """The pass is on demand, so the page must offer the action — not run it on
    load. The button is the Review tab's affordance."""
    src = JS.read_text()
    assert "'/conflicts'" in src or '"/conflicts"' in src, "the page never calls /conflicts"
    assert "Find disagreements" in src, "the page offers no way to run the pass"
