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
        if self.path.exists():
            self.items = json.loads(self.path.read_text(encoding="utf-8")).get("items", {})

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(
            json.dumps({"items": self.items}, ensure_ascii=False, indent=1), encoding="utf-8"
        )

    def ids(self) -> set[str]:
        return set(self.items)

    def add_candidates(self, products: list[Product]) -> int:
        n = 0
        for p in products:
            if p.id not in self.items:
                self.items[p.id] = {
                    **p.to_dict(),
                    "status": "candidate",
                    "affiliate_link": "",
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
        return True

    def mark_published(self, pid: str, fb_post_id: str = "") -> None:
        self.items[pid].update(status="published", published_at=_now(), fb_post_id=fb_post_id or "")

    def mark_stale(self, pid: str) -> None:
        self.items[pid]["status"] = "stale"

    @staticmethod
    def product(it: dict) -> Product:
        return Product.from_dict(it)
