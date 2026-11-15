# The Vault — handoff

**Last updated:** 2026-11-15 ~02:00 EST
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

**Tests:** 29 passed.
```bash
cd /home/lisacore/work/tvl-vault
PYTHON=.venv/bin/python ./scripts/test.sh
```

**Real build:** 418 documents · 2,084 sections · 60 byte-identical duplicates · **5.2 s**.
```bash
.venv/bin/python - <<'PY'
import sys; sys.path.insert(0, "src")
from pathlib import Path
from vault import index, paths, review
db = index.rebuild(paths.corpus_roots(), Path("/tmp/vault.db"))
print(db.execute("SELECT COUNT(*) FROM documents").fetchone()[0], "documents")
PY
```
Verified searches: `sabotage` → *Paper & Claim Verification Report* · `chunking` → *CIA of AI — Canonical Logic* · `budget` → *Validize Research Pipeline v2*.

**Corpus roots:** `~/.hermes/profiles/charlene/attachments` · `/home/lisacore/work` · `/home/lisacore/Projects`
**New corpus landed 2026-11-14:** `/home/lisacore/work/tvl-ingest/Trillionverselabs vision/` — 25 PDFs, 51 MB, already indexed.

---

## Next, in order

| Task | What | Where |
|---|---|---|
| 6 | Backend routes + desktop page. **Copy the approved mockup's CSS and force layout verbatim.** Tabs: Graph · Wall · Ask · Review | `dashboard/plugin_api.py`, `desktop/plugin.js` |
| 7 | Cited question answers on the session model (free Nous) | `src/vault/qa.py` |
| 8 | One-command rebuild + flag summary | `src/vault/cli.py`, `scripts/rebuild.sh` |
| 9 | Images: dedupe (done) + dimensions + vision captions, **non-junk only** | `src/vault/images.py` |
| 10 | Conflict detection — model-assisted, on demand, capped at 200 pairs | `src/vault/review.py` |
| 11 | Package: `plugin.yaml`, `hermes plugins validate . --install-deps`, README/SCHEMA/CORPUS/DECISIONS | repo root, `docs/` |
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

A cron job **`tvl-vault-build`** (id `e2821cda9d9f`) runs **every 2 h**, 12 times, catch-up on, delivering locally. It reads this file, does the first undone task, commits, and updates this file. It stops and writes a "Needs Lisa" line rather than guessing.
Pause it with `hermes cron pause tvl-vault-build`; resume with `hermes cron resume tvl-vault-build`.
A `systemd-inhibit` blocker is running so idle sleep does not stop it.

---

## Direction decisions — 2026-11-15 (from Lisa, binding)

1. **The path is the research-to-product pipeline.** The Vault → scored opportunities → products. That is the work; everything else waits.
2. **The digital product is dropped.** The earlier "$7–27 digital product" idea is old and is not part of the plan.
3. **Let the numbers speak.** Evidence-first: no vanity numbers, no aspirational figures presented as measurements. Every number carries a source, a formula and a threshold.
4. **The goal ladder:** survive **$1.54M** annual revenue → middle **$100M** → ultimate **$5–10 billion**. (Revenue vs valuation is not yet pinned; the big numbers read as valuation.)
5. **Monthly allowance is $0.** The doctrine's $300 / $80 / $100 figures assumed a Google credit offer that **expired** after Google's rule churn. The corpus already records this in `Projects/youtube-channel/docs/DOCTRINE-REVIEW.md` §1 — **do not repeat the stale budget numbers** in anything written from here.
6. **The dream:** three versions were considered — **A** the Auditable Company (headline), **B** the Self-Building Company (mechanism), **C** the Strategy Engine (product). Agreed direction: A as the headline, B as the mechanism, C as the product.

## Two things to know

- **Two ingest servers** are running on port 8787 — pid 3051597 on `127.0.0.1`, pid 3054259 on `100.122.23.86` — both started by the earlier session, both writing `/home/lisacore/work/tvl-ingest`. Redundant, not harmful. Stop them once the ingest is finished.
- **pytest** lives in `.venv`. If it is missing: `.venv/bin/python <get-pip.py>` then `.venv/bin/python -m pip install pytest`.
