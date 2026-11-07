"""Material para publicar a mano, por cada producto que está en la página:

docs/media/cards/{id}-sq.jpg   tarjeta cuadrada (Facebook)
docs/media/cards/{id}-v.jpg    tarjeta vertical (TikTok)
docs/media/video/{id}.mp4      video corto (TikTok)
docs/media/texts/{id}.txt      textos para cada red + link

docs/media/feed.json lo lee la app para el botón "Descargar".
"""
from __future__ import annotations

import json
import re
import sys
import unicodedata
from datetime import datetime, timezone
from pathlib import Path

from .. import cards, copywriter, video
from ..config import Config
from ..meli import Product
from ..store import Store

PAGE_LIMIT = 100        # mismos productos que muestra la web (channels/web.py)
MAX_BACKFILL = 10       # cuántos productos sin material se completan por corrida


def media_dir(cfg: Config) -> Path:
    return Path(cfg.docs_dir) / "media"


def on_page(store: Store) -> list[dict]:
    pub = [v for v in store.with_status("published") if v.get("published_at")]
    pub.sort(key=lambda v: v["published_at"], reverse=True)
    return pub[:PAGE_LIMIT]


def folder_name(p: Product) -> str:
    """Nombre de carpeta seguro y legible: 'Juego De Sabanas King Size - MLM53457233'."""
    t = unicodedata.normalize("NFKD", p.title).encode("ascii", "ignore").decode()
    t = re.sub(r"[^A-Za-z0-9 ]+", " ", t)
    t = re.sub(r"\s+", " ", t).strip()[:40].strip()
    return f"{t} - {p.id}" if t else p.id


def folder_for(it: dict) -> str:
    """Con código al inicio para que se ordenen: '012 Juego De Sabanas King - MLM53457233'."""
    name = folder_name(Store.product(it))
    return f"{int(it['code']):03d} {name}" if it.get("code") else name


def texts(p: Product, link: str, copy: dict, code: int = 0, web_url: str = "") -> str:
    old = f" (antes ${p.original_price:,.0f}, -{p.discount_pct:.0f}%)" if p.discount_pct else ""
    parts = [
        f"CÓDIGO {code}: {p.title}" if code else f"PRODUCTO: {p.title}",
        f"Precio: ${p.price:,.0f}{old}",
        f"Link de afiliado (directo a Mercado Libre): {link}",
    ]
    if web_url and code:
        parts.append(f"En tu web (link de tu perfil de TikTok): {web_url.rstrip('/')}/#{code}")
    parts += [
        "",
        "===== FACEBOOK (pega junto con facebook.jpg) =====",
        copy.get("facebook", ""),
        "",
        "===== TIKTOK: descripción (pega junto con tiktok.mp4) =====",
        copy.get("tiktok_caption", ""),
        "",
        "===== TIKTOK: guion si quieres grabar tu voz =====",
        copy.get("tiktok_script", ""),
        "",
        "===== WHATSAPP =====",
        copy.get("whatsapp", ""),
        "",
        "Facebook y WhatsApp: link directo a Mercado Libre. TikTok: el código lleva a tu web (link en tu perfil).",
    ]
    return "\n".join(parts).strip() + "\n"


def make_media(it: dict, cfg: Config, http=None) -> dict:
    """Genera tarjetas, video y textos de un producto. Devuelve los nombres de archivo."""
    p = Store.product(it)
    code = int(it.get("code") or 0)
    md = media_dir(cfg)
    kw = {"http": http} if http else {}
    out: dict = {}
    try:
        out.update(cards.make_cards(p, str(md / "cards"), cfg.site_name, code=code, **kw))
    except Exception as e:  # sin tarjeta se publica con la foto original
        print(f"[aviso] no pude generar la tarjeta de {p.id}: {e}", file=sys.stderr)
        return out
    try:
        video.build_product(str(md / "cards" / out["vertical"]), str(md / "video" / f"{p.id}.mp4"),
                            p.discount_pct, code=code)
        out["video"] = f"{p.id}.mp4"
    except Exception as e:
        print(f"[aviso] no pude generar el video de {p.id}: {e}", file=sys.stderr)
    copy = it.get("copy") or copywriter.generate(p, it.get("affiliate_link", ""), cfg, code=code, **kw)
    it["copy"] = copy
    (md / "texts").mkdir(parents=True, exist_ok=True)
    (md / "texts" / f"{p.id}.txt").write_text(
        texts(p, it.get("affiliate_link", ""), copy, code, cfg.web_url), encoding="utf-8")
    out["text"] = f"{p.id}.txt"
    return out


def _complete(it: dict, md: Path) -> bool:
    m = it.get("cards") or {}
    return all(m.get(k) for k in ("square", "vertical", "video", "text")) and all(
        (md / sub / m[k]).exists() for k, sub in
        (("square", "cards"), ("vertical", "cards"), ("video", "video"), ("text", "texts")))


def build(store: Store, cfg: Config, http=None) -> dict:
    """Completa el material que falte de los productos de la página y escribe feed.json."""
    md = media_dir(cfg)
    page = on_page(store)
    for it in sorted(page, key=lambda v: v["published_at"]):  # códigos para los que no tengan
        if not it.get("code"):
            store.assign_code(it["id"])
    done = 0
    for it in page:
        if done >= MAX_BACKFILL:
            break
        if not _complete(it, md):
            it["cards"] = make_media(it, cfg, http)
            done += 1

    feed = {"updated": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "web_url": cfg.web_url, "items": []}
    for it in page:
        m, copy, p = it.get("cards") or {}, it.get("copy") or {}, Store.product(it)
        files = []
        for key, sub, name, mime in (("square", "cards", "facebook.jpg", "image/jpeg"),
                                     ("vertical", "cards", "tiktok.jpg", "image/jpeg"),
                                     ("video", "video", "tiktok.mp4", "video/mp4"),
                                     ("text", "texts", "textos.txt", "text/plain")):
            if m.get(key):
                files.append({"url": f"media/{sub}/{m[key]}", "name": name, "mime": mime})
        feed["items"].append({
            "id": p.id, "code": it.get("code", 0), "title": p.title, "price": p.price, "discount": p.discount_pct,
            "link": it.get("affiliate_link", ""), "folder": folder_for(it),
            "square": f"media/cards/{m['square']}" if m.get("square") else "",
            "files": files,
            "facebook": copy.get("facebook", ""), "tiktok_caption": copy.get("tiktok_caption", ""),
            "whatsapp": copy.get("whatsapp", ""), "published_at": it["published_at"],
        })
    md.mkdir(parents=True, exist_ok=True)
    (md / "feed.json").write_text(json.dumps(feed, ensure_ascii=False, indent=1), encoding="utf-8")
    _prune(md, {it["id"] for it in page})
    return feed


def _prune(md: Path, keep_ids: set[str]) -> None:
    """Borra el material de productos que ya no están en la página."""
    for sub, pat in (("cards", "*.jpg"), ("video", "*.mp4"), ("texts", "*.txt")):
        for f in (md / sub).glob(pat):
            pid = f.stem.rsplit("-", 1)[0] if sub == "cards" else f.stem
            if pid not in keep_ids:
                f.unlink()
