"""Build a self-contained HTML gallery of listings for eyeballing.

Cards are ordered by verdict (buyable first) then price, each showing the
photos, key stats, verdict + reasons, and a link to the source listing.

A lightweight taste-labeling UI (👍 / 👎 / skip per listing, saved to the
browser's localStorage with a JSON export button) lets the owner build a
labeled dataset for a future "taste" model — exactly the eventual goal.
"""

from __future__ import annotations

import html
from pathlib import Path

from .models import Listing

VERDICT_ORDER = {"pass": 0, "stretch": 1, "flagged": 2, "reject": 3}
VERDICT_COLOR = {
    "pass": "#1a7f37", "stretch": "#9a6700", "flagged": "#0969da", "reject": "#82071e",
}


def _rel(path: str, out_dir: Path) -> str:
    try:
        return str(Path(path).resolve().relative_to(out_dir.resolve()))
    except ValueError:
        return path


def _card(l: Listing, out_dir: Path) -> str:
    color = VERDICT_COLOR.get(l.verdict or "", "#57606a")
    price_yen = f"¥{l.price_yen:,}" if l.price_yen else "price ?"
    price_usd = f"${round(l.price_yen / 150):,}" if l.price_yen else ""
    reasons = "; ".join(l.verdict_reasons or [])
    imgs = l.local_images or l.image_urls
    img_html = "".join(
        f'<img loading="lazy" src="{html.escape(_rel(src, out_dir) if l.local_images else src)}" />'
        for src in imgs[:8]
    ) or '<div class="noimg">no photos</div>'

    stats = " · ".join(
        s for s in [
            l.layout or "",
            f"{l.building_m2:.0f}m² bldg" if l.building_m2 else "",
            f"{l.land_m2:.0f}m² land" if l.land_m2 else "",
            f"built {l.build_year}" if l.build_year else "",
        ] if s
    )
    return f"""
    <div class="card" data-verdict="{l.verdict}" data-key="{html.escape(l.key)}">
      <div class="photos">{img_html}</div>
      <div class="body">
        <div class="head">
          <span class="badge" style="background:{color}">{l.verdict}</span>
          <span class="town">{html.escape(l.town or '—')}</span>
          <span class="price">{price_yen} <em>{price_usd}</em></span>
        </div>
        <div class="stats">{html.escape(stats)}</div>
        <div class="reasons">{html.escape(reasons)}</div>
        <div class="foot">
          <a href="{html.escape(l.url)}" target="_blank" rel="noopener">{l.source}:{html.escape(l.source_id)} ↗</a>
          <span class="taste">
            <button class="up" data-v="good">👍</button>
            <button class="down" data-v="bad">👎</button>
            <button class="meh" data-v="skip">🚫</button>
          </span>
        </div>
      </div>
    </div>"""


_CSS = """
:root{color-scheme:light dark}
body{font:14px/1.4 -apple-system,Segoe UI,Roboto,sans-serif;margin:0;background:#f6f8fa;color:#1f2328}
@media(prefers-color-scheme:dark){body{background:#0d1117;color:#e6edf3}.card{background:#161b22!important;border-color:#30363d!important}}
header{position:sticky;top:0;background:inherit;padding:12px 16px;border-bottom:1px solid #d0d7de;z-index:5}
header h1{margin:0 0 6px;font-size:16px}
.filters button{margin-right:6px;padding:4px 10px;border:1px solid #d0d7de;border-radius:6px;background:transparent;color:inherit;cursor:pointer}
.filters button.active{background:#0969da;color:#fff;border-color:#0969da}
#grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(320px,1fr));gap:14px;padding:16px}
.card{border:1px solid #d0d7de;border-radius:10px;overflow:hidden;background:#fff;display:flex;flex-direction:column}
.photos{display:flex;overflow-x:auto;gap:2px;background:#e5e7eb;scroll-snap-type:x mandatory}
@media(prefers-color-scheme:dark){.photos{background:#1f2937}}
.photos img{height:190px;width:auto;object-fit:cover;scroll-snap-align:start;flex:1 1 auto;min-width:0}
.noimg{height:190px;display:flex;align-items:center;justify-content:center;color:#888;width:100%}
.body{padding:10px 12px;display:flex;flex-direction:column;gap:6px}
.head{display:flex;align-items:center;gap:8px;flex-wrap:wrap}
.badge{color:#fff;padding:1px 8px;border-radius:20px;font-size:11px;text-transform:uppercase;letter-spacing:.03em}
.town{font-weight:600}.price{margin-left:auto;font-weight:600}.price em{color:#57606a;font-style:normal;font-weight:400}
.stats{color:#57606a}.reasons{font-size:12px;color:#6e7781;min-height:1em}
.foot{display:flex;align-items:center;justify-content:space-between;margin-top:4px}
.foot a{color:#0969da;text-decoration:none;font-size:12px}
.taste button{border:none;background:transparent;font-size:16px;cursor:pointer;opacity:.4;transition:opacity .1s}
.taste button.sel{opacity:1;transform:scale(1.25)}
.card[data-taste=good]{outline:2px solid #1a7f37}.card[data-taste=bad]{outline:2px solid #82071e;opacity:.55}
"""

_JS = """
const LS='akiya_taste';
const load=()=>JSON.parse(localStorage.getItem(LS)||'{}');
const save=o=>localStorage.setItem(LS,JSON.stringify(o));
function apply(){const t=load();document.querySelectorAll('.card').forEach(c=>{
  const v=t[c.dataset.key];if(v){c.dataset.taste=v;c.querySelectorAll('.taste button').forEach(b=>b.classList.toggle('sel',b.dataset.v===v));}});}
document.addEventListener('click',e=>{
  if(e.target.matches('.taste button')){const c=e.target.closest('.card');const t=load();
    t[c.dataset.key]=e.target.dataset.v;save(t);apply();}
  if(e.target.matches('.filters button')){const f=e.target.dataset.f;
    document.querySelectorAll('.filters button').forEach(b=>b.classList.toggle('active',b===e.target));
    document.querySelectorAll('.card').forEach(c=>{c.style.display=(f==='all'||c.dataset.verdict===f)?'':'none';});}
});
function exportLabels(){const blob=new Blob([JSON.stringify(load(),null,2)],{type:'application/json'});
  const a=document.createElement('a');a.href=URL.createObjectURL(blob);a.download='taste_labels.json';a.click();}
apply();
"""


def build(listings: list[Listing], out_path: Path) -> Path:
    out_dir = out_path.parent
    ordered = sorted(
        listings,
        key=lambda l: (VERDICT_ORDER.get(l.verdict or "", 9), l.price_yen or 10**12),
    )
    counts = {}
    for l in ordered:
        counts[l.verdict] = counts.get(l.verdict, 0) + 1
    filters = "".join(
        f'<button data-f="{v}" class="{"active" if v=="all" else ""}">{v} '
        f'({len(ordered) if v=="all" else counts.get(v, 0)})</button>'
        for v in ["all", "pass", "stretch", "flagged", "reject"]
    )
    cards = "\n".join(_card(l, out_dir) for l in ordered)
    doc = f"""<!doctype html><html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>akiya gallery ({len(ordered)})</title><style>{_CSS}</style></head>
<body>
<header>
  <h1>Hokkaido akiya — {len(ordered)} listings</h1>
  <div class="filters">{filters}
    <button onclick="exportLabels()" style="float:right">⬇ export taste labels</button>
  </div>
</header>
<div id="grid">{cards}</div>
<script>{_JS}</script>
</body></html>"""
    out_path.write_text(doc, encoding="utf-8")
    return out_path
