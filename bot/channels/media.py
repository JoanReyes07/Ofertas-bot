"""Material para compartir: tarjetas, video diario y docs/media/feed.json,
que la app lee para los botones "Compartir a TikTok / WhatsApp"."""
from __future__ import annotations

import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from .. import cards, video
from ..config import Config
from ..meli import Product
from ..store import Store

MX = ZoneInfo("America/Mexico_City")
MONTHS = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto",
          "septiembre", "octubre", "noviembre", "diciembre"]
FEED_DAYS = 2  # cuántos días de publicaciones muestra la app
KEEP_VIDEO_DAYS = 7
VIDEO_MAX = 5


def media_dir(cfg: Config) -> Path:
    return Path(cfg.docs_dir) / "media"


def make_cards(p: Product, cfg: Config, http=None) -> dict:
    kw = {"http": http} if http else {}
    try:
        return cards.make_cards(p, str(media_dir(cfg) / "cards"), cfg.site_name, **kw)
    except Exception as e:  # sin tarjeta se publica con la foto original
        print(f"[aviso] no pude generar la tarjeta de {p.id}: {e}", file=sys.stderr)
        return {}


def _mx_day(iso: str) -> str:
    try:
        return datetime.fromisoformat(iso).astimezone(MX).strftime("%Y-%m-%d")
    except ValueError:
        return ""


def day_label(day: str) -> str:
    y, m, d = (int(x) for x in day.split("-"))
    return f"{d} de {MONTHS[m - 1]}"


def video_caption(items: list[dict]) -> str:
    lines = [f"Top {len(items)} ofertas de hoy en Mercado Libre 🔥", ""]
    for i, it in enumerate(items, 1):
        p = Product.from_dict(it)
        off = f" (-{p.discount_pct:.0f}%)" if p.discount_pct else ""
        lines.append(f"{i}. {p.title[:45]} ${p.price:,.0f}{off}")
    lines += ["", "Links en mi perfil 👆 Los precios pueden cambiar.", "#ofertas #mercadolibre #mexico #compras"]
    return "\n".join(lines)


def build(store: Store, cfg: Config, day: str, new_published: int) -> dict:
    """Escribe feed.json y, si hubo publicaciones nuevas, el video del día."""
    md = media_dir(cfg)
    cutoff = datetime.now(timezone.utc) - timedelta(days=FEED_DAYS)
    pub = [v for v in store.with_status("published") if v.get("published_at")]
    pub.sort(key=lambda v: v["published_at"], reverse=True)
    recent = [v for v in pub if datetime.fromisoformat(v["published_at"]) >= cutoff]

    # video del día: los mejores descuentos publicados hoy que tengan tarjeta vertical
    today = [v for v in pub if _mx_day(v["published_at"]) == day and (v.get("cards") or {}).get("vertical")]
    today.sort(key=lambda v: Product.from_dict(v).discount_pct, reverse=True)
    today = today[:VIDEO_MAX]
    video_rel = f"video/{day}.mp4"
    if today and (new_published or not (md / video_rel).exists()):
        try:
            video.build([str(md / "cards" / v["cards"]["vertical"]) for v in today],
                        str(md / video_rel), day_label(day), cfg.web_url)
        except Exception as e:
            print(f"[aviso] no pude generar el video: {e}", file=sys.stderr)

    feed = {
        "updated": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "day": day,
        "web_url": cfg.web_url,
        "video": None,
        "items": [],
    }
    if today and (md / video_rel).exists():
        feed["video"] = {"url": f"media/{video_rel}", "label": day_label(day),
                         "caption": video_caption(today), "count": len(today)}
    for v in recent[:20]:
        p = Product.from_dict(v)
        c, copy = v.get("cards") or {}, v.get("copy") or {}
        feed["items"].append({
            "id": p.id, "title": p.title, "price": p.price, "discount": p.discount_pct,
            "link": v.get("affiliate_link", ""),
            "square": f"media/cards/{c['square']}" if c.get("square") else "",
            "vertical": f"media/cards/{c['vertical']}" if c.get("vertical") else "",
            "whatsapp": copy.get("whatsapp", ""), "facebook": copy.get("facebook", ""),
            "tiktok_caption": copy.get("tiktok_caption", ""),
            "published_at": v["published_at"],
        })
    md.mkdir(parents=True, exist_ok=True)
    (md / "feed.json").write_text(json.dumps(feed, ensure_ascii=False, indent=1), encoding="utf-8")
    _prune(md, {v["id"] for v in recent}, day)
    return feed


def _prune(md: Path, keep_ids: set[str], day: str) -> None:
    """Borra tarjetas de productos viejos y videos de hace más de una semana."""
    for f in (md / "cards").glob("*.jpg"):
        if f.name.rsplit("-", 1)[0] not in keep_ids:
            f.unlink()
    limit = (datetime.fromisoformat(day) - timedelta(days=KEEP_VIDEO_DAYS)).strftime("%Y-%m-%d")
    for f in (md / "video").glob("*.mp4"):
        if f.stem < limit:
            f.unlink()
