"""SQLite + FTS5 index. The DB is derived: rebuild it any time from the corpus."""

from __future__ import annotations

import json
import re
import sqlite3
from pathlib import Path

from . import extract, sources

SCHEMA = """
CREATE TABLE IF NOT EXISTS documents (
  doc_id      TEXT PRIMARY KEY,
  path        TEXT NOT NULL,
  kind        TEXT NOT NULL,
  title       TEXT NOT NULL,
  sha256      TEXT NOT NULL,
  size        INTEGER,
  is_junk     INTEGER DEFAULT 0,
  meta_json   TEXT DEFAULT '{}',
  rag_json    TEXT DEFAULT '{}',
  extracted_at TEXT
);
CREATE TABLE IF NOT EXISTS sections (
  section_id  TEXT PRIMARY KEY,
  doc_id      TEXT NOT NULL REFERENCES documents(doc_id) ON DELETE CASCADE,
  ord         INTEGER NOT NULL,
  title       TEXT NOT NULL,
  level       INTEGER,
  body        TEXT,
  line        INTEGER,
  word_count  INTEGER
);
CREATE TABLE IF NOT EXISTS duplicates (
  sha256      TEXT NOT NULL,
  path        TEXT NOT NULL,
  PRIMARY KEY (sha256, path)
);
CREATE VIRTUAL TABLE IF NOT EXISTS sections_fts USING fts5(
  title, body, content='sections', content_rowid='rowid'
);
CREATE TRIGGER IF NOT EXISTS sections_ai AFTER INSERT ON sections BEGIN
  INSERT INTO sections_fts(rowid, title, body) VALUES (new.rowid, new.title, new.body);
END;
CREATE TRIGGER IF NOT EXISTS sections_ad AFTER DELETE ON sections BEGIN
  INSERT INTO sections_fts(sections_fts, rowid, title, body)
  VALUES ('delete', old.rowid, old.title, old.body);
END;
CREATE INDEX IF NOT EXISTS idx_sections_doc ON sections(doc_id, ord);
"""


def _connect(path: Path) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(path)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA journal_mode=WAL")
    db.executescript(SCHEMA)
    return db


def _fts_quote(q: str) -> str:
    """Make any user input safe for MATCH. Punctuation is dropped, never fatal."""
    words = [w for w in re.split(r"[^0-9A-Za-z]+", q or "") if w]
    if not words:
        return '""'
    return " ".join(f'"{w}"' for w in words)


def rebuild(roots: Path | list[Path], db_path: Path) -> sqlite3.Connection:
    """Rebuild the whole index in one pass. *roots* is one path or several.

    The delete happens once, before the pass — calling this per root would wipe
    whatever the previous root had written.
    """
    if isinstance(roots, Path):
        roots = [roots]
    db = _connect(db_path)
    db.execute("DELETE FROM duplicates")
    db.execute("DELETE FROM sections")
    db.execute("DELETE FROM documents")
    seen: set[str] = set()
    for root in roots:
        for doc in sources.scan(root):
            if doc.sha256 in seen:
                # same bytes under another root: record it as a duplicate, do not re-extract
                db.execute("INSERT OR IGNORE INTO duplicates(sha256,path) VALUES(?,?)",
                           (doc.sha256, str(doc.path)))
                continue
            seen.add(doc.sha256)
            if doc.kind == "image":
                # images are indexed separately (Task 9); the text index has no use for them
                db.execute(
                    "INSERT OR REPLACE INTO documents(doc_id,path,kind,title,sha256,size,is_junk,meta_json,rag_json,extracted_at)"
                    " VALUES(?,?,?,?,?,?,?,'{}','{}',datetime('now'))",
                    (doc.sha256[:16], str(doc.path), doc.kind, doc.path.stem, doc.sha256,
                     doc.size, int(doc.is_junk)),
                )
                for dup in doc.duplicates:
                    db.execute("INSERT OR IGNORE INTO duplicates(sha256,path) VALUES(?,?)",
                               (doc.sha256, str(dup)))
                continue
            try:
                ex = extract.extract_document(doc.path, doc.kind)
            except Exception as exc:                 # one bad file must not kill the build
                ex = extract.Extracted(doc.path, doc.kind, doc.path.stem, "", [], {}, {}, str(exc))
            db.execute(
                "INSERT OR REPLACE INTO documents(doc_id,path,kind,title,sha256,size,is_junk,meta_json,rag_json,extracted_at)"
                " VALUES(?,?,?,?,?,?,?,?,?,datetime('now'))",
                (doc.sha256[:16], str(doc.path), doc.kind, ex.title or doc.path.stem, doc.sha256,
                 doc.size, int(doc.is_junk), _json(ex.meta), _json(ex.rag)),
            )
            for i, s in enumerate(ex.sections):
                db.execute(
                    "INSERT OR REPLACE INTO sections(section_id,doc_id,ord,title,level,body,line,word_count)"
                    " VALUES(?,?,?,?,?,?,?,?)",
                    (f"{doc.sha256[:16]}-{i:04d}", doc.sha256[:16], i, s.title, s.level,
                     s.body, s.line, len(s.body.split())),
                )
            for dup in doc.duplicates:
                db.execute("INSERT OR IGNORE INTO duplicates(sha256,path) VALUES(?,?)",
                           (doc.sha256, str(dup)))
    db.commit()
    return db


def _json(d: dict) -> str:
    return json.dumps(d, ensure_ascii=False)


def search(db: sqlite3.Connection, query: str, limit: int = 25) -> list[dict]:
    """BM25 over section title+body. Returns rows with document provenance."""
    rows = db.execute(
        """
        SELECT s.section_id, s.title AS section_title, s.body, s.level,
               d.title AS doc_title, d.path AS doc_path, d.kind,
               bm25(sections_fts) AS score
        FROM sections_fts f
        JOIN sections s ON s.rowid = f.rowid
        JOIN documents d ON d.doc_id = s.doc_id
        WHERE sections_fts MATCH ?
        ORDER BY score
        LIMIT ?
        """,
        (_fts_quote(query), limit),
    ).fetchall()
    return [dict(r) for r in rows]
