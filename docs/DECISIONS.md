# The Vault — decisions

Every decision below was taken with Lisa, or is a technical choice made for a
stated reason. Nothing here is a guess presented as a decision.

---

## 1. The four decisions taken with Lisa (2026-11-14)

| # | Decision | Why it matters |
|---|---|---|
| 1 | **Scope:** the vault + all images + all 118 markdown docs under `~/work` and `~/Projects`. | The corpus is the business's memory. Leaving part of it out would make the index lie by omission. |
| 2 | **Surfaces:** graph view + searchable card wall + full-text search, in that order. | She asked for "those pretty visual items I see on YouTube". The graph is the hero; the search is the utility. |
| 3 | **Questions:** both — fast local search **and** an optional cited Q&A on the free Nous model. | Search is free and instant; the model is for a question that needs a sentence assembled from several sections. |
| 4 | **Staleness:** **Option A** — index every real section heading, stamp `OUTDATED` / `DUPLICATE` / `CONFLICT` / `UNCLEAR` **on the section, visibly, reversibly**. No silent rewriting of the corpus. | The documents are the record. The Vault describes them; it does not edit them. |

### What was ruled out

**Option B — cleaned, restructured copies of the corpus.** Not chosen. It would
have produced a second corpus that silently disagreed with the first, and the
disagreement would be invisible. Corrections live in a `corrections` table; the
source files keep their bytes. Revisit only if Lisa asks.

**A vector database.** Ruled out on size: the corpus is ~2.7 MB of text. BM25 +
a title tiebreak is better at that size, free, and explainable — a reviewer can
see *why* a section matched. Embeddings are a YAGNI trap here.

**OCR.** Ruled out by the host: `tesseract` is not installed. Images are captioned
by the vision model instead, and only the ~116 non-junk ones.

---

## 2. The direction decisions (2026-11-15, binding)

1. **The path is the research-to-product pipeline.** The Vault → scored
   opportunities → products. That is the work; everything else waits.
2. **The digital product is dropped.** The earlier "$7–27 digital product" idea is
   old and is not part of the plan.
3. **Let the numbers speak.** Evidence-first: no vanity numbers, no aspirational
   figures presented as measurements. Every number carries a source, a formula and
   a threshold.
4. **The goal ladder:** survive **$1.54M** annual revenue → middle **$100M** →
   ultimate **$5–10 billion**.
5. **Monthly allowance is $0.** The doctrine's $300 / $80 / $100 figures assumed a
   Google credit offer that **expired**. Do not repeat the stale budget numbers.
6. **The dream:** **A** the Auditable Company (headline), **B** the Self-Building
   Company (mechanism), **C** the Strategy Engine (product).

---

## 3. Technical decisions, and the reason for each

| Decision | Reason |
|---|---|
| **Text extraction: `pdftotext -layout` via `subprocess`** | poppler 26.01.0 is already installed; `-layout` preserves the column structure the doctrine uses. No pip. |
| **DOCX: `zipfile` + `xml.etree`** | A `.docx` is a zip. `python-docx` is not installed and pip is absent (PEP 668). |
| **HTML: `html.parser`** | No bs4. |
| **Index: SQLite + FTS5, one file** | Rebuildable from the corpus in seconds; no server; survives a plugin update; BM25 is built in. |
| **Images: dimensions from the header, captions from the vision model** | No OCR and no Pillow. `pyproject.toml` must keep `dependencies = []` or the desktop's non-interactive install aborts. |
| **UI: Hermes desktop plugin (`desktop/plugin.js` + `dashboard/plugin_api.py`)** | The pretty graph is free — no extra service, no npm, offline. |
| **Q&A: `ctx.llm`, session model, temperature 0** | Already the session's model. No provider or model override — that needs a consent-gated capability this plugin does not declare. |
| **Graph: hand-rolled SVG** | ~120 lines of vanilla JS. A force library would be a dependency and a build step for one screen. |
| **Model passes are on demand, never in `rebuild`** | Every call costs money and breaks when the free model is throttled. `rebuild` is $0 and offline; `POST /conflicts` and `POST /ask` are the only callers. |

---

## 4. Constraints that are non-negotiable

- **$0 recurring.** Free Nous model only; everything else stdlib + poppler.
- **Private.** No GitHub remote without Lisa's explicit word.
- **Local-first.** No account, no telemetry. Writes go only to the profile's
  plugin data root.
- **Sources are never modified.** A correction is a row in `corrections`.
- **Evidence-first.** No number without a source, a formula and a threshold.
- **One clean working copy per project.**

---

## 5. Lessons that changed the implementation

These are recorded in full in `HANDOFF.md` under "Learned while doing this"; they
are decisions in their own right.

- **A one-word subject test is not a subject test.** Pairing any two sections that
  share a salient word made 724,410 pairs on the real corpus, and the 200-call cap
  went on `10px`, `9000` and `lighter`. A candidate now needs ≥ 2 shared terms, and
  numbers, hex colours and CSS units are not terms at all.
- **A flag that names a pair must store the pair.** A conflict flag's `section_id`
  slot carries the partner document's id; a title lookup goes stale the moment a
  document is renamed.
- **An image is not a claim.** Images are excluded from `unclear` and from the
  review queue; "current" would be a false statement about a picture.
- **The Vault must not index itself.** `tvl-vault` lives inside `~/work`, a corpus
  root; its own plan and handoff would otherwise outrank the doctrine.
- **A fixture that lacks the failing case proves nothing.** Two real defects (60
  images on the queue, ten `popup*` screenshots indexed as content) were found by
  running the real corpus, not the suite.
