#!/usr/bin/env python3
"""Build a self-contained audit of everything on the review queue.

The desktop Review tab is the live surface, but a decision this consequential
also has to be readable as a document — and readable by a person, not by an
engineer. For every item this file answers, in plain words:

    what is this document?      (it has been a year; a filename is not an identity)
    what needs a decision?      (why it is even in this list)
    which sections differ?      (the unit of review is the section, not the file)
    what do I recommend, and why?

    ./scripts/review_audit.py                    # writes docs/REVIEW-AUDIT.html
    ./scripts/review_audit.py /path/to/out.html

Everything is rendered here in Python. No item depends on JavaScript: the Hermes
desktop previews HTML without running scripts, and a page that needs JS to show
its content reads as a blank document there. JS is only an enhancement (the
decision buttons and copy-to-clipboard). Items are delivered in batches of ten.
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
BATCH = 10
PAIR_LIMIT = 6

CSS = """
  *{box-sizing:border-box}
  body{margin:0;background:#f6f7f9;color:#14181f;
       font:15px/1.55 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Arial,sans-serif}
  .wrap{max-width:1120px;margin:0 auto;padding:34px 28px 90px}
  h1{font-size:27px;margin:0 0 6px;letter-spacing:-.02em}
  .sub{color:#5b6675;margin:0 0 18px}
  .howto{background:#fff;border:1px solid #dfe3e8;border-radius:10px;padding:14px 18px;
         margin:0 0 20px;font-size:14px;color:#37414f}
  .howto b{color:#14181f}
  .howto ol{margin:6px 0 0;padding-left:20px}
  .howto li{margin:3px 0}
  .meta{background:#fff;border:1px solid #dfe3e8;border-radius:10px;padding:13px 18px;
        margin:0 0 14px;color:#37414f;font-size:14px}
  .meta b{color:#14181f}
  /* the filter is pure CSS, so it works in a viewer that runs no scripts */
  .fl{position:absolute;opacity:0;pointer-events:none}
  .filters{display:flex;gap:8px;flex-wrap:wrap;align-items:center;margin:0 0 18px}
  .filters label{font-size:13px;padding:7px 14px;border-radius:20px;border:1px solid #c8d0da;
                 background:#fff;color:#2a3340;cursor:pointer}
  .filters label:hover{border-color:#8a93a0}
  #fl-all:checked ~ .filters label[for=fl-all],
  #fl-dup:checked ~ .filters label[for=fl-dup],
  #fl-unc:checked ~ .filters label[for=fl-unc],
  #fl-out:checked ~ .filters label[for=fl-out],
  #fl-con:checked ~ .filters label[for=fl-con]{background:#14181f;border-color:#14181f;color:#fff}
  #fl-dup:checked ~ .items .batch:not(:has(.flag-duplicate)){display:none}
  #fl-unc:checked ~ .items .batch:not(:has(.flag-unclear)){display:none}
  #fl-out:checked ~ .items .batch:not(:has(.flag-outdated)){display:none}
  #fl-con:checked ~ .items .batch:not(:has(.flag-conflict)){display:none}
  #fl-dup:checked ~ .items .item:not(.flag-duplicate),
  #fl-unc:checked ~ .items .item:not(.flag-unclear),
  #fl-out:checked ~ .items .item:not(.flag-outdated),
  #fl-con:checked ~ .items .item:not(.flag-conflict){display:none}
  #fl-dup:checked ~ .index tbody tr:not(.flag-duplicate),
  #fl-unc:checked ~ .index tbody tr:not(.flag-unclear),
  #fl-out:checked ~ .index tbody tr:not(.flag-outdated),
  #fl-con:checked ~ .index tbody tr:not(.flag-conflict){display:none}
  .batch{margin:26px 0 12px;font-size:15px;font-weight:600;letter-spacing:-.01em}
  .batch span{color:#6a7482;font-weight:400;font-size:13px}
  details.item{background:#fff;border:1px solid #dfe3e8;border-radius:10px;
               margin:0 0 12px;overflow:hidden}
  details.item>summary{cursor:pointer;padding:12px 16px;list-style:none;display:flex;
                       gap:10px;align-items:baseline;flex-wrap:wrap}
  details.item>summary::-webkit-details-marker{display:none}
  details.item>summary:hover{background:#fafbfc}
  summary .n{color:#8a93a0;font-variant-numeric:tabular-nums}
  summary .t{font-weight:600;font-size:15px}
  summary .p{color:#6a7482;font-size:12.5px;font-family:ui-monospace,Consolas,monospace}
  summary .rec{margin-left:auto;font-size:12px;color:#2d4a9a;background:#eef3fe;
               padding:2px 9px;border-radius:20px;white-space:nowrap}
  .flag{display:inline-block;padding:2px 8px;border-radius:20px;font-size:11.5px;
        font-weight:600;white-space:nowrap}
  .f-duplicate{background:#fff2d6;color:#8a5a00}
  .f-unclear{background:#e8eefc;color:#2d4a9a}
  .f-outdated{background:#eceff2;color:#4a5563}
  .f-conflict{background:#fde6e6;color:#a33}
  .body{padding:0 16px 16px;border-top:1px solid #eceff2}
  .body h3{margin:16px 0 6px;font-size:12px;letter-spacing:.09em;text-transform:uppercase;
           color:#6a7482}
  .body p{margin:0 0 8px;font-size:14px;color:#37414f}
  .gist{background:#fafbfc;border-left:3px solid #dfe3e8;padding:9px 12px;
        font-size:13.5px;color:#37414f;font-style:italic}
  .heads{font-size:13px;color:#5b6675;margin-bottom:4px}
  .heads b{color:#37414f;font-weight:600}
  .files{display:grid;gap:7px;margin:8px 0 4px}
  .files>div{font-size:13.5px;padding:9px 12px;border-radius:8px;border:1px solid #eceff2}
  .files .me{background:#eef7ff;border-color:#cfe3f7}
  .files .other{background:#fafbfc}
  .files b{display:block;font-size:11px;letter-spacing:.08em;text-transform:uppercase;
           color:#6a7482;margin-bottom:2px}
  .files span{font-family:ui-monospace,Consolas,monospace;font-size:12.5px;
              word-break:break-all}
  .compare{margin:8px 0 4px;border:1px solid #eceff2;border-radius:8px;overflow:hidden}
  .cleg{display:grid;grid-template-columns:1fr 1fr;font-size:11px;letter-spacing:.07em;
        text-transform:uppercase;color:#6a7482;background:#fafbfc}
  .cleg span{padding:7px 11px}
  .cleg span+span{border-left:1px solid #eceff2}
  .crow{display:grid;grid-template-columns:1fr 1fr;border-top:1px solid #eceff2}
  .crow .ct{grid-column:1/-1;font-size:12.5px;font-weight:600;padding:8px 11px 0;color:#37414f}
  .crow .cc{font-size:12.5px;line-height:1.5;color:#37414f;padding:3px 11px 9px;
            white-space:pre-wrap;word-break:break-word;min-width:0}
  .crow .cc+.cc{border-left:1px solid #eceff2}
  .crow.changed{background:#fff6e5}
  .crow.changed .ct::after{content:" · differs";color:#a35c00;font-weight:600;
                           text-transform:none;letter-spacing:0}
  .crow.only,.crow.onlyb{background:#fdf2f2}
  .crow.only .ct::after{content:" · only in this file";color:#a33;font-weight:600;
                        text-transform:none;letter-spacing:0}
  .crow.onlyb .ct::after{content:" · only in the other file";color:#a33;font-weight:600;
                         text-transform:none;letter-spacing:0}
  .legend{font-size:12.5px;color:#4a5563;margin:8px 0 0}
  .legend .hl{padding:1px 7px;border-radius:4px;font-size:11px;font-weight:600;
              background:#ffe3b3;color:#8a5a00}
  .recbox{margin:12px 0 0;padding:11px 13px;background:#fff8e8;border:1px solid #f0e0b4;
          border-radius:8px;font-size:13.5px}
  .recbox b{text-transform:uppercase;font-size:10.5px;letter-spacing:.09em;color:#8a5a00;
            display:block;margin-bottom:3px}
  .preview{margin:8px 0 0;padding:11px 13px;background:#0f1420;color:#c9d3e0;border-radius:8px;
           font:12.5px/1.55 ui-monospace,Consolas,Menlo,monospace;white-space:pre-wrap;
           word-break:break-word;max-height:340px;overflow:auto}
  .acts{display:flex;gap:8px;margin-top:14px;flex-wrap:wrap;align-items:center}
  button{font:inherit;font-size:13px;padding:8px 15px;border-radius:7px;cursor:pointer;
         border:1px solid #c8d0da;background:#fff;color:#2a3340}
  button:hover{border-color:#8a93a0}
  button.p{background:#14181f;border-color:#14181f;color:#fff}
  button[aria-pressed="true"]{background:#14181f;border-color:#14181f;color:#fff}
  .note{font-size:12px;color:#6a7482}
  .bar{position:sticky;top:0;background:#f6f7f9;padding:10px 0 12px;margin-bottom:12px;
       border-bottom:1px solid #dfe3e8;display:flex;gap:10px;align-items:center;flex-wrap:wrap}
  .bar .count{font-size:13px;color:#37414f}
  .index{margin-top:26px}
  .index table{border:none;border-radius:0 0 10px 10px}
  table{width:100%;border-collapse:collapse;background:#fff;font-size:13.5px}
  th,td{text-align:left;padding:8px 11px;border-bottom:1px solid #eceff2;vertical-align:top}
  th{background:#fafbfc;font-size:11px;letter-spacing:.08em;text-transform:uppercase;
     color:#6a7482;font-weight:600}
  code{font:12.5px ui-monospace,Consolas,Menlo,monospace;color:#37414f;word-break:break-all}
  .plainnote{margin:0 0 18px;padding:11px 14px;background:#fff8e8;border:1px solid #f0e0b4;
             border-radius:8px;font-size:13.5px;color:#6b4c00}
  @media print{button,.bar,.filters,.plainnote{display:none}
               details.item{break-inside:avoid}
               .compare{grid-template-columns:1fr}}
"""

# JS is an enhancement only: every word of content is already in the HTML.
JS = r"""
const ITEMS = __ITEMS__;
ITEMS.forEach(i => { i.decision = null; i.note = ''; });

function decide(n, action, note){
  const it = ITEMS.find(i => i.n === n);
  if (!it) return;
  if (it.decision === action) { it.decision = null; it.note = ''; }
  else { it.decision = action; it.note = note || ''; }
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
      pill.textContent = it.rec_label;
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

render();
"""


def e(text) -> str:
    return html.escape("" if text is None else str(text))


def primary_action(r: dict):
    """(action, label, note) for the main button on this item."""
    if r["flag"] == "duplicate":
        return ("confirm", "Keep " + r["short"], "keep " + r["path"])
    rec = r["rec"]
    if rec["action"] == "edit":
        return ("edit", "Not knowledge", "not knowledge — video build output, not a document")
    if rec["action"] == "confirm":
        return ("confirm", "Confirm", "Reviewed and confirmed.")
    return ("keep", "Keep it", "keep for now")


def render_about(r: dict) -> str:
    a = r["about"]
    bits = [a["kind_plain"], f'{a["sections"]} sections' if a["sections"] else "no sections read"]
    if a["words"]:
        bits.append(f'{a["words"]:,} words')
    if a["size"]:
        bits.append(f'{a["size"]:,} bytes')
    out = ['<h3>What this document is</h3>', '<p>' + e(" · ".join(bits)) + "</p>"]
    if a["headings"]:
        out.append('<p class="heads">It covers: ' + " · ".join(
            f"<b>{e(h)}</b>" for h in a["headings"][:6]) + "</p>")
    if a["gist"]:
        out.append('<p class="gist">“' + e(a["gist"]) + "…”</p>")
    return "".join(out)


def render_compare(r: dict) -> str:
    """Section by section, with the differing ones highlighted."""
    d = r.get("diff")
    if not d:
        return ""
    other = (r.get("copies") or [None])[0]
    name_b = other["name"] if other else "the other file"

    rows, shown = [], 0
    for p in d["pairs"]:
        if shown >= PAIR_LIMIT:
            break
        shown += 1
        cls = "changed" if p["status"] == "changed" else ""
        rows.append(
            f'<div class="crow {cls}"><div class="ct">{e(p["title"]) or "—"}</div>'
            f'<div class="cc">{e(p["a"]) or "<i>empty</i>"}</div>'
            f'<div class="cc">{e(p["b"]) or "<i>empty</i>"}</div></div>')
    for s in d["only_a"][:PAIR_LIMIT]:
        rows.append(
            f'<div class="crow only"><div class="ct">{e(s["title"]) or "—"}</div>'
            f'<div class="cc">{e(s["body"])}</div><div class="cc"></div></div>')
    for s in d["only_b"][:PAIR_LIMIT]:
        rows.append(
            f'<div class="crow onlyb"><div class="ct">{e(s["title"]) or "—"}</div>'
            f'<div class="cc"></div><div class="cc">{e(s["body"])}</div></div>')

    more = (len(d["pairs"]) + len(d["only_a"]) + len(d["only_b"])) - shown
    if more > 0:
        rows.append(f'<div class="crow"><div class="ct">…and {more} more section'
                    f'{"s" if more != 1 else ""} that are identical.</div></div>')

    if d["identical"]:
        verdict = ("Every section is word-for-word the same. Nothing differs — the "
                   "decision is only which file to keep.")
    else:
        verdict = (f'{d["changed"]} section{"s" if d["changed"] != 1 else ""} differ'
                   + (f', {len(d["only_a"])} only in this file' if d["only_a"] else "")
                   + (f', {len(d["only_b"])} only in the other' if d["only_b"] else "")
                   + ".")

    return ('<h3>Compare them, section by section</h3>'
            '<div class="compare">'
            '<div class="cleg"><span>This file: ' + e(r["short"]) + "</span>"
            "<span>The other file: " + e(name_b) + "</span></div>"
            + "".join(rows) + "</div>"
            '<p class="legend"><span class="hl">differs</span> &nbsp;Highlighted rows are '
            "where the two files disagree. " + e(verdict) + "</p>")


def render_item(r: dict) -> str:
    label = FLAG_LABEL.get(r["flag"], r["flag"])
    rec = r["rec"]
    action, btn_label, note = primary_action(r)

    if r["flag"] == "duplicate":
        files = ('<div class="files">'
                 f'<div class="me"><b>This file</b><span>{e(r["path"])}</span></div>'
                 + "".join(f'<div class="other"><b>The other file</b><span>{e(c["path"])}</span></div>'
                           for c in r["copies"]) + "</div>")
        what = '<h3>What needs a decision</h3><p>' + e(r["plain"] or r["reason"]) + "</p>" + files
    else:
        what = '<h3>What needs a decision</h3><p>' + e(r["plain"] or r["reason"]) + "</p>"
        if not r["sections"] and r["excerpt"]:
            what += '<h3>What the file actually contains</h3><pre class="preview">' + e(r["excerpt"]) + "</pre>"

    buttons = [f'<button class="p" data-act="{e(action)}" '
               f"onclick=\"decide({r['n']},'{e(action)}','{e(note)}')\">{e(btn_label)}</button>"]
    if r["flag"] == "duplicate":
        for c in r["copies"]:
            buttons.append(
                f"<button data-act=\"confirm\" "
                f"onclick=\"decide({r['n']},'confirm','keep {e(c['path'])}')\">"
                f"Keep {e(c['name'])}</button>")
    buttons.append("<button data-act=\"keep\" "
                   f"onclick=\"decide({r['n']},'keep','')\">Leave for later</button>")

    return f"""<details class="item flag-{e(r['flag'])}" data-n="{r['n']}">
  <summary><span class="n">#{r['n']}</span>
    <span class="flag {FLAG_CLASS.get(r['flag'], '')}">{e(label)}</span>
    <span class="t">{e(r['title'])}</span>
    <span class="rec">{e(rec['label'])}</span></summary>
  <div class="body">
    {render_about(r)}
    {what}
    {render_compare(r)}
    <div class="recbox"><b>My recommendation · {e(rec['action'])}</b>{e(rec['plain'])}</div>
    <div class="acts">{''.join(buttons)}</div>
  </div>
</details>"""


def collect() -> list[dict]:
    db = sqlite3.connect(paths.vault_db_path())
    db.row_factory = sqlite3.Row
    rows = []
    for f in review.queue(db):
        c = review.compare(db, f["doc_id"], f["flag"])
        d = c["document"]
        rec = c["recommendation"]
        probe = {"flag": f["flag"], "short": Path(f["path"]).name, "path": f["path"],
                 "copies": d["counterparts"], "rec": rec}
        _, label, _ = primary_action(probe)
        rows.append({
            "doc_id": f["doc_id"],
            "flag": f["flag"],
            "n": 0,
            "title": f["title"],
            "path": f["path"],
            "short": Path(f["path"]).name,
            "kind": f["kind"],
            "reason": c["reason"],
            "plain": c["plain"],
            "rec": {"action": rec["action"], "plain": rec["plain"],
                    "label": "MY RECOMMENDATION: " + label},
            "sections": d["sections"],
            "excerpt": d["excerpt"],
            "copies": d["counterparts"],
            "diff": d["diff"],
            "about": d["about"],
            "rec_action": rec["action"],
        })
    rows.sort(key=lambda r: (ORDER.get(r["flag"], 9), r["path"]))
    for n, r in enumerate(rows, start=1):
        r["n"] = n
    return rows


def build(rows: list[dict], out_path: Path) -> Path:
    # JS needs only the item numbers and the labels already shown; all visible
    # content is in the HTML. A corpus excerpt can itself contain `<script>` (the
    # unclear items are HTML scene files) — `\/` is a valid JSON escape for `/`,
    # so the data is unchanged and the tag cannot close this script.
    payload = json.dumps([{"n": r["n"], "flag": r["flag"], "rec_label": r["rec"]["label"]}
                          for r in rows]).replace("</", "<\\/")
    js = JS.replace("__ITEMS__", payload)

    counts = {f: sum(1 for r in rows if r["flag"] == f) for f in FLAG_LABEL}

    def cnt(n: int, one: str, many: str) -> str:
        return f"{n} {one if n == 1 else many}"

    batches = []
    for i in range(0, len(rows), BATCH):
        chunk = rows[i:i + BATCH]
        batches.append(
            f'<div class="batch">Items {chunk[0]["n"]}–{chunk[-1]["n"]} '
            f'<span>{len(chunk)} to review</span></div>'
            + "".join(render_item(r) for r in chunk))

    summary = "".join(
        "<tr class='flag-{}'><td class='n'>{}</td>"
        "<td><span class='flag {}'>{}</span></td>"
        "<td>{}</td><td><code>{}</code></td><td>{}</td></tr>".format(
            r["flag"], r["n"], FLAG_CLASS.get(r["flag"], ""),
            e(FLAG_LABEL.get(r["flag"], r["flag"])),
            e(r["title"]), e(r["path"]), e(r["rec_action"] or ""))
        for r in rows)

    doc = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<title>The Vault — review audit</title>
<style>{CSS}</style></head>
<body><div class="wrap">
  <h1>The Vault — review audit</h1>
  <p class="sub">Every document waiting on a decision, with its actual text and a
     recommendation. Ten at a time, in plain words.</p>
  <div class="howto"><b>How to read this</b>
    <ol>
      <li>Each item says <b>what the document is</b> — you last saw these a year ago,
          so a filename on its own tells you nothing.</li>
      <li><b>Compare</b> shows the two documents side by side, section by section.
          Highlighted rows are where they differ.</li>
      <li><b>My recommendation</b> says what I would do and why. Overrule it if you disagree.</li>
      <li>Pick a button. Or reply with your decisions in words — both are recorded the same way.</li>
    </ol>
  </div>
  <div class="meta">
    <b>{len(rows)} items</b> &nbsp;·&nbsp;
    <b>{cnt(counts['duplicate'], 'duplicate', 'duplicates')}</b> &nbsp;·&nbsp;
    <b>{cnt(counts['unclear'], 'unclear', 'unclear')}</b> &nbsp;·&nbsp;
    <b>{cnt(counts['outdated'], 'outdated', 'outdated')}</b> &nbsp;·&nbsp;
    <b>{cnt(counts['conflict'], 'disagreement', 'disagreements')}</b>
  </div>
  <input class="fl" type="radio" name="filter" id="fl-all" checked>
  <input class="fl" type="radio" name="filter" id="fl-dup">
  <input class="fl" type="radio" name="filter" id="fl-unc">
  <input class="fl" type="radio" name="filter" id="fl-out">
  <input class="fl" type="radio" name="filter" id="fl-con">
  <div class="bar">
    <button id="copy" class="p" onclick="copyDecisions()" disabled>Copy my decisions</button>
    <span id="count" class="count">0 of {len(rows)} decided</span>
    <span class="note">Confirm = the flag stands. Keep = leave it for later.
      Edit = a correction is needed.</span>
  </div>
  <div class="filters">
    <label for="fl-all">All {len(rows)}</label>
    <label for="fl-dup">Duplicates {counts['duplicate']}</label>
    <label for="fl-unc">Unclear {counts['unclear']}</label>
    <label for="fl-out">Outdated {counts['outdated']}</label>
    <label for="fl-con">Disagreements {counts['conflict']}</label>
  </div>
  <div class="plainnote">If a button does nothing when you click it, this viewer does not
    run scripts — the audit above is still complete. Read it and reply with your
    decisions in words, for example <code>keep 1-10, not knowledge 11-49</code>.</div>
  <div class="items">
    {''.join(batches)}
  </div>
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
