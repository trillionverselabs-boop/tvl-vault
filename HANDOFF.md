# The Vault — handoff

**Last updated:** 2026-11-15 ~16:40 EST
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
| 8 | **One-command rebuild + flag summary** | commit `9272142` — `src/vault/cli.py` + `src/vault/__main__.py` + `scripts/rebuild.sh`; `./scripts/rebuild.sh` on the real corpus: **369 documents · 1,866 sections · 118 duplicates · 199 images · flags: duplicate=118, unclear=43, current=260 in 6.7 s**; worktree: **100 passed** |
| 9 | **Images on the wall, out of the review queue** | commits `5714ae8` · `7f4139c` · `6ef4c65` · `68a4691`; worktree at `68a4691`: **136 passed**; `./scripts/rebuild.sh` on the real corpus: **images: 116 shown · 83 test screenshots**, review queue **161 → 101 with 0 images**; `hermes plugins validate .` → **`Validation passed.`** + **`security scan — safe`** |

**Tests:** 136 passed.
```bash
cd /home/lisacore/work/tvl-vault
PYTHON=.venv/bin/python ./scripts/test.sh
# 136 passed, 1 warning in 55.41 s
```
Every commit above was checked out into a throwaway worktree and tested on its own
(33 → 35 → 40 → 52 → 85 → 100 → 108 → 126 → 135 → 136 passing); no broken
intermediate state is recorded.

**Real build (at `68a4691`):** 369 documents · 1,866 sections · 118 duplicates · 199 images · **6.8 s**.
```bash
cd /home/lisacore/work/tvl-vault
./scripts/rebuild.sh --db /home/lisacore/.hermes/profiles/charlene/cache/scratch/task9-red/wt-final.db
# exit 0 in 6.8 s
# vault: 4 roots → …/wt-final.db
#   documents 369 · sections 1866 · duplicates 118 · images 199 · flags: duplicate=118, unclear=43, current=92 · images: 116 shown · 83 test screenshots
```
Run twice in a row, identical counts (idempotent).
`python -m vault stats --db <file>` prints the same numbers without writing anything.

**The wall (task 9):** 199 images → **116 shown, 83 test screenshots** (counted, not
listed, never sent to the model). 0 unreadable dimensions. Review queue **101**
(58 duplicate + 43 unclear), **0 images**.
Verified searches: `sabotage` → *Paper & Claim Verification Report* §2.2 "Tournament sabotage" · `chunking` → *TVL — CIA of AI — Canonical Logic (v1.0)* §RAG System Definition · `budget` → *Validize Research Pipeline v2*.
`python -m vault stats --db <file>` prints the same numbers without writing anything.

**Corpus roots:** `~/.hermes/profiles/charlene/attachments` · `/home/lisacore/work` · `/home/lisacore/Projects` · `/home/lisacore/work/tvl-ingest` (4 roots; the last is added only when it exists, and `HERMES_VAULT_ROOTS` overrides all of them)
**New corpus landed 2026-11-14:** `/home/lisacore/work/tvl-ingest/Trillionverselabs vision/` — 25 PDFs, 51 MB, already indexed.

---

## Next, in order

| Task | What | Where |
|---|---|---|
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

**This run (2026-11-15 11:17).** The 08:47 run had implemented tasks 6 and 7 (and
the review-queue half of 10) but left all of it uncommitted; it was finished as
five task-sized commits (`4a080b8`, `9665462`, `08fe1d9`, `2926270`, `40266be`),
each verified in a worktree.

This run did **task 8** and found the thing the plan had missed: nothing computed
the flags. `index.rebuild` writes documents and sections but leaves the `flags`
table empty, so the Review tab showed nothing on a fresh build — the queue was
only ever filled by a route's `_ensure_flags` fallback. `python -m vault rebuild`
now does both jobs, and the flags it writes are the ones the queue reads.

**This run (2026-11-15 16:14).** Task 9 was already written but uncommitted. It was
finished as four commits (`5714ae8`, `7f4139c`, `6ef4c65`, `68a4691`), each
verified in a worktree, and the real corpus then exposed two defects the fixtures
had hidden:

- **The `popup*` junk pattern was anchored at both ends**, so the browser's
  re-download copies (`popupd1-2.jpg`, `popupc-2.jpg`, `popupd14-2.jpg`) were
  not junk. 10 real screenshots were indexed as content, shown on the wall, and
  offered to the caption model. Fixed in `sources.JUNK_PATTERNS`; the serial is
  now one letter plus an optional `_small`/digit/counter, so `popupshire.png`
  stays content. Junk 74 → 83.
- **An image could be on the review queue as `duplicate`.** The fixture had no
  duplicate image, so the test passed while the real corpus put **60 images** on
  the queue — 161 queue rows, two-thirds of them pictures nobody could keep,
  confirm or edit. `review.queue()` now excludes images. The duplicate *flag*
  stays recorded (`/stats` still counts 118); the queue is a human decision.
  Queue 161 → 101, 0 images.

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
- **`paths.corpus_roots()` was hard-pinned to `/home/lisacore`.** Task 8's test that
  pointed `HERMES_HOME` at a throwaway tree still read the real corpus (242 documents
  from `~/work` and `~/Projects`), so a test could never be hermetic and a second
  machine would read folders that do not exist. It now takes `HERMES_VAULT_ROOTS`
  (a `os.pathsep` list) as an override, and the ingest drop zone
  `~/work/tvl-ingest` is a fourth root when it exists.
- **The duplicate count is 118, not 99.** The earlier `evidence.py` probe indexed only
  the attachments root. The real command indexes all four roots; measured split of the
  118 `duplicates` rows: **image 60 · pdf 32 · markdown 22 · html 2 · text 2**. And
  `documents` is 369 = image 199 · markdown 94 · pdf 35 · html 26 · text 10 · csv 4 ·
  docx 1. The 199 image documents are the corpus's images, not just the ~28 portraits.
- **`python -m vault` needs `__main__.py`.** A package without one fails with
  "No module named vault.__main__". `scripts/rebuild.sh` sets `PYTHONPATH=src` and
  calls `python -m vault rebuild`; the tests import `vault.cli` as a *package*
  module, because a standalone `spec_from_file_location` cannot resolve its
  relative imports.
- **A fixture that lacks the failing case proves nothing.** Task 9's image tests
  passed while the real corpus put 60 images on the review queue, because the
  fixture had no byte-identical image. Both defects above were found by running
  the real corpus, not the suite. Every new flag rule now carries a fixture with
  the real shape (`calvin.png` + `calvin-copy.png`), not just the happy path.
- **Dimensions need no library.** PNG's IHDR, JPEG's SOFn marker and WebP's
  `VP8 `/`VP8L`/`VP8X` chunks are all in the file header, so `pyproject.toml`
  keeps `dependencies = []` — which the desktop's non-interactive install
  requires. Four real files are WebP bytes named `.jpg`, so the type sent to the
  vision model is sniffed from content, not the extension.
- **The junk rule is corpus-specific and drifts.** `^popup[a-z0-9_]*$` was
  written for the names that existed when task 2 shipped. Two families are still
  not covered and are now Lisa's call (see Needs Lisa #5): 45 video frames under
  `work/arena-demo-video/arena-demo/frames/` and 4 `strategic-arena/assets/*.png`
  screenshots. Both are indexed as content today.

---

## Needs Lisa (open questions — not blocking)

1. Should `work/tvl-*` get git repos of their own, or is the Vault DB enough history?
2. The ~130 plugin-test screenshots: keep indexed as artifacts (current plan), or drop?
3. The `validize{a..n}.jpg` renders — current brand assets, or superseded by `tvl-brand`?
4. The 1.6 MB Nous Arete-27B page — keep it as a captured source, or drop it?
5. **New (task 9):** 49 images are indexed as content but look like build output —
   45 video frames in `work/arena-demo-video/arena-demo/frames/` (`f1.png`…`v5_53.png`)
   and 4 screenshots in `work/strategic-arena/assets/` (`banner`, `how-it-works`,
   `marketplace`). Junk (counted, never captioned), or real content? Today they
   are content, so the caption model would be asked to describe 45 video frames.

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
