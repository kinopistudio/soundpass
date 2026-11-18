"""A single static HTML page to audition a pack (or a palette sampler) in any browser."""
from __future__ import annotations

import html
import json

CATEGORY_ORDER = ["ui", "pickup", "movement", "combat", "puzzle", "jingle", "custom"]

PAGE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>%(title)s</title>
<style>
:root { --bg:#f6f4ef; --card:#fff; --ink:#1d1b18; --mute:#6b665d; --line:#e4dfd5; --accent:#d9542b; --accent-ink:#fff; }
@media (prefers-color-scheme: dark) { :root { --bg:#141311; --card:#1d1c19; --ink:#efebe3; --mute:#9a9489; --line:#2e2c27; --accent:#ff7a4d; --accent-ink:#141311; } }
* { box-sizing: border-box; }
body { margin:0; background:var(--bg); color:var(--ink); font:15px/1.5 ui-sans-serif, system-ui, -apple-system, "Segoe UI", sans-serif; }
main { max-width: 1040px; margin: 0 auto; padding: 32px 16px 64px; }
h1 { font-size: 26px; margin: 0 0 4px; letter-spacing: -0.01em; }
.sub { color: var(--mute); margin: 0 0 24px; }
h2 { font-size: 13px; text-transform: uppercase; letter-spacing: .08em; color: var(--mute); margin: 28px 0 10px; }
.grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(220px, 1fr)); gap: 10px; }
.card { background: var(--card); border: 1px solid var(--line); border-radius: 12px; padding: 12px 14px; }
.card h3 { margin: 0; font-size: 15px; font-family: ui-monospace, SFMono-Regular, Menlo, monospace; }
.card p { margin: 2px 0 10px; color: var(--mute); font-size: 13px; min-height: 2.6em; }
.btns { display: flex; flex-wrap: wrap; gap: 6px; }
button { font: inherit; font-size: 13px; border: 1px solid var(--line); background: transparent; color: var(--ink);
  border-radius: 999px; padding: 4px 11px; cursor: pointer; }
button:hover { border-color: var(--accent); }
button.on { background: var(--accent); border-color: var(--accent); color: var(--accent-ink); }
.tabs { display: flex; flex-wrap: wrap; gap: 6px; margin: 0 0 8px; }
.tabs button { padding: 6px 14px; font-size: 14px; }
.pdesc { color: var(--mute); margin: 6px 0 0; min-height: 1.5em; }
.hint { color: var(--mute); font-size: 13px; margin-top: 28px; }
kbd { font: 12px ui-monospace, monospace; border: 1px solid var(--line); border-radius: 4px; padding: 0 4px; }
</style>
</head>
<body>
<main>
<h1>%(title)s</h1>
<p class="sub">%(subtitle)s</p>
<div id="app"></div>
<p class="hint">Click a button to play. <kbd>Shift</kbd>+click plays every variant in turn. Made with soundpass.</p>
</main>
<script>
const DATA = %(data)s;
const CAT_ORDER = %(order)s;
const app = document.getElementById('app');
let current = null;
function play(src, btn) {
  if (current) { current.pause(); }
  const a = new Audio(src); current = a; a.play();
  if (btn) { btn.classList.add('on'); a.onended = () => btn.classList.remove('on'); setTimeout(() => btn.classList.remove('on'), 2500); }
  return a;
}
function playAll(files, btns, i = 0) {
  if (i >= files.length) return;
  const a = play(files[i], btns[i]);
  a.onended = () => { btns[i].classList.remove('on'); setTimeout(() => playAll(files, btns, i + 1), 120); };
}
function renderPack(pack, root) {
  root.innerHTML = '';
  const groups = {};
  for (const s of pack.sounds) (groups[s.category] = groups[s.category] || []).push(s);
  const cats = Object.keys(groups).sort((a, b) => (CAT_ORDER.indexOf(a) + 99 * (CAT_ORDER.indexOf(a) < 0)) - (CAT_ORDER.indexOf(b) + 99 * (CAT_ORDER.indexOf(b) < 0)));
  for (const cat of cats) {
    const h = document.createElement('h2'); h.textContent = cat; root.appendChild(h);
    const grid = document.createElement('div'); grid.className = 'grid'; root.appendChild(grid);
    for (const s of groups[cat]) {
      const card = document.createElement('div'); card.className = 'card';
      const t = document.createElement('h3'); t.textContent = s.id; card.appendChild(t);
      const p = document.createElement('p'); p.textContent = s.desc || ''; card.appendChild(p);
      const row = document.createElement('div'); row.className = 'btns'; card.appendChild(row);
      const files = s.files.map(f => (pack.base || '') + f);
      const btns = files.map((f, i) => {
        const b = document.createElement('button');
        b.textContent = files.length === 1 ? 'play' : (s.ladder ? 'lv ' + (i + 1) : 'v' + (i + 1));
        b.onclick = (e) => e.shiftKey ? playAll(files, btns) : play(f, b);
        row.appendChild(b); return b;
      });
      grid.appendChild(card);
    }
  }
}
if (DATA.packs) {
  const tabs = document.createElement('div'); tabs.className = 'tabs'; app.appendChild(tabs);
  const desc = document.createElement('p'); desc.className = 'pdesc'; app.appendChild(desc);
  const body = document.createElement('div'); app.appendChild(body);
  const tbtns = DATA.packs.map((pack, i) => {
    const b = document.createElement('button'); b.textContent = pack.palette;
    b.onclick = () => { tbtns.forEach(x => x.classList.remove('on')); b.classList.add('on');
      desc.textContent = pack.palette_desc || ''; renderPack(pack, body); };
    tabs.appendChild(b); return b;
  });
  tbtns[0].click();
} else {
  renderPack(DATA, app);
}
</script>
</body>
</html>
"""


def write(path, data, title, subtitle):
    with open(path, "w", encoding="utf-8") as f:
        f.write(PAGE % {
            "title": html.escape(title),
            "subtitle": html.escape(subtitle),
            "data": json.dumps(data, ensure_ascii=False).replace("</", "<\\/"),
            "order": json.dumps(CATEGORY_ORDER),
        })
