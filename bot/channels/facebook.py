"""Publica en una Página de Facebook con la Graph API oficial."""
from __future__ import annotations

from pathlib import Path

import requests

from ..config import Config
from ..meli import Product

GRAPH = "https://graph.facebook.com/v21.0"


def post(p: Product, text: str, link: str, cfg: Config, image_path=None, http=requests) -> str:
    if not (cfg.fb_page_id and cfg.fb_token):
        raise RuntimeError("Falta FB_PAGE_ID o FB_PAGE_TOKEN")
    if image_path and Path(image_path).exists():
        # tarjeta de oferta generada por el bot (precio, descuento, etc.)
        with open(image_path, "rb") as fh:
            r = http.post(
                f"{GRAPH}/{cfg.fb_page_id}/photos",
                data={"caption": text, "access_token": cfg.fb_token},
                files={"source": (Path(image_path).name, fh, "image/jpeg")},
                timeout=60,
            )
    elif p.image:
        r = http.post(
            f"{GRAPH}/{cfg.fb_page_id}/photos",
            data={"url": p.image, "caption": text, "access_token": cfg.fb_token},
            timeout=40,
        )
    else:
        r = http.post(
            f"{GRAPH}/{cfg.fb_page_id}/feed",
            data={"message": text, "link": link, "access_token": cfg.fb_token},
            timeout=40,
        )
    r.raise_for_status()
    j = r.json()
    return str(j.get("post_id") or j.get("id") or "")
