"""SQLite + FTS5 index. The DB is derived: rebuild it any time from the corpus."""

from __future__ import annotations

import json
import re
import sqlite3
from pathlib import Path

from . import extract, sources

# How many sections of one document may appear in a single result set. Enough to
# carry the section that names a word and the one that explains it; few enough
# that one document cannot crowd out every other.
PER_DOCUMENT_SECTIONS = 2

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
    """Make any user input safe for MATCH. Punctuation is dropped, never fatal.

    Each term is quoted *individually*: a bare `rag OR 1=1` would be read as an
    FTS5 boolean query and match everything, which is worse than an error.
    """
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


def rank(rows: list[dict], wanted: list[str], limit: int) -> list[dict]:
    """Order matched rows: a section *named* with a query word first, then BM25.

    FTS5's own `bm25()` weights the title and body columns equally, so on a tie
    the body wins — and a section that talks about "chunking" in passing then
    beats the doctrine section titled "Chunking". The title bonus is a tiebreak,
    not a replacement: BM25 still orders the body matches among themselves.

    Two sections per document at most: a document split into overlapping sections
    would otherwise take every slot and crowd out the document that answers, but
    one is too blunt — the section that names the word and the one that explains
    it are often two different sections.
    """
    out = [r for r in rows if (r.get("body") or "").strip()]
    for r in out:
        title = (r.get("section_title") or "").lower()
        r["title_hit"] = sum(1 for w in wanted if w in title)
    out.sort(key=lambda r: (r["title_hit"] > 0, -r["score"]), reverse=True)
    per_doc: dict[str, int] = {}
    kept = []
    for r in out:
        n = per_doc.get(r["doc_id"], 0)
        if n >= PER_DOCUMENT_SECTIONS:
            continue
        per_doc[r["doc_id"]] = n + 1
        kept.append(r)
    return kept[:limit]


def _matched(db: sqlite3.Connection, match_query: str) -> list[dict]:
    """Every section matching an already-safe FTS5 MATCH expression."""
    rows = db.execute(
        """
        SELECT s.section_id, s.doc_id, s.title AS section_title, s.body, s.level,
               d.title AS doc_title, d.path AS doc_path, d.kind,
               bm25(sections_fts) AS score
        FROM sections_fts f
        JOIN sections s ON s.rowid = f.rowid
        JOIN documents d ON d.doc_id = s.doc_id
        WHERE sections_fts MATCH ?
        """,
        (match_query,),
    ).fetchall()
    return [dict(r) for r in rows]


def search(db: sqlite3.Connection, query: str, limit: int = 25) -> list[dict]:
    """Ranked sections with document provenance. *query* is user text."""
    wanted = [w.lower() for w in re.split(r"[^0-9A-Za-z]+", query or "") if w]
    return rank(_matched(db, _fts_quote(query)), wanted, limit)


def search_or(db: sqlite3.Connection, words: list[str], limit: int = 25) -> list[dict]:
    """Ranked sections matching ANY of *words* (already-clean terms).

    `search()` runs user text through `_fts_quote`, which drops `OR` as
    punctuation and quotes it as a literal — so a boolean query has to be built
    here, from terms the caller has already vetted.
    """
    clean = [w for w in re.split(r"[^0-9A-Za-z]+", " ".join(words or [])) if w]
    if not clean:
        return []
    return rank(_matched(db, _or_query(clean)), [w.lower() for w in clean], limit)


def search_prefix(db: sqlite3.Connection, query: str, limit: int = 25) -> list[dict]:
    """Like `search`, but every term is a *prefix* match.

    A question says "chunk" and the doctrine says "Chunking"; an exact-token
    MATCH misses that, and the Ask path would never surface the section that
    answers. Prefix matching is the recall ladder's job — `/search` keeps exact
    semantics for a user who wants a literal.
    """
    words = [w.lower() for w in re.split(r"[^0-9A-Za-z]+", query or "") if w]
    if not words:
        return []
    return rank(_matched(db, _prefix_or(words)), words, limit)


def _or_query(words: list[str]) -> str:
    return " OR ".join(f'"{w}"' for w in words)


def _prefix_or(words: list[str]) -> str:
    return " OR ".join(f'"{w}"*' for w in words)
