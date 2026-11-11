"""Configuración leída de variables de entorno / archivo .env."""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path


def load_env(path: str = ".env") -> None:
    p = Path(path)
    if not p.exists():
        return
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def _list(name: str, default: str) -> list[str]:
    raw = os.environ.get(name, "").strip() or default  # variable vacía = usar valor por defecto
    return [x.strip() for x in raw.split(",") if x.strip()]


def _bool(name: str, default: bool) -> bool:
    return os.environ.get(name, str(default)).strip().lower() in ("1", "true", "si", "sí", "yes")


def _tags(raw: str) -> dict:
    """"facebook=cazafb, web=cazaweb" -> {"facebook": "cazafb", "web": "cazaweb"}
    (las palabras sin "=" se ignoran)."""
    import re

    out = {}
    for part in re.split(r"[,;\s]+", raw):  # acepta comas, espacios o saltos de línea
        if "=" in part:
            k, v = part.split("=", 1)
            if k.strip() and v.strip():
                out[k.strip().lower()] = v.strip()
    return out


@dataclass
class Config:
    meli_client_id: str = ""
    meli_client_secret: str = ""
    meli_site: str = "MLM"
    categories: list[str] = field(default_factory=list)
    min_discount: float = 30.0
    max_rank: int = 20
    min_price: float = 80.0
    max_price: float = 5000.0
    require_green: bool = True
    fetch_limit: int = 20
    publish_limit: int = 20  # todas juntas en la web
    # Facebook (2026-11-09): un Reel por producto, por tandas para no saturar la Página;
    # el muro lleva solo el Top 5 del día y las historias las que más se venden.
    fb_per_run: int = 2        # Reels por tanda (4 tandas al día = 8 Reels)
    fb_stories: int = 6        # historias al día (0 = apagado)
    fb_top5: bool = True       # post "Top 5 del día" en el muro
    fb_reel_comment: bool = True  # además del link en la descripción, comentarlo en el Reel
    short_url: str = ""        # link corto de la web que se muestra al público (sin .github.io)
    fb_min_gap_h: float = 2.5  # horas mínimas entre tandas (la app también lanza publish)
    fb_max_age_h: float = 24.0  # más viejas que esto ya no se mandan (la oferta pudo terminar)
    verify_price: bool = True
    channels: list[str] = field(default_factory=lambda: ["web", "facebook", "whatsapp", "tiktok"])
    anthropic_key: str = ""
    anthropic_model: str = "claude-haiku-5-5"
    fb_page_id: str = ""
    fb_token: str = ""
    site_name: str = "Cazaofertas MX"
    web_url: str = ""
    data_dir: str = "data"
    out_dir: str = "out"
    docs_dir: str = "docs"
    links_csv: str = "links_pendientes.csv"
    # Links de afiliado automáticos (apagado hasta confirmar que Mercado Libre cuenta los clics)
    auto_links: bool = False
    matt_word: str = ""
    matt_tool: str = ""
    # Etiqueta por canal (MELI_TAGS="facebook=cazafb,web=cazaweb,whatsapp=cazawa").
    # Cada etiqueta debe existir antes en el panel de afiliados (Etiquetas de seguimiento).
    channel_tags: dict = field(default_factory=dict)
    inbox_dir: str = "data/inbox"

    def tag(self, channel: str) -> str:
        return self.channel_tags.get(channel, "")

    @property
    def public_url(self) -> str:
        """Link de la web que ve la gente: el corto si existe."""
        return self.short_url or self.web_url

    @classmethod
    def from_env(cls) -> "Config":
        e = os.environ.get
        return cls(
            meli_client_id=e("MELI_CLIENT_ID", ""),
            meli_client_secret=e("MELI_CLIENT_SECRET", ""),
            meli_site=e("MELI_SITE", "MLM"),
            # Hogar, Electrónica, Electrodomésticos, Belleza, Mascotas, Deportes, Juguetes
            categories=_list("CATEGORIES", "MLM1574,MLM1000,MLM1575,MLM1246,MLM1071,MLM1276,MLM1132"),
            min_discount=float(e("MIN_DISCOUNT", "30")),
            max_rank=int(e("MAX_RANK", "20")),
            min_price=float(e("MIN_PRICE", "80")),
            max_price=float(e("MAX_PRICE", "5000")),
            require_green=_bool("REQUIRE_GREEN", True),
            fetch_limit=int(e("FETCH_LIMIT", "20")),
            publish_limit=int(e("PUBLISH_LIMIT", "20")),
            fb_per_run=int(e("FB_PER_RUN", "") or 2),
            fb_stories=int(e("FB_STORIES", "") or 6),
            fb_top5=_bool("FB_TOP5", True),
            fb_reel_comment=_bool("FB_REEL_COMMENT", True),
            short_url=e("SHORT_URL", "").strip(),
            fb_min_gap_h=float(e("FB_MIN_GAP_H", "2.5")),
            fb_max_age_h=float(e("FB_MAX_AGE_H", "24")),
            verify_price=_bool("VERIFY_PRICE", True),
            channels=_list("CHANNELS", "web,facebook,whatsapp,tiktok"),
            anthropic_key=e("ANTHROPIC_API_KEY", ""),
            anthropic_model=e("ANTHROPIC_MODEL", "claude-haiku-5-5"),
            fb_page_id=e("FB_PAGE_ID", ""),
            fb_token=e("FB_PAGE_TOKEN", ""),
            site_name=e("SITE_NAME") or "Cazaofertas MX",
            web_url=e("WEB_URL", ""),
            auto_links=_bool("AUTO_LINKS", False),
            matt_word=e("MELI_MATT_WORD", "").strip(),
            matt_tool=e("MELI_MATT_TOOL", "").strip(),
            channel_tags=_tags(e("MELI_TAGS", "")),
        )
