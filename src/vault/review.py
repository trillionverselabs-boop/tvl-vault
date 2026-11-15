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

    # 4. nothing extractable
    for d in docs:
        if d["kind"] == "image":
            continue
        n = db.execute("SELECT COUNT(*) FROM sections WHERE doc_id=?", (d["doc_id"],)).fetchone()[0]
        if not n:
            flags.append({"section_id": None, "doc_id": d["doc_id"], "flag": "unclear",
                          "reason": "no extractable sections", "evidence": ""})

    # 5. everything not flagged is current
    flagged = {f["doc_id"] for f in flags}
    for d in docs:
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
