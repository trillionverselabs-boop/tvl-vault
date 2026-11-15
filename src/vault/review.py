"""Five deterministic flags. No model required for any of them.

CURRENT    - newest version of its title, no contradictions found
DUPLICATE  - byte-identical copy of another document (sha256)
OUTDATED   - an older version of a title that exists in a newer version,
             or a document whose own VALIDITY tag is not Active
CONFLICT   - two documents make claims that cannot both be true (model-assisted,
             run on demand; see Task 10)
UNCLEAR    - no extractable sections, or too little text to be a claim
"""

from __future__ import annotations

import json
import re
import sqlite3
from pathlib import Path

from .paths import data_root

FLAG_ORDER = ["conflict", "outdated", "duplicate", "unclear", "current"]


def _version_tuple(v: str) -> tuple[int, int] | None:
    m = re.search(r"v?(\d+)\.(\d+)", v or "")
    return (int(m.group(1)), int(m.group(2))) if m else None


def _norm_title(t: str) -> str:
    t = re.sub(r"\s*\((?:v?\d+(?:\.\d+)?|\d{4}|Draft[^)]*)\)\s*", " ", t or "")
    return re.sub(r"[^a-z0-9]+", " ", t.lower()).strip()


def compute_flags(db: sqlite3.Connection) -> list[dict]:
    """Deterministic pass. One row per (doc_id, flag)."""
    flags: list[dict] = []
    docs = [dict(r) for r in db.execute("SELECT * FROM documents")]

    # 1. byte-identical duplicates
    for row in db.execute("SELECT sha256, path FROM duplicates"):
        flags.append({"section_id": None, "doc_id": row["sha256"][:16], "flag": "duplicate",
                      "reason": f"byte-identical copy also exists: {row['path']}",
                      "evidence": row["path"]})

    # 2. version regress: group by normalized title
    by_title: dict[str, list[dict]] = {}
    for d in docs:
        by_title.setdefault(_norm_title(d["title"]), []).append(d)
    for _title, group in by_title.items():
        if len(group) < 2:
            continue
        vers = [(_version_tuple(json.loads(d["meta_json"]).get("version", "")), d) for d in group]
        vers = [(v, d) for v, d in vers if v]
        if len({v for v, _ in vers}) < 2:
            continue
        newest = max(v for v, _ in vers)
        for v, d in vers:
            if v < newest:
                flags.append({"section_id": None, "doc_id": d["doc_id"], "flag": "outdated",
                              "reason": f"v{v[0]}.{v[1]} — superseded by v{newest[0]}.{newest[1]}",
                              "evidence": json.loads(d["meta_json"]).get("version", "")})

    # 3. VALIDITY tag not Active
    for d in docs:
        val = json.loads(d["rag_json"]).get("validity", "")
        if val and "active" not in val.lower():
            flags.append({"section_id": None, "doc_id": d["doc_id"], "flag": "outdated",
                          "reason": f"VALIDITY tag says {val!r}", "evidence": val})

    # 4. nothing extractable. An image is not a claim: it has no sections and
    #    never did. Flagging 199 pictures as UNCLEAR is what made 43 of the real
    #    corpus's unclear flags meaningless, so they are excluded here and shown
    #    on the wall instead (Task 9).
    for d in docs:
        if d["kind"] == "image":
            continue
        n = db.execute("SELECT COUNT(*) FROM sections WHERE doc_id=?", (d["doc_id"],)).fetchone()[0]
        if not n:
            flags.append({"section_id": None, "doc_id": d["doc_id"], "flag": "unclear",
                          "reason": "no extractable sections", "evidence": ""})

    # 5. everything not flagged is current — except an image, which has no
    #    status at all. "Current" is a claim about a document's text; a picture
    #    makes no claim, so it is left flagless and the UI calls it an artifact.
    flagged = {f["doc_id"] for f in flags}
    for d in docs:
        if d["kind"] == "image":
            continue
        if d["doc_id"] not in flagged:
            flags.append({"section_id": None, "doc_id": d["doc_id"], "flag": "current",
                          "reason": "newest version, no contradiction found", "evidence": ""})
    return flags


def write_flags(db: sqlite3.Connection, flags: list[dict]) -> None:
    db.execute("CREATE TABLE IF NOT EXISTS flags ("
               "doc_id TEXT, section_id TEXT, flag TEXT, reason TEXT, evidence TEXT, "
               "PRIMARY KEY(doc_id, section_id, flag))")
    db.execute("DELETE FROM flags")
    for f in flags:
        db.execute("INSERT OR REPLACE INTO flags VALUES(?,?,?,?,?)",
                   (f["doc_id"], f["section_id"], f["flag"], f["reason"], f["evidence"]))
    db.commit()


def conflicts(db: sqlite3.Connection) -> list[dict]:
    """Pairs of sections that contradict. Model-assisted; see Task 10. Empty until then."""
    return []


# ── corrections ─────────────────────────────────────────────────────────
# A decision is never written back into a source file (rule 4). It lives here:
# `corrections` is the human's answer to a flag, and `resolved` replaces the
# flag's effect everywhere it is read. The source keeps its original bytes.

_CORRECTIONS_SCHEMA = """
CREATE TABLE IF NOT EXISTS corrections (
  doc_id    TEXT PRIMARY KEY,
  flag      TEXT NOT NULL,
  action    TEXT NOT NULL,
  note      TEXT DEFAULT '',
  created_at TEXT DEFAULT (datetime('now'))
)
"""


def correction_path() -> Path:
    """Where the review decisions are kept: beside the index, in the data root."""
    return data_root() / "corrections.jsonl"


def write_correction(db: sqlite3.Connection, doc_id: str, flag: str,
                     action: str, note: str = "") -> dict:
    """Record one review decision. Idempotent per document.

    Keyed on `doc_id`, not on `(doc_id, flag)`: a document's status is one
    decision. A `(doc_id, flag)` key would let confirming the duplicate flag
    silently erase a decision already taken on the same document's other flag.
    """
    db.executescript(_CORRECTIONS_SCHEMA)
    db.execute(
        "INSERT INTO corrections(doc_id, flag, action, note) VALUES(?,?,?,?) "
        "ON CONFLICT(doc_id) DO UPDATE SET flag=excluded.flag, action=excluded.action, "
        "note=excluded.note, created_at=datetime('now')",
        (doc_id, flag, action, note),
    )
    db.commit()
    row = db.execute(
        "SELECT doc_id, flag, action, note, created_at FROM corrections WHERE doc_id=?",
        (doc_id,)).fetchone()
    _append_jsonl({
        "doc_id": doc_id, "flag": flag, "action": action,
        "note": note, "created_at": row["created_at"],
    })
    return dict(row)


def _append_jsonl(record: dict) -> None:
    """Mirror each decision to a JSONL log, so a lost DB still has the history."""
    try:
        correction_path().parent.mkdir(parents=True, exist_ok=True)
        with correction_path().open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, ensure_ascii=False) + "\n")
    except OSError:
        pass          # the DB row is the record; the log is a convenience


def corrections(db: sqlite3.Connection) -> list[dict]:
    """Every recorded decision, newest first."""
    db.executescript(_CORRECTIONS_SCHEMA)
    return [dict(r) for r in db.execute(
        "SELECT doc_id, flag, action, note, created_at FROM corrections "
        "ORDER BY created_at DESC, doc_id")]


def resolved_doc_ids(db: sqlite3.Connection) -> set[str]:
    """Documents the human has decided on. `confirm` clears their flags; `keep`
    leaves them on the queue so the next reviewer sees them again."""
    db.executescript(_CORRECTIONS_SCHEMA)
    out: set[str] = set()
    for row in db.execute("SELECT doc_id, action FROM corrections"):
        if row["action"] in ("confirm", "edit"):
            out.add(row["doc_id"])
    return out


def queue(db: sqlite3.Connection) -> list[dict]:
    """The review queue as the UI should show it.

    `resolved_doc_ids` is applied here, once, so every reader (the /review route,
    the CLI summary) agrees: a confirmed document leaves the queue and is shown
    as current; a `keep` decision stays.

    Images are left out entirely. The deterministic pass records a byte-identical
    image as a `duplicate` flag — that is a fact, and `/stats` still counts it —
    but a duplicate *decision* is for a human reading text. On the real corpus
    60 of the 118 duplicate flags were images, so the queue was two-thirds
    pictures nobody could keep, confirm or edit.
    """
    done = resolved_doc_ids(db)
    image_ids = {r[0] for r in db.execute(
        "SELECT doc_id FROM documents WHERE kind='image'")}
    rows = db.execute(
        "SELECT f.doc_id, f.flag, f.reason, f.evidence, d.title, d.path, d.kind "
        "FROM flags f JOIN documents d ON d.doc_id=f.doc_id "
        "WHERE f.flag!='current' ORDER BY f.flag").fetchall()
    sev = {"conflict": 0, "outdated": 1, "duplicate": 2, "unclear": 3}
    flags = [dict(r) for r in rows
             if r["doc_id"] not in done and r["doc_id"] not in image_ids]
    flags.sort(key=lambda f: sev.get(f["flag"], 9))
    return flags
