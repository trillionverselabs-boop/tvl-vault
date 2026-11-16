# The Vault — one indexed, visually searchable home for the whole TVL corpus

A local-first Hermes desktop plugin. It reads every TVL document, image and note
already on this machine, puts them in one deduplicated, section-indexed SQLite
file, and shows them as a **graph**, a **card wall**, a **full-text search**, a
**cited question-answering view**, and a **review queue** that marks every
section `CURRENT / OUTDATED / DUPLICATE / CONFLICT / UNCLEAR` instead of silently
trusting a document because it is old.

No account. No server. No telemetry. The corpus is **only ever read** — nothing
in this plugin writes to a source file, and a review decision goes to a
`corrections` table, not to the document.

---

## What it is

| | |
|---|---|
| **One index** | `~/.hermes/profiles/<profile>/tvl-vault/vault.db` — SQLite + FTS5, one file, rebuildable in seconds. |
| **Four surfaces** | Graph (documents + sections + dependencies) · Wall (cards + pictures) · Ask (cited answers) · Review (the human queue). |
| **Five flags** | `current`, `outdated`, `duplicate`, `conflict`, `unclear` — computed by code, shown in plain language. |
| **Two model passes** | Only Ask and the conflict pass touch a model. Both are on demand; a rebuild is $0 and offline. |
| **Cost** | $0 recurring. Everything is Python stdlib + `pdftotext` (poppler). No pip packages. |

## What it is not

- **Not a rewrite of the corpus.** It indexes what is there. A correction is a row in a table; your documents keep their original bytes.
- **Not a vector database.** The corpus is ~2.7 MB of text; BM25 + a title tiebreak is better at that size and free. No embeddings.
- **Not an agent toolset.** It registers no tools (`provides_tools: []`). The desktop page is the product.
- **Not a server.** No port, no URL, no cloud. It runs inside the Hermes desktop.
- **Not a claim that the corpus is clean.** It is messy, and the review queue says so.

---

## Install

The Vault is a desktop plugin. In the Hermes desktop: **Install from Git**, paste
this repository's URL, tick **Desktop**, install unpinned. Nothing to build, no
dependencies to install.

> The repository is **private**. Do not make it public, and do not add a remote,
> without Lisa saying so.

---

## Rebuild the index

One command. It reads the corpus, writes the index, recomputes the flags.

```bash
cd /home/lisacore/work/tvl-vault
./scripts/rebuild.sh
```

```
vault: 4 roots → /home/lisacore/.hermes/profiles/charlene/tvl-vault/vault.db
  documents 369 · sections 1866 · duplicates 118 · images 199 · flags: duplicate=118, unclear=43, current=92 · images: 116 shown · 83 test screenshots
```

Useful variants:

```bash
./scripts/rebuild.sh --db /tmp/vault.db     # write somewhere else
./scripts/rebuild.sh --root ~/work         # one root only (repeatable)
python -m vault stats                      # read the counts, write nothing
```

**Rebuild is safe and idempotent.** The index is derived; running it twice gives
the same rows. It never writes to a source file, and it never calls a model.

---

## The four flags

| Flag | UI name | What it means | How it is decided |
|---|---|---|---|
| `current` | Current | newest version, no contradiction found | code |
| `outdated` | Outdated | a newer version of the same title exists, or its own VALIDITY tag is not Active | code |
| `duplicate` | Duplicate | a byte-identical copy also exists (sha256) | code |
| `conflict` | Needs review | two passages make claims that cannot both be true | model, on demand |
| `unclear` | Unclear | no extractable sections, or too little text to be a claim | code |

A picture has **no flag at all** — an image makes no claim, so "current" would be
a false statement about it. The wall shows it as an artifact instead.

---

## Where things live

| Path | What |
|---|---|
| `src/vault/` | the build: `paths`, `sources`, `extract`, `index`, `review`, `qa`, `images`, `cli` |
| `dashboard/plugin_api.py` | the backend, `/api/plugins/tvl-vault/` |
| `desktop/plugin.js` | the window (Graph · Wall · Ask · Review) |
| `docs/PLAN.md` | the plan, measured before any code |
| `docs/SCHEMA.md` | the database tables, column by column |
| `docs/CORPUS.md` | the measured inventory, with exact hashes |
| `docs/DECISIONS.md` | the decisions and what was ruled out |

---

## Tests

```bash
cd /home/lisacore/work/tvl-vault
PYTHON=.venv/bin/python ./scripts/test.sh
# 180 passed
```

The suite is hermetic: `tests/conftest.py` has an autouse fixture that points
`HERMES_HOME` at a throwaway tree, so no test can read the real corpus or
write the real profile data root — a module that forgets to redirect still
cannot touch `~/.hermes/profiles/charlene/tvl-vault/`. `HERMES_VAULT_ROOTS`
pins the corpus roots per module where a test builds its own fixture.
