"""Backend namespace /api/plugins/tvl-vault/ — mounted by the dashboard loader.

The loader imports this file standalone (not as part of the agent package), so
`src/vault` is brought in by importing the plugin root package, which puts
`src/` on `sys.path` itself. Never put the plugin directory on `sys.path`: this
plugin ships a package named `vault`, and a top-level module that shadows a host
module is how `upfront`'s `tools.py` broke the gateway.

Paths (all read-only; the index is rebuilt by `vault rebuild`, never by a route):
  GET  /health                 liveness + the data root
  GET  /stats                  document / section / duplicate / flag counts
  GET  /graph                  nodes (documents + sections) and edges
  GET  /search?q=…             BM25 sections with provenance
  GET  /review                 the non-current flags, worst first
  GET  /document/{doc_id}      one document and its sections
  GET  /wall                   the card wall (documents, junk collapsed)
  GET  /images[?with_captions=1]  the picture half: dimensions + captions
  GET  /file?path=…            one corpus file's bytes (the wall's <img>)
  POST /ask                    a cited answer, on the session model
"""

from __future__ import annotations

import hashlib
import importlib
import importlib.util
import json
import re
import sqlite3
import sys
import types
from pathlib import Path

from fastapi import APIRouter, HTTPException

_PLUGIN_ROOT = Path(__file__).resolve().parent.parent
_PKG_NAME = "_tvl_vault_dashboard_" + hashlib.sha256(
    str(_PLUGIN_ROOT).encode("utf-8")).hexdigest()[:16]

# The host-owned model. `ctx.llm` only exists inside the agent half's
# `register(ctx)`, and this file is imported standalone under a different module
# name — so a module global here would be invisible there. `sys.modules` is
# process-wide, so a holder under a fixed key is the one piece of state both
# halves share (the same shape as strategic-arena's llm_binding).
_LLM_HOLDER_KEY = "_tvl_vault_llm_binding"


def set_llm(llm) -> None:
    """Bind the session model. Called from `register(ctx)` with `ctx.llm`."""
    holder = sys.modules.get(_LLM_HOLDER_KEY)
    if holder is None:
        holder = types.ModuleType(_LLM_HOLDER_KEY)
        sys.modules[_LLM_HOLDER_KEY] = holder
    holder.llm = llm


def get_llm():
    """The bound session model, or None when the agent half is not loaded."""
    return getattr(sys.modules.get(_LLM_HOLDER_KEY), "llm", None)


def _load_package():
    """Import the plugin root package from this directory, without touching sys.path."""
    mod = sys.modules.get(_PKG_NAME)
    if mod is not None:
        return mod
    spec = importlib.util.spec_from_file_location(
        _PKG_NAME, _PLUGIN_ROOT / "__init__.py",
        submodule_search_locations=[str(_PLUGIN_ROOT)])
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load the plugin package from {_PLUGIN_ROOT}")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[_PKG_NAME] = mod
    spec.loader.exec_module(mod)
    return mod


_load_package()
# `vault` lives under `src/`, which the plugin root package put on sys.path.
# Import it as the plain package it is — the same module object the tests and the
# CLI use, so one index, one code path.
_paths = importlib.import_module("vault.paths")
_index = importlib.import_module("vault.index")
_review = importlib.import_module("vault.review")
_qa = importlib.import_module("vault.qa")
_images = importlib.import_module("vault.images")

router = APIRouter()

_DOC_ID = re.compile(r"[0-9a-f]{16}")


def _ensure_flags(db: sqlite3.Connection) -> None:
    """The `flags` table is written by the rebuild command; a DB built by
    `index.rebuild` alone (a test, a partial build) has documents but no flags.
    Compute them here rather than 500-ing — the flags are deterministic."""
    has = db.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='flags'").fetchone()
    if has:
        return
    _review.write_flags(db, _review.compute_flags(db))


def _db() -> sqlite3.Connection:
    p = _paths.vault_db_path()
    if not p.exists():
        raise HTTPException(404, "vault not built — run `./scripts/rebuild.sh`")
    db = sqlite3.connect(p)
    db.row_factory = sqlite3.Row
    _ensure_flags(db)
    return db


def _flag_map(db: sqlite3.Connection) -> dict[str, str]:
    """doc_id -> its worst flag. A document carries at most one visible status.

    An image has no flag at all (`review.compute_flags` leaves it out): a picture
    makes no claim, so "current" would be a false statement about it. The wall
    and the graph read that as `None` and show it as an artifact instead.
    """
    worst = {"conflict": 0, "outdated": 1, "duplicate": 2, "unclear": 3, "current": 4}
    out: dict[str, str] = {}
    image_ids = {r[0] for r in db.execute("SELECT doc_id FROM documents WHERE kind='image'")}
    for row in db.execute("SELECT doc_id, flag FROM flags"):
        prev = out.get(row["doc_id"])
        if prev is None or worst.get(row["flag"], 9) < worst.get(prev, 9):
            out[row["doc_id"]] = row["flag"]
    return {k: v for k, v in out.items() if k not in image_ids}


@router.get("/health")
async def health() -> dict:
    return {"ok": True, "data_root": str(_paths.data_root()),
            "db": str(_paths.vault_db_path())}


@router.get("/stats")
async def stats() -> dict:
    db = _db()
    flags = [dict(r) for r in db.execute(
        "SELECT flag, COUNT(*) AS n FROM flags GROUP BY flag")]
    return {
        "documents": db.execute("SELECT COUNT(*) FROM documents").fetchone()[0],
        "sections": db.execute("SELECT COUNT(*) FROM sections").fetchone()[0],
        "duplicates": db.execute("SELECT COUNT(*) FROM duplicates").fetchone()[0],
        "images": db.execute("SELECT COUNT(*) FROM documents WHERE kind='image'").fetchone()[0],
        "flags": flags,
    }


@router.get("/graph")
async def graph() -> dict:
    """Nodes = documents + sections; edges = contains, depends-on, duplicates."""
    db = _db()
    flags = _flag_map(db)
    nodes: list[dict] = []
    for d in db.execute("SELECT doc_id,title,kind,path FROM documents"):
        nodes.append({"id": d["doc_id"], "label": d["title"], "kind": "document",
                      "group": d["kind"], "path": d["path"],
                      # an image makes no claim, so it has no status; the UI shows
                      # it as an artifact rather than "current"
                      "flag": flags.get(d["doc_id"]) if d["kind"] != "image"
                      else None})
    for s in db.execute("SELECT section_id,doc_id,title FROM sections ORDER BY ord"):
        nodes.append({"id": s["section_id"], "label": s["title"], "kind": "section",
                      "group": s["doc_id"], "doc": s["doc_id"]})
    edges: list[dict] = []
    for s in db.execute("SELECT section_id,doc_id FROM sections"):
        edges.append({"source": s["doc_id"], "target": s["section_id"], "kind": "contains"})
    # the RAG tag block is the dependency graph in plain text
    for d in db.execute("SELECT doc_id, rag_json FROM documents"):
        rag = json.loads(d["rag_json"] or "{}")
        for dep in rag.get("dependency", []):
            needle = dep.split("(")[0].strip()
            target = db.execute("SELECT doc_id FROM documents WHERE title LIKE ?",
                                (f"%{needle}%",)).fetchone()
            if target:
                edges.append({"source": d["doc_id"], "target": target["doc_id"], "kind": "depends"})
    # Duplicates are a status on the canonical document (`flags`), not an edge:
    # an edge needs two nodes, and the copy's path is not one. The count is in
    # /stats and the flag is on the node.
    return {"nodes": nodes, "edges": edges}


@router.get("/search")
async def search(q: str = "", limit: int = 25) -> dict:
    db = _db()
    return {"results": _index.search(db, q, limit)}


@router.get("/review")
async def review_queue() -> dict:
    """The review queue: every non-current flag the human has not decided on,
    worst first, with the document it belongs to."""
    db = _db()
    return {"flags": _review.queue(db)}


@router.get("/corrections")
async def correction_log() -> dict:
    """Every recorded review decision, newest first."""
    db = _db()
    return {"corrections": _review.corrections(db)}


@router.post("/review")
async def decide(body: dict) -> dict:
    """Record one decision. The source file is never written.

    `action` is `confirm` (the flag stands — the document leaves the queue),
    `keep` (leave it on the queue) or `edit` (a correction is needed; the note
    says what). An `edit` without a note is refused: a correction with no text
    is not actionable.
    """
    doc_id = str(body.get("doc_id", ""))
    flag = str(body.get("flag", ""))
    action = str(body.get("action", ""))
    note = str(body.get("note", "")).strip()
    if not _DOC_ID.fullmatch(doc_id):
        raise HTTPException(400, "bad doc_id")
    if action not in ("confirm", "keep", "edit"):
        raise HTTPException(400, "action must be confirm, keep or edit")
    if action == "edit" and not note:
        raise HTTPException(400, "an edit needs a note saying what to correct")
    db = _db()
    if not db.execute("SELECT 1 FROM documents WHERE doc_id=?", (doc_id,)).fetchone():
        raise HTTPException(404, "no such document")
    row = _review.write_correction(db, doc_id, flag, action, note)
    return {"correction": row, "queue": _review.queue(db)}


@router.post("/ask")
async def ask(body: dict) -> dict:
    """A cited answer, written by the session model from the retrieved sections.

    The model is bound by the agent half's `register(ctx)`; if it is not bound
    in this process the route says so rather than guessing with a second model.
    The source corpus is never modified — an answer is a read.
    """
    question = str(body.get("question", "")).strip()
    if not question:
        raise HTTPException(400, "a question is required")
    if len(question) > 2000:
        raise HTTPException(400, "question is too long")
    llm = get_llm()
    if llm is None:
        raise HTTPException(503, "no model is bound in this process — reload the plugin")
    db = _db()
    out = _qa.answer(db, question, llm, k=int(body.get("k", _qa.DEFAULT_K)))
    out["question"] = question
    return out


@router.get("/document/{doc_id}")
async def document(doc_id: str) -> dict:
    if not _DOC_ID.fullmatch(doc_id):
        raise HTTPException(400, "bad doc_id")
    db = _db()
    d = db.execute("SELECT * FROM documents WHERE doc_id=?", (doc_id,)).fetchone()
    if not d:
        raise HTTPException(404, "no such document")
    secs = db.execute(
        "SELECT ord,title,body,level FROM sections WHERE doc_id=? ORDER BY ord", (doc_id,))
    return {"document": dict(d), "sections": [dict(s) for s in secs]}


@router.get("/wall")
async def wall(with_captions: bool = False) -> dict:
    """Documents for the card wall, plus the pictures the wall exists for.

    `documents` is the text corpus (junk screenshots collapsed behind
    `junk_count`). `images` is the picture half, built by `vault.images.wall`:
    dimensions read from each file's header, and one vision caption for every
    non-junk image. Junk is counted, never listed and never sent to the model.

    Captions are opt-in (`?with_captions=1`) because each one is a model call.
    The page asks for them once, when the Wall tab is opened with a model bound;
    without them the route is instant and free, and the wall still shows every
    picture.
    """
    db = _db()
    flags = _flag_map(db)
    rows = db.execute(
        "SELECT doc_id,title,kind,path,is_junk FROM documents "
        "WHERE kind!='image' AND is_junk=0 ORDER BY kind, title")
    iw = _images.wall(db, get_llm() if with_captions else None)
    return {
        "junk_count": iw["junk_count"],
        "documents": [dict(r) | {"flag": flags.get(r["doc_id"], "current")} for r in rows],
        "images": iw["images"],
        "captions": iw["captions"],
    }


@router.get("/images")
async def images_route(with_captions: bool = False) -> dict:
    """The picture half alone: `{images, junk_count, captions}`.

    Captions are opt-in for the same reason they are on `/wall`: each is a model
    call, and a wall that renders while the free model is throttled must still
    render. Dimensions and titles are always free.
    """
    db = _db()
    return _images.wall(db, get_llm() if with_captions else None)


# The corpus roots, resolved once. `/file` is the one route that reads a path
# from the request, so it may only ever serve a file the index itself lists —
# never an arbitrary path from the query string.
def _indexed_paths(db: sqlite3.Connection) -> dict[str, str]:
    return {str(row["path"]): row["path"] for row in db.execute("SELECT path FROM documents")}


@router.get("/file")
async def file(path: str = ""):
    """One corpus file's bytes, for the wall's `<img>`.

    The path must be a document the index knows. That check is the whole point
    of the route: a plugin that echoed any path would be an open file server,
    and the desktop page is the only caller.
    """
    if not path:
        raise HTTPException(400, "a path is required")
    db = _db()
    known = _indexed_paths(db)
    if path not in known:
        raise HTTPException(404, "that file is not in the index")
    p = Path(path)
    if not p.is_file():
        raise HTTPException(404, "that file is gone")
    from fastapi.responses import Response

    return Response(content=p.read_bytes(), media_type=_images.mime_of(p))


