#!/usr/bin/env python3
"""Build a self-contained audit of everything on the review queue.

The desktop Review tab is the live surface, but a decision this consequential
should also be readable as a document: every item, its actual text, the copy it
is measured against, and a recommendation with its reason — in one file, with no
app, no account, and nothing leaving the machine.

    ./scripts/review_audit.py                    # writes docs/REVIEW-AUDIT.html
    ./scripts/review_audit.py /path/to/out.html
"""

from __future__ import annotations

import html
import json
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from vault import paths, review  # noqa: E402

FLAG_LABEL = {
    "conflict": "Disagrees",
    "outdated": "Outdated",
    "duplicate": "Duplicate",
    "unclear": "Unclear",
}
FLAG_CLASS = {
    "conflict": "f-conflict",
    "outdated": "f-outdated",
    "duplicate": "f-duplicate",
    "unclear": "f-unclear",
}
ORDER = {"conflict": 0, "outdated": 1, "duplicate": 2, "unclear": 3}

CSS = """
  *{box-sizing:border-box}
  body{margin:0;background:#f6f7f9;color:#14181f;
       font:15px/1.55 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Arial,sans-serif}
  .wrap{max-width:1080px;margin:0 auto;padding:36px 30px 80px}
  h1{font-size:26px;margin:0 0 6px;letter-spacing:-.02em}
  .sub{color:#5b6675;margin:0 0 22px}
  .meta{background:#fff;border:1px solid #dfe3e8;border-radius:10px;padding:14px 18px;
        margin:0 0 26px;color:#37414f;font-size:14px}
  .meta b{color:#14181f}
  table{width:100%;border-collapse:collapse;background:#fff;border:1px solid #dfe3e8;
        border-radius:10px;overflow:hidden;font-size:13.5px}
  th,td{text-align:left;padding:8px 11px;border-bottom:1px solid #eceff2;vertical-align:top}
  th{background:#fafbfc;font-size:11px;letter-spacing:.08em;text-transform:uppercase;
     color:#6a7482;font-weight:600}
  tr:last-child td{border-bottom:none}
  .n{color:#8a93a0;font-variant-numeric:tabular-nums}
  code{font:12.5px ui-monospace,"SF Mono",Consolas,Menlo,monospace;color:#37414f;word-break:break-all}
  .flag{display:inline-block;padding:2px 8px;border-radius:20px;font-size:11.5px;
        font-weight:600;white-space:nowrap}
  .f-duplicate{background:#fff2d6;color:#8a5a00}
  .f-unclear{background:#e8eefc;color:#2d4a9a}
  .f-outdated{background:#eceff2;color:#4a5563}
  .f-conflict{background:#fde6e6;color:#a33}
  details{background:#fff;border:1px solid #dfe3e8;border-radius:10px;margin:0 0 12px;
          overflow:hidden}
  summary{cursor:pointer;padding:12px 16px;list-style:none;display:flex;gap:10px;
          align-items:baseline;flex-wrap:wrap}
  summary::-webkit-details-marker{display:none}
  summary:hover{background:#fafbfc}
  summary .t{font-weight:600;font-size:15px}
  summary .p{color:#6a7482;font-size:12.5px;font-family:ui-monospace,Consolas,monospace}
  summary .rec{margin-left:auto;font-size:12px;color:#2d4a9a;background:#eef3fe;
               padding:2px 9px;border-radius:20px;white-space:nowrap}
  .body{padding:0 16px 16px;border-top:1px solid #eceff2}
  .reason{margin:12px 0 0;padding:9px 12px;background:#fafbfc;border-left:3px solid #dfe3e8;
          font-size:13.5px;color:#37414f}
  .recbox{margin:10px 0 0;padding:11px 13px;background:#fff8e8;border:1px solid #f0e0b4;
          border-radius:8px;font-size:13.5px}
  .recbox b{text-transform:uppercase;font-size:10.5px;letter-spacing:.09em;color:#8a5a00;
            display:block;margin-bottom:3px}
  .cols{display:grid;grid-template-columns:1fr 1fr;gap:14px;margin-top:12px}
  .col{border:1px solid #eceff2;border-radius:8px;padding:11px 13px;min-width:0}
  .col h4{margin:0 0 8px;font-size:11px;letter-spacing:.07em;text-transform:uppercase;
          color:#6a7482;font-family:ui-monospace,Consolas,monospace;
          overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
  .sec{margin:0 0 10px}
  .sec h5{margin:0 0 3px;font-size:13px}
  .sec p{margin:0;font-size:13px;color:#37414f;line-height:1.5}
  .ex{font-size:13px;color:#37414f;white-space:pre-wrap;word-break:break-word;margin:0 0 8px}
  .copy{margin:0 0 6px;font-size:13px}
  .copy b{font-weight:600}
  .copy span{color:#5b6675;font-family:ui-monospace,Consolas,monospace;font-size:12px;
             word-break:break-all}
  .acts{display:flex;gap:8px;margin-top:14px;flex-wrap:wrap;align-items:center}
  button{font:inherit;font-size:13px;padding:7px 14px;border-radius:7px;cursor:pointer;
         border:1px solid #c8d0da;background:#fff;color:#2a3340}
  button:hover{border-color:#8a93a0}
  button.p{background:#14181f;border-color:#14181f;color:#fff}
  button[aria-pressed="true"]{background:#14181f;border-color:#14181f;color:#fff}
  .note{font-size:12px;color:#6a7482}
  .bar{position:sticky;top:0;background:#f6f7f9;padding:10px 0 12px;margin-bottom:14px;
       border-bottom:1px solid #dfe3e8;display:flex;gap:10px;align-items:center;flex-wrap:wrap}
  .bar .count{font-size:13px;color:#37414f}
  @media print{button,.bar{display:none}details{break-inside:avoid}.cols{grid-template-columns:1fr}}
  .index{margin-top:26px}
  .index table{border:none;border-radius:0 0 10px 10px}
  .index[open]{border-top:none}
"""

JS = r"""
const FLAG_LABEL = __FLAG_LABEL__;
const FLAG_CLASS = __FLAG_CLASS__;
const ITEMS = __ITEMS__;
ITEMS.forEach(i => { i.decision = null; i.note = ''; });

function esc(s){
  return String(s == null ? '' : s).replace(/[&<>"']/g,
    m => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[m]));
}

function decide(n, action){
  const it = ITEMS.find(i => i.n === n);
  if (!it) return;
  if (it.decision === action) { it.decision = null; it.note = ''; }
  else {
    it.decision = action;
    if (action === 'edit' && !it.note) it.note = window.prompt('What should be corrected?') || '';
  }
  render();
}

function render(){
  document.querySelectorAll('details.item').forEach(d => {
    const it = ITEMS.find(i => i.n === Number(d.dataset.n));
    if (!it) return;
    const pill = d.querySelector('.rec');
    if (it.decision) {
      pill.textContent = 'YOU: ' + it.decision.toUpperCase() + (it.note ? ' — ' + it.note : '');
      pill.style.background = '#e6f4ea'; pill.style.color = '#1d6b3a';
    } else {
      pill.textContent = 'MY RECOMMENDATION: ' + it.rec_action.toUpperCase();
      pill.style.background = '#eef3fe'; pill.style.color = '#2d4a9a';
    }
    d.querySelectorAll('button[data-act]').forEach(b =>
      b.setAttribute('aria-pressed', String(b.dataset.act === it.decision)));
  });
  const done = ITEMS.filter(i => i.decision).length;
  document.getElementById('count').textContent = done + ' of ' + ITEMS.length + ' decided';
  document.getElementById('copy').disabled = done === 0;
}

function copyDecisions(){
  const rows = ITEMS.filter(i => i.decision);
  const text = rows.map(r =>
    '#' + r.n + ' [' + r.flag + '] ' + r.action + (r.note ? ' — ' + r.note : '')).join('\n');
  const btn = document.getElementById('copy');
  navigator.clipboard.writeText(text).then(() => {
    btn.textContent = 'Copied ' + rows.length + ' — paste them to Charlene';
    setTimeout(() => { btn.textContent = 'Copy my decisions'; }, 5000);
  });
}

function item(i){
  const secs = i.sections.length
    ? i.sections.map(s => '<div class="sec"><h5>' + esc(s.title || '—') +
        '</h5><p>' + esc(s.body) + '</p></div>').join('')
    : '<p class="ex">' + esc(i.excerpt || 'No text could be extracted.') + '</p>';

  let right;
  if (i.copies.length) {
    right = '<h4>The copy</h4>' +
      i.copies.map(cp => '<div class="copy"><b>' + esc(cp.name) + '</b><br>' +
        '<span>' + esc(cp.path) + '</span></div>').join('') +
      '<div class="sec"><h5>The same text</h5><p>Identical bytes — sha256 ' +
      esc(String(i.sha).slice(0, 16)) + '…</p></div>' +
      (i.sections.length ? '<p class="ex">' + esc(i.sections[0].body) + '</p>' : '');
  } else {
    right = '<h4>Why it is flagged</h4><p class="ex">' +
      esc(i.reason || 'No reason recorded.') + '</p>' +
      (i.excerpt ? '<p class="ex">' + esc(i.excerpt) + '</p>' : '');
  }

  const label = FLAG_LABEL[i.flag] || i.flag;
  return '<details class="item" data-n="' + i.n + '">' +
    '<summary><span class="n">#' + i.n + '</span>' +
    '<span class="flag ' + (FLAG_CLASS[i.flag] || '') + '">' + esc(label) + '</span>' +
    '<span class="t">' + esc(i.title) + '</span>' +
    '<span class="p">' + esc(i.path) + '</span>' +
    '<span class="rec"></span></summary>' +
    '<div class="body">' +
      '<p class="reason"><b>' + esc(label) + '.</b> ' + esc(i.reason) + '</p>' +
      '<div class="recbox"><b>My recommendation · ' + esc(i.rec_action) + '</b>' +
        esc(i.rec_why) + '</div>' +
      '<div class="cols">' +
        '<div class="col"><h4>' + esc(i.kind) + ' · ' + esc(i.path) + '</h4>' + secs +
          '<div class="note">' + i.section_count + ' sections</div></div>' +
        '<div class="col">' + right + '</div>' +
      '</div>' +
      '<div class="acts">' +
        '<button class="p" data-act="confirm" onclick="decide(' + i.n + ',\'confirm\')">Confirm</button>' +
        '<button data-act="keep" onclick="decide(' + i.n + ',\'keep\')">Keep</button>' +
        '<button data-act="edit" onclick="decide(' + i.n + ',\'edit\')">Edit</button>' +
      '</div>' +
    '</div></details>';
}

document.getElementById('items').innerHTML = ITEMS.map(item).join('');
render();
"""


def collect() -> list[dict]:
    db = sqlite3.connect(paths.vault_db_path())
    db.row_factory = sqlite3.Row
    rows = []
    for f in review.queue(db):
        c = review.compare(db, f["doc_id"], f["flag"])
        d = c["document"]
        rows.append({
            "doc_id": f["doc_id"],
            "flag": f["flag"],
            "title": f["title"],
            "path": f["path"],
            "kind": f["kind"],
            "reason": c["reason"],
            "evidence": c["evidence"],
            "rec_action": c["recommendation"]["action"],
            "rec_why": c["recommendation"]["why"],
            "sections": d["sections"],
            "excerpt": d["excerpt"],
            "copies": d["counterparts"],
            "section_count": d["section_count"],
            "sha": d["sha256"],
        })
    rows.sort(key=lambda r: ORDER.get(r["flag"], 9))
    for n, r in enumerate(rows, start=1):
        r["n"] = n
    return rows


def build(rows: list[dict], out_path: Path) -> Path:
    # A corpus excerpt can itself contain `<script>` (the unclear items are HTML
    # scene files). Left alone it closes this inline script and the whole audit
    # renders blank. `\/` is a valid JSON escape for `/`, so the data is
    # unchanged and the tag is broken.
    payload = json.dumps(rows).replace("</", "<\\/")
    js = (JS.replace("__FLAG_LABEL__", json.dumps(FLAG_LABEL))
             .replace("__FLAG_CLASS__", json.dumps(FLAG_CLASS))
             .replace("__ITEMS__", payload))

    summary = "".join(
        "<tr><td class='n'>{}</td><td><span class='flag {}'>{}</span></td>"
        "<td>{}</td><td><code>{}</code></td><td>{}</td></tr>".format(
            r["n"], FLAG_CLASS.get(r["flag"], ""),
            html.escape(FLAG_LABEL.get(r["flag"], r["flag"])),
            html.escape(r["title"]), html.escape(r["path"]), html.escape(r["rec_action"] or ""))
        for r in rows)

    counts = {f: sum(1 for r in rows if r["flag"] == f) for f in FLAG_LABEL}
    def cnt(n: int, one: str, many: str) -> str:
        return f"{n} {one if n == 1 else many}"
    doc = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<title>The Vault — review audit</title>
<style>{CSS}</style></head>
<body><div class="wrap">
  <h1>The Vault — review audit</h1>
  <p class="sub">Every document waiting on a decision, with its actual text and a
     recommendation. Reading it changes nothing; a decision is only recorded when
     you say so. Open an item, read it, then Confirm, Keep or Edit.</p>
  <div class="meta">
    <b>{len(rows)} items</b> &nbsp;·&nbsp;
    <b>{cnt(counts['duplicate'], 'duplicate', 'duplicates')}</b> &nbsp;·&nbsp;
    <b>{cnt(counts['unclear'], 'unclear', 'unclear')}</b> &nbsp;·&nbsp;
    <b>{cnt(counts['outdated'], 'outdated', 'outdated')}</b> &nbsp;·&nbsp;
    <b>{cnt(counts['conflict'], 'disagreement', 'disagreements')}</b>
  </div>
  <div class="bar">
    <button id="copy" class="p" onclick="copyDecisions()" disabled>Copy my decisions</button>
    <span id="count" class="count">0 of {len(rows)} decided</span>
    <span class="note">Confirm = the flag stands. Keep = leave it for later.
      Edit = a correction is needed.</span>
  </div>
  <div id="items"></div>
  <details class="index"><summary>Index of all {len(rows)} items</summary>
  <table><thead><tr><th>#</th><th>Flag</th><th>Document</th><th>Path</th>
    <th>My recommendation</th></tr></thead><tbody>{summary}</tbody></table>
  </details>
</div>
<script>{js}</script>
</body></html>
"""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(doc)
    return out_path


def main(argv: list[str]) -> int:
    out = Path(argv[1]) if len(argv) > 1 else ROOT / "docs" / "REVIEW-AUDIT.html"
    rows = collect()
    if not rows:
        print("the review queue is empty — nothing to audit")
        return 0
    print(f"{len(rows)} items -> {build(rows, out)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
