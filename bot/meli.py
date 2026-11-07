"""Cliente de la API de Mercado Libre y modelo de producto.

Con un token client_credentials, /sites/{site}/search y /items/{id} responden 403.
Por eso las ofertas se obtienen de los más vendidos por categoría:
  /highlights/{site}/category/{cat}  -> top 20 (productos de catálogo)
  /products/{id}/items               -> precio, precio original y vendedor del ganador
  /products/{id}                     -> nombre e imagen
  /users/{seller_id}                 -> reputación del vendedor
"""
from __future__ import annotations

import time
from dataclasses import asdict, dataclass

import requests

API = "https://api.mercadolibre.com"
WEB = "https://www.mercadolibre.com.mx"

# Categorías que el programa de afiliados no permite: vehículos, inmuebles y servicios.
BLOCKED_CATEGORIES = {"MLM1743", "MLM1459", "MLM1540"}


@dataclass
class Product:
    id: str  # ID del producto de catálogo (MLM...)
    title: str
    price: float
    original_price: float | None
    image: str
    permalink: str
    rank: int = 0  # posición en los más vendidos de su categoría (1 = el más vendido)
    seller_level: str = ""
    item_id: str = ""  # publicación ganadora dentro del producto
    category: str = ""

    @property
    def discount_pct(self) -> float:
        if self.original_price and self.original_price > self.price:
            return round((1 - self.price / self.original_price) * 100, 1)
        return 0.0

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "Product":
        keys = cls.__dataclass_fields__.keys()
        return cls(**{k: d[k] for k in keys if k in d})


def best_offer(items_json: dict) -> dict | None:
    """Primera publicación activa del producto (la que muestra la página /p/)."""
    for r in (items_json or {}).get("results") or []:
        if r.get("price") is not None:
            return r
    return None


def parse_offer(product: dict, offer: dict, seller_level: str = "", rank: int = 0, category: str = "") -> Product | None:
    try:
        pid = product["id"]
        price = float(offer["price"])
    except (KeyError, TypeError, ValueError):
        return None
    orig = offer.get("original_price")
    pics = product.get("pictures") or []
    image = (pics[0].get("url") or "") if pics else ""
    return Product(
        id=pid,
        title=product.get("name", ""),
        price=price,
        original_price=float(orig) if orig else None,
        image=image.replace("http://", "https://"),
        permalink=product.get("permalink") or f"{WEB}/p/{pid}",
        rank=rank,
        seller_level=seller_level,
        item_id=offer.get("item_id", ""),
        category=category,
    )


class MeliClient:
    def __init__(self, client_id: str = "", client_secret: str = "", site: str = "MLM", http=requests):
        self.client_id, self.client_secret, self.site, self.http = client_id, client_secret, site, http
        self._token = ""
        self._exp = 0.0
        self._sellers: dict[str, str] = {}

    def _headers(self) -> dict:
        if self.client_id and self.client_secret and time.time() > self._exp - 60:
            r = self.http.post(
                f"{API}/oauth/token",
                data={
                    "grant_type": "client_credentials",
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                },
                headers={"accept": "application/json", "content-type": "application/x-www-form-urlencoded"},
                timeout=20,
            )
            r.raise_for_status()
            j = r.json()
            self._token = j["access_token"]
            self._exp = time.time() + int(j.get("expires_in", 21600))
        return {"Authorization": f"Bearer {self._token}"} if self._token else {}

    def _get(self, path: str, **params) -> dict | list | None:
        """GET que devuelve None en 404 (p. ej. producto sin publicaciones activas)."""
        r = self.http.get(f"{API}{path}", params=params or None, headers=self._headers(), timeout=20)
        if r.status_code == 404:
            return None
        r.raise_for_status()
        return r.json()

    def seller_level(self, seller_id) -> str:
        key = str(seller_id or "")
        if not key:
            return ""
        if key not in self._sellers:
            try:
                u = self._get(f"/users/{key}") or {}
                self._sellers[key] = (u.get("seller_reputation") or {}).get("level_id") or ""
            except Exception:
                self._sellers[key] = ""
        return self._sellers[key]

    def top_sellers(self, category: str, min_discount: float = 0.0) -> list[Product]:
        """Más vendidos de una categoría con su oferta actual.

        Descarta temprano los que no llegan a min_discount para ahorrar llamadas.
        """
        if category in BLOCKED_CATEGORIES:
            return []
        hl = self._get(f"/highlights/{self.site}/category/{category}") or {}
        out = []
        for rank, entry in enumerate(hl.get("content") or [], start=1):
            if entry.get("type") != "PRODUCT":
                continue  # ITEM y USER_PRODUCT de otros vendedores responden 403
            pid = entry["id"]
            try:
                offer = best_offer(self._get(f"/products/{pid}/items", limit=1))
                if not offer:
                    continue
                orig = offer.get("original_price")
                if not orig or (1 - float(offer["price"]) / float(orig)) * 100 < min_discount:
                    continue
                product = self._get(f"/products/{pid}") or {}
                p = parse_offer(product, offer, self.seller_level(offer.get("seller_id")), rank, category)
            except Exception:
                continue  # un producto con error no detiene la categoría
            if p:
                out.append(p)
        return out

    def current_offer(self, product_id: str) -> dict | None:
        """Oferta vigente de un producto (para verificar el precio antes de publicar)."""
        return best_offer(self._get(f"/products/{product_id}/items", limit=1))
