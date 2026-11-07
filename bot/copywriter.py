"""Textos por canal. Claude redacta; si falla o inventa, se usa una plantilla."""
from __future__ import annotations

import json

import requests

from .config import Config
from .meli import Product

DISCLOSURE = "Enlace de afiliado: puedo ganar una comisión sin costo extra para ti."
KEYS = ("facebook", "whatsapp", "tiktok_script", "tiktok_caption", "web_blurb")


def money(x: float) -> str:
    return f"${x:,.0f}"


def fallback(p: Product, link: str) -> dict:
    old = f" (antes {money(p.original_price)})" if p.original_price else ""
    off = f" {p.discount_pct:.0f}% de descuento." if p.discount_pct else ""
    return {
        "facebook": f"🔥 {p.title}\nHoy en {money(p.price)}{old}.{off}\nVer oferta 👉 {link}",
        "whatsapp": f"🔥 *{p.title}*\n{money(p.price)}{old}\n{off.strip()}\n👉 {link}".replace("\n\n", "\n"),
        "tiktok_script": (
            f"GANCHO (0-3s): ¿Sabías que este producto está al {p.discount_pct:.0f}% menos?\n"
            f"CUERPO (3-15s): {p.title}. Hoy cuesta {money(p.price)}{old}.\n"
            "CIERRE (15-20s): El enlace está en mi perfil. Los precios cambian, corre."
        ),
        "tiktok_caption": f"{p.title[:90]} a {money(p.price)} 🔥 Enlace en mi perfil #ofertas #mercadolibre #mexico",
        "web_blurb": f"{p.title}. Precio actual {money(p.price)}{old}.",
    }


def _prompt(p: Product, link: str) -> str:
    facts = {
        "titulo": p.title,
        "precio_actual": money(p.price),
        "precio_anterior": money(p.original_price) if p.original_price else None,
        "descuento_pct": p.discount_pct,
        "vendidos": p.sold,
        "enlace": link,
    }
    return (
        "Eres redactor de ofertas para público de México. Español neutro mexicano, tono cercano, sin exagerar.\n"
        "USA SOLO los datos dados. NO inventes especificaciones, marcas, envío gratis, stock, calificaciones, "
        "garantías ni urgencia falsa. No digas 'últimas piezas' ni similares.\n"
        f"DATOS: {json.dumps(facts, ensure_ascii=False)}\n"
        "Responde SOLO un JSON con claves: facebook (post corto con emojis, incluye el enlace exacto y el precio), "
        "whatsapp (mensaje breve, *negritas* con asteriscos, incluye el enlace exacto y el precio), "
        "tiktok_script (guion de 20s: GANCHO, CUERPO, CIERRE; el cierre dice que el enlace está en el perfil, "
        "sin URL), tiktok_caption (máx 150 caracteres con 3 hashtags), web_blurb (1-2 frases)."
    )


def _valid(c: dict, p: Product, link: str) -> bool:
    if not all(isinstance(c.get(k), str) and c[k].strip() for k in KEYS):
        return False
    for k in ("facebook", "whatsapp"):
        if link not in c[k] or money(p.price) not in c[k]:
            return False
    return "http" not in c["tiktok_script"]


def generate(p: Product, link: str, cfg: Config, http=requests) -> dict:
    copy = None
    if cfg.anthropic_key:
        try:
            r = http.post(
                "https://api.anthropic.com/v1/messages",
                headers={
                    "x-api-key": cfg.anthropic_key,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json",
                },
                json={
                    "model": cfg.anthropic_model,
                    "max_tokens": 900,
                    "messages": [{"role": "user", "content": _prompt(p, link)}],
                },
                timeout=40,
            )
            r.raise_for_status()
            text = r.json()["content"][0]["text"]
            copy = json.loads(text[text.index("{") : text.rindex("}") + 1])
        except Exception:
            copy = None
    if not copy or not _valid(copy, p, link):
        copy = fallback(p, link)
    copy = {k: copy[k].strip() for k in KEYS}
    copy["facebook"] += f"\n\n{DISCLOSURE}"
    copy["whatsapp"] += f"\n_{DISCLOSURE}_"
    return copy
