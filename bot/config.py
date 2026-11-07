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


@dataclass
class Config:
    meli_client_id: str = ""
    meli_client_secret: str = ""
    meli_site: str = "MLM"
    queries: list[str] = field(default_factory=list)
    min_discount: float = 30.0
    min_sold: int = 50
    min_price: float = 80.0
    max_price: float = 5000.0
    require_green: bool = True
    fetch_limit: int = 10
    publish_limit: int = 5
    verify_price: bool = True
    channels: list[str] = field(default_factory=lambda: ["web", "facebook", "whatsapp", "tiktok"])
    anthropic_key: str = ""
    anthropic_model: str = "claude-haiku-5-5"
    fb_page_id: str = ""
    fb_token: str = ""
    site_name: str = "Ofertas del Día México"
    web_url: str = ""
    data_dir: str = "data"
    out_dir: str = "out"
    docs_dir: str = "docs"
    links_csv: str = "links_pendientes.csv"

    @classmethod
    def from_env(cls) -> "Config":
        e = os.environ.get
        return cls(
            meli_client_id=e("MELI_CLIENT_ID", ""),
            meli_client_secret=e("MELI_CLIENT_SECRET", ""),
            meli_site=e("MELI_SITE", "MLM"),
            queries=_list(
                "QUERIES",
                "audífonos bluetooth,freidora de aire,smartwatch,cama para perro,organizador hogar,lámpara led",
            ),
            min_discount=float(e("MIN_DISCOUNT", "30")),
            min_sold=int(e("MIN_SOLD", "50")),
            min_price=float(e("MIN_PRICE", "80")),
            max_price=float(e("MAX_PRICE", "5000")),
            require_green=_bool("REQUIRE_GREEN", True),
            fetch_limit=int(e("FETCH_LIMIT", "10")),
            publish_limit=int(e("PUBLISH_LIMIT", "5")),
            verify_price=_bool("VERIFY_PRICE", True),
            channels=_list("CHANNELS", "web,facebook,whatsapp,tiktok"),
            anthropic_key=e("ANTHROPIC_API_KEY", ""),
            anthropic_model=e("ANTHROPIC_MODEL", "claude-haiku-5-5"),
            fb_page_id=e("FB_PAGE_ID", ""),
            fb_token=e("FB_PAGE_TOKEN", ""),
            site_name=e("SITE_NAME") or "Ofertas del Día México",
            web_url=e("WEB_URL", ""),
        )
