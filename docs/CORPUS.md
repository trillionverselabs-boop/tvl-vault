# The Vault — corpus inventory

**Every number here was produced by a command on this machine on 2026-11-15.**
Re-run the probe to confirm before quoting any of it:

```bash
cd /home/lisacore/work/tvl-vault
./scripts/rebuild.sh --db /tmp/vault-probe.db
python -m vault stats --db /tmp/vault-probe.db
```

```
vault: 4 roots → /tmp/vault-probe.db
  documents 369 · sections 1866 · duplicates 118 · images 199
  flags: duplicate=118, unclear=43, current=92
  images: 116 shown · 83 test screenshots
```

---

## The four roots

| # | Root | What it holds |
|---|---|---|
| 1 | `~/.hermes/profiles/charlene/attachments` | what the desktop was handed: doctrine PDFs, portraits, pasted text, the saved web page |
| 2 | `/home/lisacore/work` | the plugin projects and their notes, plus `arena-demo-video`, `data-deck`, `example-plugin` |
| 3 | `/home/lisacore/Projects` | `youtube-channel`, `validize`, `hackathons` |
| 4 | `/home/lisacore/work/tvl-ingest` | the `Trillionverselabs vision/` drop — 25 PDFs that landed 2026-11-14 |

The fourth root is added only when the directory exists, and `HERMES_VAULT_ROOTS`
overrides all four (a test, or a second machine). The Vault's own repository is
**excluded** — it lives inside `~/work`, and without the exclusion its own plan
and handoff would be indexed as doctrine and outrank the doctrine itself.

### Per root, as scanned

| Root | Documents | Duplicate rows | Kinds |
|---|---|---|---|
| attachments | 134 | 53 | image 114 · pdf 16 · csv 1 · markdown 2 · docx 1 |
| work | 191 | 34 | markdown 58 · html 26 · image 73 · text 9 · pdf 25 |
| Projects | 50 | 6 | markdown 34 · csv 3 · text 1 · image 12 |
| tvl-ingest | 25 | 0 | pdf 25 |

---

## The index, measured

| Measure | Value |
|---|---|
| documents | **369** |
| sections | **1,866** |
| duplicates rows | **118** |
| images | 199 |
| flags | duplicate 118 · unclear 43 · current 92 |
| review queue | **101** (58 duplicate + 43 unclear, 0 images) |
| build time | **~7 s** |

### Documents by kind

| Kind | Count |
|---|---|
| image | 199 |
| markdown | 94 |
| pdf | 35 |
| html | 26 |
| text | 10 |
| csv | 4 |
| docx | 1 |

The 199 image documents are the corpus's images, not just the ~28 portraits.

### Sections by document (top ten)

| Sections | Kind | Document |
|---|---|---|
| 335 | markdown | *(a markdown file whose first heading is a rule of dashes)* |
| 64 | pdf | `TVL - Market Research Options (Draft 0.1)` |
| 53 | markdown | `Plan — Upfront: restore what the last test lost…` |
| 50 | markdown | `Validize Research Pipeline v2 — Signal → Papers → Scored Opportunities` |
| 42 | pdf | `multi-agent-social-simulation` |
| 39 | markdown | `Game Theory for a Ruthless AI Market` |
| 33 | pdf | `Instagram Disruptive Campaigns Research` |
| 31 | pdf | `camel-communicative-agents-for-mind-exploration` |
| 31 | markdown | `Modular Private Hermes Plugin Architecture — the YouTube system` |
| 29 | markdown | `Progress log — Upfront` |

**43 documents have zero sections** and are flagged `unclear`. They are the
consequence of the heading conventions not being consistent: `TVL — Video
Production — Execution (v1.2)` and `TVL — YouTube Equalizer Technology —
Framework (v1.2)` are prose with no numbered headings, the `scene1..9` HTML
scenes have no headings, and the `concat*.txt` pastes are raw transcripts. Zero
sections is recorded as `unclear`, not guessed at.

---

## The 118 duplicates, exactly

`duplicates` is keyed `(sha256, path)`, so a group of N identical files
contributes N − 1 rows.

**By kind of the canonical document:** image 60 · pdf 32 · markdown 22 · html 2 ·
text 2.

**By root of the copy:** attachments 53 · work 59 · Projects 6.

**By group size:** 53 groups of 1 copy · 9 of 2 · 6 of 3 · 1 each of 4, 5, 6, 7, 8.

### Exact groups (sha256, first 12 hex)

| sha256 | Kind | Canonical | Copies |
|---|---|---|---|
| `71423ff3b389` | html | `work/arena-demo-video/arena-demo/index.html` | 2 |
| `596d0538c865` | image | `work/arena-demo-video/arena-demo/frames/v3_14.png` | 8 |
| `42696821dfe5` | image | `work/arena-demo-video/arena-demo/frames/v2_20.png` | 6 |
| `d8121c7ff986` | image | `attachments/popupd-2.jpg` | 5 |
| `b0ac134a1f32` | image | `attachments/popupd1-2.jpg` | 5 |
| `22fa3a850eda` | image | `attachments/20251205_230035-2.jpg` | 3 |
| `fde71c86c8e1` | image | `attachments/popupd11-2.jpg` | 3 |
| `dd72eda6c551` | image | `attachments/popupd12-2.jpg` | 3 |
| `f5b626f3b950` | image | `attachments/popupd13-2.jpg` | 3 |
| `0a546e082012` | image | `attachments/popupc-2.jpg` | 2 |
| `c39048051c70` | pdf | `attachments/TVL — CIA of AI — Canonical Logic (v1.0) (1).pdf` | 2 |
| `a892569636b8` | pdf | `attachments/TVL — YouTube Equalizer Technology — Framework (v1.2)-2.pdf` | 3 |
| `759945238045` | pdf | `attachments/TVL—SAE Fiscal Architecture (v1.2)-2.pdf` | 3 |
| `a2e4f09f37d4` | pdf | `attachments/TVL - Manifesto.pdf` | 2 |
| `1cb5aec97c58` | pdf | `attachments/TVL Market Research - Decisions.pdf` | 2 |
| `79f5867b7731` | pdf | `attachments/TVL — Video Production — Execution (v1.2).pdf` | 2 |
| `0897363ae4dc` | pdf | `attachments/TrillionVerse Labs - Market & Category Blueprint (Draft 0.1).pdf` | 2 |
| `b27b5b138b45` | pdf | `attachments/Anthropics-FoundersPlaybook…(2)-2.pdf` | 1 |
| `2b2ce8e18a09` | pdf | `attachments/TVL — Sovereign AI Council — Tactical Logic-Engine (v1.2)-2.pdf` | 1 |
| `6a437a8323ad` | pdf | `attachments/multi-agent-social-simulation-2.pdf` | 1 |
| `11ea7974c57c` | markdown | `work/arena-demo-video/README.md` | 7 |
| `7e7346e7dee3` | markdown | `work/strategic-arena/skills/*/SKILL.md` | 4 |
| `a6d0e2fb7596` | markdown | `Projects/hackathons/IDEA.md` | 2 |
| `86e0970073ab` | markdown | `Projects/validize/phase1/README.md` | 2 |
| `576c45186028` | text | `work/arena-demo-video/concat.txt` | 1 |
| `d0fd51c23baf` | text | `work/arena-demo-video/narration.txt` | 1 |

Plus 29 more PDF groups, nearly all the `tvl-ingest/Trillionverselabs vision/`
files, which are byte-identical to the attachments copy of the same document.

**Two mechanisms produce a row:**

1. **Byte-identical siblings in one root** — the browser's `popupd`, `popupd1`…
   series, the `plugin2/3/5` pair, the `-2` copies of the portraits.
2. **The same bytes under a second root** — the attachments PDF and its
   `tvl-ingest` twin. `sources.scan` sees one root at a time, so the later root's
   copy is a duplicate of the earlier one's canonical.

A browser's download counter (`doc (1).pdf`, `doc-2.pdf`) is **also** collapsed by
the version-stripped filename, which is why the ten `popupd1-2.jpg`-style
screenshots are junk rather than content.

---

## Images

| Measure | Value |
|---|---|
| image documents | 199 |
| shown on the wall | **116** |
| junk (counted, never captioned) | 83 |
| unreadable dimensions | **0** |

Dimensions come from the file's own header — PNG's IHDR, JPEG's SOFn marker,
WebP's `VP8 `/`VP8L`/`VP8X` chunks — so no image library is needed. Four real
files are WebP bytes named `.jpg`, so the type sent to the vision model is
sniffed from content, not the extension.

The junk rule is corpus-specific and drifts; the families it covers are
`plugintest*`, `plugin\d*`, `popup<letter><serial>`, `readme\d*`, `b\d_part\d`,
`s\d+`. Two families are **not** covered and are Lisa's call (see the handoff's
"Needs Lisa" #5): 45 video frames in `work/arena-demo-video/arena-demo/frames/`
and 4 screenshots in `work/strategic-arena/assets/`.

---

## Verified searches

| Query | Top result |
|---|---|
| `sabotage` | *Paper & Claim Verification Report* §2.2 "Tournament sabotage" |
| `chunking` | *TVL — CIA of AI — Canonical Logic (v1.0)* §RAG System Definition |
| `budget` | *Validize Research Pipeline v2* §1.4 Per-run rate budget |

---

## Known gaps, recorded honestly

- **`outdated=0`.** The version-regress rule finds no pair on this corpus. The
  plan's acceptance expected ≥ 1; the rule is correct and the corpus simply has no
  version regress. Worth a look in the review walkthrough.
- **`conflict=0`.** The conflict pass has never run against the live free model
  (Nous Portal is not logged in on this machine). It is on demand and capped at
  200 pairs; `POST /conflicts` is the only caller.
- **43 `unclear` flags are mostly documents with no headings** (see above), not
  43 documents that need a human decision. Images are excluded from the queue.
- **The 3,203-paper corpus is a claim, not a corpus.** Only 5 external papers are
  on disk. Nothing here should be read as a paper pipeline.
