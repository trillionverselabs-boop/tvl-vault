# The Vault — schema

One SQLite file. Everything in it is derived from the corpus, so any table can be
rebuilt; nothing in it is the only copy of a fact except `corrections`, which is
mirrored to `corrections.jsonl` in the data root.

**File:** `~/.hermes/profiles/<profile>/tvl-vault/vault.db`
**Engine:** SQLite 3.53.1 with FTS5. **No migrations** — a rebuild recreates it.

```bash
python -m vault stats          # the counts, read-only
```

---

## `documents`

One row per unique source file. `doc_id` is the first 16 hex characters of the
file's **sha256** — a stable identity that survives a rename of the file, and the
key every other table refers to. A file whose bytes appear twice is one row; the
second path is in `duplicates`.

| Column | Type | Meaning |
|---|---|---|
| `doc_id` | TEXT PK | `sha256[:16]`. The document's identity. |
| `path` | TEXT | Absolute path to the canonical copy. |
| `kind` | TEXT | `pdf` · `docx` · `markdown` · `html` · `csv` · `text` · `image`. |
| `title` | TEXT | The document's own title: the PDF header block, the HTML `<title>`, the first markdown heading, else the filename stem. |
| `sha256` | TEXT | The full content hash. |
| `size` | INTEGER | Bytes. |
| `is_junk` | INTEGER | 1 for a plugin-test screenshot. Indexed as an artifact, never captioned, never on the review queue. |
| `meta_json` | TEXT | The header block: `title`, `version`, `owner`, `layer`, `status`, `mission`, `purpose`. |
| `rag_json` | TEXT | The RAG tag block: `entity[]`, `intent[]`, `dependency[]`, `validity`, `au2i[]`. `dependency` is the graph's edge list. |
| `extracted_at` | TEXT | `datetime('now')` at extraction. |

---

## `sections`

One row per real section heading. This is the unit the whole system works in —
retrieval, search, flags and citations all point at a section, not a document.

| Column | Type | Meaning |
|---|---|---|
| `section_id` | TEXT PK | `<doc_id>-<ord, 4 digits>`, e.g. `c39048051c70a1b2-0003`. |
| `doc_id` | TEXT FK | → `documents.doc_id`, `ON DELETE CASCADE`. |
| `ord` | INTEGER | Order within the document, from 0. |
| `title` | TEXT | The heading text, with `**` and numbering stripped. |
| `level` | INTEGER | Heading depth: 1 for `SECTION 0 — …` and `#`, 2 for `1. …`, 3 for `##`. |
| `body` | TEXT | The section's text, up to the next heading. |
| `line` | INTEGER | The line in the extracted text where the heading starts. |
| `word_count` | INTEGER | Words in `body`. A section under 24 words cannot state a claim. |

**Heading conventions recognised** (they are not consistent across the corpus):
`SECTION 0 — Title` (U+2014 em dash), `1. Title`, `# Title`, `# **Title**`,
`## **1.1 Title**`. A document with none of these gets **zero sections** and is
flagged `unclear` — honestly, rather than guessing a structure.

---

## `duplicates`

Keyed `(sha256, path)`, so a group of N identical files contributes **N − 1** rows
and one canonical document can own several.

| Column | Type | Meaning |
|---|---|---|
| `sha256` | TEXT | The shared content hash (with `path`, the primary key). |
| `path` | TEXT | The copy that is *not* the canonical file. |

Measured on the real corpus: **118 rows** — image 60 · pdf 32 · markdown 22 ·
html 2 · text 2. A row can come from two places: a byte-identical sibling in the
same root, or the same bytes appearing under a second root (the attachments copy
and the `tvl-ingest` copy of a PDF).

---

## `flags`

Keyed `(doc_id, section_id, flag)`. One row per status a document or section
carries. `section_id` is NULL for a whole-document flag.

| Column | Type | Meaning |
|---|---|---|
| `doc_id` | TEXT | The document the flag is about. |
| `section_id` | TEXT or NULL | The section, for a section-level flag. **For a `conflict` flag this slot carries the *partner document's* `doc_id`** — the table is keyed on this slot, so it is what makes a rerun know the exact pair is already settled. |
| `flag` | TEXT | `current` · `outdated` · `duplicate` · `conflict` · `unclear`. |
| `reason` | TEXT | Plain-language sentence, shown in the UI. |
| `evidence` | TEXT | The quote, path or model reason behind it. A conflict flag always carries non-empty evidence. |

Measured: `duplicate=118`, `unclear=43`, `current=92`. **`outdated=0`** — the
version-regress rule finds no pair on this corpus (the Platform Governance
`.docx` is the same v1.1 as its `.pdf`), and no VALIDITY tag says anything but
Active. That is an honest zero, not a missing feature.

`flags` is written by `rebuild` (`review.compute_flags` + `write_flags`). A route
that finds the table missing computes it, so a partial build still shows a queue.

---

## `corrections`

One row per document the human has decided on. **This is the only table a person
writes, and it never touches a source file.**

| Column | Type | Meaning |
|---|---|---|
| `doc_id` | TEXT PK | The document decided on. Keyed per document, not per flag: a document's status is one decision. |
| `flag` | TEXT | The flag the decision was about. |
| `action` | TEXT | `confirm` (the flag stands, the document leaves the queue) · `keep` (stays on the queue) · `edit` (a correction is needed; `note` says what). |
| `note` | TEXT | The reviewer's note. Required for `edit`. |
| `created_at` | TEXT | `datetime('now')`. |

A decision is also appended to `corrections.jsonl` in the data root, so a lost
database still has the history. `confirm` and `edit` clear the document's flags
everywhere they are read; `keep` leaves them.

---

## `sections_fts`

A virtual FTS5 table over `sections(title, body)`, `content='sections'`,
`content_rowid='rowid'`, kept in step by two triggers (`sections_ai`,
`sections_ad`). It is how `/search` and the Ask path find a section.

Search is **BM25** with a title tiebreak and a cap of two sections per document,
so a document split into overlapping sections cannot crowd out the one that
answers. User text is quoted per word before it reaches `MATCH` — `rag OR 1=1`
becomes three literal terms, never a boolean query.

---

## The graph's edges

Not a table — they are read from `documents.rag_json` on request:

| Edge | From → To | Source |
|---|---|---|
| `contains` | document → its sections | `sections.doc_id` |
| `depends` | document → the document named in its `DEPENDENCY:` tag | `rag_json.dependency`, matched by title |

A duplicate is **not** an edge: it needs two nodes, and the copy's path is not
one. The copy is a flag on the canonical document.
