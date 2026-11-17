"""Five deterministic flags. No model required for any of them.

CURRENT    - newest version of its title, no contradictions found
DUPLICATE  - byte-identical copy of another document (sha256)
OUTDATED   - an older version of a title that exists in a newer version,
             or a document whose own VALIDITY tag is not Active
CONFLICT   - two documents make claims that cannot both be true (model-assisted,
             run on demand only; see `conflicts` below)
UNCLEAR    - no extractable sections, or too little text to be a claim
"""

from __future__ import annotations

import json
import re
import sqlite3
from collections import Counter
from pathlib import Path

from .paths import data_root

FLAG_ORDER = ["conflict", "outdated", "duplicate", "unclear", "current"]

# The conflict pass's ceiling: at most this many model calls per run. A free
# model is throttled, and a run that asked about every section pair would be
# thousands of calls for nothing.
MAX_CONFLICT_PAIRS = 200

# A section shorter than this cannot state a claim, so it cannot contradict
# one. Headings are usually 3-6 words; 24 words is a sentence and a half.
MIN_CLAIM_WORDS = 24

# Two sections are candidates only if they share a *subject*. A shared
# stopword ("the", "doctrine") is not a subject, and neither is a number: the
# real corpus paired the character sheet with a CSS token contract on `10px`
# and a voice note with a data plan on `9000`. Numbers are dropped before
# matching, and a candidate needs at least `MIN_SHARED_TERMS` shared terms.
_MIN_TERM_LEN = 4
MIN_SHARED_TERMS = 2

# A term must appear in at least this many sections to be a subject at all.
# One section's vocabulary is a coincidence, not a subject.
_MIN_TERM_SECTIONS = 2

_STOPWORDS = frozenset("""
a about above after again against all am an and any are as at be because been
before being below between both but by can cannot could did do does doing down
during each few for from further had has have having he her here hers him his
how i if in into is it its itself just me more most my no nor not now of off
on once only or other our ours out over own same she should so some such than
that the their theirs them then there these they this those through to too
under until up very was we were what when where which while who whom why will
with you your
""".split())

# Words that are shared by much of the corpus and say nothing about a subject.
# Measured on the real index: these appear in 200+ of its ~1,866 sections.
_SALIENCE_STOP = frozenset("""
document section system tvl vault doctrine rag data structure logic
every page real first run must content model use build research market
""".split())

_WORD_RE = re.compile(r"[0-9A-Za-z]{3,}")
_NUMERIC_RE = re.compile(r"^[0-9.,:%$#/x-]+$")
# Hex colours (`22d3ee`) and CSS units (`10px`, `60ms`) are values, not subjects.
_CODE_RE = re.compile(r"^(?:[0-9a-f]{6,8}|[0-9]+(?:px|em|rem|khz|ms|s|x))$")

# A conflict must name what the disagreement is about. The model is asked for a
# short reason; a bare `true` with no reason is not reviewable.
_CONFLICT_INSTRUCTIONS = (
    "You are checking a business document corpus for contradictions. "
    "Two passages are shown. Decide whether they make claims that cannot both "
    "be true. A difference of emphasis, a restatement, or two subjects that "
    "merely share a word is NOT a contradiction. Answer JSON: "
    '{"contradicts": true|false, "reason": "one short sentence, or empty"}. '
    "Plain language. No jargon."
)


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


def _section_rows(db: sqlite3.Connection) -> list[dict]:
    return [dict(r) for r in db.execute(
        "SELECT s.section_id, s.doc_id, s.title, s.body, d.title AS doc_title, "
        "d.path AS doc_path FROM sections s JOIN documents d ON d.doc_id=s.doc_id")]


def _terms(text: str) -> set[str]:
    """The words that can carry a subject: distinctive, non-numeric, 4+ chars.

    Numbers, hex colours and CSS units are dropped on purpose. On the real
    corpus the character sheet and a CSS token contract were paired on `10px`,
    a voice note and a data plan on `9000`, and a brand book with a plugin
    style guide on `22d3ee`/`a855f7`. A number is a *value*, not a subject —
    a disagreement about a value is exactly what the model is for, but a shared
    number or colour is not evidence that two passages are about the same thing.
    """
    out = set()
    for w in _WORD_RE.findall((text or "").lower()):
        if len(w) < _MIN_TERM_LEN or w in _STOPWORDS or w in _SALIENCE_STOP:
            continue
        if _NUMERIC_RE.match(w) or _CODE_RE.match(w):
            continue
        out.add(w)
    return out


def _salient_terms(db: sqlite3.Connection) -> dict[str, int]:
    """Term -> in how many sections it appears.

    A subject has to be shared, so a term in one section is not salient; a term
    in most sections (`document`, `model`) is shared by everything and says
    nothing about which pair is about the same thing. Both ends are cut.
    """
    n = db.execute("SELECT COUNT(*) FROM sections").fetchone()[0]
    counts: Counter[str] = Counter()
    for row in db.execute("SELECT title, body FROM sections"):
        counts.update(_terms(f"{row['title']}\n{row['body']}"))
    lo = _MIN_TERM_SECTIONS
    hi = max(lo, n * 0.2)
    return {t: c for t, c in counts.items() if lo <= c <= hi}


def _candidates(db: sqlite3.Connection) -> list[tuple[dict, dict]]:
    """Section pairs worth asking the model about, best pairs first.

    Two sections are candidates when they are from different documents, both
    state a claim (>= `MIN_CLAIM_WORDS` words), and share at least
    `MIN_SHARED_TERMS` salient terms. One shared word is a coincidence — the
    real corpus made 724,410 such pairs and spent its 200 calls on `10px`.

    Ordered by how *rare* the shared terms are, so the cap spends its calls
    where two documents most plausibly discuss the same subject.
    """
    sections = _section_rows(db)
    salient = _salient_terms(db)
    by_id = {s["section_id"]: s for s in sections}
    term_map = {s["section_id"]: _terms(f"{s['title']}\n{s['body']}") & set(salient)
                for s in sections}
    pairs: list[tuple[int, int, str, str]] = []
    for i, a in enumerate(sections):
        if len((a["body"] or "").split()) < MIN_CLAIM_WORDS:
            continue
        for b in sections[i + 1:]:
            if a["doc_id"] == b["doc_id"]:
                continue
            if len((b["body"] or "").split()) < MIN_CLAIM_WORDS:
                continue
            shared = term_map[a["section_id"]] & term_map[b["section_id"]]
            if len(shared) < MIN_SHARED_TERMS:
                continue
            # rarest shared term first, then the pair sharing the most terms
            pairs.append((max(salient[t] for t in shared), len(shared),
                          a["section_id"], b["section_id"]))
    pairs.sort(key=lambda p: (p[0], -p[1]))
    return [(by_id[aid], by_id[bid]) for _, _, aid, bid in pairs[:MAX_CONFLICT_PAIRS]]


def _verdict(llm, a: dict, b: dict) -> dict:
    """One model call. `{"contradicts": bool, "reason": str}`, or `{}`."""
    text_a = f"{a['title']}\n{a['body']}"[:1800]
    text_b = f"{b['title']}\n{b['body']}"[:1800]
    prompt = (
        f"PASSAGE 1 (from {a['doc_title']}):\n{text_a}\n\n"
        f"PASSAGE 2 (from {b['doc_title']}):\n{text_b}"
    )
    res = llm.complete_structured(
        instructions=_CONFLICT_INSTRUCTIONS,
        input=[{"type": "text", "text": prompt}],
        temperature=0,
        purpose="tvl-vault conflict check",
    )
    parsed = getattr(res, "parsed", None)
    if isinstance(parsed, dict):
        return parsed
    raw = (getattr(res, "text", "") or "").strip()
    m = re.search(r"\{.*\}", raw, re.S)
    if not m:
        return {}
    try:
        out = json.loads(m.group(0))
    except ValueError:
        return {}
    return out if isinstance(out, dict) else {}


def _conflict_key(a: dict, b: dict) -> tuple[str, str]:
    return tuple(sorted((a["doc_id"], b["doc_id"])))          # type: ignore[return-value]


def _conflict_key_ids(x: str, y: str) -> tuple[str, str]:
    return tuple(sorted((x, y)))                              # type: ignore[return-value]


def conflicts(db: sqlite3.Connection, llm) -> list[dict]:
    """The model-assisted pass: find pairs of sections that contradict.

    **On demand only.** It is never part of `rebuild` — every call is a model
    call, and a rebuild that asked about 200 pairs would cost money and break
    when the free model is throttled. The desktop's Review tab offers the run;
    `POST /api/plugins/tvl-vault/conflicts` is the route.

    Guardrails, all deliberate:

    * at most `MAX_CONFLICT_PAIRS` (200) model calls per run;
    * `temperature=0`, no provider or model override — the same corpus gives
      the same verdicts;
    * a pair already recorded as a conflict is not asked again (a rerun adds,
      it does not redo);
    * a pair the human has already decided on is not asked again;
    * a model failure is skipped, never fatal;
    * every recorded flag carries the model's reason as `evidence`, because a
      conflict a reviewer cannot read is not reviewable.

    Returns the flags it wrote, and writes them to the `flags` table.
    """
    if llm is None or db is None:
        return []
    return _run_conflicts(db, llm)


def pairs_asked() -> int:
    """How many model calls the last run spent. The cap is a promise, and the
    route reports it so a reviewer can see the promise was kept."""
    return _STATE.pairs_asked


class _State:
    """One run's counters. A module-level holder, not a global per field."""

    pairs_asked = 0


_STATE = _State()


def _run_conflicts(db: sqlite3.Connection, llm) -> list[dict]:
    _STATE.pairs_asked = 0
    # A pair already recorded as a conflict is settled: the flag names the
    # document it was found against, and the pair key is the two doc ids. Both
    # are read back from the flags table, so a rerun adds conflicts without
    # redoing the ones already on the queue.
    settled: set[tuple[str, str]] = set()
    try:
        recorded = [dict(r) for r in db.execute(
            "SELECT doc_id, section_id FROM flags WHERE flag='conflict'")]
    except sqlite3.Error:
        recorded = []
    for f in recorded:
        other = f["section_id"] or ""
        if other:
            settled.add(_conflict_key_ids(f["doc_id"], other))
    decided = resolved_doc_ids(db)

    written: list[dict] = []
    for a, b in _candidates(db):
        if _STATE.pairs_asked >= MAX_CONFLICT_PAIRS:
            break
        key = _conflict_key(a, b)
        if key in settled:
            continue
        if a["doc_id"] in decided or b["doc_id"] in decided:
            continue
        try:
            v = _verdict(llm, a, b)
        except Exception:
            continue                       # a throttled model: skip, never crash
        _STATE.pairs_asked += 1
        if not v or not v.get("contradicts"):
            continue
        reason = str(v.get("reason") or "").strip()
        flag = {
            # `section_id` carries the partner document's id: a conflict flag is
            # keyed (doc_id, section_id, flag), and that slot is what makes a
            # rerun know this exact pair is already settled.
            "section_id": b["doc_id"],
            "doc_id": a["doc_id"],
            "flag": "conflict",
            "reason": f"disagrees with “{b['doc_title']}”"
                       + (f": {reason}" if reason else ""),
            "evidence": reason or f"model verdict: contradicts ({b['doc_title']})",
        }
        written.append(flag)
        settled.add(key)
    if written:
        db.execute("CREATE TABLE IF NOT EXISTS flags ("
                   "doc_id TEXT, section_id TEXT, flag TEXT, reason TEXT, evidence TEXT, "
                   "PRIMARY KEY(doc_id, section_id, flag))")
        for f in written:
            db.execute("INSERT OR REPLACE INTO flags VALUES(?,?,?,?,?)",
                       (f["doc_id"], f["section_id"], f["flag"], f["reason"], f["evidence"]))
        db.commit()
    return written


# ── corrections ─────────────────────────────────────────────────────────
# A decision is never written back into a source file (rule 4). It lives here:
# `corrections` is the human's answer to a flag, and `resolved` replaces the
# flag's effect everywhere it is read. The source keeps its original bytes.

_CORRECTIONS_SCHEMA = """
CREATE TABLE IF NOT EXISTS corrections (
  doc_id    TEXT NOT NULL,
  flag      TEXT NOT NULL,
  action    TEXT NOT NULL,
  note      TEXT DEFAULT '',
  created_at TEXT DEFAULT (datetime('now')),
  PRIMARY KEY (doc_id, flag)
)
"""


def _ensure_corrections(db: sqlite3.Connection) -> None:
    """Create the table, and move an older document-level table to per-flag.

    The first version keyed a decision on `doc_id` alone, so confirming one flag
    silently cleared every other flag on the same document. Four doctrine PDFs
    on the real corpus carried both `duplicate` (their `tvl-ingest` copy) and
    `unclear` (no numbered headings); the duplicate confirmation erased the
    reading review. The key is now `(doc_id, flag)`.
    """
    db.execute(_CORRECTIONS_SCHEMA)
    pk = [r[1] for r in db.execute("PRAGMA table_info(corrections)") if r[5]]
    if pk == ["doc_id", "flag"]:
        return
    db.execute("ALTER TABLE corrections RENAME TO corrections_legacy")
    db.execute(_CORRECTIONS_SCHEMA)
    db.execute(
        "INSERT OR IGNORE INTO corrections(doc_id,flag,action,note,created_at) "
        "SELECT doc_id,flag,action,note,created_at FROM corrections_legacy")
    db.execute("DROP TABLE corrections_legacy")
    db.commit()


def correction_path() -> Path:
    """Where the review decisions are kept: beside the index, in the data root."""
    return data_root() / "corrections.jsonl"


def write_correction(db: sqlite3.Connection, doc_id: str, flag: str,
                     action: str, note: str = "") -> dict:
    """Record one review decision. Idempotent per document.

    Keyed on `(doc_id, flag)`. A document can carry more than one flag — a
    confirmed duplicate that still needs its reading reviewed — and a decision
    about one must not erase the other.
    """
    _ensure_corrections(db)
    db.execute(
        "INSERT INTO corrections(doc_id, flag, action, note) VALUES(?,?,?,?) "
        "ON CONFLICT(doc_id, flag) DO UPDATE SET action=excluded.action, "
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
    _ensure_corrections(db)
    return [dict(r) for r in db.execute(
        "SELECT doc_id, flag, action, note, created_at FROM corrections "
        "ORDER BY created_at DESC, doc_id, flag")]


def resolved_flags(db: sqlite3.Connection) -> set[tuple[str, str]]:
    """`(doc_id, flag)` pairs the human has settled.

    `confirm` and `edit` clear that flag's effect; `keep` leaves it. Per flag,
    not per document — a document can be a confirmed duplicate *and* still need
    its reading reviewed.
    """
    _ensure_corrections(db)
    return {(r["doc_id"], r["flag"]) for r in db.execute(
        "SELECT doc_id, flag FROM corrections WHERE action IN ('confirm','edit')")}


def resolved_doc_ids(db: sqlite3.Connection) -> set[str]:
    """Documents the human has decided on at all. The conflict pass skips these."""
    _ensure_corrections(db)
    return {r["doc_id"] for r in db.execute(
        "SELECT doc_id FROM corrections WHERE action IN ('confirm','edit')")}


def queue(db: sqlite3.Connection) -> list[dict]:
    """The review queue as the UI should show it.

    `resolved_flags` is applied here, once, so every reader (the /review route,
    the CLI summary) agrees: a confirmed *flag* leaves the queue and the
    document's other flags stay. Images are left out entirely. The
    deterministic pass records a byte-identical image as a `duplicate` flag —
    that is a fact, and `/stats` still counts it — but a duplicate *decision*
    is for a human reading text. On the real corpus 60 of the 118 duplicate
    flags were images, so the queue was two-thirds pictures nobody could keep,
    confirm or edit.
    """
    done = resolved_flags(db)
    image_ids = {r[0] for r in db.execute(
        "SELECT doc_id FROM documents WHERE kind='image'")}
    rows = db.execute(
        "SELECT f.doc_id, f.flag, f.reason, f.evidence, d.title, d.path, d.kind "
        "FROM flags f JOIN documents d ON d.doc_id=f.doc_id "
        "WHERE f.flag!='current' ORDER BY f.flag").fetchall()
    sev = {"conflict": 0, "outdated": 1, "duplicate": 2, "unclear": 3}
    flags = [dict(r) for r in rows
             if (r["doc_id"], r["flag"]) not in done and r["doc_id"] not in image_ids]
    flags.sort(key=lambda f: sev.get(f["flag"], 9))
    return flags


# ── the comparison a decision needs ──────────────────────────────────────
# A queue row says *what* is wrong — "byte-identical copy also exists: <path>".
# It cannot say what the document actually says, and a decision made without
# reading is not a review. `compare` is the payload for that: the document's own
# text, the copy it is measured against, and a recommendation with its reason.

_DOWNLOAD_RE = re.compile(r"^(.*?)\s*(?:\(\d+\)|[-_ ]\d+)$")

# Output of the video pipeline: no headings because it was never written to be
# read. A note *about* it is not knowledge about the doctrine.
_DERIVED_DIRS = ("/compositions/", "/frames/", "/render/", "/output/")
_DERIVED_NAMES = ("concat", "narration", "transcript", "scene", "frame", "prelude", "storyboard")

_TEXT_KINDS = {"markdown", "text", "html", "csv"}


def _is_derived_output(path: str) -> bool:
    p = path.lower()
    name = Path(p).name
    return any(d in p for d in _DERIVED_DIRS) or any(name.startswith(n) for n in _DERIVED_NAMES)


def _sections_brief(db: sqlite3.Connection, doc_id: str, limit: int = 8, chars: int = 900):
    rows = db.execute(
        "SELECT ord, title, level, body FROM sections WHERE doc_id=? ORDER BY ord LIMIT ?",
        (doc_id, limit)).fetchall()
    out = []
    for r in rows:
        body = (r["body"] or "").strip()
        if not body:
            continue
        out.append({"ord": r["ord"], "title": r["title"] or "", "level": r["level"],
                    "body": body[:chars], "words": len(body.split())})
    total = db.execute("SELECT COUNT(*) FROM sections WHERE doc_id=?", (doc_id,)).fetchone()[0]
    return out, total


def _excerpt(path: str, kind: str, limit: int = 1600) -> str:
    """The file's own opening text — for a document the reader could not parse."""
    if kind not in _TEXT_KINDS:
        return ""
    try:
        text = Path(path).read_text(errors="replace")
    except OSError:
        return ""
    return " ".join(text.split())[:limit]


def recommend(doc: dict, flag: str) -> dict:
    """What I would do, and why — stated so it can be argued with."""
    if flag == "duplicate":
        copies = [c["path"] for c in doc.get("counterparts", [])]
        suffixed = [p for p in copies if _DOWNLOAD_RE.match(Path(p).stem)]
        if suffixed:
            return {"action": "confirm",
                    "why": "The copy is a browser re-download (" +
                           ", ".join(Path(p).name for p in suffixed) +
                           "). The bytes are identical, so keep the cleanly named file."}
        if copies:
            return {"action": "keep",
                    "why": f"Same bytes under {len(copies)} other clean name(s). Pick the folder "
                           "that is the source of truth, delete the rest, then confirm."}
        return {"action": "keep", "why": "Flagged as a duplicate but no copy path was recorded."}

    if flag == "unclear":
        if _is_derived_output(doc["path"]):
            return {"action": "edit",
                    "why": "This is pipeline output (a video composition or a concat/narration "
                           "file), not a source document. It has no headings because it was never "
                           "written to be read — mark it not-knowledge."}
        if doc["kind"] == "pdf":
            return {"action": "keep",
                    "why": "A real document the reader could not parse (no numbered headings). "
                           "Keep it — the reader needs fixing, not the file."}
        return {"action": "keep", "why": "No headings found. Read the excerpt and decide."}

    return {"action": "keep", "why": "No rule applies. Read it and decide."}


def compare(db: sqlite3.Connection, doc_id: str, flag: str,
            limit: int = 8, chars: int = 900) -> dict:
    """Everything the review UI needs to show the actual text, not just a filename."""
    row = db.execute("SELECT * FROM documents WHERE doc_id=?", (doc_id,)).fetchone()
    if row is None:
        raise KeyError(doc_id)
    doc = dict(row)
    doc["sections"], doc["section_count"] = _sections_brief(db, doc_id, limit, chars)
    doc["excerpt"] = _excerpt(doc["path"], doc["kind"])
    doc["counterparts"] = []
    if flag == "duplicate":
        for r in db.execute("SELECT path FROM duplicates WHERE sha256=?", (doc["sha256"],)):
            cp = r["path"]
            other = db.execute(
                "SELECT doc_id, title, kind FROM documents WHERE path=?", (cp,)).fetchone()
            doc["counterparts"].append({
                "path": cp, "name": Path(cp).name,
                "listed": other is not None,
                "title": other["title"] if other else Path(cp).stem,
                "kind": other["kind"] if other else doc["kind"],
            })
    frow = db.execute(
        "SELECT reason, evidence FROM flags WHERE doc_id=? AND flag=?", (doc_id, flag)).fetchone()
    return {
        "doc_id": doc_id,
        "flag": flag,
        "reason": frow["reason"] if frow else "",
        "evidence": frow["evidence"] if frow else "",
        "document": doc,
        "recommendation": recommend(doc, flag),
    }
