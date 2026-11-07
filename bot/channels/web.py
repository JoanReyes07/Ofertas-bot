"""Sitio estático pensado para celular (docs/index.html + products.json).

Es el "link en bio" de TikTok: el video dice "código 12", la persona abre la web,
busca el 12 y toca "Ver oferta" (link de afiliado directo a Mercado Libre).
"""
from __future__ import annotations

import json
from html import escape
from pathlib import Path

from ..cards import CATEGORY_NAMES
from ..config import Config
from ..copywriter import money
from ..meli import Product

CSS = """
:root{--bg:#EBF2E1;--bg2:#DDEACB;--card:#fff;--ink:#102015;--muted:#7D8A80;--line:#E2EAD8;--forest:#1E2B20;
--mint:#CDE8AA;--orange:#1E2B20;--lime:#A6E36B;--lime-text:#3F8A22;--chip:#fff;--shadow:0 2px 12px rgba(16,32,21,.07)}
*{box-sizing:border-box;-webkit-tap-highlight-color:transparent}
html{scroll-behavior:smooth}
body{margin:0;font-family:"Poppins",system-ui,-apple-system,"Segoe UI",Roboto,sans-serif;background:var(--bg);color:var(--ink);
font-size:15px;line-height:1.4}
.hero{background:linear-gradient(180deg,var(--bg) 0%,var(--bg2) 100%);padding:18px 16px 6px}
.top{display:flex;align-items:center;justify-content:space-between}
.logo{font-weight:800;font-size:21px;margin:0;color:var(--ink)}.logo b{color:var(--lime-text);font-weight:800}
.pill-note{font-size:12px;font-weight:600;background:var(--card);color:var(--forest);padding:6px 10px;border-radius:999px;box-shadow:var(--shadow)}
.big{display:flex;align-items:center;gap:12px;margin:18px 0 4px}
.big .n{font-size:54px;font-weight:800;line-height:1;color:var(--ink);letter-spacing:-2px}
.big .l{font-size:19px;font-weight:700;line-height:1.15}
.sub{margin:6px 0 0;color:var(--muted);font-size:14px}
.tools{position:sticky;top:0;z-index:5;background:var(--bg2);padding:10px 16px 10px}
.search{display:flex;align-items:center;gap:8px;background:var(--card);border-radius:999px;padding:0 16px;box-shadow:var(--shadow)}
.search svg{flex:none;opacity:.55}
.search input{flex:1;min-width:0;font:inherit;font-size:16px;padding:13px 0;border:0;background:transparent;color:var(--ink);outline:none}
.chips{display:flex;gap:8px;overflow-x:auto;padding:10px 0 0;scrollbar-width:none}
.chips::-webkit-scrollbar{display:none}
.chip{flex:none;border:0;border-radius:999px;padding:8px 14px;font:inherit;font-size:13px;font-weight:600;background:var(--chip);color:var(--ink);box-shadow:var(--shadow)}
.chip.on{background:var(--forest);color:#fff}
main{max-width:1100px;margin:auto;padding:12px 12px 8px;display:grid;grid-template-columns:repeat(2,1fr);gap:12px}
@media (min-width:720px){main{grid-template-columns:repeat(3,1fr)}}
@media (min-width:1000px){main{grid-template-columns:repeat(4,1fr)}}
.card{background:var(--card);border-radius:22px;overflow:hidden;box-shadow:var(--shadow);display:flex;flex-direction:column;
scroll-margin-top:130px;transition:box-shadow .3s}
.card.hit{box-shadow:0 0 0 3px var(--lime)}
.media{position:relative;background:#fff;aspect-ratio:1/1}
.media img{width:100%;height:100%;object-fit:contain;padding:14px}
.code{position:absolute;left:8px;top:8px;background:#EEF2EA;color:#102015;font-weight:700;font-size:12px;padding:4px 9px;border-radius:999px}
.off{position:absolute;right:8px;top:8px;background:var(--lime);color:#102015;font-weight:800;font-size:13px;padding:4px 9px;border-radius:999px}
.new{position:absolute;left:8px;bottom:8px;background:var(--mint);color:var(--forest);font-weight:700;font-size:11px;padding:3px 8px;border-radius:999px}
.b{padding:10px 12px 12px;display:flex;flex-direction:column;gap:3px;flex:1}
.t{font-size:13px;font-weight:500;line-height:1.3;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden;min-height:2.6em}
.old{color:var(--muted);text-decoration:line-through;font-size:12px;margin-top:4px}
.p{font-size:22px;font-weight:800;letter-spacing:-.5px;line-height:1.1}
.meta{font-size:11px;color:var(--muted);min-height:1.4em}
.btn{margin-top:8px;display:flex;align-items:center;justify-content:space-between;gap:6px;background:var(--orange);color:#fff;
font-weight:700;font-size:14px;padding:6px 6px 6px 14px;border-radius:999px;text-decoration:none}
.btn i{flex:none;width:30px;height:30px;border-radius:50%;background:var(--lime);display:grid;place-items:center}
.btn:active{transform:scale(.97)}
.empty{grid-column:1/-1;text-align:center;color:var(--muted);padding:40px 10px}
footer{background:var(--forest);color:#D5E6D6;margin-top:18px;padding:22px 18px 40px;font-size:13px;border-radius:28px 28px 0 0}
footer h2{font-size:15px;color:#fff;margin:14px 0 6px}
footer ol{padding-left:20px;margin:0}
"""

JS = """
const q=document.getElementById('q'),cards=[...document.querySelectorAll('.card')],chips=[...document.querySelectorAll('.chip')];
const none=document.getElementById('none');let cat='';
function ago(iso){const h=(Date.now()-new Date(iso))/36e5;if(h<1)return'hace minutos';if(h<24)return'hace '+Math.floor(h)+' h';
const d=Math.floor(h/24);return d===1?'ayer':'hace '+d+' días'}
cards.forEach(c=>{const iso=c.dataset.pub;if(!iso)return;const m=c.querySelector('.meta');if(m)m.textContent=(m.textContent?m.textContent+' · ':'')+ago(iso);
if(Date.now()-new Date(iso)<864e5)c.querySelector('.media').insertAdjacentHTML('beforeend','<span class="new">Nuevo hoy</span>')});
function apply(){const v=q.value.trim().toLowerCase().replace(/^#|^c[oó]digo\\s*/,'');let n=0,hit=null;
cards.forEach(c=>{const byCode=/^\\d+$/.test(v);const ok=(!cat||c.dataset.cat===cat)&&(!v||(byCode?c.dataset.code===v:c.dataset.s.includes(v)));
c.hidden=!ok;c.classList.toggle('hit',ok&&byCode);if(ok){n++;if(byCode)hit=c}});none.hidden=n>0;return hit}
q.addEventListener('input',apply);
q.addEventListener('keydown',e=>{if(e.key==='Enter'){const h=apply();if(h)h.scrollIntoView({block:'start'});q.blur()}});
chips.forEach(b=>b.onclick=()=>{cat=b.dataset.cat;chips.forEach(x=>x.classList.toggle('on',x===b));apply()});
function fromHash(){const m=location.hash.match(/^#(\\d+)$/);if(!m)return;q.value=m[1];const h=apply();
if(h)setTimeout(()=>h.scrollIntoView({block:'start'}),50)}
addEventListener('hashchange',fromHash);fromHash();
"""


def _card(it: dict) -> str:
    p = Product.from_dict(it)
    code = it.get("code") or ""
    cat = CATEGORY_NAMES.get(p.category, "")
    old = f'<div class="old">{money(p.original_price)}</div>' if p.original_price and p.discount_pct else ""
    off = f'<span class="off">-{p.discount_pct:.0f}%</span>' if p.discount_pct else ""
    code_html = f'<span class="code">Código {code}</span>' if code else ""
    top = f"Top {p.rank} en {cat}" if p.rank and cat else ""
    search = escape(f"{p.title} {cat}".lower(), True)
    return (
        f'<article class="card" id="c{code}" data-code="{code}" data-cat="{escape(cat, True)}" '
        f'data-s="{search}" data-pub="{escape(it.get("published_at", ""), True)}">'
        f'<div class="media"><img loading="lazy" src="{escape(p.image, True)}" alt="{escape(p.title, True)}">'
        f"{code_html}{off}</div>"
        f'<div class="b"><div class="t">{escape(p.title)}</div>{old}'
        f'<div class="p">{money(p.price)}</div>'
        f'<div class="meta">{escape(top)}</div>'
        f'<a class="btn" rel="sponsored nofollow noopener" target="_blank" '
        f'href="{escape(it.get("affiliate_link", ""), True)}">Ver oferta<i><svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#102015" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"><path d="M5 12h14M13 6l6 6-6 6"/></svg></i></a></div></article>'
    )


def render(items: list[dict], cfg: Config) -> str:
    name = escape(cfg.site_name)
    if cfg.site_name.strip().lower() == "cazaofertas mx":
        logo = "Caza<b>ofertas</b> MX"
    else:
        logo = name
    cats = sorted({CATEGORY_NAMES.get(Product.from_dict(i).category, "") for i in items} - {""})
    chips = '<button class="chip on" data-cat="">Todas</button>' + "".join(
        f'<button class="chip" data-cat="{escape(c, True)}">{escape(c)}</button>' for c in cats)
    url = cfg.web_url.rstrip("/")
    og = (
        f'<meta property="og:type" content="website"><meta property="og:title" content="{name}: ofertas de hoy">'
        f'<meta property="og:description" content="Descuentos reales en Mercado Libre, revisados cada día.">'
        + (f'<meta property="og:url" content="{escape(url, True)}/"><meta property="og:image" content="{escape(url, True)}/og.jpg">'
           if url else "")
        + '<meta name="twitter:card" content="summary_large_image">'
    )
    return (
        '<!doctype html><html lang="es-MX"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">'
        f"<title>{name}: ofertas de hoy en Mercado Libre</title>"
        '<meta name="description" content="Descuentos reales en Mercado Libre México, revisados cada día. Busca el código del video.">'
        '<meta name="theme-color" content="#EBF2E1"><meta name="color-scheme" content="light"><link rel="icon" href="icon-192.png"><link rel="apple-touch-icon" href="icon-192.png">'
        f"{og}<style>{CSS}</style></head><body>"
        f'<header class="hero"><div class="top"><p class="logo">{logo}</p>'
        '<span class="pill-note">Te llevamos a Mercado Libre</span></div>'
        f'<div class="big"><span class="n">{len(items)}</span><span class="l">ofertas<br>de hoy</span></div>'
        '<p class="sub">Aquí no se compra: elige una oferta y la abrimos en Mercado Libre, con su envío y garantía.</p></header>'
        '<div class="tools"><div class="search"><svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round"><circle cx="11" cy="11" r="7"/><path d="m20 20-3.5-3.5"/></svg><input id="q" type="search" inputmode="search" enterkeyhint="search" '
        'placeholder="Escribe el código del video (ej. 12)" autocomplete="off" aria-label="Buscar"></div>'
        f'<div class="chips">{chips}</div></div>'
        f"<main>{''.join(_card(i) for i in items)}"
        '<p class="empty" id="none" hidden>No encontramos ese código. Revisa el número del video.</p>'
        + ('' if items else '<p class="empty">Pronto habrá ofertas.</p>')
        + "</main>"
        "<footer><h2>¿Cómo funciona?</h2><ol><li>Escribe el código que viste en el video.</li>"
        "<li>Toca <b>Ver oferta</b>.</li><li>Se abre Mercado Libre: ahí compras, con su envío y garantía.</li></ol>"
        "<h2>Transparencia</h2><p>Los enlaces son de afiliado: si compras, puedo ganar una pequeña comisión sin costo extra "
        "para ti. Los precios pueden cambiar; confírmalos siempre en Mercado Libre. Sitio independiente, no oficial de "
        f"Mercado Libre.</p></footer><script>{JS}</script></body></html>"
    )


def build(store_items: dict, cfg: Config, limit: int = 100) -> str:
    pub = [v for v in store_items.values() if v["status"] == "published"]
    pub.sort(key=lambda v: v.get("published_at", ""), reverse=True)
    pub = pub[:limit]
    d = Path(cfg.docs_dir)
    d.mkdir(parents=True, exist_ok=True)
    (d / "index.html").write_text(render(pub, cfg), encoding="utf-8")
    (d / "products.json").write_text(json.dumps(pub, ensure_ascii=False, indent=1), encoding="utf-8")
    _brand_assets(d)
    return str(d / "index.html")


def _brand_assets(d: Path) -> None:
    """Ícono y vista previa para compartir (se generan una vez)."""
    from .. import cards

    if not (d / "icon-192.png").exists():
        cards.make_icon(192).save(d / "icon-192.png")
    if not (d / "og.jpg").exists():
        cards.make_og().save(d / "og.jpg", "JPEG", quality=88)
