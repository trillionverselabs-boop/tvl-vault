# The Vault — handoff

**Last updated:** 2026-11-15 ~09:05 EST
**Owner:** this session (charlene). **One working copy:** `/home/lisacore/work/tvl-vault`
**Repo:** local git only — **no remote, therefore private.** Do not add a remote without Lisa saying so.

---

## Done, with evidence

| # | What | Evidence |
|---|---|---|
| 0 | Corpus backed up | `/home/lisacore/backups/tvl-corpus-2026-11-14.tar.gz` (133 MB) · `tvl-notes-2026-11-14.tar.gz` (206 KB) |
| 0.5 | **The approved look** | `docs/mockup/vault-mockup.html` — self-contained, no dependencies; screens in `docs/mockup/shots/01..06` |
| 1 | Paths | `src/vault/paths.py` — profile-scoped data root, corpus roots, junk-dir excludes |
| 2 | Sources | `src/vault/sources.py` — enumerate, classify, sha256 dedupe |
| 3 | Extract | `src/vault/extract.py` — pdf/docx/html/csv/markdown → text + **real section headings** |
| 4 | Index | `src/vault/index.py` — one-pass rebuild, SQLite FTS5, BM25, punctuation-safe |
| 5 | Flags | `src/vault/review.py` — deterministic duplicate / outdated / unclear / current |
| 5.5 | Retrieval quality | commit `4a080b8` — title-weighted BM25, per-document cap, `search_prefix` (catches `chunk` → `Chunking`); worktree at that commit: **33 passed** |
| 5.6 | Corpus hygiene | commit `9665462` — the Vault no longer indexes its own repo; browser download copies (`doc (1).pdf`) collapse; worktree: **35 passed** |
| 5.7 | Review queue + corrections | commit `08fe1d9` — `corrections` table, `review.queue()`, a decision never writes a source; worktree: **40 passed** |
| 6 | **Backend routes + desktop page** | commit `40266be` — `dashboard/plugin_api.py`, `desktop/plugin.js` (Graph · Wall · Ask · Review), `__init__.py`, `plugin.yaml`. `hermes plugins validate .` → **`Validation passed.`** + `security scan — safe`; worktree: **85 passed** |
| 7 | **Cited question answers** | commit `2926270` — `src/vault/qa.py` (retrieval ladder + IDF ranking + citations, session model, temperature 0); worktree: **52 passed** |

**Tests:** 85 passed.
```bash
cd /home/lisacore/work/tvl-vault
PYTHON=.venv/bin/python ./scripts/test.sh
# 85 passed, 1 warning in 34.62 s
```
Every commit above was checked out into a throwaway worktree and tested on its own
(33 → 35 → 40 → 52 → 85 passing); no broken intermediate state is recorded.

**Real build:** 369 documents · 1,866 sections · 99 duplicates · **5.2 s**.
```bash
.venv/bin/python /home/lisacore/.hermes/profiles/charlene/cache/scratch/evidence.py
# BUILD 5.2s documents=369 sections=1866 duplicates=99
# FLAGS {'duplicate': 99, 'unclear': 43, 'current': 278}
```
Verified searches: `sabotage` → *Paper & Claim Verification Report* · `chunking` → *TVL — CIA of AI — Canonical Logic* · `budget` → *Validize Research Pipeline v2*.
Ask path (`what did the doctrine say about chunking?`) returns the CIA of AI *RAG System Definition* section in the top 6.

**Corpus roots:** `~/.hermes/profiles/charlene/attachments` · `/home/lisacore/work` · `/home/lisacore/Projects`
**New corpus landed 2026-11-14:** `/home/lisacore/work/tvl-ingest/Trillionverselabs vision/` — 25 PDFs, 51 MB, already indexed.

---

## Next, in order

| Task | What | Where |
|---|---|---|
| 8 | One-command rebuild + flag summary | `src/vault/cli.py`, `scripts/rebuild.sh` |
| 9 | Images: dimensions + vision captions, **non-junk only**; keep images out of the review queue | `src/vault/images.py` |
| 10 | Conflict detection — model-assisted, on demand, capped at 200 pairs. *(The review-queue half — Keep / Confirm / Edit + `corrections` — is already done in commit `08fe1d9`; only the model-assisted conflict pass remains.)* | `src/vault/review.py` |
| 11 | Package: `hermes plugins validate . --install-deps`, README/SCHEMA/CORPUS/DECISIONS | repo root, `docs/` |
| 12 | **Review walkthrough with Lisa** — needs her, not autonomous | — |
| 13 | **Draft the eight-document spine** (mission → metrics) + the dream statement, each section citing the corpus. One read, then split into site pages | `docs/SPINE.md` |
| 14 | **The research-to-product pipeline**: Vault → scored opportunities → products. The chosen path | `src/vault/` + `docs/` |

Full detail and copy-pasteable code: `docs/PLAN.md`.

---

## Rules — do not break

1. **Private.** No GitHub remote without Lisa's explicit word.
2. **No plugins work.** Lisa said resolve The Vault first.
3. **$0.** Free Nous model only; everything else stdlib + `pdftotext`.
4. **Sources are never modified.** Corrections go into a `corrections` table.
5. One approved item at a time. Commit often. TDD per task.

---

## Continuation

A cron job **`tvl-vault-build`** (id `e2821cda9d9f`) runs **every 2 h** (4/12 used), catch-up on, delivering locally. It reads this file, does the first undone task, commits, and updates this file. It stops and writes a "Needs Lisa" line rather than guessing.
Pause it with `hermes cron pause tvl-vault-build`; resume with `hermes cron resume tvl-vault-build`.
A `systemd-inhibit` blocker is running so idle sleep does not stop it.

**This run (2026-11-15 08:47).** The 06:00 run had implemented tasks 6 and 7 (and the
review-queue half of 10) but left all of it **uncommitted**, with one failing test. This
run finished it: fixed the retrieval ranking, committed the work as five task-sized
commits (`4a080b8`, `9665462`, `08fe1d9`, `2926270`, `40266be`), and verified each in a
worktree. Nothing is pushed; no remote exists.

---

## Learned while doing this

- **Exact-token FTS5 misses morphology.** A question says `chunk`, the doctrine says
  `Chunking`; `MATCH '"chunk"'` finds nothing. The Ask path now uses prefix search
  (`"chunk"*`) per significant word. `/search` keeps exact semantics on purpose.
- **Rank by distinctiveness, not by word count.** The first version re-sorted by how
  many question words a section contained, so a section mentioning `document` three
  times beat the section that actually answers. Now the primary key is the rarest
  matched word (IDF), then a title match, then the match count, then BM25.
- **A recall ladder must not be capped at `k`.** With `limit=k` on each rung,
  `retrieve(db, q, 2)` and `retrieve(db, q, 6)` returned different corpora. The rungs
  now reach a fixed `RECALL_DEPTH = 25`; only the final selection is capped.
- **The Vault used to index itself.** `tvl-vault` lives inside `~/work`, a corpus root,
  so its own plan and handoff were being ranked as doctrine. `paths.is_excluded_dir`
  now skips it.
- **No `outdated` flags on the real corpus.** The deterministic version-regress rule
  finds no pair here (the Platform Governance `.docx` is the same v1.1 as its `.pdf`).
  That is honest, but the plan's acceptance expected ≥ 1 — worth a look in the task-12
  walkthrough.
- **43 `unclear` flags are mostly images.** Images are indexed as documents with no
  sections, so the deterministic pass calls them unclear. Task 9 gives them
  dimensions/captions and should keep them out of the human review queue.

---

## Needs Lisa (open questions — not blocking)

1. Should `work/tvl-*` get git repos of their own, or is the Vault DB enough history?
2. The ~130 plugin-test screenshots: keep indexed as artifacts (current plan), or drop?
3. The `validize{a..n}.jpg` renders — current brand assets, or superseded by `tvl-brand`?
4. The 1.6 MB Nous Arete-27B page — keep it as a captured source, or drop it?

---

## Direction decisions — 2026-11-15 (from Lisa, binding)

1. **The path is the research-to-product pipeline.** The Vault → scored opportunities → products. That is the work; everything else waits.
2. **The digital product is dropped.** The earlier "$7–27 digital product" idea is old and is not part of the plan.
3. **Let the numbers speak.** Evidence-first: no vanity numbers, no aspirational figures presented as measurements. Every number carries a source, a formula and a threshold.
4. **The goal ladder:** survive **$1.54M** annual revenue → middle **$100M** → ultimate **$5–10 billion**. (Revenue vs valuation is not yet pinned; the big numbers read as valuation.)
5. **Monthly allowance is $0.** The doctrine's $300 / $80 / $100 figures assumed a Google credit offer that **expired** after Google's rule churn. The corpus already records this in `Projects/youtube-channel/docs/DOCTRINE-REVIEW.md` §1 — **do not repeat the stale budget numbers** in anything written from here.
6. **The dream:** three versions were considered — **A** the Auditable Company (headline), **B** the Self-Building Company (mechanism), **C** the Strategy Engine (product). Agreed direction: A as the headline, B as the mechanism, C as the product.

## Two things to know

- **Two ingest servers** may still be running on port 8787 — pid 3051597 on `127.0.0.1`, pid 3054259 on `100.122.23.86` — both started by the earlier session, both writing `/home/lisacore/work/tvl-ingest`. Redundant, not harmful. Stop them once the ingest is finished.
- **pytest** lives in `.venv`. If it is missing: `.venv/bin/python <get-pip.py>` then `.venv/bin/python -m pip install pytest`.
