"""Cliente de la API pública de Mercado Libre y modelo de producto."""
from __future__ import annotations

import time
from dataclasses import asdict, dataclass

import requests

API = "https://api.mercadolibre.com"


@dataclass
class Product:
    id: str
    title: str
    price: float
    original_price: float | None
    image: str
    permalink: str
    sold: int = 0
    seller_level: str = ""

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


def parse_result(r: dict) -> Product | None:
    try:
        price = float(r["price"])
        pid = r["id"]
    except (KeyError, TypeError, ValueError):
        return None
    orig = r.get("original_price")
    thumb = (r.get("thumbnail") or "").replace("http://", "https://").replace("-I.jpg", "-O.jpg")
    level = ((r.get("seller") or {}).get("seller_reputation") or {}).get("level_id") or ""
    return Product(
        id=pid,
        title=r.get("title", ""),
        price=price,
        original_price=float(orig) if orig else None,
        image=thumb,
        permalink=r.get("permalink", ""),
        sold=int(r.get("sold_quantity") or 0),
        seller_level=level,
    )


class MeliClient:
    def __init__(self, client_id: str = "", client_secret: str = "", site: str = "MLM", http=requests):
        self.client_id, self.client_secret, self.site, self.http = client_id, client_secret, site, http
        self._token = ""
        self._exp = 0.0

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

    def search(self, query: str, limit: int = 50) -> list[Product]:
        r = self.http.get(
            f"{API}/sites/{self.site}/search",
            params={"q": query, "limit": limit},
            headers=self._headers(),
            timeout=20,
        )
        r.raise_for_status()
        out = [parse_result(x) for x in r.json().get("results", [])]
        return [p for p in out if p]

    def get_item(self, item_id: str) -> dict:
        r = self.http.get(f"{API}/items/{item_id}", headers=self._headers(), timeout=20)
        r.raise_for_status()
        return r.json()
