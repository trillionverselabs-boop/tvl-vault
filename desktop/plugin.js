// tvl-vault — desktop half. Loads UNCOMPILED (no JSX): jsx()/jsxs() only.
// Imports are limited to @hermes/plugin-sdk, react, react/jsx-runtime.
//
// The look is the approved mockup (docs/mockup/vault-mockup.html, Task 0.5),
// copied verbatim: the same palette tokens, the same three-column shell, the
// same force layout. What changed is only the source of the data — the mockup's
// hardcoded `DATA` is now the `/graph` JSON, fetched with ctx.rest.
//
// The desktop lint (hermes_cli/plugin_validate_desktop.py) refuses eval, dynamic
// import, script injection and reaching into the app's own markup. Everything
// here stays inside the SDK surface: host.state, ctx.rest, ctx.register.
import { host, useValue, ROUTES_AREA, SIDEBAR_NAV_AREA } from '@hermes/plugin-sdk'
import { useState, useEffect, useRef } from 'react'
import { jsx, jsxs } from 'react/jsx-runtime'

const BUILD = '0.1.0 · ui1'    // bump on every UI change — how you know the app reloaded
const NAME = 'The Vault'

// ── the approved palette. Exact values; do not substitute. ────────────────
const C = {
  canvas: '#05070d',
  panel: '#0a0f18',
  panel2: '#0d1420',
  border: 'rgba(255,255,255,.07)',
  border2: 'rgba(255,255,255,.14)',
  text: '#e8edf5',
  muted: '#a3b0c4',
  micro: '#93a3b8',
  sel: '#f59e0b',
  doctrine: '#22d3ee',
  notes: '#a78bfa',
  papers: '#34d399',
  images: '#fbbf24',
  conflict: '#f87171',
  outdated: '#94a3b8',
  duplicate: '#64748b',
  current: '#4ade80',
  mono: 'ui-monospace,"Cascadia Code","SF Mono",Consolas,"Liberation Mono",Menlo,monospace',
  sans: '"Segoe UI",-apple-system,BlinkMacSystemFont,Roboto,"Helvetica Neue",Arial,sans-serif',
}

const KIND_LABEL = { doctrine: 'Doctrine', notes: 'Notes', papers: 'Papers', images: 'Images' }
const KIND_ORDER = ['doctrine', 'notes', 'papers', 'images']
const FLAG = {
  current: { c: C.current, label: 'Current' },
  outdated: { c: C.outdated, label: 'Outdated' },
  duplicate: { c: C.duplicate, label: 'Duplicate' },
  conflict: { c: C.conflict, label: 'Disagrees' },
  unclear: { c: C.text, label: 'Unclear' },
}
const FLAG_ORDER = ['conflict', 'outdated', 'duplicate', 'unclear', 'current']

// The approved mockup's own style block, verbatim. In the plugin it is injected
// once into the document head rather than inlined into every element, so the
// page keeps the same cascade the mockup was judged on.
const CSS = `
  .vz-root{--vz-canvas:${C.canvas};--vz-panel:${C.panel};--vz-panel2:${C.panel2};
    --vz-border:${C.border};--vz-border2:${C.border2};--vz-text:${C.text};
    --vz-muted:${C.muted};--vz-micro:${C.micro};--vz-sel:${C.sel};
    background:var(--vz-canvas);color:var(--vz-text);font-family:${C.sans};
    font-size:14px;line-height:1.45;-webkit-font-smoothing:antialiased;height:100%;
    display:flex;flex-direction:column;min-height:0;overflow:hidden}
  .vz-root *{box-sizing:border-box}
  .vz-root ::-webkit-scrollbar{width:10px;height:10px}
  .vz-root ::-webkit-scrollbar-thumb{background:#1b2432;border-radius:6px;border:2px solid var(--vz-canvas)}
  .vz-root ::-webkit-scrollbar-track{background:transparent}
  .vz-micro{font-family:${C.mono};font-size:10px;letter-spacing:.14em;text-transform:uppercase;color:var(--vz-micro)}
  .vz-head{height:52px;display:flex;align-items:center;gap:16px;padding:0 18px;
    border-bottom:1px solid var(--vz-border);background:var(--vz-panel);flex:0 0 auto}
  .vz-brand{display:flex;align-items:baseline;gap:10px;min-width:0}
  .vz-brand h1{margin:0;font-family:${C.mono};font-size:15px;font-weight:600;letter-spacing:.16em;text-transform:uppercase}
  .vz-brand .tag{color:var(--vz-muted);font-size:13px;white-space:nowrap}
  .vz-head .spacer{flex:1}
  .vz-hstat{display:flex;flex-direction:column;align-items:flex-end;line-height:1.1}
  .vz-hstat b{font-family:${C.mono};font-size:16px;font-weight:600}
  .vz-hstat span{font-size:11px;color:var(--vz-muted)}
  .vz-shell{display:grid;grid-template-columns:264px minmax(0,1fr) 336px;flex:1;min-height:0}
  .vz-left{border-right:1px solid var(--vz-border);background:var(--vz-panel);padding:16px 14px;overflow-y:auto}
  .vz-block{margin-bottom:22px}
  .vz-block>.vz-micro{display:block;margin-bottom:9px}
  .vz-kind{display:flex;align-items:center;gap:9px;padding:5px 0;font-size:13.5px}
  .vz-dot{width:8px;height:8px;border-radius:50%;flex:0 0 auto}
  .vz-kind .n{margin-left:auto;font-family:${C.mono};font-size:12px;color:var(--vz-muted)}
  .vz-kind .t{overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
  .vz-chip{display:flex;align-items:center;gap:8px;width:100%;padding:7px 10px;margin-bottom:5px;
    border-radius:8px;border:1px solid var(--vz-border);background:transparent;color:var(--vz-text);
    font:inherit;font-size:13px;text-align:left;cursor:pointer;transition:border-color .12s,background .12s}
  .vz-chip:hover{border-color:var(--vz-border2);background:var(--vz-panel2)}
  .vz-chip[aria-pressed="true"]{border-color:var(--vz-sel);background:rgba(245,158,11,.09)}
  .vz-chip .n{margin-left:auto;font-family:${C.mono};font-size:12px;color:var(--vz-muted)}
  .vz-chip[aria-pressed="true"] .n{color:var(--vz-sel)}
  .vz-chip .sw{width:7px;height:7px;border-radius:50%}
  .vz-center{display:flex;flex-direction:column;min-width:0;background:var(--vz-canvas)}
  .vz-tabs{display:flex;gap:2px;padding:9px 16px 0;border-bottom:1px solid var(--vz-border);background:var(--vz-panel)}
  .vz-tab{padding:8px 14px;border:1px solid transparent;border-bottom:none;border-radius:8px 8px 0 0;
    background:transparent;color:var(--vz-muted);font:inherit;font-size:13px;cursor:pointer}
  .vz-tab:hover{color:var(--vz-text)}
  .vz-tab[aria-selected="true"]{background:var(--vz-canvas);color:var(--vz-text);border-color:var(--vz-border);position:relative;top:1px}
  .vz-kpis{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:1px;
    background:var(--vz-border);border-bottom:1px solid var(--vz-border)}
  .vz-kpi{background:var(--vz-panel);padding:11px 16px 12px}
  .vz-kpi b{display:block;font-family:${C.mono};font-size:22px;font-weight:600;line-height:1.15;
    letter-spacing:-.01em;font-variant-numeric:tabular-nums}
  .vz-kpi span{display:block;font-size:11.5px;color:var(--vz-muted);margin-top:2px}
  .vz-kpi.warn b{color:var(--vz-conflict)}
  .vz-pane{position:relative;flex:1;min-height:0;display:none}
  .vz-pane.on{display:block}
  .vz-graph{overflow:hidden}
  .vz-root svg{display:block;width:100%;height:100%;cursor:grab}
  .vz-root svg.dragging{cursor:grabbing}
  .vz-edge{stroke:rgba(255,255,255,.10);stroke-width:1}
  .vz-edge.depends{stroke:rgba(255,255,255,.20)}
  .vz-node{cursor:pointer}
  .vz-node circle.core{stroke:none}
  .vz-node circle.glow{opacity:.09}
  .vz-node text{font-family:${C.mono};font-size:10.5px;fill:${C.muted};
    paint-order:stroke;stroke:${C.canvas};stroke-width:3px;stroke-linejoin:round}
  .vz-node.sec text{opacity:0;transition:opacity .12s}
  .vz-node.sec:hover text{opacity:1}
  .vz-node.dim{opacity:.14}
  .vz-node.sel text{fill:var(--vz-text);font-size:12px;opacity:1}
  .vz-node.sel circle.ring{fill:none;stroke:var(--vz-sel);stroke-width:1.6}
  .vz-hint{position:absolute;left:14px;bottom:12px;display:flex;gap:8px;
    font-family:${C.mono};font-size:10.5px;letter-spacing:.06em;color:var(--vz-micro);pointer-events:none}
  .vz-hint span+span::before{content:"·";margin-right:8px;color:var(--vz-border2)}
  .vz-legend{position:absolute;right:14px;bottom:12px;display:flex;gap:12px;
    padding:7px 11px;border:1px solid var(--vz-border);border-radius:8px;background:rgba(10,15,24,.88)}
  .vz-legend i{display:flex;align-items:center;gap:6px;font-style:normal;font-size:11px;color:var(--vz-muted)}
  .vz-wall{overflow-y:auto;padding:18px}
  .vz-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(232px,1fr));gap:12px}
  .vz-card{border:1px solid var(--vz-border);border-radius:10px;background:var(--vz-panel);
    padding:13px 14px;cursor:pointer;transition:border-color .12s,transform .12s}
  .vz-card:hover{border-color:var(--vz-border2);transform:translateY(-1px)}
  .vz-card .k{font-family:${C.mono};font-size:10px;letter-spacing:.1em;text-transform:uppercase}
  .vz-card h3{margin:6px 0 5px;font-size:14px;font-weight:600;line-height:1.3}
  .vz-card p{margin:0;font-size:12.5px;color:var(--vz-muted)}
  .vz-card .badge{margin-top:10px}
  .vz-badge{display:inline-flex;align-items:center;gap:6px;font-family:${C.mono};font-size:10px;
    letter-spacing:.08em;text-transform:uppercase;padding:3px 8px;border-radius:20px;
    border:1px solid var(--vz-border2);color:var(--vz-muted)}
  .vz-badge::before{content:"";width:6px;height:6px;border-radius:50%;background:currentColor}
  .vz-badge.current{color:${C.current}}
  .vz-badge.outdated{color:${C.outdated}}
  .vz-badge.duplicate{color:#9aa8bb}
  .vz-badge.conflict{color:${C.conflict};border-color:rgba(248,113,113,.4)}
  .vz-badge.unclear{color:var(--vz-text);border-style:dashed}
  .vz-ask{overflow-y:auto;padding:22px}
  .vz-askwrap{max-width:760px;margin:0 auto}
  .vz-askwrap h2{margin:0 0 6px;font-size:19px;font-weight:600;letter-spacing:-.01em}
  .vz-askwrap .sub{margin:0 0 18px;color:var(--vz-muted);font-size:13.5px}
  .vz-qbox{display:flex;gap:9px}
  .vz-qbox input{flex:1;padding:11px 13px;border-radius:9px;border:1px solid var(--vz-border2);
    background:var(--vz-panel);color:var(--vz-text);font:inherit;font-size:14px}
  .vz-qbox input:focus{outline:none;border-color:var(--vz-sel)}
  .vz-btn{padding:11px 16px;border-radius:9px;border:1px solid var(--vz-border2);
    background:var(--vz-panel2);color:var(--vz-text);font:inherit;font-size:14px;cursor:pointer;white-space:nowrap}
  .vz-btn:hover{border-color:var(--vz-sel)}
  .vz-answer{margin-top:20px;padding:16px 18px;border:1px solid var(--vz-border);
    border-radius:10px;background:var(--vz-panel)}
  .vz-answer p{margin:0 0 12px;font-size:14.5px;line-height:1.6}
  .vz-answer sup{font-family:${C.mono};font-size:11px;color:var(--vz-sel)}
  .vz-cites{border-top:1px solid var(--vz-border);padding-top:12px;display:grid;gap:7px}
  .vz-cite{display:flex;gap:9px;font-size:12.5px;color:var(--vz-muted);align-items:baseline}
  .vz-cite .n{font-family:${C.mono};color:var(--vz-sel);font-size:11px;flex:0 0 auto}
  .vz-cite button{margin-left:auto;background:none;border:none;color:var(--vz-micro);font:inherit;
    font-size:11.5px;cursor:pointer;text-decoration:underline;text-underline-offset:2px;padding:0}
  .vz-cite button:hover{color:var(--vz-text)}
  .vz-note{margin-top:14px;font-size:12px;color:var(--vz-micro);display:flex;gap:8px;align-items:flex-start}
  .vz-review{overflow-y:auto;padding:18px}
  .vz-revlist{display:grid;gap:10px;max-width:900px}
  .vz-rev{border:1px solid var(--vz-border);border-radius:10px;background:var(--vz-panel);padding:13px 15px}
  .vz-rev.conflict{border-color:rgba(248,113,113,.32)}
  .vz-revtop{display:flex;align-items:center;gap:10px;margin-bottom:7px}
  .vz-revtop h3{margin:0;font-size:14px;font-weight:600;flex:1;min-width:0;
    overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
  .vz-rev .why{margin:0 0 4px;font-size:13px}
  .vz-rev .evid{margin:0 0 11px;font-size:12.5px;color:var(--vz-muted);
    padding-left:11px;border-left:2px solid var(--vz-border2)}
  .vz-rev .evid b{color:var(--vz-micro);font-weight:500;font-family:${C.mono};
    font-size:10.5px;letter-spacing:.08em;text-transform:uppercase;display:block;margin-bottom:2px}
  .vz-rev .acts{display:flex;gap:7px}
  .vz-act{padding:6px 12px;border-radius:7px;border:1px solid var(--vz-border2);
    background:transparent;color:var(--vz-muted);font:inherit;font-size:12.5px;cursor:pointer}
  .vz-act:hover{color:var(--vz-text);border-color:var(--vz-sel)}
  .vz-act.primary{background:var(--vz-sel);border-color:var(--vz-sel);color:#1a1205;font-weight:600}
  .vz-act.primary:hover{color:#1a1205;filter:brightness(1.06)}
  .vz-right{border-left:1px solid var(--vz-border);background:var(--vz-panel);padding:18px;overflow-y:auto}
  .vz-empty{height:100%;display:flex;flex-direction:column;align-items:center;justify-content:center;
    text-align:center;gap:8px;color:var(--vz-micro);padding:24px}
  .vz-empty .big{font-size:15px;color:var(--vz-muted)}
  .vz-empty .small{font-size:12.5px;max-width:230px;line-height:1.5}
  .vz-dhead .k{font-family:${C.mono};font-size:10px;letter-spacing:.12em;text-transform:uppercase}
  .vz-dhead h2{margin:7px 0 9px;font-size:17px;font-weight:600;line-height:1.28}
  .vz-dmeta{margin:14px 0;padding-top:13px;border-top:1px solid var(--vz-border);display:grid;gap:9px}
  .vz-dmeta div{display:flex;gap:9px;font-size:12.5px;align-items:baseline}
  .vz-dmeta dt{color:var(--vz-micro);font-family:${C.mono};font-size:10px;
    letter-spacing:.1em;text-transform:uppercase;flex:0 0 74px}
  .vz-dmeta dd{margin:0;color:var(--vz-muted);word-break:break-word}
  .vz-dsec{margin-top:16px;padding-top:14px;border-top:1px solid var(--vz-border)}
  .vz-dsec .vz-micro{display:block;margin-bottom:8px}
  .vz-dsec h4{margin:0 0 5px;font-size:13.5px;font-weight:600}
  .vz-dsec p{margin:0;font-size:13px;color:var(--vz-muted);line-height:1.6}
  .vz-open{margin-top:18px;width:100%;padding:11px;border-radius:9px;border:1px solid var(--vz-border2);
    background:var(--vz-panel2);color:var(--vz-text);font:inherit;font-size:13.5px;cursor:pointer}
  .vz-open:hover{border-color:var(--vz-sel)}
  .vz-tip{position:fixed;z-index:50;pointer-events:none;opacity:0;max-width:290px;padding:8px 11px;
    border-radius:8px;border:1px solid var(--vz-border2);background:rgba(13,20,32,.96);
    font-size:12px;color:var(--vz-text);transition:opacity .1s}
  .vz-tip .t{font-weight:600;margin-bottom:2px}
  .vz-tip .s{color:var(--vz-muted);font-size:11.5px}
  .vz-loading{padding:24px;color:var(--vz-muted);font-size:13px}
  @media (prefers-reduced-motion:reduce){.vz-root *{transition:none!important;animation:none!important}}
  @media (max-width:1180px){.vz-shell{grid-template-columns:220px minmax(0,1fr) 290px}}
`

// The approved force layout, verbatim from the mockup. Runs once, synchronously,
// on the documents-only view — 400 ticks over a few hundred nodes is a fraction
// of a frame budget and keeps the graph deterministic between reloads.
function simulate(nodes, edges, ticks) {
  const w = 1000, h = 700
  nodes.forEach((n, i) => {
    n.x = w / 2 + Math.cos(i * 2.399) * 200
    n.y = h / 2 + Math.sin(i * 2.399) * 170
    n.vx = 0; n.vy = 0
  })
  const byId = new Map(nodes.map(n => [n.id, n]))
  for (let t = 0; t < ticks; t++) {
    for (const n of nodes) for (const m of nodes) {
      if (n === m) continue
      const dx = n.x - m.x, dy = n.y - m.y
      const d2 = dx * dx + dy * dy || 0.01
      const f = 620 / d2
      n.vx += dx * f * 0.018; n.vy += dy * f * 0.018
    }
    for (const e of edges) {
      const a = byId.get(e.source), b = byId.get(e.target)
      if (!a || !b) continue
      const dx = b.x - a.x, dy = b.y - a.y
      const d = Math.sqrt(dx * dx + dy * dy) || 0.01
      const want = e.kind === 'contains' ? 78 : (e.kind === 'conflict' ? 210 : 165)
      const f = (d - want) * 0.014
      a.vx += dx / d * f; a.vy += dy / d * f
      b.vx -= dx / d * f; b.vy -= dy / d * f
    }
    for (const n of nodes) {
      n.vx += (w / 2 - n.x) * 0.0022
      n.vy += (h / 2 - n.y) * 0.0022
    }
    for (const n of nodes) {
      n.vx *= 0.82; n.vy *= 0.82
      n.x = Math.max(46, Math.min(w - 46, n.x + n.vx))
      n.y = Math.max(34, Math.min(h - 34, n.y + n.vy))
    }
  }
  return { w, h }
}

function short(s, n) {
  s = String(s == null ? '' : s)
  return s.length > (n || 34) ? s.slice(0, (n || 34) - 1) + '…' : s
}

function useVault(path, restRef) {
  const [data, setData] = useState(null)
  const [error, setError] = useState(null)
  useEffect(() => {
    let alive = true
    setData(null); setError(null)
    restRef.current(path)
      .then(d => { if (alive) setData(d) })
      .catch(e => { if (alive) setError(String(e)) })
    return () => { alive = false }
  }, [path])
  return { data, error }
}

function Badge({ flag }) {
  const f = FLAG[flag] || FLAG.current
  return jsx('span', { className: 'vz-badge ' + flag, children: f.label })
}

function Loading({ error }) {
  if (error) return jsx('div', { className: 'vz-loading', children: 'Could not reach the vault: ' + error })
  return jsx('div', { className: 'vz-loading', children: 'Loading…' })
}

/* ── the graph pane ─────────────────────────────────────────────────────── */
function GraphPane({ ctx, graph, showSections, flagFilter, onSelect, selectedId }) {
  const svgRef = useRef(null)
  const worldRef = useRef(null)
  const tipRef = useRef(null)
  const viewRef = useRef({ k: 1, tx: 0, ty: 0 })
  const dragRef = useRef(null)
  const [built, setBuilt] = useState(null)

  // Build the laid-out node set whenever the data or the section toggle changes.
  useEffect(() => {
    if (!graph) return
    const docs = graph.nodes.filter(n => n.kind === 'document')
    const secs = graph.nodes.filter(n => n.kind === 'section')
    const contains = graph.edges.filter(e => e.kind === 'contains')
    const others = graph.edges.filter(e => e.kind !== 'contains')
    const visibleSecs = showSections ? secs : []
    const nodes = docs.concat(visibleSecs)
    const edges = (showSections ? contains : []).concat(others)
    // degree drives the radius, exactly as the mockup
    const deg = new Map()
    for (const e of edges) {
      if (!e.source || !e.target) continue
      deg.set(e.source, (deg.get(e.source) || 0) + 1)
      deg.set(e.target, (deg.get(e.target) || 0) + 1)
    }
    nodes.forEach(n => { n.deg = deg.get(n.id) || 0 })
    simulate(nodes, edges, matchMedia('(prefers-reduced-motion: reduce)').matches ? 1 : 420)
    setBuilt({ nodes, edges, byId: new Map(nodes.map(n => [n.id, n])), w: 1000, h: 700 })
  }, [graph, showSections])

  // Draw. Plain DOM: this is the approved mockup's own rendering, unchanged.
  useEffect(() => {
    if (!built || !worldRef.current) return
    const world = worldRef.current
    world.textContent = ''
    const svg = svgRef.current
    const visible = n => showSections || n.kind === 'document'
    const dimmed = n => {
      if (flagFilter) return !(n.kind === 'document' && n.flag === flagFilter)
      return false
    }
    for (const e of built.edges) {
      if (e.kind === 'contains' && !showSections) continue
      const a = built.byId.get(e.source), b = built.byId.get(e.target)
      if (!visible(a) || !visible(b)) continue
      const ln = document.createElementNS('http://www.w3.org/2000/svg', 'line')
      ln.setAttribute('class', 'vz-edge ' + e.kind)
      ln.setAttribute('x1', a.x); ln.setAttribute('y1', a.y)
      ln.setAttribute('x2', b.x); ln.setAttribute('y2', b.y)
      world.appendChild(ln)
    }
    for (const n of built.nodes) {
      if (!visible(n)) continue
      const g = document.createElementNS('http://www.w3.org/2000/svg', 'g')
      g.setAttribute('class', 'vz-node' + (n.kind === 'section' ? ' sec' : '')
        + (dimmed(n) ? ' dim' : '') + (n.id === selectedId ? ' sel' : ''))
      g.setAttribute('transform', `translate(${n.x},${n.y})`)
      const r = n.kind === 'document' ? 5 + Math.min(8, n.deg) : 2.6 + Math.min(4, n.deg)
      const colour = n.kind === 'document'
        ? (C[n.group] || C.notes)
        : (C[(built.byId.get(n.group) || {}).group] || C.notes)
      if (n.kind === 'document') {
        const glow = document.createElementNS('http://www.w3.org/2000/svg', 'circle')
        glow.setAttribute('class', 'glow'); glow.setAttribute('r', r * 2.6); glow.setAttribute('fill', colour)
        g.appendChild(glow)
      }
      const core = document.createElementNS('http://www.w3.org/2000/svg', 'circle')
      core.setAttribute('class', 'core'); core.setAttribute('r', r); core.setAttribute('fill', colour)
      g.appendChild(core)
      if (n.id === selectedId) {
        const ring = document.createElementNS('http://www.w3.org/2000/svg', 'circle')
        ring.setAttribute('class', 'ring'); ring.setAttribute('r', r + 4)
        g.appendChild(ring)
      }
      const t = document.createElementNS('http://www.w3.org/2000/svg', 'text')
      const label = n.kind === 'document' ? short(n.label, 34) : short(n.label, 40)
      if (n.x > built.w * 0.60) {
        t.setAttribute('x', -(r + 6)); t.setAttribute('y', 3.5); t.setAttribute('text-anchor', 'end')
      } else {
        t.setAttribute('x', r + 6); t.setAttribute('y', 3.5)
      }
      t.textContent = label
      g.appendChild(t)
      g.addEventListener('click', ev => { ev.stopPropagation(); onSelect(n) })
      g.addEventListener('mousemove', ev => {
        const tip = tipRef.current
        if (!tip) return
        const doc = n.kind === 'document' ? n : built.byId.get(n.group)
        const f = FLAG[(doc && doc.flag) || 'current'] || FLAG.current
        tip.innerHTML = `<div class="t"></div><div class="s"></div>`
        tip.querySelector('.t').textContent = n.label
        tip.querySelector('.s').textContent = `${doc ? doc.label : ''} · ${f.label}`
        tip.style.opacity = 1
        tip.style.left = Math.min(innerWidth - 300, ev.clientX + 14) + 'px'
        tip.style.top = (ev.clientY + 14) + 'px'
      })
      g.addEventListener('mouseleave', () => { if (tipRef.current) tipRef.current.style.opacity = 0 })
      world.appendChild(g)
    }
    // fit the cluster into the canvas, as the mockup does
    const vis = built.nodes.filter(visible)
    const xs = vis.map(n => n.x), ys = vis.map(n => n.y)
    const minX = Math.min.apply(null, xs), maxX = Math.max.apply(null, xs)
    const minY = Math.min.apply(null, ys), maxY = Math.max.apply(null, ys)
    const pad = 66
    const bw = Math.max(1, maxX - minX) + pad * 2
    const bh = Math.max(1, maxY - minY) + pad * 2
    const k = Math.min(built.w / bw, built.h / bh, 1.5)
    viewRef.current = { k, tx: built.w / 2 - ((minX + maxX) / 2) * k, ty: built.h / 2 - ((minY + maxY) / 2) * k }
    world.setAttribute('transform', `translate(${viewRef.current.tx},${viewRef.current.ty}) scale(${viewRef.current.k})`)
  }, [built, showSections, flagFilter, selectedId, onSelect])

  // zoom / pan
  useEffect(() => {
    const svg = svgRef.current
    if (!svg) return
    const onWheel = e => {
      e.preventDefault()
      const r = svg.getBoundingClientRect()
      const mx = e.clientX - r.left, my = e.clientY - r.top
      const dk = e.deltaY < 0 ? 1.12 : 0.89
      const v = viewRef.current
      const nk = Math.max(0.4, Math.min(3, v.k * dk))
      v.tx = mx - (mx - v.tx) * (nk / v.k)
      v.ty = my - (my - v.ty) * (nk / v.k)
      v.k = nk
      if (worldRef.current) worldRef.current.setAttribute('transform', `translate(${v.tx},${v.ty}) scale(${v.k})`)
    }
    const onDown = e => {
      dragRef.current = { x: e.clientX, y: e.clientY, tx: viewRef.current.tx, ty: viewRef.current.ty }
      svg.classList.add('dragging')
    }
    const onMove = e => {
      const d = dragRef.current
      if (!d) return
      viewRef.current.tx = d.tx + (e.clientX - d.x)
      viewRef.current.ty = d.ty + (e.clientY - d.y)
      if (worldRef.current) worldRef.current.setAttribute('transform',
        `translate(${viewRef.current.tx},${viewRef.current.ty}) scale(${viewRef.current.k})`)
    }
    const onUp = () => { dragRef.current = null; svg.classList.remove('dragging') }
    svg.addEventListener('wheel', onWheel, { passive: false })
    svg.addEventListener('mousedown', onDown)
    window.addEventListener('mousemove', onMove)
    window.addEventListener('mouseup', onUp)
    return () => {
      svg.removeEventListener('wheel', onWheel)
      svg.removeEventListener('mousedown', onDown)
      window.removeEventListener('mousemove', onMove)
      window.removeEventListener('mouseup', onUp)
    }
  }, [built])

  return jsxs('div', {
    className: 'vz-pane on vz-graph',
    children: [
      jsxs('svg', {
        ref: svgRef, role: 'img', 'aria-label': 'Document relationship graph',
        children: [jsx('g', { ref: worldRef })],
      }),
      jsx('div', { className: 'vz-legend', children: KIND_ORDER.map(k => jsxs('i', {
        children: [jsx('span', { className: 'vz-dot', style: { background: C[k] } }), KIND_LABEL[k]],
      }, k)) }),
      jsx('div', { className: 'vz-hint', children: ['scroll to zoom', 'drag to move', 'click a dot to read it'] }),
      jsx('div', { ref: tipRef, className: 'vz-tip' }),
    ],
  })
}

/* ── the wall ───────────────────────────────────────────────────────────── */
function WallPane({ ctx, wall, onSelect }) {
  if (!wall) return jsx(Loading, {})
  const docs = wall.documents || []
  return jsxs('div', {
    className: 'vz-pane on vz-wall',
    children: [
      jsx('div', { className: 'vz-grid', children: docs.map(d => jsxs('div', {
        className: 'vz-card', onClick: () => onSelect(d),
        children: [
          jsx('div', { className: 'k', style: { color: C[d.kind] || C.notes }, children: KIND_LABEL[d.kind] || d.kind }),
          jsx('h3', { children: d.title }),
          jsx('div', { className: 'badge', children: jsx(Badge, { flag: d.flag }) }),
        ],
      }, d.doc_id)) }),
      wall.junk_count ? jsx('div', {
        className: 'vz-note', style: { maxWidth: 900 },
        children: `${wall.junk_count} test screenshots are indexed but kept out of this wall. They are build artifacts, not doctrine.`,
      }) : null,
    ],
  })
}

/* ── the review queue ───────────────────────────────────────────────────── */
// One decision per document, matching the approved mockup's three actions and
// the backend's `corrections` record:
//   confirm — the flag stands, the document is current after review
//   keep    — leave it on the queue for the next pass
//   edit    — a correction is needed; the note says what (the source is never
//             rewritten, rule 4)
function ReviewPane({ ctx, review, onSelect, onDecide, decisions, busy }) {
  if (!review) return jsx(Loading, {})
  const flags = review.flags || []
  const ACTION_LABEL = {
    conflict: 'Resolve conflict', outdated: 'Confirm outdated',
    duplicate: 'Confirm duplicate', unclear: 'Confirm unclear',
  }
  return jsx('div', {
    className: 'vz-pane on vz-review',
    children: jsx('div', {
      className: 'vz-revlist',
      children: flags.length ? flags.map((f, i) => {
        const done = decisions && decisions[f.doc_id]
        const isBusy = busy === f.doc_id
        return jsxs('div', {
          className: 'vz-rev ' + f.flag,
          children: [
            jsxs('div', {
              className: 'vz-revtop',
              children: [
                jsx('span', { className: 'vz-dot', style: { background: C[f.kind] || C.notes } }),
                jsx('h3', { children: f.title }),
                jsx(Badge, { flag: f.flag }),
              ],
            }),
            jsx('p', { className: 'why', children: f.reason }),
            jsx('p', { className: 'evid', children: f.evidence }),
            done ? jsx('p', {
              className: 'why',
              style: { color: C.current },
              children: 'Recorded: ' + done.label + (done.note ? ' — ' + done.note : ''),
            }) : null,
            jsxs('div', {
              className: 'acts',
              children: [
                jsx('button', {
                  className: 'vz-act primary', disabled: isBusy,
                  onClick: () => onDecide(f, ACTION_LABEL[f.flag] || 'Confirm', {
                    action: 'confirm', note: 'Reviewed and confirmed.',
                  }),
                  children: ACTION_LABEL[f.flag] || 'Confirm',
                }),
                jsx('button', {
                  className: 'vz-act', disabled: isBusy,
                  onClick: () => onDecide(f, 'Keep', { action: 'keep' }),
                  children: 'Keep',
                }),
                jsx('button', {
                  className: 'vz-act', disabled: isBusy,
                  onClick: () => onDecide(f, 'Edit', { action: 'edit' }),
                  children: 'Edit',
                }),
                jsx('button', {
                  className: 'vz-act', disabled: isBusy,
                  onClick: () => onSelect(f),
                  children: 'Read it',
                }),
              ],
            }),
          ],
        }, f.doc_id + i)
      }) : jsx('div', {
        className: 'vz-rev',
        children: jsx('p', { className: 'why', children: 'Nothing needs a decision. Every document is current.' }),
      }),
    }),
  })
}

/* ── the ask pane ────────────────────────────────────────────────────────── */
// The approved mockup's Ask pane: a question box, the answer, then the sources
// it came from. The answer is written by the session model from the retrieved
// sections only, and the citation list is what the model actually cited.
function AskPane({ ctx, restRef, onOpen }) {
  const [q, setQ] = useState('What did the doctrine say about how to chunk a document?')
  const [busy, setBusy] = useState(false)
  const [out, setOut] = useState(null)
  const [error, setError] = useState(null)

  async function ask() {
    const question = q.trim()
    if (!question || busy) return
    setBusy(true); setError(null); setOut(null)
    try {
      const res = await restRef.current('/ask', {
        method: 'POST',
        body: { question },
      })
      setOut(res)
      if (res && res.error) setError(res.error)
    } catch (e) {
      setError(String(e))
    } finally {
      setBusy(false)
    }
  }

  const cites = (out && out.citations) || []
  return jsxs('div', {
    className: 'vz-pane on vz-ask',
    children: jsxs('div', {
      className: 'vz-askwrap',
      children: [
        jsx('h2', { children: 'Ask the corpus' }),
        jsx('p', {
          className: 'sub',
          children: 'Plain question. The answer comes only from your documents, and every line says which one.',
        }),
        jsxs('div', {
          className: 'vz-qbox',
          children: [
            jsx('input', {
              type: 'text', value: q, 'aria-label': 'Question',
              onChange: e => setQ(e.target.value),
              onKeyDown: e => { if (e.key === 'Enter') ask() },
            }),
            jsx('button', { className: 'vz-btn', disabled: busy, onClick: ask,
                            children: busy ? 'Asking…' : 'Ask' }),
          ],
        }),
        error ? jsx('div', {
          className: 'vz-note',
          children: 'The model could not answer: ' + error,
        }) : null,
        out && !error ? jsxs('div', {
          className: 'vz-answer',
          children: [
            jsx('p', { children: out.answer || 'Not answered by the corpus.' }),
            cites.length ? jsx('div', {
              className: 'vz-cites',
              children: cites.map(c => jsxs('div', {
                className: 'vz-cite',
                children: [
                  jsx('span', { className: 'n', children: '[' + c.n + ']' }),
                  jsx('span', {
                    children: [
                      jsx('b', { style: { color: C.text, fontWeight: 600 }, children: c.title }),
                      jsx('br', {}),
                      c.doc,
                    ],
                  }),
                  jsx('button', {
                    onClick: () => onOpen({ path: c.path, id: c.n }),
                    children: 'open',
                  }),
                ],
              }, c.n)) }) : jsx('div', {
                className: 'vz-note',
                children: 'No source was cited, so nothing here can be checked. Try a question your documents actually cover.',
              }),
          ],
        }) : null,
        jsx('div', {
          className: 'vz-note',
          children: [
            jsx('span', { children: '·' }),
            jsx('span', {
              children: 'The answer is written by this session’s model from the passages it retrieved, and it is refused if they do not cover the question. It reads your documents; it never changes them.',
            }),
          ],
        }),
      ],
    }),
  })
}

/* ── the page ───────────────────────────────────────────────────────────── */
function Page({ ctx }) {
  const gateway = useValue(host.state.gateway)
  const model = useValue(host.state.model) || 'this session’s model'
  const [tab, setTab] = useState('graph')
  const [selected, setSelected] = useState(null)
  const [showSections, setShowSections] = useState(false)
  const [flagFilter, setFlagFilter] = useState(null)

  // ctx.rest is the plugin SDK's own gateway call: it carries the session's
  // credential scope, so no token is read or stored here. Held in a ref so the
  // data effect does not re-run (and refetch) on every render.
  const restRef = useRef(null)
  restRef.current = (path, options) =>
    ctx.rest ? ctx.rest(path, options) : Promise.reject(new Error('no ctx.rest'))
  const { data: graph, error: graphError } = useVault('/graph', restRef)
  const { data: stats } = useVault('/stats', restRef)
  const { data: wall } = useVault('/wall', restRef)
  const { data: review, error: reviewError } = useVault('/review', restRef)
  const [decisions, setDecisions] = useState({})
  // `busy` is the doc_id being decided on, so its buttons cannot be clicked twice.
  const [busy, setBusy] = useState(null)

  const docs = (graph && graph.nodes ? graph.nodes : []).filter(n => n.kind === 'document')
  const sections = (graph && graph.nodes ? graph.nodes : []).filter(n => n.kind === 'section')
  const flagCounts = {}
  for (const d of docs) flagCounts[d.flag] = (flagCounts[d.flag] || 0) + 1
  const reviewCount = FLAG_ORDER.filter(f => f !== 'current')
    .reduce((n, f) => n + (flagCounts[f] || 0), 0)

  function select(node) {
    setSelected(node)
    setTab('graph')
  }

  // A decision is posted to the backend; the returned queue replaces the local
  // copy so the left rail's counts and the Review tab agree. An `edit` with an
  // empty note is refused by the backend, so the note is collected first.
  async function decide(f, label, { action, note }) {
    let text = note || ''
    if (action === 'edit' && !text) {
      text = window.prompt('What should this document say instead?', '') || ''
      if (!text) return
    }
    setBusy(f.doc_id)
    try {
      const res = await restRef.current('/review', {
        method: 'POST',
        body: { doc_id: f.doc_id, flag: f.flag, action, note: text },
      })
      setReview(res.queue ? { flags: res.queue } : review)
      setDecisions(d => ({ ...d, [f.doc_id]: { action, note: text, label } }))
      host.notify({
        kind: 'success',
        message: label + ' — recorded. The source file was not changed.',
      })
    } catch (e) {
      host.notify({ kind: 'error', message: 'Could not record that decision: ' + e })
    } finally {
      setBusy(null)
    }
  }

  function openDocument(sel) {
    if (!sel) return
    // The source file lives on the host. `ctx.os.revealPath` is the SDK's
    // reveal-in-file-manager verb; `ctx.files` has no reveal, so the earlier
    // `ctx.files.reveal(docId)` was a call to a verb that does not exist, and it
    // passed the doc id where a filesystem path belongs.
    try {
      if (ctx.os && ctx.os.revealPath) { ctx.os.revealPath(sel.path); return }
    } catch (_) {}
    host.notify({ kind: 'info', message: sel.path || String(sel.id || '') })
  }

  const sel = selected || docs.find(d => d.flag !== 'current') || docs[0] || null

  return jsxs('div', {
    className: 'vz-root',
    children: [
      jsx('style', { children: CSS }),
      jsxs('header', {
        className: 'vz-head',
        children: [
          jsxs('div', {
            className: 'vz-brand',
            children: [
              jsx('h1', { children: NAME }),
              jsx('span', { className: 'tag', children: 'Every TVL document, one searchable picture' }),
            ],
          }),
          jsx('div', { className: 'spacer' }),
          jsxs('div', {
            className: 'vz-hstat', style: { display: 'flex', gap: 22 },
            children: [
              jsxs('div', { className: 'vz-hstat', children: [jsx('b', { children: String(docs.length) }), jsx('span', { children: 'documents' })] }),
              jsxs('div', { className: 'vz-hstat', children: [jsx('b', { children: String(sections.length) }), jsx('span', { children: 'sections' })] }),
              jsxs('div', { className: 'vz-hstat', children: [
                jsx('b', { style: { color: C.conflict }, children: String(reviewCount) }),
                jsx('span', { children: 'need review' }),
              ] }),
            ],
          }),
        ],
      }),
      jsxs('div', {
        className: 'vz-shell',
        children: [
          /* left rail */
          jsxs('aside', {
            className: 'vz-left',
            children: [
              jsxs('div', {
                className: 'vz-block',
                children: [
                  jsx('span', { className: 'vz-micro', children: 'Documents' }),
                  KIND_ORDER.map(k => {
                    const items = docs.filter(d => d.group === k)
                    if (!items.length) return null
                    return jsxs('div', {
                      className: 'vz-kind',
                      children: [
                        jsx('span', { className: 'vz-dot', style: { background: C[k] } }),
                        jsx('span', { className: 't', children: KIND_LABEL[k] }),
                        jsx('span', { className: 'n', children: String(items.length) }),
                      ],
                    }, k)
                  }),
                ],
              }),
              jsxs('div', {
                className: 'vz-block',
                children: [
                  jsx('span', { className: 'vz-micro', children: 'Needs review' }),
                  FLAG_ORDER.map(f => jsx('button', {
                    className: 'vz-chip', 'aria-pressed': String(flagFilter === f),
                    onClick: () => setFlagFilter(flagFilter === f ? null : f),
                    children: [
                      jsx('span', { className: 'sw', style: { background: FLAG[f].c } }),
                      FLAG[f].label,
                      jsx('span', { className: 'n', children: String(flagCounts[f] || 0) }),
                    ],
                  }, f)),
                ],
              }),
              jsxs('div', {
                className: 'vz-block',
                children: [
                  jsx('span', { className: 'vz-micro', children: 'Graph' }),
                  jsx('button', {
                    className: 'vz-chip', 'aria-pressed': String(showSections),
                    onClick: () => setShowSections(!showSections),
                    children: [
                      jsx('span', { className: 'sw', style: { background: C.text } }),
                      showSections ? 'Hide sections' : 'Show sections',
                      jsx('span', { className: 'n', children: String(sections.length) }),
                    ],
                  }),
                ],
              }),
              jsx('div', {
                className: 'vz-block',
                children: jsx('div', {
                  style: { fontSize: 12.5, color: C.muted, lineHeight: 1.6 },
                  children: 'Each dot is a document. A line means one document depends on another. Click a dot to read it.',
                }),
              }),
            ],
          }),
          /* centre */
          jsxs('div', {
            className: 'vz-center',
            children: [
              jsx('div', {
                className: 'vz-tabs', role: 'tablist',
                children: ['graph', 'wall', 'ask', 'review'].map(t => jsx('button', {
                  className: 'vz-tab', role: 'tab', 'aria-selected': String(tab === t),
                  onClick: () => setTab(t),
                  children: t.charAt(0).toUpperCase() + t.slice(1),
                }, t)),
              }),
              jsx('div', {
                className: 'vz-kpis',
                children: [
                  jsxs('div', { className: 'vz-kpi', children: [jsx('b', { children: String(docs.length) }), jsx('span', { children: 'documents indexed' })] }),
                  jsxs('div', { className: 'vz-kpi', children: [jsx('b', { children: String(sections.length) }), jsx('span', { children: 'sections read' })] }),
                  jsxs('div', { className: 'vz-kpi warn', children: [jsx('b', { children: String(reviewCount) }), jsx('span', { children: 'need a decision' })] }),
                  jsxs('div', { className: 'vz-kpi', children: [
                    jsx('b', { children: String((flagCounts.duplicate || 0) + (flagCounts.conflict || 0)) }),
                    jsx('span', { children: 'duplicates or disagreements' }),
                  ] }),
                ],
              }),
              tab === 'graph' ? jsx(GraphPane, {
                ctx, graph, showSections, flagFilter, selectedId: sel && sel.id,
                onSelect: select,
              }) : null,
              tab === 'wall' ? jsx(WallPane, { ctx, wall, onSelect: d => select({
                id: d.doc_id, kind: 'document', label: d.title, group: d.kind, flag: d.flag, path: d.path,
              }) }) : null,
              tab === 'ask' ? jsx(AskPane, {
                ctx, restRef, onOpen: sel => openDocument(sel),
              }) : null,
              tab === 'review' ? jsx(ReviewPane, { ctx, review, decisions, busy, onSelect: f => select({
                id: f.doc_id, kind: 'document', label: f.title, group: f.kind, flag: f.flag, path: f.path,
              }), onDecide: decide }) : null,
            ],
          }),
          /* right detail */
          jsx('aside', {
            className: 'vz-right',
            children: sel ? jsxs('div', {
              children: [
                jsxs('div', {
                  className: 'vz-dhead',
                  children: [
                    jsx('div', { className: 'k', style: { color: C[sel.group] || C.notes }, children: KIND_LABEL[sel.group] || sel.group }),
                    jsx('h2', { children: sel.label }),
                    jsx(Badge, { flag: sel.flag }),
                  ],
                }),
                jsxs('div', {
                  className: 'vz-dmeta',
                  children: [
                    jsxs('div', { children: [jsx('dt', { children: 'Status' }), jsx('dd', { children: (FLAG[sel.flag] || FLAG.current).label })] }),
                    jsxs('div', { children: [jsx('dt', { children: 'File' }), jsx('dd', { children: sel.path || '' })] }),
                    jsxs('div', { children: [jsx('dt', { children: 'Gateway' }), jsx('dd', { children: `${gateway} · ${model}` })] }),
                  ],
                }),
                jsx('button', { className: 'vz-open', onClick: () => openDocument(sel.path), children: 'Open the source document' }),
              ],
            }) : jsx('div', {
              className: 'vz-empty',
              children: [
                jsx('div', { className: 'big', children: 'Click any dot to read it here' }),
                jsx('div', { className: 'small', children: 'The plain-language status, the reason for it, and the exact place in the source document.' }),
              ],
            }),
          }),
        ],
      }),
      graphError ? jsx('div', { className: 'vz-note', children: String(graphError) }) : null,
    ],
  })
}

export default {
  id: 'tvl-vault',      // must equal the folder name
  name: NAME,
  defaultEnabled: false,
  register(ctx) {
    ctx.register({ id: 'page', area: ROUTES_AREA, data: { path: '/tvl-vault' }, render: () => jsx(Page, { ctx }) })
    ctx.register({ id: 'nav', area: SIDEBAR_NAV_AREA, data: { path: '/tvl-vault', label: NAME, codicon: 'database' } })
  },
}
