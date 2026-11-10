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


def _need(cfg: Config) -> None:
    if not (cfg.fb_page_id and cfg.fb_token):
        raise RuntimeError("Falta FB_PAGE_ID o FB_PAGE_TOKEN")


def _ok(r) -> dict:
    r.raise_for_status()
    j = r.json()
    if isinstance(j, dict) and j.get("error"):
        raise RuntimeError(j["error"].get("message", "error de Facebook"))
    return j


def photo(image_path: str, caption: str, cfg: Config, http=requests) -> str:
    """Foto con texto en el muro (se usa para el Top 5 del día)."""
    _need(cfg)
    with open(image_path, "rb") as fh:
        j = _ok(http.post(f"{GRAPH}/{cfg.fb_page_id}/photos",
                          data={"caption": caption, "access_token": cfg.fb_token},
                          files={"source": (Path(image_path).name, fh, "image/jpeg")}, timeout=60))
    return str(j.get("post_id") or j.get("id") or "")


def story(image_path: str, cfg: Config, http=requests) -> str:
    """Historia con foto: se sube la foto sin publicar y luego se publica como historia."""
    _need(cfg)
    with open(image_path, "rb") as fh:
        j = _ok(http.post(f"{GRAPH}/{cfg.fb_page_id}/photos",
                          data={"published": "false", "access_token": cfg.fb_token},
                          files={"source": (Path(image_path).name, fh, "image/jpeg")}, timeout=60))
    j = _ok(http.post(f"{GRAPH}/{cfg.fb_page_id}/photo_stories",
                      data={"photo_id": j["id"], "access_token": cfg.fb_token}, timeout=60))
    return str(j.get("post_id") or j.get("id") or "")


def reel(video_path: str, description: str, cfg: Config, http=requests) -> str:
    """Reel en 3 pasos (start, subida del archivo, finish). Devuelve el id del video."""
    _need(cfg)
    url = f"{GRAPH}/{cfg.fb_page_id}/video_reels"
    j = _ok(http.post(url, data={"upload_phase": "start", "access_token": cfg.fb_token}, timeout=60))
    vid = j["video_id"]
    up = j.get("upload_url") or f"https://rupload.facebook.com/video-upload/{GRAPH.rsplit('/', 1)[1]}/{vid}"
    data = Path(video_path).read_bytes()
    _ok(http.post(up, headers={"Authorization": f"OAuth {cfg.fb_token}", "offset": "0",
                               "file_size": str(len(data))}, data=data, timeout=300))
    _ok(http.post(url, data={"upload_phase": "finish", "video_id": vid, "video_state": "PUBLISHED",
                             "description": description, "access_token": cfg.fb_token}, timeout=60))
    return str(vid)


def comment(object_id: str, message: str, cfg: Config, http=requests) -> str:
    """Comentario de la Página en su propia publicación (por ejemplo, el link en un Reel)."""
    _need(cfg)
    j = _ok(http.post(f"{GRAPH}/{object_id}/comments",
                      data={"message": message, "access_token": cfg.fb_token}, timeout=40))
    return str(j.get("id") or "")
