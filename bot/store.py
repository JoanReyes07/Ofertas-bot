"""Estado persistente en JSON (se puede versionar en git)."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from .meli import Product


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class Store:
    def __init__(self, path: str):
        self.path = Path(path)
        self.items: dict[str, dict] = {}
        self.meta: dict = {}
        if self.path.exists():
            data = json.loads(self.path.read_text(encoding="utf-8"))
            self.items = data.get("items", {})
            self.meta = data.get("meta", {})

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(
            json.dumps({"meta": self.meta, "items": self.items}, ensure_ascii=False, indent=1), encoding="utf-8"
        )

    def ids(self) -> set[str]:
        return set(self.items)

    @property
    def link_cache(self) -> dict[str, str]:
        """Links de afiliado ya pegados alguna vez, por producto (sobreviven a los reinicios de ofertas)."""
        return self.meta.setdefault("link_cache", {})

    def add_candidates(self, products: list[Product]) -> int:
        n = 0
        for p in products:
            if p.id not in self.items:
                cached = self.link_cache.get(p.id, "")
                self.items[p.id] = {
                    **p.to_dict(),
                    # si ya lo habías enlazado antes, entra listo con el mismo link
                    "status": "ready" if cached else "candidate",
                    "affiliate_link": cached,
                    "added_at": _now(),
                    "published_at": "",
                    "fb_post_id": "",
                }
                n += 1
        return n

    def with_status(self, status: str) -> list[dict]:
        return [v for v in self.items.values() if v["status"] == status]

    def set_link(self, pid: str, link: str) -> bool:
        it = self.items.get(pid)
        if not it or it["status"] not in ("candidate", "ready"):
            return False
        it["affiliate_link"] = link
        it["status"] = "ready"
        self.link_cache[pid] = link
        return True

    def assign_code(self, pid: str) -> int:
        """Código corto y fijo del producto (#12) para buscarlo en la web desde TikTok."""
        it = self.items[pid]
        if not it.get("code"):
            code = int(self.meta.get("next_code", 1))
            it["code"] = code
            self.meta["next_code"] = code + 1
        return it["code"]

    def mark_published(self, pid: str, fb_post_id: str = "") -> None:
        self.assign_code(pid)
        self.items[pid].update(status="published", published_at=_now(), fb_post_id=fb_post_id or "")

    def discard(self, pid: str) -> bool:
        """Descartado a mano desde la app: no se publica ni se vuelve a sugerir."""
        it = self.items.get(pid)
        if not it or it["status"] not in ("candidate", "ready"):
            return False
        it["status"] = "discarded"
        return True

    def mark_stale(self, pid: str) -> None:
        self.items[pid]["status"] = "stale"

    @staticmethod
    def product(it: dict) -> Product:
        return Product.from_dict(it)
