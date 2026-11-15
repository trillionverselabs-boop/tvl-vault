#!/usr/bin/env python3
"""One-shot TVL ingest drop zone.

Serves a single page that accepts a whole folder (or many files) and writes
them, preserving relative paths, into /home/lisacore/work/tvl-ingest/.

Tailnet-only: exposed with `tailscale serve`, so only your own devices can
reach it. No authentication by design -- it is started and stopped per ingest.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

from fastapi import FastAPI, File, Form, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse

DEST = Path("/home/lisacore/work/tvl-ingest")
DEST.mkdir(parents=True, exist_ok=True)

app = FastAPI(title="TVL Ingest Drop Zone")

PAGE = """<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>TVL Ingest</title>
<style>
  :root { color-scheme: dark; }
  * { box-sizing: border-box; }
  body { margin: 0; font: 16px/1.5 system-ui, -apple-system, sans-serif;
         background: #0d1117; color: #e6edf3; display: flex;
         align-items: center; justify-content: center; min-height: 100vh; padding: 24px; }
  .card { width: 100%; max-width: 720px; background: #161b22;
          border: 1px solid #30363d; border-radius: 14px; padding: 32px; }
  h1 { margin: 0 0 6px; font-size: 22px; }
  p.sub { margin: 0 0 24px; color: #8b949e; font-size: 14px; }
  #drop { border: 2px dashed #30363d; border-radius: 12px; padding: 44px 20px;
          text-align: center; cursor: pointer; transition: .15s; }
  #drop.over { border-color: #2ce8a2; background: rgba(44,232,162,.06); }
  #drop b { color: #2ce8a2; }
  .row { margin-top: 18px; display: flex; gap: 10px; align-items: center; flex-wrap: wrap; }
  button { background: #2ce8a2; color: #04120c; border: 0; border-radius: 8px;
           padding: 11px 20px; font: inherit; font-weight: 600; cursor: pointer; }
  button:disabled { opacity: .45; cursor: default; }
  label.ghost { background: transparent; color: #e6edf3; border: 1px solid #30363d; }
  #log { margin-top: 22px; font: 13px/1.6 ui-monospace, monospace;
         color: #8b949e; white-space: pre-wrap; max-height: 260px; overflow: auto; }
  .ok { color: #2ce8a2; }
  .bad { color: #f85149; }
  .hidden { display: none; }
</style></head><body>
<div class="card">
  <h1>TVL Ingest</h1>
  <p class="sub">Pick the folder, or drop it here. Everything goes straight into the vault queue on lisacore.</p>

  <div id="drop">
    <div><b>Drop a folder here</b></div>
    <div style="color:#8b949e;font-size:14px;margin-top:6px">or click to choose one</div>
    <input id="folder" type="file" webkitdirectory class="hidden">
  </div>

  <div class="row">
    <button id="send" disabled>Send files</button>
    <label class="ghost"><button type="button" class="ghost" onclick="document.getElementById('files').click()">Add individual files</button>
      <input id="files" type="file" multiple class="hidden"></label>
    <span id="count" style="color:#8b949e;font-size:14px"></span>
  </div>

  <div id="log"></div>
</div>

<script>
let pending = [];
const log = document.getElementById('log');
function say(t, cls) { const d = document.createElement('div'); if (cls) d.className = cls; d.textContent = t; log.appendChild(d); }
function scan(list) {
  const out = [];
  for (const f of list) {
    // webkitRelativePath carries "folder/sub/file.pdf"; fall back to name.
    const rel = f.webkitRelativePath || f.name;
    if (!rel) continue;
    if (/\\.\\./.test(rel)) { say('skipped unsafe path: ' + rel, 'bad'); continue; }
    if (rel.split('/').some(p => p.startsWith('.') && p.length > 1)) continue; // skip .git etc
    out.push({ file: f, rel });
  }
  return out;
}
function add(list) {
  pending = pending.concat(scan(list));
  document.getElementById('count').textContent = pending.length + ' file(s) ready';
  document.getElementById('send').disabled = pending.length === 0;
}
const drop = document.getElementById('drop');
const fi = document.getElementById('folder');
drop.onclick = () => fi.click();
fi.onchange = e => add(e.target.files);
document.getElementById('files').onchange = e => add(e.target.files);
['dragenter','dragover'].forEach(n => drop.addEventListener(n, e => { e.preventDefault(); drop.classList.add('over'); }));
['dragleave','drop'].forEach(n => drop.addEventListener(n, e => { e.preventDefault(); drop.classList.remove('over'); }));
drop.addEventListener('drop', e => {
  if (e.dataTransfer.items) {
    const items = [...e.dataTransfer.items].filter(i => i.kind === 'file').map(i => i.webkitGetAsEntry()).filter(Boolean);
    (async () => {
      const files = [];
      async function walk(entry, prefix) {
        if (entry.isFile) { const f = await new Promise(r => entry.file(r)); files.push(f); }
        else if (entry.isDirectory) {
          const r = entry.createReader();
          for (;;) { const batch = await new Promise(res => r.readEntries(res)); if (!batch.length) break;
                 for (const c of batch) await walk(c, prefix + entry.name + '/'); }
        }
      }
      for (const it of items) await walk(it, '');
      add(files);
    })();
  } else add(e.dataTransfer.files);
});
document.getElementById('send').onclick = async () => {
  if (!pending.length) return;
  const btn = document.getElementById('send'); btn.disabled = true;
  say('sending ' + pending.length + ' file(s)...');
  const fd = new FormData();
  for (const p of pending) fd.append('files', p.file, p.rel);
  try {
    const r = await fetch('/upload', { method: 'POST', body: fd });
    const j = await r.json();
    if (!r.ok) { say('FAILED: ' + (j.detail || r.status), 'bad'); btn.disabled = false; return; }
    say('done: ' + j.saved + ' saved, ' + j.bytes + ' bytes', 'ok');
    if (j.skipped.length) say('skipped: ' + j.skipped.join(', '), 'bad');
    pending = []; document.getElementById('count').textContent = '';
  } catch (err) { say('ERROR: ' + err, 'bad'); btn.disabled = false; }
};
</script></body></html>"""


@app.get("/", response_class=HTMLResponse)
def index() -> str:
    return PAGE


@app.get("/healthz")
def healthz() -> dict:
    return {"ok": True, "dest": str(DEST)}


@app.post("/upload")
async def upload(files: list[UploadFile] = File(...)) -> JSONResponse:
    saved = 0
    total = 0
    skipped: list[str] = []
    for up in files:
        rel = (up.filename or "").replace("\\", "/").lstrip("/")
        if not rel or ".." in rel.split("/"):
            skipped.append(up.filename or "<unnamed>")
            continue
        target = (DEST / rel).resolve()
        try:
            target.relative_to(DEST.resolve())
        except ValueError:
            skipped.append(rel)
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        data = await up.read()
        target.write_bytes(data)
        saved += 1
        total += len(data)
        print(f"  {rel}  {len(data)} bytes", flush=True)
    return JSONResponse({"saved": saved, "bytes": total, "skipped": skipped})


if __name__ == "__main__":
    import uvicorn

    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8787
    host = sys.argv[2] if len(sys.argv) > 2 else "127.0.0.1"
    print(f"TVL ingest drop zone on {host}:{port} -> {DEST}", flush=True)
    uvicorn.run(app, host=host, port=port, log_level="warning")
