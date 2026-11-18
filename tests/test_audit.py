"""`scripts/review_audit.py` — the audit document the desktop cannot replace.

A decision this consequential has to be readable as a document, and readable by
a person rather than an engineer. These tests guard the ways it could silently go
wrong: a corpus excerpt containing `<script>`, items drawn by JS (the Hermes
desktop previews HTML without running scripts), and a queue query that drifts
from the Review tab.
"""

from __future__ import annotations

import importlib.util
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
        "short": "scene2-artifact.html", "kind": "html",
        "reason": "no extractable sections", "plain": "No sections could be read.",
        "rec": {"action": "edit", "plain": "This is a video build file, not a note.",
                "label": "MY RECOMMENDATION: NOT KNOWLEDGE"},
        "rec_action": "edit", "sections": [], "excerpt": "<script>x</script>",
        "copies": [], "diff": None,
        "about": {"kind": "html", "kind_plain": "a web page (HTML)", "size": 1204,
                  "sections": 0, "words": 0, "headings": [], "gist": ""},
    }
    row.update(over)
    return row


def _dup(**over):
    base = _row(
        n=1, flag="duplicate", title="docs/RESEARCH-1.md",
        path="/home/lisacore/Projects/youtube-channel/docs/RESEARCH-1.md",
        short="RESEARCH-1.md", kind="markdown",
        reason="byte-identical copy also exists: /x/RESEARCH-2.md",
        plain="Two files hold the same words. Only one belongs in the index.",
        rec={"action": "confirm",
             "plain": "Keep RESEARCH-1.md. The other one is the same file re-saved.",
             "label": "MY RECOMMENDATION: KEEP RESEARCH-1.MD"},
        rec_action="confirm",
        sections=[{"ord": 0, "title": "1. Keywords", "level": 2, "body": "seed table",
                   "words": 3}],
        excerpt="",
        copies=[{"name": "RESEARCH-2.md", "path": "/x/RESEARCH-2.md",
                 "listed": False, "doc_id": "", "title": "RESEARCH-2.md",
                 "kind": "markdown"}],
        diff={"pairs": [{"title": "1. Keywords", "a": "seed table", "b": "seed table",
                         "status": "same"}],
              "only_a": [], "only_b": [], "changed": 0, "same": 1, "identical": True},
        about={"kind": "markdown", "kind_plain": "a markdown note", "size": 9000,
               "sections": 10, "words": 2380,
               "headings": ["1. Keywords", "2. Competitor landscape"],
               "gist": "First real research pass — free sources, collected 2026-11-12."})
    base.update(over)
    return base


def test_a_corpus_script_tag_does_not_blank_the_page(tmp_path):
    """The unclear items *are* HTML scene files, so their excerpt can contain
    `<script>`. Unescaped it closes the audit's own inline script and every item
    disappears — the page loads, the counts read right, and nothing is there."""
    mod = _load()
    html = mod.build([_row()], tmp_path / "audit.html").read_text()

    assert html.count("</script>") == 1, "a corpus </script> closed the audit's own script"
    assert "const ITEMS" in html
    assert 'details class="item' in html


def test_the_items_are_static_html_not_drawn_by_script(tmp_path):
    """The Hermes desktop previews HTML without running scripts. If the items are
    drawn by JS the file reads as a blank document there — the counts show, the
    index shows, and there is nothing to review."""
    mod = _load()
    html = mod.build([_row(n=1), _row(n=2)], tmp_path / "audit.html").read_text()

    assert html.count('details class="item') == 2, "items are not in the static HTML"
    assert html.count('class="recbox"') == 2
    assert "innerHTML = ITEMS" not in html, "the page still draws its content with JS"
    assert "<script>" in html and html.count("</script>") == 1


def test_each_item_says_what_it_is_and_what_differs(tmp_path):
    """A filename is not an identity, and the unit of review is the section."""
    mod = _load()
    html = mod.build([_dup()], tmp_path / "audit.html").read_text()

    for heading in ("What this document is", "What needs a decision",
                    "Compare them, section by section", "My recommendation"):
        assert heading in html, f"missing: {heading}"

    # what it is, from its own words
    assert "a markdown note" in html and "10 sections" in html
    assert "2,380 words" in html
    assert "First real research pass" in html
    assert "1. Keywords" in html and "2. Competitor landscape" in html

    # the comparison, and the verdict when nothing differs
    assert "This file: RESEARCH-1.md" in html and "The other file: RESEARCH-2.md" in html
    assert "Every section is word-for-word the same" in html

    # the buttons name the files, so the choice is concrete
    assert "Keep RESEARCH-1.md" in html and "Keep RESEARCH-2.md" in html
    assert "Leave for later" in html


def test_a_differing_section_is_highlighted(tmp_path):
    mod = _load()
    row = _dup(diff={"pairs": [{"title": "One", "a": "alpha", "b": "CHANGED",
                                "status": "changed"}],
                     "only_a": [], "only_b": [{"title": "Three", "body": "new"}],
                     "changed": 1, "same": 0, "identical": False})
    html = mod.build([row], tmp_path / "audit.html").read_text()

    assert 'class="crow changed"' in html, "the differing section is not highlighted"
    assert "differs" in html
    assert 'class="crow onlyb"' in html and "only in the other file" in html
    assert "1 section differ" in html


def test_the_audit_is_batched_in_tens(tmp_path):
    mod = _load()
    html = mod.build([_row(n=i) for i in range(1, 23)], tmp_path / "audit.html").read_text()

    assert "Items 1–10" in html and "Items 11–20" in html and "Items 21–22" in html


def test_the_filter_works_without_scripts(tmp_path):
    """Clicking a count must narrow the list, and it must not need JS."""
    mod = _load()
    html = mod.build([_dup(), _row(n=2)], tmp_path / "audit.html").read_text()

    assert '<input class="fl" type="radio" name="filter" id="fl-dup">' in html
    assert "#fl-dup:checked ~ .items .item:not(.flag-duplicate)" in html
    assert "#fl-dup:checked ~ .items .batch:not(:has(.flag-duplicate))" in html
    assert "Duplicates 1" in html


def test_collect_reads_the_profile_queue(tmp_path, monkeypatch):
    """End to end against a real (throwaway) index: the audit is built from the
    same queue the Review tab shows, not a second query that can drift."""
    from vault import index, review

    monkeypatch.setenv("HERMES_VAULT_DB", str(tmp_path / "vault.db"))
    (tmp_path / "a.md").write_text("# Alpha\n\nbody\n")
    (tmp_path / "b.pdf").write_bytes(b"%PDF-1.4 empty")
    db = index.rebuild(tmp_path, tmp_path / "vault.db")
    review.write_flags(db, review.compute_flags(db))
    db.close()

    rows = _load().collect()

    assert [r["flag"] for r in rows] == ["unclear"]
    assert rows[0]["path"].endswith("b.pdf")
    assert rows[0]["rec"]["label"]
    assert rows[0]["about"]["kind_plain"]
