"""Genera el sitio estático (docs/index.html + products.json)."""
from __future__ import annotations

import json
from datetime import datetime
from html import escape
from pathlib import Path

from ..config import Config
from ..copywriter import DISCLOSURE, money
from ..meli import Product

CSS = """
*{box-sizing:border-box}body{margin:0;font-family:system-ui,sans-serif;background:#f5f5f7;color:#1d1d1f}
header{background:#ffe600;padding:20px 16px}h1{margin:0;font-size:22px}
.note{font-size:12px;margin:6px 0 0}main{max-width:1000px;margin:auto;padding:16px;
display:grid;grid-template-columns:repeat(auto-fill,minmax(220px,1fr));gap:14px}
.card{background:#fff;border-radius:12px;overflow:hidden;display:flex;flex-direction:column}
.card img{width:100%;height:200px;object-fit:contain;background:#fff}
.b{padding:12px;display:flex;flex-direction:column;gap:6px;flex:1}
.t{font-size:14px;line-height:1.3}.old{text-decoration:line-through;color:#888;font-size:13px}
.p{font-size:22px;font-weight:700}.off{color:#00a650;font-weight:700;font-size:13px}
.btn{margin-top:auto;background:#3483fa;color:#fff;text-align:center;padding:10px;border-radius:8px;text-decoration:none;font-weight:600}
footer{max-width:1000px;margin:auto;padding:16px;font-size:12px;color:#666}
"""


def render(items: list[dict], cfg: Config) -> str:
    cards = []
    for it in items:
        p = Product.from_dict(it)
        old = f'<span class="old">{money(p.original_price)}</span>' if p.original_price else ""
        off = f'<span class="off">{p.discount_pct:.0f}% OFF</span>' if p.discount_pct else ""
        cards.append(
            f'<article class="card"><img loading="lazy" src="{escape(p.image, True)}" alt="{escape(p.title, True)}">'
            f'<div class="b"><div class="t">{escape(p.title)}</div>{old}'
            f'<div class="p">{money(p.price)}</div>{off}'
            f'<a class="btn" rel="sponsored nofollow noopener" target="_blank" '
            f'href="{escape(it["affiliate_link"], True)}">Ver en Mercado Libre</a></div></article>'
        )
    stamp = datetime.now().strftime("%d/%m/%Y %H:%M")
    name = escape(cfg.site_name)
    return (
        f'<!doctype html><html lang="es-MX"><head><meta charset="utf-8">'
        f'<meta name="viewport" content="width=device-width,initial-scale=1">'
        f"<title>{name}</title>"
        f'<meta name="description" content="Las mejores ofertas de Mercado Libre México, seleccionadas por descuento y ventas.">'
        f"<style>{CSS}</style></head><body>"
        f"<header><h1>{name}</h1><p class='note'>{escape(DISCLOSURE)} "
        f"Los precios pueden cambiar; confirma siempre en Mercado Libre. Actualizado: {stamp}</p></header>"
        f"<main>{''.join(cards) or '<p>Pronto habrá ofertas.</p>'}</main>"
        f"<footer>Sitio independiente, no oficial de Mercado Libre.</footer></body></html>"
    )


def build(store_items: dict, cfg: Config, limit: int = 100) -> str:
    pub = [v for v in store_items.values() if v["status"] == "published"]
    pub.sort(key=lambda v: v["published_at"], reverse=True)
    pub = pub[:limit]
    d = Path(cfg.docs_dir)
    d.mkdir(parents=True, exist_ok=True)
    (d / "index.html").write_text(render(pub, cfg), encoding="utf-8")
    (d / "products.json").write_text(json.dumps(pub, ensure_ascii=False, indent=1), encoding="utf-8")
    return str(d / "index.html")
