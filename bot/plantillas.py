"""Plantillas de texto de Facebook (bot/plantillas.json).

Cada clave puede ser un texto o una lista; con lista se elige una según `semilla`
(por ejemplo, el código del producto) para que no salgan todas iguales.
"""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from .links import for_channel
from .meli import Product

ARCHIVO = Path(__file__).parent / "plantillas.json"


@lru_cache(maxsize=1)
def _cargar() -> dict:
    return json.loads(ARCHIVO.read_text(encoding="utf-8"))


def money(x: float) -> str:
    return f"${x:,.0f}"


def corto(title: str, n: int = 45) -> str:
    return title if len(title) <= n else title[: n - 1].rsplit(" ", 1)[0] + "…"


def datos(it: dict, web: str = "", n: int = 0, tag: str = "") -> dict:
    """Marcadores disponibles para un producto guardado en state.json."""
    p = Product.from_dict(it)
    return {
        "n": n, "titulo": p.title, "titulo_corto": corto(p.title), "precio": money(p.price),
        "antes": money(p.original_price or p.price), "pct": f"{p.discount_pct:.0f}",
        "codigo": it.get("code", ""), "link": for_channel(it.get("affiliate_link", ""), tag), "web": web,
    }


def texto(clave: str, semilla: int = 0, **valores) -> str:
    t = _cargar()[clave]
    if isinstance(t, list):
        t = t[int(semilla or 0) % len(t)]
    return t.format(**valores)
