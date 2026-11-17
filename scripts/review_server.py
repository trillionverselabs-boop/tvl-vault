#!/usr/bin/env python3
"""A localhost review console for The Vault queue.

The desktop half of The Vault loads through the app's plugin shell, which on this
machine is not picking the folder up. This is the same review, served as a page:
every queued item with Keep / Mark current / Correct, writing the decision
through `vault.review.write_correction` — the exact call the desktop makes.

    ./scripts/review_server.py         # http://127.0.0.1:8790
"""

from __future__ import annotations

import json
import sqlite3
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from vault import paths, review  # noqa: E402

DB = paths.vault_db_path()
PORT = 8790

PAGE = """<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8"><title>The Vault — review</title>
<style>
  :root { color-scheme: dark; }
  body { margin: 0; background: #05070d; color: #e8edf5;
         font: 14px/1.5 system-ui, -apple-system, "Segoe UI", sans-serif; }
  header { padding: 18px 22px; border-bottom: 1px solid rgba(255,255,255,.07);
           display: flex; align-items: baseline; gap: 14px; flex-wrap: wrap; }
  h1 { margin: 0; font-size: 18px; letter-spacing: -.01em; }
  .sub { color: #93a3b8; font-size: 12px; }
  .kpis { margin-left: auto; display: flex; gap: 10px; }
  .kpi { background: #0a0f18; border: 1px solid rgba(255,255,255,.07); border-radius: 10px;
         padding: 6px 12px; }
  .kpi b { font-size: 17px; }
  .kpi span { display: block; color: #93a3b8; font-size: 10px; text-transform: uppercase;
              letter-spacing: .06em; }
  .wrap { padding: 18px 22px 60px; }
  .group { margin-bottom: 26px; }
  .group h2 { font-size: 12px; text-transform: uppercase; letter-spacing: .08em;
              color: #93a3b8; margin: 0 0 10px; }
  .card { background: #0a0f18; border: 1px solid rgba(255,255,255,.07); border-radius: 12px;
          padding: 12px 14px; margin-bottom: 8px; display: flex; gap: 14px;
          align-items: flex-start; }
  .card.done { opacity: .35; }
  .main { flex: 1; min-width: 0; }
  .title { font-weight: 600; }
  .path { color: #93a3b8; font-size: 12px; word-break: break-all; }
  .reason { color: #a3b0c4; font-size: 12.5px; margin-top: 4px; }
  .badge { font-size: 10px; text-transform: uppercase; letter-spacing: .06em;
           border-radius: 999px; padding: 3px 8px; margin-top: 6px; display: inline-block; }
  .b-duplicate { background: rgba(245,158,11,.16); color: #f59e0b; }
  .b-unclear { background: rgba(167,139,250,.16); color: #a78bfa; }
  .b-outdated { background: rgba(100,116,139,.2); color: #94a3b8; }
  .b-conflict { background: rgba(248,113,113,.16); color: #f87171; }
  .actions { display: flex; gap: 6px; flex-shrink: 0; }
  button { background: #0d1420; color: #e8edf5; border: 1px solid rgba(255,255,255,.14);
           border-radius: 8px; padding: 7px 11px; font: 500 12px system-ui, sans-serif;
           cursor: pointer; }
  button:hover { border-color: #f59e0b; }
  .empty { color: #93a3b8; padding: 30px 0; }
</style></head><body>
<header>
  <div>
    <h1>The Vault — review</h1>
    <div class="sub">Decide each item. Nothing here edits a source file.</div>
  </div>
  <div class="kpis" id="kpis"></div>
</header>
<div class="wrap" id="list"><div class="empty">Loading…</div></div>
<script>
async function load() {
  const r = await fetch('/queue');
  const data = await r.json();
  document.getElementById('kpis').innerHTML =
    `<div class="kpi"><b>${data.total}</b><span>to review</span></div>` +
    `<div class="kpi"><b>${data.done}</b><span>decided</span></div>`;
  const list = document.getElementById('list');
  if (!data.items.length) {
    list.innerHTML = '<div class="empty">Nothing left. The queue is clear.</div>';
    return;
  }
  const groups = {};
  for (const it of data.items) (groups[it.flag] = groups[it.flag] || []).push(it);
  const label = { duplicate: 'Duplicate — a copy exists', unclear: 'Unclear — no readable sections',
                  outdated: 'Outdated — superseded', conflict: 'Needs review — disagreement' };
  list.innerHTML = Object.entries(groups).map(([flag, items]) =>
    `<div class="group"><h2>${label[flag] || flag} · ${items.length}</h2>` +
    items.map(it => `
      <div class="card" id="card-${it.doc_id}">
        <div class="main">
          <div class="title">${escapeHtml(it.title || '(untitled)')}</div>
          <div class="path">${escapeHtml(it.path)}</div>
          <div class="reason">${escapeHtml(it.reason || '')}</div>
          <span class="badge b-${flag}">${flag}</span>
        </div>
        <div class="actions">
          <button data-act="confirm">Confirm ${flag}</button>
          <button data-act="keep">Keep</button>
          <button data-act="edit">Edit</button>
        </div>
      </div>`).join('') + '</div>').join('');
  list.querySelectorAll('button').forEach(btn => btn.onclick = () => {
    const card = btn.closest('.card');
    const doc_id = card.id.slice(5);
    const flag = card.querySelector('.badge').textContent;
    const note = btn.dataset.act === 'confirm' ? 'Reviewed and confirmed.'
      : btn.dataset.act === 'edit' ? (prompt('What is wrong with it?') || '') : '';
    fetch('/decision', { method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ doc_id, flag, action: btn.dataset.act, note }) })
      .then(r => r.json()).then(() => load());
  });
}
function escapeHtml(s) { const d = document.createElement('div'); d.textContent = s; return d.innerHTML; }
load();
</script></body></html>
"""


def _queue() -> dict:
    db = sqlite3.connect(DB)
    db.row_factory = sqlite3.Row
    items = review.queue(db)
    done = len(review.corrections(db))
    db.close()
    return {"total": len(items), "done": done, "items": items}


class Handler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass

    def _send(self, body: str, ctype: str, code: int = 200):
        raw = body.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def do_GET(self):
        if self.path.startswith("/queue"):
            self._send(json.dumps(_queue()), "application/json")
        else:
            self._send(PAGE, "text/html; charset=utf-8")

    def do_POST(self):
        if self.path != "/decision":
            self._send('{"ok":false,"error":"bad path"}', "application/json", 404)
            return
        n = int(self.headers.get("Content-Length", 0))
        payload = json.loads(self.rfile.read(n) or b"{}")
        db = sqlite3.connect(DB)
        try:
            review.write_correction(db, payload["doc_id"], payload["flag"],
                                    payload["action"], payload.get("note", ""))
        finally:
            db.close()
        self._send('{"ok":true}', "application/json")


if __name__ == "__main__":
    print(f"The Vault review → http://127.0.0.1:{PORT}   (index: {DB})")
    ThreadingHTTPServer(("127.0.0.1", PORT), Handler).serve_forever()
