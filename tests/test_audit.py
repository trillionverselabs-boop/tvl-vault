"""`scripts/review_audit.py` — the audit document the desktop cannot replace.

A decision this consequential has to be readable as a document: every item, its
actual text, the copy it is measured against, and a recommendation with its
reason. These tests guard the two ways the page could silently go blank.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

SCRIPT = ROOT / "scripts" / "review_audit.py"


def _load():
    spec = importlib.util.spec_from_file_location("_test_review_audit", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _row(**over):
    row = {
        "n": 1, "doc_id": "f" * 16, "flag": "unclear", "title": "scene2",
        "path": "/work/arena-demo-video/compositions/scene2-artifact.html",
        "kind": "html", "reason": "no extractable sections", "evidence": "",
        "rec_action": "edit", "rec_why": "This is pipeline output, not a source document.",
        "sections": [], "excerpt": "<script>alert(1)</script>", "copies": [],
        "section_count": 0, "sha": "ab" * 16,
    }
    row.update(over)
    return row


def test_a_corpus_script_tag_does_not_blank_the_page(tmp_path):
    """The unclear items *are* HTML scene files, so their excerpt can contain
    `<script>`. Unescaped it closes the audit's own inline script and every item
    disappears — the page loads, the counts read right, and nothing is there."""
    mod = _load()
    out = mod.build([_row()], tmp_path / "audit.html")
    html = out.read_text()

    assert html.count("</script>") == 1, "a corpus </script> closed the audit's own script"
    assert "const ITEMS" in html
    assert "document.getElementById('items')" in html
    # the data survived the escape
    assert json.loads(json.dumps(_row()))["excerpt"] == "<script>alert(1)</script>"


def test_the_audit_carries_the_decision_controls_and_the_index(tmp_path):
    mod = _load()
    rows = [
        _row(n=1, flag="duplicate", title="docs/RESEARCH-1.md",
             path="/home/lisacore/Projects/youtube-channel/docs/RESEARCH-1.md",
             kind="markdown", rec_action="confirm",
             reason="byte-identical copy also exists: /x/RESEARCH-2.md",
             copies=[{"name": "RESEARCH-2.md", "path": "/x/RESEARCH-2.md",
                      "listed": True, "title": "RESEARCH-2.md", "kind": "markdown"}],
             sections=[{"ord": 0, "title": "1. Keywords", "level": 2, "body": "seed table"}],
             section_count=10),
        _row(n=2),
    ]
    html = mod.build(rows, tmp_path / "audit.html").read_text()

    for label in ("Confirm", "Keep", "Edit"):
        assert f"data-act=\"{label.lower()}\"" in html, f"missing {label}"
    assert "Index of all 2 items" in html
    assert "1 duplicate" in html and "1 unclear" in html
    assert "MY RECOMMENDATION" in html
    # the duplicate's copy is named — a row without it is not reviewable
    assert "RESEARCH-2.md" in html


def test_collect_reads_the_profile_queue(tmp_path, monkeypatch):
    """End to end against a real (throwaway) index: the audit is built from the
    same queue the Review tab shows, not a second query that can drift."""
    from vault import index, paths, review

    monkeypatch.setenv("HERMES_VAULT_DB", str(tmp_path / "vault.db"))
    (tmp_path / "a.md").write_text("# Alpha\n\nbody\n")
    (tmp_path / "b.pdf").write_bytes(b"%PDF-1.4 empty")
    db = index.rebuild(tmp_path, tmp_path / "vault.db")
    review.write_flags(db, review.compute_flags(db))
    db.close()

    mod = _load()
    rows = mod.collect()

    assert [r["flag"] for r in rows] == ["unclear"]
    assert rows[0]["path"].endswith("b.pdf")
    assert rows[0]["rec_action"] in ("confirm", "keep", "edit")
    assert rows[0]["rec_why"]
