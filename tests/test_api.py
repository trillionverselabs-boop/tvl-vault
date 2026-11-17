"""The dashboard backend (`dashboard/plugin_api.py`).

FastAPI's ``TestClient`` runs the router in-process, so these tests exercise the
real routes. ``HERMES_HOME`` is pointed at a throwaway tree and the DB path is
overridden, so nothing here touches the profile's real ``vault.db`` or the
corpus. The desktop surface (`desktop/plugin.js`) is checked by its own test.
"""

from __future__ import annotations

import importlib.util
import json
import re
import sqlite3
import sys
import types
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
API = ROOT / "dashboard" / "plugin_api.py"
JS = ROOT / "desktop" / "plugin.js"

sys.path.insert(0, str(ROOT / "src"))

from vault import index  # noqa: E402


def _load_api(tmp_path: Path, monkeypatch):
    """Import the router the way the dashboard loader does — standalone, by spec."""
    monkeypatch.setenv("HERMES_VAULT_DB", str(tmp_path / "vault.db"))
    spec = importlib.util.spec_from_file_location("_test_tvl_vault_api", API)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["_test_tvl_vault_api"] = mod
    spec.loader.exec_module(mod)
    return mod


def _seed(tmp_path: Path) -> Path:
    """Two documents: one with sections, one empty (so it is flagged unclear)."""
    (tmp_path / "alpha.md").write_text("# Alpha Doctrine\n\nsabotage contest logic\n")
    (tmp_path / "beta.pdf").write_bytes(b"%PDF-1.4 empty")
    db = index.rebuild(tmp_path, tmp_path / "vault.db")
    return tmp_path / "vault.db"


@pytest.fixture()
def api(tmp_path, monkeypatch):
    db_path = _seed(tmp_path)
    mod = _load_api(tmp_path, monkeypatch)
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    app = FastAPI()
    app.include_router(mod.router)
    return mod, TestClient(app), db_path


def test_health_names_the_data_root(api):
    mod, client, _ = api
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["ok"] is True
    assert r.json()["data_root"]


def test_stats_counts_documents_and_sections(api):
    _, client, _ = api
    s = client.get("/stats").json()
    assert s["documents"] == 2
    assert s["sections"] == 1


def test_graph_returns_document_nodes_and_contains_edges(api):
    _, client, _ = api
    g = client.get("/graph").json()
    assert len(g["nodes"]) == 3          # 2 documents + 1 section
    assert any(e["kind"] == "contains" for e in g["edges"])
    assert all("id" in n and "label" in n for n in g["nodes"])


def test_graph_edges_all_resolve_to_nodes(api):
    """Every edge must name two nodes — a dangling edge cannot be drawn or clicked."""
    _, client, _ = api
    g = client.get("/graph").json()
    ids = {n["id"] for n in g["nodes"]}
    dangling = [e for e in g["edges"] if e["source"] not in ids or e["target"] not in ids]
    assert dangling == []


def test_search_returns_a_section_with_provenance(api):
    _, client, _ = api
    r = client.get("/search", params={"q": "sabotage"}).json()
    assert r["results"] and r["results"][0]["doc_title"] == "Alpha Doctrine"


def test_review_queue_carries_a_flag_and_a_reason(api):
    _, client, _ = api
    rows = client.get("/review").json()["flags"]
    assert rows, "the empty PDF must be flagged"
    assert any(row["flag"] == "unclear" for row in rows)
    assert all(row["title"] for row in rows)


def test_document_detail_has_sections(api):
    _, client, _ = api
    doc_id = client.get("/graph").json()["nodes"][0]["id"]
    d = client.get(f"/document/{doc_id}").json()
    assert d["document"]["doc_id"] == doc_id
    assert isinstance(d["sections"], list)


def test_the_review_item_shows_the_text_behind_a_row(api):
    """A queue row carries a filename and a reason; the decision needs the text."""
    _, client, _ = api
    row = next(r for r in client.get("/review").json()["flags"] if r["flag"] == "unclear")

    out = client.get(f"/review/{row['doc_id']}", params={"flag": row["flag"]}).json()

    assert out["doc_id"] == row["doc_id"]
    assert out["reason"] == row["reason"]
    assert out["recommendation"]["action"] in ("confirm", "keep", "edit")
    assert out["recommendation"]["why"], "a recommendation with no reason is not reviewable"
    assert isinstance(out["document"]["sections"], list)


def test_a_duplicate_row_names_the_copy_it_is_measured_against(api):
    _, client, db_path = api
    root = db_path.parent
    (root / "alpha-copy.md").write_text("# Alpha Doctrine\n\nsabotage contest logic\n")
    index.rebuild(root, db_path)

    row = next(r for r in client.get("/review").json()["flags"] if r["flag"] == "duplicate")

    out = client.get(f"/review/{row['doc_id']}", params={"flag": "duplicate"}).json()

    assert out["document"]["counterparts"], "the copy's path is the whole point"
    assert {c["name"] for c in out["document"]["counterparts"]} == {"alpha.md"}
    # A clean name is a judgement call, not a rule: leave it to the human.
    assert out["recommendation"]["action"] == "keep"


def test_an_unknown_review_item_is_a_404(api):
    _, client, _ = api
    assert client.get("/review/ffffffffffffffff").status_code == 404
    assert client.get("/review/not-a-doc-id").status_code == 400


def test_bad_doc_id_is_refused(api):
    _, client, _ = api
    assert client.get("/document/../../etc/passwd").status_code in (400, 404)
    assert client.get("/document/not-a-doc-id").status_code == 400


def test_unbuilt_vault_is_a_404_not_a_crash(tmp_path, monkeypatch):
    mod = _load_api(tmp_path, monkeypatch)          # no seed: no vault.db
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    app = FastAPI()
    app.include_router(mod.router)
    client = TestClient(app, raise_server_exceptions=False)
    assert client.get("/stats").status_code == 404


def test_desktop_page_registers_the_four_tabs_and_stays_inside_the_sdk():
    src = JS.read_text()
    assert "ROUTES_AREA" in src and "SIDEBAR_NAV_AREA" in src
    assert "ctx.rest(" in src
    for tab in ("Graph", "Wall", "Ask", "Review"):
        assert tab in src, f"tab missing: {tab}"
    # the loader refuses these; a plugin that uses them does not install
    assert "eval(" not in src
    assert "document.write" not in src
    # the approved mockup's palette and its force layout must be the ones shipped
    assert "#05070d" in src            # canvas token
    assert "function simulate(" in src


def test_manifest_names_the_backend():
    manifest = json.loads((ROOT / "dashboard" / "manifest.json").read_text())
    assert manifest["name"] == "tvl-vault"
    assert manifest["api"] == "plugin_api.py"


# ── the review queue is a decision record, not a filter ───────────────────

def _flagged_doc(client):
    rows = client.get("/review").json()["flags"]
    assert rows, "seed must leave something on the queue"
    return rows[0]


def test_confirming_a_flag_takes_the_document_off_the_queue(api):
    _, client, _ = api
    row = _flagged_doc(client)
    r = client.post("/review", json={"doc_id": row["doc_id"], "flag": row["flag"],
                                     "action": "confirm"})
    assert r.status_code == 200
    assert r.json()["correction"]["action"] == "confirm"
    assert row["doc_id"] not in {f["doc_id"] for f in r.json()["queue"]}


def test_keep_leaves_the_document_on_the_queue(api):
    _, client, _ = api
    row = _flagged_doc(client)
    r = client.post("/review", json={"doc_id": row["doc_id"], "flag": row["flag"],
                                     "action": "keep"})
    assert r.status_code == 200
    assert row["doc_id"] in {f["doc_id"] for f in r.json()["queue"]}


def test_an_edit_without_a_note_is_refused(api):
    _, client, _ = api
    row = _flagged_doc(client)
    r = client.post("/review", json={"doc_id": row["doc_id"], "flag": row["flag"],
                                     "action": "edit"})
    assert r.status_code == 400


def test_a_decision_never_touches_the_source_file(api):
    """Rule 4: corrections are a record, not a rewrite of the corpus."""
    mod, client, db_path = api
    row = _flagged_doc(client)
    src = Path(row["path"])
    before = src.read_bytes() if src.exists() else None
    client.post("/review", json={"doc_id": row["doc_id"], "flag": row["flag"],
                                 "action": "edit", "note": "rewrite the budget line"})
    if before is not None:
        assert src.read_bytes() == before, "a source file was rewritten by a decision"


def test_the_correction_log_lists_decisions_newest_first(api):
    _, client, _ = api
    row = _flagged_doc(client)
    client.post("/review", json={"doc_id": row["doc_id"], "flag": row["flag"],
                                 "action": "confirm"})
    log = client.get("/corrections").json()["corrections"]
    assert log and log[0]["doc_id"] == row["doc_id"]


def test_the_desktop_review_tab_offers_a_decision_per_flag():
    """The approved mockup's Review row has three actions; the shipped page
    must not drop the decision (the whole point of the tab)."""
    src = _code_only(JS.read_text())
    assert "action: 'confirm'" in src or 'action:"confirm"' in src, "no confirm action"
    # The mockup's three labels, in the shipped wording: `Mark current` is the
    # confirm action (its label is per-flag, so the words appear in its button).
    for label in ("Keep", "Confirm", "Edit"):
        assert label in src, f"review action missing: {label}"
    # the decision must be posted to the backend, not only held in local state
    assert re.search(r"restRef\.current\(\s*'/review'", src), "decision is not posted"
    assert re.search(r"method:\s*'POST'", src), "the decision is not a POST"


def test_the_review_row_shows_the_text_not_just_the_filename():
    """A reviewer cannot decide from a path. The row must offer the document's
    own text, and that request must go to the per-document comparison route."""
    src = _code_only(JS.read_text())
    assert "Show the text" in src, "the row does not offer the text"
    assert re.search(r"/review/' \+ docId", src), "the comparison is not fetched per document"
    assert "recommendation" in src, "no recommendation is shown"
    assert "counterparts" in src, "the duplicate's copy is not shown"


def test_the_left_rail_counts_what_is_left_to_decide():
    """The rail is titled "needs review", so it must agree with the Review tab.
    Counting every flag ever recorded disagreed: 95 duplicate flags with 30
    already decided read as "31 to review" when 1 was left."""
    src = _code_only(JS.read_text())
    assert "for (const f of queue)" in src, "the rail counts flags, not the queue"
    assert "corpusCounts" in src, "the corpus KPI lost its own counts"


def test_every_area_and_route_the_page_registers_is_inside_the_plugin():
    src = JS.read_text()
    # the page is served at /tvl-vault, the API namespace is /api/plugins/tvl-vault/
    assert "/tvl-vault" in src
    assert "/graph" in src and "/stats" in src and "/wall" in src and "/review" in src


def test_the_approved_look_is_what_ships():
    """The palette and the layout are Lisa's approved mockup, not a redesign."""
    mockup = (ROOT / "docs" / "mockup" / "vault-mockup.html").read_text()
    src = JS.read_text()
    for token in ("#05070d", "#0a0f18", "#f59e0b", "#22d3ee", "#a78bfa", "#34d399", "#fbbf24"):
        assert token in mockup, f"mockup no longer defines {token}"
        assert token in src, f"desktop page dropped the approved token {token}"
    # the force layout's own constants, verbatim
    for snippet in ("const f = 620 / d2", "e.kind === 'contains' ? 78", "n.vx *= 0.82"):
        assert snippet in mockup, f"mockup layout changed: {snippet}"
        assert snippet in src, f"desktop page drifted from the approved layout: {snippet}"


def test_plugin_manifest_declares_no_dependencies():
    """A non-empty dependency list makes the desktop's non-interactive install abort."""
    text = (ROOT / "plugin.yaml").read_text()
    assert not re.search(r"^\s*python_dependencies\s*:", text, re.M), "declares python_dependencies"
    assert not re.search(r"^\s*capabilities\s*:", text, re.M), "declares capabilities"
    assert re.search(r"^name:\s*tvl-vault\s*$", text, re.M)
    pyproject = (ROOT / "pyproject.toml").read_text()
    assert "dependencies = []" in pyproject


# ── the page may only call verbs the SDK actually declares ───────────────────

# The desktop lint refuses dangerous *constructs* (eval, remote import, app-DOM
# reach) but not an invented API: `ctx.files.reveal(...)` is ordinary JS and
# passes every lint, then fails at the click. This list is the SDK document's
# own verb table (desktop-plugin-sdk.md, `PluginContext` / `ctx.os` / `ctx.files`).
SDK_VERBS = {
    "os": {"notify", "openExternal", "revealPath", "writeClipboard"},
    "files": {"requestFolder", "release", "folders", "list", "readText",
              "writeText", "rename", "trash", "readDataUrl", "stat"},
    "pet": {"say", "clear"},
    "storage": {"get", "set", "remove"},
    "preview": {"executeJavaScript"},
}


def _code_only(src: str) -> str:
    """Drop // and /* */ comments, so a comment quoting a bad verb cannot fail the scan."""
    src = re.sub(r"/\*.*?\*/", " ", src, flags=re.S)
    return re.sub(r"(?<![:\w])//[^\n]*", " ", src)


def test_no_invented_ctx_verb_is_called():
    """Every `ctx.<ns>.<verb>(` in the page must be a verb the SDK declares."""
    src = _code_only(JS.read_text())
    invented = []
    for ns, verb in re.findall(r"\bctx\.([A-Za-z_]\w*)\.([A-Za-z_]\w*)\(", src):
        if verb not in SDK_VERBS.get(ns, set()):
            invented.append(f"ctx.{ns}.{verb}")
    assert not invented, f"desktop page calls SDK verbs that do not exist: {sorted(set(invented))}"


def test_open_the_source_document_reveals_a_path():
    """Reveal is `ctx.os.revealPath`, and it takes the file path, not the doc id."""
    src = _code_only(JS.read_text())
    body = src[src.index("function openDocument("):]
    body = body[:body.index("\n  }")]
    assert "ctx.os.revealPath(sel.path)" in body, body


def test_every_registered_area_is_a_real_sdk_area():
    """A contribution to an area the SDK does not publish never renders."""
    src = JS.read_text()
    areas = set(re.findall(r"area:\s*([A-Za-z_0-9_]+)", src))
    assert areas == {"ROUTES_AREA", "SIDEBAR_NAV_AREA"}, areas


# ── Ask: a cited answer on the session model ───────────────────────────────

class _FakeLlm:
    """Stands in for `ctx.llm`; records the one call it received."""

    def __init__(self, text):
        self.text = text
        self.calls = []

    def complete(self, messages, **kw):
        self.calls.append({"messages": messages, "kw": kw})
        return types.SimpleNamespace(text=self.text)


def test_ask_refuses_an_empty_question(api):
    _, client, _ = api
    assert client.post("/ask", json={"question": "   "}).status_code == 400


def test_ask_without_a_bound_model_says_so(api, monkeypatch):
    """No model bound in this process: a clear 503, not a wrong answer."""
    mod, client, _ = api
    monkeypatch.setattr(mod, "get_llm", lambda: None)
    r = client.post("/ask", json={"question": "what does the doctrine say?"})
    assert r.status_code == 503
    assert "model" in r.json()["detail"].lower()


def test_ask_returns_the_answer_and_its_citations(api, monkeypatch):
    mod, client, _ = api
    llm = _FakeLlm("The doctrine says sabotage lowers output. [1]")
    monkeypatch.setattr(mod, "get_llm", lambda: llm)
    r = client.post("/ask", json={"question": "what does the doctrine say about sabotage?"})
    assert r.status_code == 200
    body = r.json()
    assert "sabotage lowers output" in body["answer"]
    assert body["question"].startswith("what does the doctrine")
    assert body["citations"] and body["citations"][0]["title"]
    assert body["citations"][0]["doc"] == "Alpha Doctrine"
    assert len(llm.calls) == 1


def test_ask_runs_the_session_model_without_an_override(api, monkeypatch):
    """No provider/model override: that needs a capability the plugin lacks."""
    mod, client, _ = api
    llm = _FakeLlm("answer [1]")
    monkeypatch.setattr(mod, "get_llm", lambda: llm)
    client.post("/ask", json={"question": "sabotage"})
    kw = llm.calls[0]["kw"]
    assert kw.get("model") in (None, "") and kw.get("provider") in (None, "")
    assert kw.get("temperature") == 0


def test_ask_passes_the_question_and_numbered_passages_to_the_model(api, monkeypatch):
    mod, client, _ = api
    llm = _FakeLlm("answer [1]")
    monkeypatch.setattr(mod, "get_llm", lambda: llm)
    client.post("/ask", json={"question": "what does the doctrine say about sabotage?"})
    content = llm.calls[0]["messages"][0]["content"]
    assert "sabotage contest logic" in content
    assert "[1]" in content
    assert "Do not invent" in content


def test_ask_survives_a_model_failure(api, monkeypatch):
    class Boom:
        def complete(self, messages, **kw):
            raise RuntimeError("the model call timed out")

    mod, client, _ = api
    monkeypatch.setattr(mod, "get_llm", lambda: Boom())
    body = client.post("/ask", json={"question": "sabotage"}).json()
    assert body["answer"] == ""
    assert "timed out" in body["error"]


def test_ask_never_writes_to_the_corpus(api, monkeypatch):
    """An answer is a read: the source documents and the index rows are unchanged.

    Compared by content, not by mtime — opening the SQLite file touches its WAL
    even for a SELECT.
    """
    mod, client, db_path = api
    llm = _FakeLlm("answer [1]")
    monkeypatch.setattr(mod, "get_llm", lambda: llm)
    corpus = Path(str(db_path)).parent
    sources = {p.name: p.read_bytes() for p in corpus.iterdir()
               if p.suffix in (".md", ".pdf")}
    db = sqlite3.connect(db_path)
    before = db.execute("SELECT COUNT(*) FROM documents").fetchone()[0], \
        db.execute("SELECT COUNT(*) FROM sections").fetchone()[0]
    client.post("/ask", json={"question": "sabotage"})
    after = db.execute("SELECT COUNT(*) FROM documents").fetchone()[0], \
        db.execute("SELECT COUNT(*) FROM sections").fetchone()[0]
    db.close()
    assert before == after
    assert sources == {p.name: p.read_bytes() for p in corpus.iterdir()
                       if p.suffix in (".md", ".pdf")}


def test_the_register_hook_binds_the_session_model():
    """`register(ctx)` must put `ctx.llm` where the routes can find it."""
    import types as _types

    import vault  # noqa: F401  (ensures src/ is importable)

    plugin_root = ROOT
    spec = importlib.util.spec_from_file_location("_test_tvl_vault_root", plugin_root / "__init__.py")
    root = importlib.util.module_from_spec(spec)
    sys.modules["_test_tvl_vault_root"] = root
    spec.loader.exec_module(root)

    # a fresh holder, so the test does not depend on import order
    for key in [k for k in sys.modules if k == root._LLM_HOLDER_KEY]:
        del sys.modules[key]
    ctx = _types.SimpleNamespace(llm=_FakeLlm("bound [1]"),
                                 log=lambda msg: None)
    root.register(ctx)
    holder = sys.modules[root._LLM_HOLDER_KEY]
    assert holder.llm is ctx.llm, "register() did not bind the session model"


def test_the_root_and_the_backend_share_one_holder_key():
    """Two different keys would silently leave /ask with no model."""
    spec = importlib.util.spec_from_file_location("_test_tvl_vault_root2", ROOT / "__init__.py")
    root = importlib.util.module_from_spec(spec)
    sys.modules["_test_tvl_vault_root2"] = root
    spec.loader.exec_module(root)
    assert root._LLM_HOLDER_KEY == "_tvl_vault_llm_binding"
    assert "_tvl_vault_llm_binding" in (ROOT / "dashboard" / "plugin_api.py").read_text()


def test_the_desktop_ask_tab_calls_the_backend():
    """The Ask tab must be wired to /ask, not left as the mockup's placeholder."""
    src = _code_only(JS.read_text())
    assert "'/ask'" in src or '"/ask"' in src, "the page never calls /ask"
    assert "Task 7" not in JS.read_text(), "the Ask tab is still the placeholder"
    # the answer is rendered with its citations, as the mockup shows
    assert "cites" in src and "answer" in src


# ── the wall's picture half (Task 9) ────────────────────────────────────────

def _png(width: int, height: int, tag: bytes = b"\x11") -> bytes:
    """A real PNG header + a real IDAT chunk, written by hand (no Pillow)."""
    import struct
    import zlib

    raw = b"".join(b"\x00" + tag * width for _ in range(height))

    def chunk(tag_bytes: bytes, data: bytes) -> bytes:
        body = tag_bytes + data
        return (struct.pack(">I", len(data)) + body
                + struct.pack(">I", zlib.crc32(body)))

    return (b"\x89PNG\r\n\x1a\n"
            + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(raw, 9))
            + chunk(b"IEND", b""))


def _seed_images(tmp_path: Path) -> Path:
    """One real portrait, one junk screenshot, one note — then an index over them.

    The note is written here rather than by `_seed` because that helper also
    drops a byte-identical `beta.pdf`, which would leave the note flagged as a
    duplicate and hide the status these tests are reading.
    """
    (tmp_path / "calvin.png").write_bytes(_png(640, 480, tag=b"\x11"))
    (tmp_path / "plugintest5a.png").write_bytes(_png(800, 600, tag=b"\x22"))
    (tmp_path / "doctrine.md").write_text("# Alpha Doctrine\n\nsabotage contest logic\n")
    return index.rebuild(tmp_path, tmp_path / "vault.db")


def test_the_wall_serves_the_pictures_the_wall_exists_for(tmp_path, monkeypatch):
    """The user's 'pretty visual items' are the portraits; the wall must carry
    them, with dimensions read from the file rather than from a library."""
    _seed_images(tmp_path)
    mod = _load_api(tmp_path, monkeypatch)
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    app = FastAPI()
    app.include_router(mod.router)
    client = TestClient(app)

    w = client.get("/wall").json()
    assert [Path(i["path"]).name for i in w["images"]] == ["calvin.png"]
    assert w["images"][0]["width"] == 640 and w["images"][0]["height"] == 480
    assert w["junk_count"] == 1
    # the junk screenshot is not in the document list either
    assert "plugintest5a" not in {d["title"] for d in w["documents"]}


def test_the_wall_captions_only_when_asked(tmp_path, monkeypatch):
    """Captions are a model call; the default wall must not spend one."""
    _seed_images(tmp_path)
    mod = _load_api(tmp_path, monkeypatch)
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    app = FastAPI()
    app.include_router(mod.router)
    client = TestClient(app)

    called = []

    class Spy:
        def complete_structured(self, **kw):
            called.append(kw)
            return types.SimpleNamespace(text="a portrait")

    monkeypatch.setattr(mod, "get_llm", lambda: Spy())
    plain = client.get("/wall").json()
    assert called == [], "the default wall called the model"
    assert plain["captions"] == 0

    captioned = client.get("/wall", params={"with_captions": 1}).json()
    assert len(called) == 1
    assert captioned["captions"] == 1 and captioned["images"][0]["caption"] == "a portrait"


def test_the_images_route_is_dimensions_without_a_model(tmp_path, monkeypatch):
    _seed_images(tmp_path)
    mod = _load_api(tmp_path, monkeypatch)
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    app = FastAPI()
    app.include_router(mod.router)
    client = TestClient(app)
    monkeypatch.setattr(mod, "get_llm", lambda: None)

    body = client.get("/images").json()
    assert [Path(i["path"]).name for i in body["images"]] == ["calvin.png"]
    assert body["images"][0]["caption"] == "" and body["images"][0]["width"] == 640


def test_an_image_carries_no_status_in_the_graph(tmp_path, monkeypatch):
    """A picture makes no claim, so it carries no flag. The UI reads that as an
    artifact rather than asserting the image is verified doctrine."""
    _seed_images(tmp_path)
    mod = _load_api(tmp_path, monkeypatch)
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    app = FastAPI()
    app.include_router(mod.router)
    client = TestClient(app)

    nodes = client.get("/graph").json()["nodes"]
    image = next(n for n in nodes if n["group"] == "image")
    assert image["flag"] is None, image
    note = next(n for n in nodes if n["group"] == "markdown")
    assert note["flag"] == "current", note


def test_the_file_route_serves_only_what_the_index_knows(tmp_path, monkeypatch):
    """The wall's <img> must not become an open file server."""
    _seed_images(tmp_path)
    mod = _load_api(tmp_path, monkeypatch)
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    app = FastAPI()
    app.include_router(mod.router)
    client = TestClient(app)

    r = client.get("/file", params={"path": str(tmp_path / "calvin.png")})
    assert r.status_code == 200
    assert r.content == (tmp_path / "calvin.png").read_bytes()
    assert r.headers["content-type"].startswith("image/")

    assert client.get("/file", params={"path": "/etc/passwd"}).status_code == 404
    assert client.get("/file").status_code == 400
    assert client.get("/file", params={"path": str(tmp_path / "absent.png")}).status_code == 404


def test_the_wall_page_shows_the_pictures_and_not_the_screenshots():
    """Task 9's acceptance: the wall is the 'pretty visual items' surface."""
    src = _code_only(JS.read_text())
    assert "wall.images" in src, "the wall pane never reads the image half"
    assert "vz-thumb" in src, "the wall does not render the picture itself"
    assert "/file?path=" in src, "the wall's image has no source route"
    assert "/images?with_captions=1" in src, "captions are never asked for"
    # the junk note stays, and junk is never listed
    assert "test screenshots are indexed but kept out of this wall" in src


def test_an_image_is_labelled_as_an_image_not_as_current():
    """A picture makes no claim; the badge must not assert it is verified."""
    src = _code_only(JS.read_text())
    assert "FLAG.artifact" in src, "no artifact status for images"
    assert "group === 'image' ? FLAG.artifact" in src

