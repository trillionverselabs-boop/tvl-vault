"""Cited question-answering. The model sees ONLY the retrieved sections.

Nothing here invents an answer. The prompt forbids it, a citation that does not
resolve to a passage is dropped, and a question the corpus cannot answer gets
one fixed sentence. The model is the session's own — no provider or model
override (that needs a consent-gated capability this plugin does not declare),
temperature 0 so the same question gives the same answer.

Retrieval note: a natural question is a sentence, and SQLite FTS5 treats the
terms as AND — "what does the doctrine say about sabotage?" matches nothing
because no section contains "what". A question is therefore retried as its
significant words, each as a prefix match ("chunk" finds "Chunking"), and
ranked by how *distinctive* the matched words are. That is a recall ladder
inside the Ask path only; `/search` keeps exact BM25 semantics.
"""

from __future__ import annotations

import math
import re
import sqlite3

from . import index

# Long enough for a section's logic, short enough that six of them plus the
# question still fit a small context. A passage that runs past this is cut, and
# the cut is the model's business, not a silent truncation of the corpus.
MAX_PASSAGE_CHARS = 1800
DEFAULT_K = 6
# How deep each ladder rung reaches before the final top-k is chosen. The rungs
# must not be capped at k: a relevant section that is fourth on one rung would
# otherwise disappear when k=3, making the answer depend on the caller's k.
RECALL_DEPTH = 25

REFUSAL = "Not answered by the corpus."

SYSTEM = """You are answering from a fixed corpus of business documents. Rules:
1. Use ONLY the numbered passages below. Do not invent, do not add outside knowledge.
2. Every claim ends with a citation [n] matching a passage number.
3. If the passages do not answer the question, reply with exactly: "Not answered by the corpus."
4. Plain language. Short sentences. No jargon."""

# English stopwords. A question's meaning lives in the other words; keeping
# these in an AND query is what made "what does the doctrine say about X"
# retrieve nothing at all.
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

_WORD_RE = re.compile(r"[0-9A-Za-z]{3,}")


def build_refusal() -> str:
    """The one sentence used when the corpus does not answer the question."""
    return REFUSAL


def _significant_words(question: str) -> list[str]:
    """The words that carry the question, in order, stopwords removed."""
    seen: set[str] = set()
    out: list[str] = []
    for w in _WORD_RE.findall((question or "").lower()):
        if w in _STOPWORDS or w in seen:
            continue
        seen.add(w)
        out.append(w)
    return out


def _or_query(words: list[str]) -> str:
    """Kept for callers that build the expression themselves; `index.search_or`
    is the supported path (it ranks and caps per document too)."""
    return " OR ".join(f'"{w}"' for w in words)


def _idf(db: sqlite3.Connection, word: str, n_sections: int) -> float:
    """Inverse document frequency of *word* over the sections.

    A word that appears in a hundred sections ("document", "doctrine") says
    nothing about which one answers; a word that appears in three ("chunk") is
    the subject of the question. BM25 alone cannot see that on a small corpus.
    """
    df = db.execute(
        "SELECT COUNT(*) FROM sections_fts WHERE sections_fts MATCH ?",
        (f'"{word}"*',),
    ).fetchone()[0]
    return math.log((n_sections + 1) / (df + 0.5))


def retrieve(db: sqlite3.Connection, question: str, k: int = DEFAULT_K) -> list[dict]:
    """Sections worth showing the model, best first, duplicates removed.

    Recall ladder: the question as asked (exact BM25), then each significant
    word on its own as a *prefix* match, then the words as a prefix OR. A
    question is a sentence, and its subject is often a different inflection
    than the corpus uses ("chunk" / "Chunking"), so the per-word rungs are
    prefix searches.

    Ranking is by distinctiveness, not by how many words a section happens to
    contain. The primary key is the rarest word a section matches (IDF); a
    section that matches "chunk" outranks one that matches "document" three
    times. A title that names one of the question's words breaks a tie, then
    the number of matched words, then BM25.
    """
    if db is None:
        return []
    words = _significant_words(question)
    if not words:
        return []
    n_sections = db.execute("SELECT COUNT(*) FROM sections").fetchone()[0]
    idf = {w: _idf(db, w, n_sections) for w in words}

    seen: set[str] = set()
    out: list[dict] = []

    def add(rows):
        for r in rows:
            if r["section_id"] in seen:
                continue
            seen.add(r["section_id"])
            out.append(r)

    add(index.search(db, question, limit=RECALL_DEPTH))
    for w in words:
        add(index.search_prefix(db, w, limit=RECALL_DEPTH))
    add(index.search_prefix(db, " ".join(words), limit=RECALL_DEPTH))

    def score(r: dict):
        text = ((r.get("section_title") or "") + "\n" + (r.get("body") or "")).lower()
        matched = [w for w in words if w in text]
        if not matched:
            return None
        title = (r.get("section_title") or "").lower()
        title_hits = sum(1 for w in matched if w in title)
        return (max(idf[w] for w in matched), title_hits, len(matched))

    scored = [(score(r), r) for r in out]
    scored = [(s, r) for s, r in scored if s is not None]
    scored.sort(key=lambda t: (-t[0][0], -t[0][1], -t[0][2], t[1].get("score", 0)))
    return [r for _, r in scored][:k]


def build_prompt(question: str, chunks: list[dict]) -> str:
    parts = []
    for i, c in enumerate(chunks, start=1):
        body = (c.get("body") or "").strip()[:MAX_PASSAGE_CHARS]
        parts.append(f"[{i}] ({c.get('doc_title', '')} — {c.get('section_title', '')})\n{body}")
    return f"{SYSTEM}\n\nQUESTION: {question}\n\nPASSAGES:\n" + "\n\n".join(parts)


def parse_citations(text: str, chunks: list[dict]) -> list[dict]:
    """The passages the answer actually cited, in order.

    A citation outside 1..len(chunks) is dropped rather than guessed at: a
    hallucinated [9] must not surface as a ninth source. Each entry is shaped
    for the UI: `n`, `title` (the section), `doc` (the document), `path`.
    """
    nums = {int(n) for n in re.findall(r"\[(\d+)\]", text or "")}
    out = []
    for n in sorted(nums):
        if not 1 <= n <= len(chunks):
            continue
        c = chunks[n - 1]
        out.append({
            "n": n,
            "title": c.get("section_title", "") or "",
            "doc": c.get("doc_title", "") or "",
            "path": c.get("doc_path", "") or "",
            "body": (c.get("body") or "")[:MAX_PASSAGE_CHARS],
        })
    return out


def answer(db: sqlite3.Connection, question: str, llm, k: int = DEFAULT_K) -> dict:
    """Answer *question* from the corpus, with citations.

    Returns `{answer, citations, sources}`. `sources` is the retrieval set (what
    the model was shown), which is not the same as `citations` (what it used) —
    the UI shows both, so a reader can see what was in front of the model.
    A model failure is returned as `{answer: "", error: ...}`, never swallowed.
    """
    if not (question or "").strip():
        return {"answer": REFUSAL, "citations": [], "sources": []}

    chunks = retrieve(db, question, k)
    if not chunks:
        return {"answer": REFUSAL, "citations": [], "sources": []}

    try:
        res = llm.complete(
            [{"role": "user", "content": build_prompt(question, chunks)}],
            temperature=0,
            purpose="tvl-vault ask",
        )
    except Exception as exc:                      # a free model times out; say so
        return {"answer": "", "error": f"{type(exc).__name__}: {exc}",
                "citations": [], "sources": chunks}

    text = (getattr(res, "text", "") or "").strip()
    return {"answer": text, "citations": parse_citations(text, chunks), "sources": chunks}
