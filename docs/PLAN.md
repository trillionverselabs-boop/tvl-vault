# Plan: The Vault — one indexed, visually searchable home for the whole TVL corpus

**Date:** 2026-11-14 · **Status:** PLAN ONLY — do not execute in this turn. Hand to an implementer.
**Host:** `rura-penthe` (user calls it `lisacore`). Active profile: `charlene`.
**Every number below was produced by a command that was actually run on this machine.** Re-run the probes to confirm before building.

---

## Goal

Build **The Vault**: a local-first Hermes plugin that ingests every TVL document, image and note already on disk into one deduplicated, section-indexed corpus, and shows it as a graph, a searchable card wall, a full-text search, and a cited question-answering view — with every section visibly marked **CURRENT / OUTDATED / DUPLICATE / CONFLICT / UNCLEAR** instead of silently trusting a document because it is old.

---

## Current context / assumptions

### 0. What the user actually asked, in her words

> "i have a aTON of documentation i put together oct 2025 to feb 2026 that outlined my business … originally they were intended to RAG documents to run my business but technology has changed. what can be done with these types of documents, ideally i want them indexed, visually searchable in those pretty visual items i see on youtube, it must be free manageable and useful i have the images but with commands i can't add attachments"

And the follow-up that settles the workflow:

> "the files and there a lot what is the best way to give to you so you can ingest absorb and categorize and put together in an organized manner so that together we go through the duplicates, the conflicts and update based on changes between when they were written and now including technological updates that back then were not possible but today are now possible"

Four decisions were taken with the user (2026-11-14):

| # | Decision |
|---|---|
| 1 | **Scope:** the vault + all images + **all 118 markdown docs** under `~/work` and `~/Projects`. |
| 2 | **Surfaces:** graph view + searchable card wall + full-text search, in that order. |
| 3 | **Questions:** both — fast local search **and** an optional cited Q&A that runs on the free Nous model. |
| 4 | **Staleness:** **Option A** — index every real section heading, stamp `OUTDATED` / `DUPLICATE` / `CONFLICT` / `UNCLEAR` **on the section, visibly, reversibly**. No silent rewriting of the corpus. |

### 1. Why the old plan (RAG over these files) is dead, and what replaced it

The doctrine documents are **RAG-shaped on purpose**. `TVL — CIA of AI — Canonical Logic (v1.0).pdf` literally opens with `1. RAG System Definition` and `1.4 Structural Design & Retrieval Assumptions`, and says:

> "Chunking must happen at the Section Header level. Retrieval systems must fetch the entire section rather than individual tokens to preserve the logic context."

That design assumed a retriever that can only read text. Three things changed:

| Then (Oct 2025 – Feb 2026) | Now (verified 2026-11-14) | Consequence |
|---|---|---|
| RAG = embed chunks, hope the right chunk comes back | **Agents read whole sections and cite them.** Hermes plugins get `ctx.llm.complete_structured(...)` with text **and image** blocks (`agent/plugin_llm.py:500`) | Retrieval is a *feature*, not the product. The index must be **auditable by a human**, because the agent will quote it. |
| "Visually searchable" meant a screenshot of a graph | A Hermes desktop plugin renders **live, interactive** HTML/SVG in the window (`desktop/plugin.js`, loaded by the SDK) | The pretty graph is free — no extra service. |
| Corpus had to be perfectly clean before indexing | Dedup + staleness stamps are **deterministic code**, and conflicts are a *review queue* with a human in the loop | We can index the messy corpus **now** and fix it in the UI. |

### 2. The corpus, measured (not guessed)

**Source A — attachments:** `/home/lisacore/.hermes/profiles/charlene/attachments/`

```
44 non-image files · 204 files total · 160 images · 92.4 MB of images · ~1.60 MB of PDF text
```

| Kind | Count | Notes |
|---|---|---|
| PDF | 20 files → **13 unique** | 7 are byte-identical duplicates |
| DOCX | 1 | Same document as its PDF (see §2.2) |
| Markdown | 2 | `TVL – Calvin's Shadow Access - Basic (Draft 0.1).md` (214,531 B) · `Hackathon papers Nov 8 2026.md` (6,891 B) |
| CSV | 1 | `Dark Logic Consistent Characters - Sheet1.csv` — character → shot → URL → animation notes |
| Pasted text | 19 | 18 real text pastes (3–55 KB) + **1 HTML page** (see §2.3) |
| Images | 160 → **85 unique** | 75 byte-identical duplicates; **~130 are plugin-test screenshots, junk** |

**Exact duplicate groups, verified by sha256:**

```
PDF:   7d7f9ace1cf36fb1926b38a04025077b  CIA of AI ×3        (all three identical)
       36cfab81ac05647c3617d58f7084dc0a  Sovereign AI Council ×2
       8bd3dca97469beb7ac18ffd5d123e257  Equalizer Technology ×2
       def4305b74d81bda4dcdc22236a1637a  SAE Fiscal Architecture ×2
       e3c6b4a2586884881eec9df13fb381fa  Anthropic Founder's Playbook ×2
       f5df7de8b9bee3a1ca7441d73757a51e  multi-agent-social-simulation ×2
IMAGES: 30 groups · 75 duplicate files · e.g. popupd* (6+6), popupd11–14 (4 each)
```

**What is real content vs junk — the honest cut:**

| Keep | Junk (index as `artifact`, never as doctrine) |
|---|---|
| 13 unique PDFs (8 TVL doctrine + 5 external papers) | ~130 `plugintest*` / `plugin*` / `popup*` / `readme*` screenshots |
| 2 markdown docs | the 1.6 MB HTML paste (a saved web page, see §2.3) |
| 1 CSV (character shot sheet) | 75 duplicate image files |
| 18 text pastes (real analysis: Nous outreach, plugin architecture, keyword tables) | |
| ~28 images: 14 character portraits (`calvin`, `calvin1`, `charlenenew`, `vyn`, `quinn`, `brandi`, `Carla`, `enginner10`, `lazys*`, …), the org chart, `validize{a..n}.jpg`, `memory1/2.jpg` (Obsidian graph screenshots) | |

**Source B — notes:** `~/work` + `~/Projects`, **118 markdown files, 1,131,157 chars**. Only **2 git repos** exist there (`work/strategic-arena`, `Projects/youtube-channel`); `work/tvl-brand`, `tvl-crystal-ball`, `tvl-flywheel`, `tvl-research`, `tvl-weekend`, `data-deck`, `data-sequence-plan`, `Projects/validize` are **plain folders with no git**. → **The Vault's SQLite file is the only history those folders will have.** Back up first (Task 1).

### 2.1 Document structure, verified per file

`pdftotext -layout <file> -` and a 3-line zipfile read of the docx were run on every document. Heading conventions are **not consistent** — the indexer must support all four:

| File | Heading style | Count |
|---|---|---|
| `TVL — YouTube — Platform Governance (v1.1).pdf` **and** its `.docx` | `SECTION 0 — …` … `SECTION 13 — …` | **14** |
| `TVL — CIA of AI — Canonical Logic (v1.0).pdf` | `1. RAG System Definition`, `2. The Canonical Section Map`… | 23 numeric |
| `TVL — Sovereign AI Council — Tactical Logic-Engine (v1.2).pdf` | `1. The Brain (C.A.L.V.I.N.)` … | 12 numeric |
| `TVL—SAE Fiscal Architecture (v1.2).pdf` | `1. The Missing "Multiplier Gate" Formula` … | 4 numeric |
| `TVL - Market Research Options (Draft 0.1).pdf` | `1️⃣`/`1.` mixed, many | 64 numeric |
| `TVL — Video Production — Execution (v1.2).pdf` | **no numbered headings** — prose + RAG TAG BLOCK only | 0 |
| `TVL — YouTube Equalizer Technology — Framework (v1.2).pdf` | **no numbered headings** — prose + RAG TAG BLOCK only | 0 |
| `camel…pdf`, `oasis…pdf` | `#` markdown headings **inside the PDF text layer** | 30 / 17 |
| `generative-agents…pdf`, `graphRAG…pdf`, `multi-agent-social-simulation.pdf` | academic numbered sections (`3.1.1`, `4.3.1`) | mixed |
| `Anthropics-FoundersPlaybook…pdf` | title + prose | 2 |
| `TVL – Calvin's Shadow Access…md` | `# **SECTION 1 — …**` + `## **1.1 …**` | 37 numeric, 140 markdown |

**Header block every TVL doctrine PDF shares** (parsed into metadata, not prose):

```
[SYSTEM AUTHORITY HEADER — DO NOT BYPASS] ENTITY: TrillionVerse Labs (TVL) STATUS: Canonical Doctrine / Root Authority
Document Title / System / Layer / Version / Owner / Mission / Purpose / Status / AI Roles
RAG TAG BLOCK → ENTITY: · INTENT: · DEPENDENCY: · VALIDITY: · AU2I_INDEX:
```

Verified counts of `VALIDITY:` / `INTENT:` / `DEPENDENCY:` per file: CIA of AI 0/0/0 (it predates the tag block), Sovereign 1/1/1, Video Production 2/2/2, Equalizer 2/2/2, SAE Fiscal 1/1/1, Platform Governance 2/2/2. **Parse these into columns — they are the dependency edges for the graph.**

### 2.2 The DOCX/PDF pair

`TVL — YouTube — Platform Governance (v1.1).docx` (42,596 B) and `.pdf` (457,200 B) are the **same document**: both have 14 `SECTION` headings with identical titles, same header block, same RAG tag block. Normalized text: PDF 55,172 chars, DOCX 52,356 chars, 40-char shingle Jaccard **0.544**. The DOCX has **no images, no tables** (`<w:tbl>` count 0, `<w:drawing>` count 0). → **Canonical = PDF; DOCX = duplicate, kept as an alternate-format record.**

### 2.3 The 1.6 MB "Pasted content" is a saved web page, not text

```
title: Introducing Arete-27B: Qwen3.8-27B Post-Trained To Reinforce Western Values | Nous Research
has self.__next_f: True · trillionverse mentions: 0 · hermes mentions: 161
```

→ Route it to the **HTML source** extractor, not the text extractor. Its `<title>` becomes the document title. This is the pattern for any future web capture.

### 2.4 Technology that did not exist when the doctrine was written

| Doctrine says | Reality now | Where it matters |
|---|---|---|
| "Use ONLY the data in the TVL RAG Corpus" | The corpus is now **one SQLite index + a graph**, searchable in milliseconds; the agent reads it, not a vector guess | The Vault's own `SCHEMA.md` |
| "3,203 T1/T2 papers" (PIPELINE-V2) | Only **5 external papers are on disk.** The 3,203 figure is a claim, not a corpus. | Mark `UNCLEAR` until the corpus is present |
| `$300 total budget / $80/mo January cap` | Still the constraint; the Vault must be **$0 recurring** | §3 stack |
| "n8n + Postgres" orchestration | Hermes plugin isolation means **plugins do not import each other**; `ctx.dispatch_tool` and per-plugin `plugin_data_dir()` are the real bus | `tvl-flywheel/docs/ORCHESTRATION-FACTS.md` |
| "RAG" as the architecture | Agent + cited retrieval + human review queue | This plan |

### 2.5 Constraints that are non-negotiable (from the user's standing rules)

- **$0 recurring.** Free Nous model (`meituan/longcat-2.5:free`) for the Q&A and for staleness classification. Everything else is stdlib + poppler.
- **Private.** New repo `trillionverselabs-boop/tvl-vault`, private. Never touch `strategic-arena` (accepted in the marketplace — memory #64).
- **Local-first.** No account, no telemetry. `plugins.plugin_storage.plugin_data_dir()` for all writes.
- **Evidence-first.** No invented metrics. Every extracted field carries `evidence_quote` + `location`, per `tvl-crystal-ball/docs/PAPER-INGESTION.md` §2.5.
- **One clean working copy per project** (user profile rule).

### 2.6 Environment facts (verified)

| Fact | Value |
|---|---|
| Python | `/usr/bin/python3` 3.14.4; **Hermes venv** `/home/lisacore/.hermes/installs/a1e1e7cd4d1adb69/environments/34d7fdebd6b44efeb7123d4e6e030822/venv/bin/python` 3.14.9 |
| Hermes venv has | `fastapi 0.133.1`, `pydantic 2.14.1`, `httpx 0.28.1`, `openai 2.54.0`, `PIL 13.0.0`, `numpy 2.5.4`, `markdown 3.11.2` |
| **Missing everywhere** | `pytest`, `yaml`, `docx`, `fitz`, `pypdf` — `pip` is absent (PEP 668) |
| `pdftotext` / `pdfinfo` / `pdfimages` | present, poppler **26.01.0** — **no pip install needed** |
| `libreoffice` | 26.2.6.3 present (fallback for docx) |
| `tesseract` | **absent** — so **no OCR**. Images get vision-model captions, not OCR. |
| SQLite | 3.53.1, **FTS5 available** |
| Network | pypi 200, `inference-api.nousresearch.com` 200, npm 200 |
| Node | v26.12.1 (only if a JS graph lib is wanted — **do not use**; hand-rolled SVG keeps it dependency-free) |

### 2.7 Stack decision (the "free, manageable" part)

| Layer | Choice | Why |
|---|---|---|
| Text extraction | `pdftotext -layout` via `subprocess` (stdlib) | Already installed; no pip; `-layout` preserves the column structure the doctrine uses |
| DOCX | `zipfile` + `xml.etree` (stdlib) | No `python-docx`; a docx is a zip |
| HTML | `html.parser.HTMLParser` (stdlib) | No bs4 |
| Index | **SQLite + FTS5**, one file, `plugins.plugin_db()` | Rebuildable from the corpus; survives plugin update; no server |
| Images | sha256 dedup + `PIL` for dimensions + **vision captions** via `ctx.llm.complete_structured` with `PluginLlmImageInput` | OCR is absent; the free model can caption a portrait |
| UI | Hermes desktop plugin: `desktop/plugin.js` (React SDK, uncompiled) + `dashboard/plugin_api.py` (FastAPI) | Proven pattern in `work/data-deck` and `work/strategic-arena` |
| Q&A | `ctx.llm.complete_structured`, cited chunks, free model | Already the session model |
| Graph | **Hand-rolled SVG in `desktop/plugin.js`** | A force-directed layout in ~120 lines of vanilla JS; no npm, no build step, offline |

**Scoring/ranking:** BM25 from FTS5 + a deterministic `recency × source_authority` tiebreak. **No embeddings** — the corpus is ~2.7 MB of text; BM25 is better here and free. Vectors are a YAGNI trap at this size.

### 2.8 Visual design — "mission-control knowledge graph"

**The user is extremely visual: she must see a layout before she can judge it, and she is not technical.** Two reference images were supplied as the look she means:

| Image | What it actually is (verified by inspection) |
|---|---|
| `attachments/memory1.jpg` | A dark "mission-control" console: dense central force-directed graph, a top strip of five large KPI numerals, flanking sidebars of compact metadata, uppercase micro-labels, near-black canvas with cyan / green / pink focal nodes. |
| `attachments/memory2.jpg` | Obsidian **Graph View**: a file-tree sidebar whose folder accent colours match the graph node colours, a dominant force-graph canvas, hairline low-opacity edges, one warm amber selection. |

**The design rule: the graph is the hero; everything else recedes.** Both references agree on this, and it is also the only look that survives 900+ nodes.

**Palette — exact values. Do not substitute.**

| Token | Value | Use |
|---|---|---|
| canvas | `#05070d` | graph background |
| panel | `#0a0f18` | sidebars, cards |
| border | `rgba(255,255,255,0.07)` | 1px dividers, card edges |
| text | `#e8edf5` | primary |
| muted | `#8b98ad` | secondary, node labels |
| micro-label | `#5c6b82` | uppercase, 10px, `letter-spacing: .08em` |
| selection | `#f59e0b` | **the only warm accent** — selected node, active filter |
| kind: doctrine | `#22d3ee` | TVL-authored doctrine PDFs |
| kind: notes | `#a78bfa` | markdown notes |
| kind: papers | `#34d399` | external papers |
| kind: images | `#fbbf24` | portraits, org chart, renders |
| flag: conflict | `#f87171` | needs a decision |
| flag: outdated / duplicate | `#64748b` | superseded or copied |
| flag: current | `#4ade80` | verified |

**Eight node colours maximum.** A ninth colour is noise; both reference images stay inside a small categorical set and tie the sidebar colour to the node colour. The Vault does the same: the colour of a document in the left tree is the colour of its node in the graph.

**Layout — three columns, fixed.**

```
┌──────────────────────────────────────────────────────────────────────┐
│  THE VAULT                                    156 docs · 900 sections │
├──────────────┬───────────────────────────────────┬───────────────────┤
│ 260 px       │  graph canvas (SVG, fills)        │ 320 px            │
│              │                                   │                   │
│ DOCUMENTS    │  156      900       82       12   │  SELECTED         │
│ ● doctrine 13│  docs   sections  dupes  review   │                   │
│ ● notes   95 │  ─────────────────────────────    │  Title            │
│ ● papers   5 │                                   │  [OUTDATED]       │
│ ● images  28 │        ●  ●   ●                    │                   │
│              │      ●  ●  ●  ●  ●   ●            │  Plain-language   │
│ NEEDS REVIEW │    ●   ● ●   ●  ● ●   ● ●          │  summary          │
│ [12] conflict│      ●  ●  ● ●  ●   ●             │                   │
│ [ 7] outdatd │        ●   ●  ●  ●                 │  "Open the source │
│ [ 8] duplic. │              ●                      │   document"       │
│              │                                   │                   │
│ ——————————   │  ▣ collapse sections   🔍 zoom     │  Why this flag    │
│ FILTER       │                                   │  Evidence …       │
│ ☑ current    │                                   │                   │
└──────────────┴───────────────────────────────────┴───────────────────┘
```

- **Left:** document tree grouped by kind, each row carrying its categorical colour dot; below it the **NEEDS REVIEW** filter chips with live counts.
- **Centre:** the graph, with a four-number strip above it. **Every number has a caption** — a bare number is noise (this is the house rule already used in `work/strategic-arena/desktop/plugin.js`).
- **Right:** the detail panel. Flag badge, plain-language summary, the evidence quote, and one button that opens the source file. No jargon: the flag names in the UI are **Needs review / Outdated / Duplicate / Unclear / Current**, never the raw enum.

**Graph rendering rules.**

| Element | Rule |
|---|---|
| Node | Filled circle, no border. Radius by degree: `r = 3 + min(7, degree)`. Colour by kind. |
| Glow | One larger circle behind the node at 12% opacity of the same colour — cheap, no SVG filter. |
| Selected | `r + 3` ring in `#f59e0b`, plus a readable label. Only one selected node at a time. |
| Edge | 1px, `rgba(255,255,255,0.10)`, no arrows. Contains-edges hidden by default (toggle "collapse sections"). |
| Hover | Tooltip: section title + document title + flag. |
| Click | Opens the right panel. |
| Double-click | Isolates that document's subgraph. |
| Zoom/pan | Mouse wheel + drag on empty canvas. |
| Density | 900 nodes is the hairball limit → default view shows **documents**; expanding a document reveals its sections. |

**Non-negotiables for a non-technical user:** no jargon anywhere in the UI; every number sits next to a sentence; nothing happens without a visible explanation; empty states say what to do next ("No documents match — try clearing the Needs-review filter"); and **the review queue is the visual centre**, because reviewing the corpus is the actual job, not browsing it.

**Build order consequence:** the look is approved **before** any plugin code, as a static mockup (Task 0.5). No plugin is written against an unapproved design.

---

## Architecture / proposed approach

`tvl-vault/` is a Hermes plugin with four modules. **`corpus.py` builds a normalized section list from the sources; `index.py` turns that into one SQLite file (FTS5 + a `sections` table + a `documents` table + a `flags` table); `review.py` computes the five status flags deterministically; `qa.py` answers questions with citations.** The desktop page (`desktop/plugin.js`) calls `dashboard/plugin_api.py` over `ctx.rest(...)` and renders three tabs — **Graph**, **Wall**, **Ask** — plus a **Review** queue that is the human-in-the-loop step.

Data flow:

```
attachments/ ─┐
~/work/**/*.md ─┼─→ corpus.py ─→ sections[] ─→ index.py ─→ vault.db (FTS5)
~/Projects/**/*.md ─┘                                        │
images/ ────────────────────────────────────────────────────┤
                                                            ↓
                                            review.py (sha256 dupes, dependency
                                            cycles, date/version staleness,
                                            conflict pairs) → flags
                                                            ↓
                                     plugin_api.py → desktop/plugin.js
                                     (Graph · Wall · Ask · Review)
```

**Rebuild is always safe:** `vault.db` is derived. `vault.py rebuild` regenerates it from the corpus in under a minute, and the corpus is never mutated.

---

## Step-by-step tasks

> **Conventions.** Repo root = `/home/lisacore/work/tvl-vault`. Plugin id = `tvl-vault`.
> Python interpreter for tests: `PYTHON=/home/lisacore/.hermes/installs/a1e1e7cd4d1adb69/environments/34d7fdebd6b44efeb7123d4e6e030822/venv/bin/python`
> Every task ends with a commit. Commit message format: `feat(module): what` / `fix(module): what`.

### Task 0 — Scaffold, backup, and one golden probe (≈10 min)

**0.1 Back up the corpus first.** The vault folders have no git; the Vault's DB is their only future history.

```bash
mkdir -p /home/lisacore/backups
tar -czf "/home/lisacore/backups/tvl-corpus-2026-11-14.tar.gz" \
  -C /home/lisacore/.hermes/profiles/charlene attachments
tar -czf "/home/lisacore/backups/tvl-notes-2026-11-14.tar.gz" \
  -C /home/lisacore work/tvl-brand work/tvl-crystal-ball work/tvl-flywheel \
  work/tvl-research work/tvl-weekend work/data-deck work/data-sequence-plan \
  Projects/validize
```

Expected: two `.tar.gz` files, non-empty.

```bash
ls -la /home/lisacore/backups/tvl-*.tar.gz
```

**0.2 Create the repo.**

```bash
mkdir -p /home/lisacore/work/tvl-vault && cd /home/lisacore/work/tvl-vault
git init -b main
mkdir -p src/vault tests docs scripts
```

Write `.gitignore`:

```
__pycache__/
*.pyc
.pytest_cache/
.venv/
```

Write `pyproject.toml` — **no `[build-system]`, `dependencies = []`** (a non-empty dependency list makes the desktop's non-interactive install abort; see `work/strategic-arena/pyproject.toml`):

```toml
[project]
name = "hermes-tvl-vault"
version = "0.1.0"
description = "The Vault — one indexed, visually searchable home for the TVL corpus."
requires-python = ">=3.11"
dependencies = []

[tool.pytest.ini_options]
testpaths = ["tests"]
addopts = "-q"
```

Write `scripts/test.sh` (copy the pattern from `work/strategic-arena/scripts/test.sh` — the checkout folder name has a hyphen, so pytest needs a valid package name):

```bash
#!/usr/bin/env bash
set -euo pipefail
root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
tmp="$(mktemp -d "${TMPDIR:-/tmp}/vault-tests.XXXXXX")"
trap 'rm -rf "$tmp"' EXIT
mkdir -p "$tmp/vault"
cp -al "$root"/. "$tmp/vault/"
cd "$tmp/vault"
PYTHON="${PYTHON:-python3}"
exec "$PYTHON" -m pytest "$@"
```

```bash
chmod +x scripts/test.sh
```

**0.3 One golden probe, before any code.** Confirm the extraction path works end to end on the real corpus:

```bash
pdftotext -layout "/home/lisacore/.hermes/profiles/charlene/attachments/TVL — CIA of AI — Canonical Logic (v1.0).pdf" - | head -8
```

Expected (first line exactly):

```
TVL — CIA of AI — Canonical Logic (v1.0)
```

```bash
python3 - <<'PY'
import sqlite3
c = sqlite3.connect(":memory:")
c.execute("CREATE VIRTUAL TABLE t USING fts5(a)")
c.execute("INSERT INTO t VALUES ('hello rag world')")
print(list(c.execute("SELECT a, bm25(t) FROM t WHERE t MATCH 'rag'")))
PY
```

Expected: `[('hello rag world', <negative float>)]` — FTS5 + BM25 work in this interpreter.

```bash
cd /home/lisacore/work/tvl-vault && git add -A && git commit -m "chore: scaffold tvl-vault plugin"
```

---

### Task 0.5 — Static HTML mockup, approved before any plugin code (≈20 min)

**Why this task exists:** the user is visual and not technical. She cannot judge a design from a description, and no plugin should be written against an unapproved look. This task produces **one self-contained HTML file with hardcoded sample data** — no plugin, no backend, no install.

Create `docs/mockup/vault-mockup.html`. Requirements, all mandatory:

1. **Zero dependencies.** No CDN, no web font, no JS library. Inline CSS and ~120 lines of vanilla JS. It must open by double-clicking, offline.
2. **Implement §2.8 exactly** — the eight palette values, the three-column layout (260 / fluid / 320), the four KPI numbers with captions, the uppercase micro-labels, the graph-first hierarchy.
3. **Hardcoded sample data** in a `const DATA = {...}` at the top: 6 documents (2 doctrine, 2 notes, 1 paper, 1 image) and 14 sections, with the real flag values (`current`, `outdated`, `duplicate`, `conflict`, `unclear`). Use **real TVL titles** so she recognises the content — e.g. `TVL — CIA of AI — Canonical Logic (v1.0)`, `TVL — YouTube Equalizer Technology — Framework (v1.2)`, `tvl-flywheel/docs/FLYWHEEL.md`.
4. **The force layout from Task 6** copied verbatim, so what she approves is what ships.
5. **Working interactions:** click a node → right panel fills; click a flag chip in the left sidebar → non-matching nodes dim to 15% opacity; the "collapse sections" toggle hides section nodes and contains-edges; hover shows a tooltip.
6. **Both reference looks represented:** the mission-control KPI strip (from `memory1.jpg`) and the Obsidian-style colour-matched document tree (from `memory2.jpg`).
7. A **"Needs review"** panel listing the 5 flagged sample items, each with a plain-language reason and a **Keep / Mark current / Edit** button (the buttons can be inert in the mockup; the point is that she sees the queue).

Verify it renders — screenshot it, do not just read the code:

```bash
cd /home/lisacore/work/tvl-vault
python3 -m http.server 8777 --directory docs/mockup >/dev/null 2>&1 &
sleep 1
# open http://127.0.0.1:8777/vault-mockup.html in a browser at 1600x900
kill %1
```

**Acceptance:** the user looks at it and says yes, or names what to change. **Do not start Task 6 until she has.** Commit: `docs(mockup): the approved-look prototype`.

---

### Task 1 — `src/vault/paths.py`: where we read and write (≈5 min, TDD)

**Test first** — `tests/test_paths.py`:

```python
from pathlib import Path

from vault import paths


def test_data_root_is_profile_scoped(tmp_path, monkeypatch):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    root = paths.data_root()
    assert root.name == "tvl-vault"
    assert str(root).startswith(str(tmp_path))


def test_corpus_roots_are_absolute_and_exist():
    roots = paths.corpus_roots()
    assert roots, "no corpus roots configured"
    for r in roots:
        assert r.is_absolute()
        assert r.exists(), r


def test_vault_db_path_is_inside_data_root(tmp_path, monkeypatch):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    assert paths.vault_db_path() == paths.data_root() / "vault.db"
```

Run and watch it fail:

```bash
cd /home/lisacore/work/tvl-vault
PYTHON=/home/lisacore/.hermes/installs/a1e1e7cd4d1adb69/environments/34d7fdebd6b44efeb7123d4e6e030822/venv/bin/python ./scripts/test.sh
# expect: ModuleNotFoundError: No module named 'vault'
```

Implement `src/vault/__init__.py` (empty) and `src/vault/paths.py`:

```python
"""Where The Vault reads and writes.

Reads are absolute, from the profile's own attachments dir plus the two note
trees. Writes go ONLY to `plugin_data_dir("tvl-vault")` — the profile-scoped
data root that survives `plugins update` and `plugins remove`.
"""

from __future__ import annotations

import os
from pathlib import Path

PLUGIN_ID = "tvl-vault"


def _hermes_home() -> Path:
    try:
        from hermes_constants import get_hermes_home

        return Path(get_hermes_home())
    except Exception:
        return Path(os.environ.get("HERMES_HOME") or (Path.home() / ".hermes"))


def data_root() -> Path:
    home = _hermes_home()
    try:
        from plugins.plugin_storage import plugin_data_dir  # type: ignore

        p = Path(plugin_data_dir(PLUGIN_ID))
        if str(p).startswith(str(home)):
            return p
    except Exception:
        pass
    return home / PLUGIN_ID


def vault_db_path() -> Path:
    return data_root() / "vault.db"


def corpus_roots() -> list[Path]:
    """Existing source directories, in priority order. Missing ones are skipped."""
    candidates = [
        _hermes_home() / "attachments",
        Path("/home/lisacore/work"),
        Path("/home/lisacore/Projects"),
    ]
    return [c for c in candidates if c.is_dir()]
```

Run:

```bash
PYTHON=/home/lisacore/.hermes/installs/a1e1e7cd4d1adb69/environments/34d7fdebd6b44efeb7123d4e6e030822/venv/bin/python ./scripts/test.sh
```

Expected: `3 passed`. Commit: `feat(paths): profile-scoped data root and corpus roots`.

> **Note for the implementer:** `plugins.plugin_storage` is importable only inside Hermes. The `except` fallback is deliberate — the same file must work in tests and standalone. Copy the pattern from `work/example-plugin/paths.py`; do not improvise.

---

### Task 2 — `src/vault/sources.py`: enumerate, classify, dedupe (≈15 min, TDD)

**Test first** — `tests/test_sources.py`:

```python
import hashlib
from pathlib import Path

from vault import sources


def _touch(d: Path, name: str, data: bytes) -> Path:
    p = d / name
    p.write_bytes(data)
    return p


def test_kind_is_decided_by_extension():
    assert sources.kind_of(Path("a.pdf")) == "pdf"
    assert sources.kind_of(Path("a.docx")) == "docx"
    assert sources.kind_of(Path("a.md")) == "markdown"
    assert sources.kind_of(Path("a.html")) == "html"
    assert sources.kind_of(Path("a.csv")) == "csv"
    assert sources.kind_of(Path("a.jpg")) == "image"
    assert sources.kind_of(Path("a.xyz")) == "other"


def test_identical_files_collapse_to_one_document(tmp_path):
    data = b"%PDF-1.4 same bytes"
    _touch(tmp_path, "a.pdf", data)
    _touch(tmp_path, "b.pdf", data)
    docs = sources.scan(tmp_path)
    pdfs = [d for d in docs if d.kind == "pdf"]
    assert len(pdfs) == 1
    assert len(pdfs[0].duplicates) == 1


def test_markdown_files_are_all_kept(tmp_path):
    _touch(tmp_path, "a.md", b"# A\n")
    _touch(tmp_path, "b.md", b"# B\n")
    assert len([d for d in sources.scan(tmp_path) if d.kind == "markdown"]) == 2


def test_junk_screenshots_are_flagged_not_dropped(tmp_path):
    _touch(tmp_path, "plugintest5a.jpg", b"\xff\xd8\xff")
    _touch(tmp_path, "calvin.png", b"\x89PNG\r\n\x1a\n")
    docs = {d.path.name: d for d in sources.scan(tmp_path)}
    assert docs["plugintest5a.jpg"].is_junk is True
    assert docs["calvin.png"].is_junk is False
```

Run, watch fail, implement `src/vault/sources.py`:

```python
"""Enumerate the corpus: what exists, what kind it is, which copies are duplicates."""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from pathlib import Path

EXT_KIND = {
    ".pdf": "pdf", ".docx": "docx", ".md": "markdown", ".markdown": "markdown",
    ".html": "html", ".htm": "html", ".csv": "csv", ".txt": "text",
    ".jpg": "image", ".jpeg": "image", ".png": "image", ".webp": "image", ".gif": "image",
}

# Plugin-test screenshots and build screenshots: index them as artifacts so the
# graph does not silently drop them, but never treat them as doctrine.
JUNK_PATTERNS = [
    r"^plugintest", r"^plugin\d", r"^pluginblogtest", r"^popup[a-z0-9_]*$",
    r"^readme\d", r"^b\d_part\d", r"^s\d+\.png$",
]


@dataclass
class Document:
    path: Path
    kind: str
    sha256: str
    size: int
    title: str = ""
    is_junk: bool = False
    duplicates: list[Path] = field(default_factory=list)

    @property
    def slug(self) -> str:
        return re.sub(r"[^a-z0-9]+", "-", (self.title or self.path.stem).lower()).strip("-")


def kind_of(path: Path) -> str:
    return EXT_KIND.get(path.suffix.lower(), "other")


def is_junk_name(name: str) -> bool:
    stem = Path(name).stem
    return any(re.match(p, stem, re.I) for p in JUNK_PATTERNS)


def scan(root: Path) -> list[Document]:
    """Every supported file under *root*, with byte-identical duplicates collapsed."""
    by_hash: dict[str, list[Path]] = {}
    for p in sorted(root.rglob("*")):
        if not p.is_file() or kind_of(p) == "other":
            continue
        if any(part.startswith(".") for part in p.parts):
            continue
        h = hashlib.sha256(p.read_bytes()).hexdigest()
        by_hash.setdefault(h, []).append(p)
    docs: list[Document] = []
    for h, paths in by_hash.items():
        canonical = paths[0]
        docs.append(Document(
            path=canonical, kind=kind_of(canonical), sha256=h, size=canonical.stat().st_size,
            is_junk=is_junk_name(canonical.name), duplicates=paths[1:],
        ))
    return docs
```

Run: expect `4 passed`. Commit: `feat(sources): enumerate, classify and dedupe the corpus`.

**Verify against the real corpus** (this is the moment to confirm the numbers in §2):

```bash
cd /home/lisacore/work/tvl-vault
PYTHON=/home/lisacore/.hermes/installs/a1e1e7cd4d1adb69/environments/34d7fdebd6b44efeb7123d4e6e030822/venv/bin/python - <<'PY'
import sys; sys.path.insert(0, "src")
from pathlib import Path
from vault import sources
for root in [Path("/home/lisacore/.hermes/profiles/charlene/attachments"),
             Path("/home/lisacore/work"), Path("/home/lisacore/Projects")]:
    docs = sources.scan(root)
    from collections import Counter
    print(root.name, Counter(d.kind for d in docs), "dupes:", sum(len(d.duplicates) for d in docs))
PY
```

Expected, approximately:

```
attachments Counter({'image': 85, 'pdf': 13, 'markdown': 2, 'csv': 1, 'docx': 1, 'html': 1, 'text': 18}) dupes: 75
work Counter({'markdown': ~95, ...}) dupes: 0
Projects Counter({'markdown': ~23, ...}) dupes: 0
```

> The attachment counts must be **exactly** `image 85, pdf 13, markdown 2, csv 1, docx 1, html 1, text 18, dupes 75`. If they differ, the classifier is wrong — fix before moving on.

---

### Task 3 — `src/vault/extract.py`: text, sections, metadata (≈25 min, TDD)

This is the heart of the build. Four extractors, one shared section splitter.

**Test first** — `tests/test_extract.py`:

```python
from pathlib import Path

from vault import extract


def test_pdf_text_is_extracted(tmp_path):
    # poppler is present on this host; use a real one-page PDF generated inline.
    pdf = tmp_path / "t.pdf"
    pdf.write_bytes(_ONE_PAGE_PDF)
    text = extract.pdf_text(pdf)
    assert "HELLOVAULT" in text.replace(" ", "").upper()


def test_docx_text_is_extracted_without_python_docx(tmp_path):
    docx = tmp_path / "t.docx"
    docx.write_bytes(_MINIMAL_DOCX)
    assert "docx body" in extract.docx_text(docx)


def test_markdown_sections_split_on_headings():
    md = "# Title\n\nintro\n\n# **SECTION 1 — ALPHA**\n\nbody a\n\n## **1.1 Sub**\n\nbody b\n"
    secs = extract.split_markdown(md)
    assert [s.title for s in secs][:3] == ["Title", "SECTION 1 — ALPHA", "1.1 Sub"]
    assert "body a" in secs[1].body


def test_pdf_section_style_is_recognised():
    txt = "TVL — YouTube — Platform Governance (v1.1)\n\nSECTION 0 — RAG Document Purpose\n\nhello\n\nSECTION 1 — Document Authority\n\nworld\n"
    secs = extract.split_pdf_text(txt)
    assert [s.title for s in secs] == ["RAG Document Purpose", "Document Authority"]


def test_numeric_heading_style_is_recognised():
    txt = "1. RAG System Definition\n\nalpha\n\n2. The Canonical Section Map\n\nbeta\n"
    secs = extract.split_pdf_text(txt)
    assert [s.title for s in secs] == ["RAG System Definition", "The Canonical Section Map"]


def test_header_block_metadata_is_parsed():
    txt = ("[SYSTEM AUTHORITY HEADER — DO NOT BYPASS] ENTITY: TrillionVerse Labs (TVL) "
           "STATUS: Canonical Doctrine / Root Authority\nDocument Title:\nTVL — X\n"
           "Version:\nv1.2 — January 2026 Document\n")
    meta = extract.parse_header(txt)
    assert meta["title"] == "TVL — X"
    assert meta["version"] == "v1.2 — January 2026 Document"
    assert "Canonical Doctrine" in meta["status"]


def test_rag_tag_block_is_parsed():
    txt = ("RAG TAG BLOCK\nENTITY: n8n, Equalizer Technology\nINTENT: Orchestration Doctrine\n"
           "DEPENDENCY: TVL — Structure (v1.0)\nVALIDITY: Active (v1.0)\n"
           "AU2I_INDEX: Workflow Composition\n")
    tag = extract.parse_rag_tag(txt)
    assert tag["entity"] == ["n8n", "Equalizer Technology"]
    assert tag["validity"] == "Active (v1.0)"
    assert tag["dependency"] == ["TVL — Structure (v1.0)"]
```

`_ONE_PAGE_PDF` and `_MINIMAL_DOCX` are small fixtures — generate them in the test with `reportlab`-free raw bytes. A minimal one-page PDF with the text `HELLOVAULT`:

```python
_ONE_PAGE_PDF = (
    b"%PDF-1.4\n1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n"
    b"2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj\n"
    b"3 0 obj<</Type/Page/Parent 2 0 R/MediaBox[0 0 300 200]/Contents 4 0 R"
    b"/Resources<</Font<</F1 5 0 R>>>>>>endobj\n"
    b"4 0 obj<</Length 44>>stream\nBT /F1 18 Tf 20 100 Td (HELLOVAULT) Tj ET\nendstream\nendobj\n"
    b"5 0 obj<</Type/Font/Subtype/Type1/BaseFont/Helvetica>>endobj\n"
    b"xref\n0 6\n0000000000 65535 f \ntrailer<</Size 6/Root 1 0 R>>\nstartxref\n0\n%%EOF\n"
)
```

> **The implementer must verify this fixture actually parses with `pdftotext` before relying on it.** Run:
> `pdftotext <fixture.pdf> -` → must print `HELLOVAULT`. If the hand-rolled xref offsets are wrong, generate the fixture once with `libreoffice --headless --convert-to pdf` on a text file and commit the resulting bytes as `tests/fixtures/one-page.pdf`. **Do not hand-tune offsets.**

`_MINIMAL_DOCX` (a real docx zip with one paragraph):

```python
import zipfile

def _minimal_docx_bytes() -> bytes:
    import io
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("[Content_Types].xml",
                   '<?xml version="1.0"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
                   '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
                   '<Default Extension="xml" ContentType="application/xml"/>'
                   '<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>'
                   '</Types>')
        z.writestr("_rels/.rels",
                   '<?xml version="1.0"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                   '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>'
                   '</Relationships>')
        z.writestr("word/document.xml",
                   '<?xml version="1.0"?><w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
                   '<w:body><w:p><w:r><w:t>docx body</w:t></w:r></w:p></w:body></w:document>')
    return buf.getvalue()
```

Implement `src/vault/extract.py`:

```python
"""Extract text and sections from every source kind. No third-party packages.

PDF   -> poppler `pdftotext -layout` (already installed, no pip).
DOCX  -> zipfile + ElementTree (a .docx is a zip).
HTML  -> html.parser (strip script/style, keep heading text).
CSV   -> csv.reader, one row per record.
Image -> no text; captions come from the vision pass in Task 9.
"""

from __future__ import annotations

import csv
import html
import io
import re
import subprocess
import zipfile
from dataclasses import dataclass, field
from html.parser import HTMLParser
from pathlib import Path
from xml.etree import ElementTree as ET


@dataclass
class Section:
    title: str
    level: int
    body: str
    page: int | None = None
    line: int = 0

    @property
    def plain(self) -> str:
        return f"{self.title}\n{self.body}".strip()


@dataclass
class Extracted:
    path: Path
    kind: str
    title: str
    text: str
    sections: list[Section]
    meta: dict = field(default_factory=dict)
    rag: dict = field(default_factory=dict)
    error: str = ""


def pdf_text(path: Path) -> str:
    out = subprocess.run(
        ["pdftotext", "-layout", str(path), "-"],
        capture_output=True, text=True, timeout=120,
    )
    if out.returncode != 0:
        raise RuntimeError(f"pdftotext failed on {path.name}: {out.stderr.strip()}")
    return out.stdout


def docx_text(path: Path) -> str:
    with zipfile.ZipFile(path) as z:
        xml = z.read("word/document.xml")
    root = ET.fromstring(xml)
    ns = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
    lines: list[str] = []
    for p in root.iter(f"{ns}p"):
        txt = "".join(t.text or "" for t in p.iter(f"{ns}t"))
        if txt.strip():
            lines.append(txt.strip())
    return "\n".join(lines)


class _TextExtractor(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts: list[str] = []
        self.skip = 0

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style", "noscript"):
            self.skip += 1
        if tag in ("p", "div", "h1", "h2", "h3", "li", "br", "tr"):
            self.parts.append("\n")

    def handle_endtag(self, tag):
        if tag in ("script", "style", "noscript") and self.skip:
            self.skip -= 1

    def handle_data(self, data):
        if not self.skip:
            self.parts.append(data)


def html_text(path: Path) -> str:
    p = _TextExtractor()
    p.feed(path.read_text("utf-8", "ignore"))
    return html.unescape("".join(p.parts))


# ── section splitters ────────────────────────────────────────────────

_SECTION_RE = re.compile(r"^SECTION\s+(\d+)\s+—\s+(.+?)\s*$", re.M)
_NUM_RE = re.compile(r"^(\d{1,2})\.\s+([A-Z][A-Za-z].*?)\s*$", re.M)
_MD_H_RE = re.compile(r"^(#{1,3})\s+\*?\*?(.+?)\*?\*?\s*$", re.M)


def split_pdf_text(text: str) -> list[Section]:
    """TVL doctrine PDFs use three conventions; recognise all three."""
    marks: list[tuple[int, int, str]] = []
    for m in _SECTION_RE.finditer(text):
        marks.append((m.start(), 1, m.group(2).strip()))
    for m in _NUM_RE.finditer(text):
        marks.append((m.start(), 2, m.group(2).strip()))
    for m in re.finditer(r"^#\s+(.+?)\s*$", text, re.M):
        marks.append((m.start(), 1, m.group(1).strip().strip("*")))
    marks.sort()
    # keep the earliest mark per position bucket so a SECTION line is not also
    # caught by the numeric rule
    secs: list[Section] = []
    for i, (pos, level, title) in enumerate(marks):
        if secs and pos - marks[i - 1][0] < 4:
            continue
        end = marks[i + 1][0] if i + 1 < len(marks) else len(text)
        body = text[pos:end]
        body = body[body.find("\n") + 1:] if "\n" in body else ""
        secs.append(Section(title=title, level=level, body=body.strip(), line=text[:pos].count("\n")))
    return secs


def split_markdown(text: str) -> list[Section]:
    marks: list[tuple[int, int, str]] = []
    for m in _MD_H_RE.finditer(text):
        marks.append((m.start(), len(m.group(1)), m.group(2).strip().strip("*")))
    marks.sort()
    secs: list[Section] = []
    for i, (pos, level, title) in enumerate(marks):
        end = marks[i + 1][0] if i + 1 < len(marks) else len(text)
        body = text[pos:end]
        body = body[body.find("\n") + 1:] if "\n" in body else ""
        secs.append(Section(title=title, level=level, body=body.strip(), line=text[:pos].count("\n")))
    return secs


_HEADER_KEYS = {
    "Document Title:": "title", "Version:": "version", "Owner:": "owner",
    "System / Layer:": "layer", "Status:": "status", "Mission:": "mission",
    "Purpose:": "purpose",
}


def parse_header(text: str) -> dict:
    meta: dict[str, str] = {}
    lines = [l.strip() for l in text.split("\n")]
    for i, line in enumerate(lines[:200]):
        for key, field_name in _HEADER_KEYS.items():
            if line == key and i + 1 < len(lines):
                meta[field_name] = lines[i + 1]
    m = re.search(r"STATUS:\s*(Canonical Doctrine[^\n]*)", text)
    if m:
        meta["status"] = m.group(1).strip()
    return meta


def parse_rag_tag(text: str) -> dict:
    """The RAG TAG BLOCK is the dependency graph in plain text."""
    tag: dict[str, list[str]] = {}
    m = re.search(r"RAG TAG BLOCK(.*?)(?:\n\s*\n|\Z)", text, re.S)
    if not m:
        return tag
    block = m.group(1)
    for key, field_name in (("ENTITY:", "entity"), ("INTENT:", "intent"),
                            ("DEPENDENCY:", "dependency"), ("AU2I_INDEX:", "au2i")):
        mm = re.search(rf"{key}\s*(.+)", block)
        if mm:
            tag[field_name] = [x.strip() for x in mm.group(1).split(",") if x.strip()]
    mv = re.search(r"VALIDITY:\s*(.+)", block)
    if mv:
        tag["validity"] = mv.group(1).strip()
    return tag


def extract_document(path: Path, kind: str) -> Extracted:
    if kind == "pdf":
        text = pdf_text(path)
        return Extracted(path, kind, path.stem, text, split_pdf_text(text),
                         parse_header(text), parse_rag_tag(text))
    if kind == "docx":
        text = docx_text(path)
        return Extracted(path, kind, path.stem, text, split_pdf_text(text),
                         parse_header(text), parse_rag_tag(text))
    if kind == "markdown":
        text = path.read_text("utf-8", "ignore")
        return Extracted(path, kind, path.stem, text, split_markdown(text),
                         parse_header(text), {})
    if kind == "html":
        text = html_text(path)
        title = re.search(r"<title[^>]*>(.*?)</title>", path.read_text("utf-8", "ignore"), re.S | re.I)
        return Extracted(path, kind, html.unescape(title.group(1).strip()) if title else path.stem,
                         text, [], {}, {})
    if kind == "csv":
        rows = list(csv.reader(io.StringIO(path.read_text("utf-8", "ignore"))))
        body = "\n".join(" | ".join(r) for r in rows if any(c.strip() for c in r))
        return Extracted(path, kind, path.stem, body, [Section("rows", 1, body)], {}, {})
    return Extracted(path, kind, path.stem, "", [], {}, {})
```

Run the tests, then **the real-corpus smoke test**:

```bash
cd /home/lisacore/work/tvl-vault
PYTHON=/home/lisacore/.hermes/installs/a1e1e7cd4d1adb69/environments/34d7fdebd6b44efeb7123d4e6e030822/venv/bin/python - <<'PY'
import sys; sys.path.insert(0, "src")
from pathlib import Path
from vault import extract
d = Path("/home/lisacore/.hermes/profiles/charlene/attachments")
for name in ["TVL — CIA of AI — Canonical Logic (v1.0).pdf",
             "TVL — YouTube — Platform Governance (v1.1).pdf",
             "TVL — YouTube — Platform Governance (v1.1).docx",
             "TVL – Calvin's Shadow Access - Basic (Draft 0.1).md"]:
    e = extract.extract_document(d / name, "docx" if name.endswith("docx") else ("markdown" if name.endswith(".md") else "pdf"))
    print(f"{name[:50]:50} sections={len(e.sections):<4} meta={sorted(e.meta)} rag={sorted(e.rag)}")
PY
```

Expected:

```
TVL — CIA of AI — Canonical Logic (v1.0).pdf   sections=23   meta=[...] rag=[]
TVL — YouTube — Platform Governance (v1.1).pdf sections=14   meta=[...] rag=[dependency,entity,intent,validity]
TVL — YouTube — Platform Governance (v1.1).docx sections=14   meta=[...] rag=[...]
TVL – Calvin's Shadow Access - Basic (Draft 0.1).md sections=140 meta=[...] rag=[]
```

> **If the Platform Governance PDF yields 0 sections**, the `SECTION` regex is not matching — check for a non-ASCII em dash (`—` U+2014) versus a hyphen. The files use U+2014. Do not "fix" it with a loose regex; match U+2014 exactly.

Commit: `feat(extract): text, sections and header metadata for every source kind`.

---

### Task 4 — `src/vault/index.py`: one SQLite index with FTS5 (≈20 min, TDD)

**Test first** — `tests/test_index.py`:

```python
from pathlib import Path

from vault import extract, index


def _doc(tmp_path: Path, name: str, title: str, body: str) -> Path:
    p = tmp_path / name
    p.write_text(f"# {title}\n\n{body}\n")
    return p


def test_rebuild_creates_documents_and_sections(tmp_path):
    _doc(tmp_path, "a.md", "Alpha", "the sab otage contest logic")
    db = index.rebuild(tmp_path, tmp_path / "vault.db")
    assert db.execute("SELECT COUNT(*) FROM documents").fetchone()[0] == 1
    assert db.execute("SELECT COUNT(*) FROM sections").fetchone()[0] == 1


def test_fts_finds_a_section_by_word(tmp_path):
    _doc(tmp_path, "a.md", "Alpha", "the sabotage contest logic")
    _doc(tmp_path, "b.md", "Beta", "unrelated gardening text")
    db = index.rebuild(tmp_path, tmp_path / "vault.db")
    rows = index.search(db, "sabotage")
    assert rows and rows[0]["title"] == "Alpha"


def test_bm25_orders_the_best_section_first(tmp_path):
    _doc(tmp_path, "a.md", "Alpha", "sabotage " * 20)
    _doc(tmp_path, "b.md", "Beta", "sabotage once")
    db = index.rebuild(tmp_path, tmp_path / "vault.db")
    rows = index.search(db, "sabotage")
    assert rows[0]["doc_title"] == "Alpha"


def test_rebuild_is_idempotent(tmp_path):
    _doc(tmp_path, "a.md", "Alpha", "body")
    db1 = index.rebuild(tmp_path, tmp_path / "vault.db")
    n1 = db1.execute("SELECT COUNT(*) FROM sections").fetchone()[0]
    db2 = index.rebuild(tmp_path, tmp_path / "vault.db")
    assert db2.execute("SELECT COUNT(*) FROM sections").fetchone()[0] == n1


def test_duplicate_documents_are_recorded_not_reindexed(tmp_path):
    (tmp_path / "a.pdf").write_bytes(b"%PDF-1.4 same")
    (tmp_path / "b.pdf").write_bytes(b"%PDF-1.4 same")
    db = index.rebuild(tmp_path, tmp_path / "vault.db")
    assert db.execute("SELECT COUNT(*) FROM documents").fetchone()[0] == 1
    assert db.execute("SELECT COUNT(*) FROM duplicates").fetchone()[0] == 1
```

Implement `src/vault/index.py`:

```python
"""SQLite + FTS5 index. The DB is derived: rebuild it any time from the corpus."""

from __future__ import annotations

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
  INSERT INTO sections_fts(rowid, title, body)
  VALUES (new.rowid, new.title, new.body);
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


def rebuild(root: Path, db_path: Path) -> sqlite3.Connection:
    db = _connect(db_path)
    db.execute("DELETE FROM duplicates")
    db.execute("DELETE FROM sections")
    db.execute("DELETE FROM documents")
    for doc in sources.scan(root):
        if doc.kind == "image":
            continue
        try:
            ex = extract.extract_document(doc.path, doc.kind)
        except Exception as exc:                      # a bad file must not kill the build
            ex = extract.Extracted(doc.path, doc.kind, doc.path.stem, "", [], {}, {}, str(exc))
        db.execute(
            "INSERT INTO documents(doc_id,path,kind,title,sha256,size,is_junk,meta_json,rag_json,extracted_at)"
            " VALUES(?,?,?,?,?,?,?,?,?,datetime('now'))",
            (doc.sha256[:16], str(doc.path), doc.kind, ex.title or doc.path.stem, doc.sha256,
             doc.size, int(doc.is_junk), _json(ex.meta), _json(ex.rag)),
        )
        for i, s in enumerate(ex.sections):
            db.execute(
                "INSERT INTO sections(section_id,doc_id,ord,title,level,body,line,word_count)"
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
    import json

    return json.dumps(d, ensure_ascii=False)


def search(db: sqlite3.Connection, query: str, limit: int = 25) -> list[dict]:
    """BM25 over section title+body. Returns rows with doc provenance."""
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
        (query, limit),
    ).fetchall()
    return [dict(r) for r in rows]
```

> **FTS5 query sanitisation is a real risk.** A user typing `rag OR 1=1` or a bare `-` will raise `sqlite3.OperationalError`. Wrap `query` before the MATCH: replace every non-alphanumeric run with `"` and quote the whole thing. Add a test:
> ```python
> def test_search_never_raises_on_punctuation(tmp_path):
>     _doc(tmp_path, "a.md", "Alpha", "body text")
>     db = index.rebuild(tmp_path, tmp_path / "vault.db")
>     assert index.search(db, 'rag OR 1=1 --') == []
> ```
> Implement `_fts_quote(q)` and use it in `search`.

Run, then **the real build**:

```bash
cd /home/lisacore/work/tvl-vault
PYTHON=/home/lisacore/.hermes/installs/a1e1e7cd4d1adb69/environments/34d7fdebd6b44efeb7123d4e6e030822/venv/bin/python - <<'PY'
import sys, time; sys.path.insert(0, "src")
from pathlib import Path
from vault import index
t=time.time()
db = index.rebuild(Path("/home/lisacore/.hermes/profiles/charlene/attachments"), Path("/tmp/vault-probe.db"))
print("secs", round(time.time()-t,1))
for q in ["SELECT COUNT(*) FROM documents", "SELECT COUNT(*) FROM sections", "SELECT COUNT(*) FROM duplicates"]:
    print(q, "->", db.execute(q).fetchone()[0])
print([r["doc_title"] for r in index.search(db, "sabotage")][:5])
PY
```

Expected: under 5 seconds, `documents ≈ 38`, `sections ≈ 250–400`, `duplicates 75`, and the sabotage search returns the CIA of AI and Calvin docs. Commit: `feat(index): SQLite FTS5 index with BM25 search`.

---

### Task 5 — `src/vault/review.py`: the five status flags (≈25 min, TDD)

This is what makes the system honest. **Deterministic first, model-assisted second.**

**Test first** — `tests/test_review.py`:

```python
from pathlib import Path

from vault import index, review


def _seed(tmp_path: Path) -> sqlite3.Connection:
    (tmp_path / "a.pdf").write_bytes(b"%PDF-1.4 A")
    (tmp_path / "b.pdf").write_bytes(b"%PDF-1.4 B")
    (tmp_path / "c.md").write_text("# Alpha\n\nbody one\n")
    (tmp_path / "d.md").write_text("# Beta\n\nbody two\n")
    return index.rebuild(tmp_path, tmp_path / "vault.db")


def test_byte_duplicate_gets_duplicate_flag(tmp_path):
    db = _seed(tmp_path)
    flags = review.compute_flags(db)
    kinds = [f["flag"] for f in flags]
    assert "duplicate" in kinds


def test_a_doc_with_no_sections_gets_unclear(tmp_path):
    (tmp_path / "empty.pdf").write_bytes(b"%PDF-1.4 no text at all")
    db = index.rebuild(tmp_path, tmp_path / "vault.db")
    flags = review.compute_flags(db)
    assert any(f["flag"] == "unclear" for f in flags)


def test_version_regress_is_flagged(tmp_path):
    # v1.0 and v1.2 of the same title: the older is OUTDATED
    (tmp_path / "x.md").write_text("# TVL — Same\n\nVersion:\nv1.0\n")
    (tmp_path / "y.md").write_text("# TVL — Same\n\nVersion:\nv1.2\n")
    db = index.rebuild(tmp_path, tmp_path / "vault.db")
    flags = [f for f in review.compute_flags(db) if f["flag"] == "outdated"]
    assert flags, "expected the v1.0 copy to be flagged outdated"
```

Implement `src/vault/review.py`:

```python
"""Five deterministic flags. No model required for any of them.

CURRENT    - newest version of its title, no contradictions found
DUPLICATE  - byte-identical copy of another document (sha256)
OUTDATED   - an older version of a title that exists in a newer version,
             or a document whose own VALIDITY tag is not Active
CONFLICT   - two documents make claims that cannot both be true (model-assisted,
             run separately; see Task 7)
UNCLEAR    - no extractable sections, or a section too short to be a claim
             (model-assisted classification; the deterministic pass marks
             "unclassified" so the UI can show it as needing a human)
"""

from __future__ import annotations

import json
import re
import sqlite3

FLAG_ORDER = ["duplicate", "outdated", "conflict", "unclear", "current"]

_VERSION_RE = re.compile(r"v?(\d+)\.(\d+)")


def _version_tuple(v: str) -> tuple[int, int] | None:
    m = _VERSION_RE.search(v or "")
    return (int(m.group(1)), int(m.group(2))) if m else None


def compute_flags(db: sqlite3.Connection) -> list[dict]:
    """Deterministic pass. One row per (section_id, flag)."""
    flags: list[dict] = []
    docs = [dict(r) for r in db.execute("SELECT * FROM documents")]

    # 1. duplicates
    for row in db.execute("SELECT sha256, path FROM duplicates"):
        flags.append({"section_id": None, "doc_id": row["sha256"][:16], "flag": "duplicate",
                      "reason": f"byte-identical to a canonical copy: {row['path']}",
                      "evidence": row["path"]})

    # 2. version regress: group by normalized title
    by_title: dict[str, list[dict]] = {}
    for d in docs:
        by_title.setdefault(_norm_title(d["title"]), []).append(d)
    for title, group in by_title.items():
        if len(group) < 2:
            continue
        vers = [( _version_tuple(json.loads(d["meta_json"]).get("version", "")), d) for d in group]
        vers = [(v, d) for v, d in vers if v]
        if len({v for v, _ in vers}) < 2:
            continue
        newest = max(v for v, _ in vers)
        for v, d in vers:
            if v < newest:
                flags.append({"section_id": None, "doc_id": d["doc_id"], "flag": "outdated",
                              "reason": f"v{v[0]}.{v[1]} superseded by v{newest[0]}.{newest[1]} of the same title",
                              "evidence": json.loads(d["meta_json"]).get("version", "")})

    # 3. validity tag not Active
    for d in docs:
        rag = json.loads(d["rag_json"])
        val = rag.get("validity", "")
        if val and "active" not in val.lower():
            flags.append({"section_id": None, "doc_id": d["doc_id"], "flag": "outdated",
                          "reason": f"VALIDITY tag says {val!r}", "evidence": val})

    # 4. unclear: no sections, or every section under 40 words
    for d in docs:
        rows = db.execute("SELECT word_count FROM sections WHERE doc_id=?", (d["doc_id"],)).fetchall()
        if not rows:
            flags.append({"section_id": None, "doc_id": d["doc_id"], "flag": "unclear",
                          "reason": "no extractable sections", "evidence": ""})

    # 5. current: everything not flagged
    flagged = {f["doc_id"] for f in flags}
    for d in docs:
        if d["doc_id"] not in flagged:
            flags.append({"section_id": None, "doc_id": d["doc_id"], "flag": "current",
                          "reason": "newest version, no contradictions found", "evidence": ""})
    return flags


def _norm_title(t: str) -> str:
    t = re.sub(r"\s*\((?:v?\d+(?:\.\d+)?|\d{4}|Draft[^)]*)\)\s*", " ", t or "")
    return re.sub(r"[^a-z0-9]+", " ", t.lower()).strip()


def write_flags(db: sqlite3.Connection, flags: list[dict]) -> None:
    db.execute("CREATE TABLE IF NOT EXISTS flags ("
               "doc_id TEXT, section_id TEXT, flag TEXT, reason TEXT, evidence TEXT, "
               "PRIMARY KEY(doc_id, section_id, flag))")
    db.execute("DELETE FROM flags")
    for f in flags:
        db.execute("INSERT OR REPLACE INTO flags VALUES(?,?,?,?,?)",
                   (f["doc_id"], f["section_id"], f["flag"], f["reason"], f["evidence"]))
    db.commit()


def conflicts(db: sqlite3.Connection) -> list[dict]:
    """Pairs of sections that contradict. Model-assisted; see Task 7. Empty until then."""
    return []
```

Run, then the real corpus:

```bash
cd /home/lisacore/work/tvl-vault
PYTHON=/home/lisacore/.hermes/installs/a1e1e7cd4d1adb69/environments/34d7fdebd6b44efeb7123d4e6e030822/venv/bin/python - <<'PY'
import sys; sys.path.insert(0,"src")
from pathlib import Path
from collections import Counter
from vault import index, review
db = index.rebuild(Path("/home/lisacore/.hermes/profiles/charlene/attachments"), Path("/tmp/vault-probe.db"))
flags = review.compute_flags(db)
print(Counter(f["flag"] for f in flags))
for f in flags:
    if f["flag"] != "current":
        print(f["flag"], "|", f["doc_id"], "|", f["reason"][:80])
PY
```

Expected: `duplicate` ≥ 7, `outdated` ≥ 1 (the Platform Governance docx, or a v1.0 vs v1.2 pair), `unclear` ≥ 1. Commit: `feat(review): deterministic duplicate/outdated/unclear flags`.

---

### Task 6 — `dashboard/plugin_api.py` + `desktop/plugin.js`: Graph, Wall, Review (≈40 min)

Copy the loader pattern from `work/data-deck/dashboard/plugin_api.py` **verbatim in shape** — loaded by spec, never `sys.path`, package name derived from the install path:

```python
"""Backend namespace /api/plugins/tvl-vault/ — mounted by the dashboard loader.

Loaded standalone, so the package is brought in by spec. Never put the plugin
directory on sys.path (it would shadow the host's own `tools` package).
"""
from __future__ import annotations

import hashlib
import importlib
import importlib.util
import sys
from pathlib import Path

from fastapi import APIRouter, HTTPException

_PLUGIN_ROOT = Path(__file__).resolve().parent.parent
_PKG_NAME = "_the_vault_dashboard_" + hashlib.sha256(
    str(_PLUGIN_ROOT).encode("utf-8")).hexdigest()[:16]


def _load_package():
    mod = sys.modules.get(_PKG_NAME)
    if mod is not None:
        return mod
    spec = importlib.util.spec_from_file_location(
        _PKG_NAME, _PLUGIN_ROOT / "__init__.py",
        submodule_search_locations=[str(_PLUGIN_ROOT)])
    mod = importlib.util.module_from_spec(spec)
    sys.modules[_PKG_NAME] = mod
    spec.loader.exec_module(mod)
    return mod


_load_package()
_paths = importlib.import_module(".paths", _PKG_NAME)
_index = importlib.import_module(".index", _PKG_NAME)
_review = importlib.import_module(".review", _PKG_NAME)

router = APIRouter()


def _db():
    p = _paths.vault_db_path()
    if not p.exists():
        raise HTTPException(404, "vault not built — run `vault.py rebuild`")
    import sqlite3
    db = sqlite3.connect(p)
    db.row_factory = sqlite3.Row
    return db


@router.get("/health")
async def health() -> dict:
    return {"ok": True, "data_root": str(_paths.data_root())}


@router.get("/stats")
async def stats() -> dict:
    db = _db()
    return {
        "documents": db.execute("SELECT COUNT(*) FROM documents").fetchone()[0],
        "sections": db.execute("SELECT COUNT(*) FROM sections").fetchone()[0],
        "duplicates": db.execute("SELECT COUNT(*) FROM duplicates").fetchone()[0],
        "images": db.execute("SELECT COUNT(*) FROM documents WHERE kind='image'").fetchone()[0],
        "flags": [dict(r) for r in db.execute(
            "SELECT flag, COUNT(*) AS n FROM flags GROUP BY flag")],
    }


@router.get("/graph")
async def graph() -> dict:
    """Nodes = documents + sections; edges = contains, depends-on, duplicates."""
    db = _db()
    nodes, edges = [], []
    for d in db.execute("SELECT doc_id,title,kind,path FROM documents"):
        nodes.append({"id": d["doc_id"], "label": d["title"], "kind": d["kind"],
                      "group": "document", "path": d["path"]})
    for s in db.execute("SELECT section_id,doc_id,title FROM sections ORDER BY ord"):
        nodes.append({"id": s["section_id"], "label": s["title"], "kind": "section",
                      "group": "section", "doc": s["doc_id"]})
        edges.append({"source": s["doc_id"], "target": s["section_id"], "kind": "contains"})
    for e in db.execute("SELECT doc_id, rag_json FROM documents"):
        import json
        rag = json.loads(e["rag_json"])
        for dep in rag.get("dependency", []):
            target = db.execute("SELECT doc_id FROM documents WHERE title LIKE ?",
                                (f"%{dep.split('(')[0].strip()}%",)).fetchone()
            if target:
                edges.append({"source": e["doc_id"], "target": target["doc_id"], "kind": "depends"})
    return {"nodes": nodes, "edges": edges}


@router.get("/search")
async def search(q: str, limit: int = 25) -> dict:
    db = _db()
    return {"results": _index.search(db, q, limit)}


@router.get("/review")
async def review_queue() -> dict:
    db = _db()
    return {"flags": [dict(r) for r in db.execute(
        "SELECT f.flag, f.reason, f.evidence, d.title, d.path FROM flags f "
        "JOIN documents d ON d.doc_id=f.doc_id ORDER BY f.flag")]}


@router.get("/document/{doc_id}")
async def document(doc_id: str) -> dict:
    if not re.fullmatch(r"[0-9a-f]{16}", doc_id):
        raise HTTPException(400, "bad doc_id")
    db = _db()
    d = db.execute("SELECT * FROM documents WHERE doc_id=?", (doc_id,)).fetchone()
    if not d:
        raise HTTPException(404, "no such document")
    secs = db.execute("SELECT ord,title,body,level FROM sections WHERE doc_id=? ORDER BY ord", (doc_id,))
    return {"document": dict(d), "sections": [dict(s) for s in secs]}
```

> **`import re` is missing in the snippet above** — add it at the top. This is the kind of thing the plan must not leave to chance.

`desktop/plugin.js` — **build it against the approved `docs/mockup/vault-mockup.html` from Task 0.5. Copy its CSS values and its force layout verbatim; the mockup's `DATA` becomes the `/graph` JSON.** Do not redesign here. Copy the loader structure of `work/data-deck/desktop/plugin.js` (BUILD constant, `useValue(host.state…)`, `ctx.rest`, `ctx.register({area: ROUTES_AREA, ...})`, `ctx.register({area: SIDEBAR_NAV_AREA, ...})`). Tabs: **Graph · Wall · Ask · Review**. No npm package.

The force layout, in full (drop into `desktop/plugin.js`):

```js
// Minimal force layout. ~40 lines, no dependencies, runs offline.
function simulate(nodes, edges, ticks = 300) {
  const w = 900, h = 620
  nodes.forEach((n, i) => {
    n.x = w / 2 + Math.cos(i * 2.399) * 180
    n.y = h / 2 + Math.sin(i * 2.399) * 160
    n.vx = 0; n.vy = 0
  })
  const byId = new Map(nodes.map(n => [n.id, n]))
  for (let t = 0; t < ticks; t++) {
    for (const n of nodes) {
      for (const m of nodes) {
        if (n === m) continue
        let dx = n.x - m.x, dy = n.y - m.y
        let d2 = dx * dx + dy * dy || 0.01
        const f = 2200 / d2
        n.vx += dx * f * 0.02; n.vy += dy * f * 0.02
      }
    }
    for (const e of edges) {
      const a = byId.get(e.source), b = byId.get(e.target)
      if (!a || !b) continue
      let dx = b.x - a.x, dy = b.y - a.y
      const d = Math.sqrt(dx * dx + dy * dy) || 0.01
      const want = e.kind === 'contains' ? 90 : 190
      const f = (d - want) * 0.012
      a.vx += dx / d * f; a.vy += dy / d * f
      b.vx -= dx / d * f; b.vy -= dy / d * f
    }
    for (const n of nodes) {
      n.vx *= 0.86; n.vy *= 0.86
      n.x = Math.max(16, Math.min(w - 16, n.x + n.vx))
      n.y = Math.max(16, Math.min(h - 16, n.y + n.vy))
    }
  }
  return { w, h }
}
```

Render `<svg>` with `<line>` for edges and `<circle>` + `<text>` for nodes, coloured by `group`, with a click handler that opens the section in the side panel. **Test it in the real window** — per the user's rule, the user runs the desktop install test; leave no backend install behind.

Commit: `feat(ui): graph, wall and review queue`.

---

### Task 7 — `src/vault/qa.py`: cited answers (≈20 min, TDD)

**Test first** — `tests/test_qa.py`:

```python
from vault import qa


def test_prompt_contains_the_citations_and_the_no_invention_rule():
    chunks = [{"title": "A", "body": "sabotage lowers output", "doc_title": "D", "path": "/x"}]
    prompt = qa.build_prompt("what does the doctrine say?", chunks)
    assert "sabotage lowers output" in prompt
    assert "no invention" in prompt.lower() or "do not invent" in prompt.lower()


def test_citations_are_parsed_from_a_model_answer():
    text = 'See [1] and [2].'
    cites = qa.parse_citations(text, [
        {"n": 1, "title": "A", "path": "/a"},
        {"n": 2, "title": "B", "path": "/b"},
    ])
    assert [c["title"] for c in cites] == ["A", "B"]
```

Implement `src/vault/qa.py`:

```python
"""Cited question-answering. The model sees ONLY the retrieved sections."""

from __future__ import annotations

import re
import sqlite3

from . import index

SYSTEM = """You are answering from a fixed corpus. Rules:
1. Use ONLY the numbered passages below. Do not invent, do not add outside knowledge.
2. Every claim ends with a citation [n] matching a passage number.
3. If the passages do not answer the question, say exactly: "Not answered by the corpus."
4. Plain language. No jargon. Short sentences.
"""


def build_prompt(question: str, chunks: list[dict]) -> str:
    parts = [f"[{i + 1}] ({c['doc_title']} — {c['section_title']})\n{c['body'][:1800]}"
             for i, c in enumerate(chunks)]
    return f"{SYSTEM}\nQUESTION: {question}\n\nPASSAGES:\n" + "\n\n".join(parts)


def parse_citations(text: str, chunks: list[dict]) -> list[dict]:
    nums = {int(n) for n in re.findall(r"\[(\d+)\]", text)}
    return [{**chunks[n - 1], "n": n} for n in sorted(nums) if 1 <= n <= len(chunks)]


def answer(db: sqlite3.Connection, question: str, llm, k: int = 6) -> dict:
    chunks = index.search(db, question, limit=k)
    if not chunks:
        return {"answer": "Not answered by the corpus.", "citations": []}
    res = llm.complete(
        [{"role": "user", "content": build_prompt(question, chunks)}],
        purpose="tvl-vault qa",
    )
    text = getattr(res, "text", "") or ""
    return {"answer": text, "citations": parse_citations(text, chunks)}
```

Wire it as `POST /api/plugins/tvl-vault/ask` in `plugin_api.py`, passing `ctx.llm` into the module at `register()` time (same pattern as `strategic-arena/llm_adapter.py`). Run on the **session model** — no override, no capability needed.

Commit: `feat(qa): cited answers over the corpus`.

---

### Task 8 — `src/vault/cli.py` + `scripts/rebuild.sh`: the one command (≈10 min)

```python
"""`python -m vault rebuild` — rebuild the index from the corpus."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import index, paths, review


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="vault")
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("rebuild")
    r.add_argument("--root", action="append", default=None)
    r.add_argument("--db", default=None)
    a = ap.parse_args(argv)

    roots = [Path(x) for x in (a.root or [])] or paths.corpus_roots()
    db_path = Path(a.db) if a.db else paths.vault_db_path()
    total_docs = total_secs = 0
    for root in roots:
        db = index.rebuild(root, db_path)
        total_docs = db.execute("SELECT COUNT(*) FROM documents").fetchone()[0]
        total_secs = db.execute("SELECT COUNT(*) FROM sections").fetchone()[0]
    flags = review.compute_flags(db)
    review.write_flags(db, flags)
    from collections import Counter

    print(f"vault: {len(roots)} roots → {db_path}")
    print(f"  documents {total_docs} · sections {total_secs} · duplicates "
          f"{db.execute('SELECT COUNT(*) FROM duplicates').fetchone()[0]}")
    print("  flags: " + ", ".join(f"{k}={v}" for k, v in Counter(f['flag'] for f in flags).items()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

`scripts/rebuild.sh`:

```bash
#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."
PYTHON="${PYTHON:-python3}"
exec "$PYTHON" -m vault rebuild "$@"
```

```bash
chmod +x scripts/rebuild.sh
./scripts/rebuild.sh --db /tmp/vault-probe.db
```

Expected:

```
vault: 3 roots → /tmp/vault-probe.db
  documents 156 · sections 900 · duplicates 75
  flags: current=…, duplicate=…, outdated=…, unclear=…
```

Commit: `feat(cli): one-command rebuild with flag summary`.

---

### Task 9 — Images: dedupe, dimensions, vision captions, wall (≈25 min)

**No OCR available** (`tesseract` absent), so images are captioned by the vision model through `ctx.llm.complete_structured(input=[PluginLlmImageInput(data=...)])` — that is the one place the image half of the corpus becomes text.

`src/vault/images.py`:

```python
"""Images: sha256 dedupe (done in sources.py), dimensions, and vision captions."""

from __future__ import annotations

from pathlib import Path

from .sources import Document, is_junk_name


def caption(llm, path: Path) -> str:
    """One short line: what this image is. Empty string on failure — never fatal."""
    try:
        from agent.plugin_llm import PluginLlmImageInput

        res = llm.complete_structured(
            instructions=(
                "Describe this image in one short line for a search index. "
                "Say what it shows and what text is legible. No more than 20 words."
            ),
            input=[PluginLlmImageInput(data=path.read_bytes(), mime_type=_mime(path))],
            purpose="tvl-vault image caption",
        )
        return (getattr(res, "text", "") or "").strip()
    except Exception:
        return ""


def _mime(path: Path) -> str:
    return {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
            ".webp": "image/webp", ".gif": "image/gif"}.get(path.suffix.lower(), "image/png")
```

Store captions in a `captions` table keyed by sha256, and add `GET /api/plugins/tvl-vault/images` returning `{sha256, path, caption, width, height, is_junk}` for the wall. The wall shows **junk collapsed behind a "show 130 test screenshots" toggle** — the user's "pretty visual items" are the portraits, the org chart and the validize renders.

Commit: `feat(images): dedupe, dimensions and vision captions`.

---

### Task 10 — Conflict detection and the review queue (≈20 min)

`review.conflicts(db, llm)` — the model-assisted pass, run **on demand** (never during `rebuild`):

1. Group sections by shared salient terms (deterministic: top BM25 terms per section).
2. For each candidate pair, ask the model: *"Do these two passages make claims that cannot both be true? Answer JSON {contradicts: bool, reason: str}."*
3. Write `conflict` flags with the model's `reason` as `evidence`.

Guardrails: **cap at 200 pairs per run**, `temperature=0`, and a test that a `conflict` flag always carries non-empty `evidence`.

The Review tab lists every non-`current` flag as a card with **Keep / Mark current / Edit** — and **Edit** writes a correction into a `corrections` table (never into the source file). That is what makes the staleness handling *reversible*, per decision 4.

Commit: `feat(review): model-assisted conflict detection and correction queue`.

---

### Task 11 — Package, validate, document (≈15 min)

`plugin.yaml`:

```yaml
name: tvl-vault
version: "0.1.0"
manifest_version: 1
kind: standalone
requires_hermes: ">=0.23.0"
author: LeMultiFox
license: MIT
homepage: https://github.com/trillionverselabs-boop/tvl-vault
tags: [knowledge-base, search, graph, local-first, research]
description: >-
  One indexed, visually searchable home for the whole TVL corpus: every document
  sectioned, deduplicated and flagged CURRENT / OUTDATED / DUPLICATE / CONFLICT /
  UNCLEAR, shown as a graph, a card wall and a cited question-answering view.
provides_tools:
  - vault_search
  - vault_ask
  - vault_rebuild
# No capabilities block: the plugin asks the host for nothing special.
# No python_dependencies: everything is stdlib + poppler, and a non-empty list
# makes the desktop's non-interactive install abort.
```

Then:

```bash
cd /home/lisacore/work/tvl-vault
hermes plugins validate . --install-deps
# expected: "Validation passed." and "security scan — safe"
```

Write `README.md` (what it is / what it is not / install / the four flags / rebuild), `docs/SCHEMA.md` (the tables, one section per column), `docs/CORPUS.md` (the measured inventory in §2 of this plan, with the exact duplicate hashes), `docs/DECISIONS.md` (the four user decisions + the stack decisions + what was ruled out).

Commit: `chore: package, validate and document`.

---

### Task 12 — The walkthrough with the user (≈30 min, no code)

Generate the review report and go through it **with her**, one approved item at a time (her standing working agreement):

```bash
./scripts/rebuild.sh
PYTHON=… python3 - <<'PY'
import sys, json; sys.path.insert(0,"src")
from pathlib import Path
from vault import paths, index, review
db = index._connect(paths.vault_db_path())
rows = db.execute("SELECT f.flag,d.title,d.path,f.reason FROM flags f JOIN documents d ON d.doc_id=f.doc_id WHERE f.flag!='current' ORDER BY f.flag").fetchall()
print(json.dumps([dict(r) for r in rows], indent=2, ensure_ascii=False))
PY
```

Then, for each flag: **keep / mark current / correct**, recorded in `corrections`. This is the "go through the duplicates, the conflicts, and update based on changes" step — done in the UI, not by editing files.

Commit: `docs: the first review pass — N flags resolved`.

---

## Tests / validation

**Per task:** write the test, run it, see it fail for the right reason, implement the minimum, run it, see it pass, commit. Commands and expected results are inline above.

**Full suite:**

```bash
cd /home/lisacore/work/tvl-vault
PYTHON=/home/lisacore/.hermes/installs/a1e1e7cd4d1adb69/environments/34d7fdebd6b44efeb7123d4e6e030822/venv/bin/python ./scripts/test.sh
# expected: all tests pass
```

**End-to-end, on the real corpus** (the acceptance test):

```bash
./scripts/rebuild.sh
```

| Assertion | Expected |
|---|---|
| documents | ~156 (13 pdf + 1 docx + 2 md + 19 pasted text + 1 html + 1 csv + ~85 images + 118 notes) |
| sections | ~900–1200 |
| duplicates | **75** image + **7** pdf = 82 rows in `duplicates` |
| `duplicate` flags | ≥ 7 |
| `outdated` flags | ≥ 1 |
| search `sabotage` | returns the CIA of AI doc and the Calvin doc |
| search `RAG OR 1=1 --` | `[]`, no exception |
| rebuild twice | identical counts |
| `hermes plugins validate . --install-deps` | `Validation passed.` |

**The user's acceptance test:** she runs the desktop install (Install from Git with the Desktop target, unpinned), opens The Vault, and checks three things: the graph renders and is clickable; the wall shows the character portraits and the org chart; and "what did the doctrine say about chunking?" returns an answer whose citations open the exact section. Per her rule: **leave no backend install behind**, and do not run that test in this plan turn.

---

## Risks, tradeoffs, and open questions

| # | Risk | Mitigation |
|---|---|---|
| 1 | **`pdftotext` layout drift.** `-layout` output changes with poppler versions; the section regexes are tuned to 26.01.0. | Pin the probe command in `docs/CORPUS.md`; the section splitter has a fallback (if 0 sections, mark `unclear` rather than guess). |
| 2 | **Heading conventions are inconsistent** (§2.1). Four styles, two files with none. | All four regexes ship at once; files with 0 sections get `unclear`, which is *honest*. |
| 3 | **Free model rate limits** will throttle the Q&A and conflict passes. | Both are on-demand, never in `rebuild`. Q&A falls back to "Not answered by the corpus." Conflict detection is capped at 200 pairs. |
| 4 | **Vision captions cost money** on 160 images. | Caption **only the ~28 non-junk images**; junk is indexed as an artifact with dimensions and no caption. |
| 5 | **`plugins.plugin_storage` is importable only inside Hermes.** | The `except` fallback is tested in Task 1. |
| 6 | **Scope creep into "cleaned, restructured copies"** (option B, which the user did **not** choose). | Corrections go to a `corrections` table; the source files are never written. Revisit only if she asks. |
| 7 | **The 3,203-paper corpus is a claim, not a corpus.** Only 5 external papers exist. | Mark `UNCLEAR` in the review report; do not build a paper pipeline until the papers are on disk. |
| 8 | **No git on most note folders.** | Task 0 backs them up; afterwards the Vault DB is the index of record. Consider `git init` on `work/tvl-*` as a separate, approved item. |
| 9 | **Desktop install test is the user's job.** | The plan does not install anything. |
| 10 | **Search quality without embeddings.** | Deliberate: 2.7 MB of text, BM25 + deterministic tiebreak. Revisit only if recall is visibly poor in the walkthrough. |

**Open questions for the user (do not block the build):**

1. Should `work/tvl-*` get git repos of their own, or is the Vault DB enough history?
2. The ~130 plugin-test screenshots: keep indexed as artifacts (current plan), or leave them out of the Vault entirely?
3. The `validize{a..n}.jpg` renders — are those current brand assets, or superseded by `tvl-brand`?
4. The 1.6 MB Nous Arete-27B page — keep it in the corpus as a captured source, or drop it?

---

## File map (what this plan creates)

```
/home/lisacore/work/tvl-vault/
├── plugin.yaml
├── pyproject.toml
├── README.md
├── .gitignore
├── scripts/
│   ├── test.sh
│   └── rebuild.sh
├── docs/
│   ├── SCHEMA.md
│   ├── CORPUS.md          ← the measured inventory, exact hashes
│   ├── DECISIONS.md
│   └── mockup/
│       └── vault-mockup.html  Task 0.5 (approved look; Task 6 copies it)
├── src/vault/
│   ├── __init__.py
│   ├── paths.py           Task 1
│   ├── sources.py         Task 2
│   ├── extract.py         Task 3
│   ├── index.py           Task 4
│   ├── review.py          Task 5, 10
│   ├── qa.py              Task 7
│   ├── images.py          Task 9
│   └── cli.py             Task 8
├── dashboard/
│   ├── manifest.json      {"name": "tvl-vault", "api": "plugin_api.py"}
│   └── plugin_api.py      Task 6, 7
├── desktop/
│   └── plugin.js          Task 6
└── tests/
    ├── test_paths.py      Task 1
    ├── test_sources.py    Task 2
    ├── test_extract.py    Task 3
    ├── test_index.py      Task 4
    ├── test_review.py     Task 5
    ├── test_qa.py         Task 7
    └── fixtures/
        └── one-page.pdf   Task 3 (generated, committed)
```
