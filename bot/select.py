"""Filtro y ranking de ofertas."""
from __future__ import annotations

import math

from .config import Config
from .meli import Product


def is_good(p: Product, cfg: Config) -> bool:
    if p.discount_pct < cfg.min_discount:
        return False
    if p.sold < cfg.min_sold:
        return False
    if not (cfg.min_price <= p.price <= cfg.max_price):
        return False
    if not p.permalink or not p.image:
        return False
    # Si la API trae la reputación, exigimos verde; si no la trae, no descartamos.
    if cfg.require_green and p.seller_level and "green" not in p.seller_level:
        return False
    return True


def score(p: Product) -> float:
    return p.discount_pct * math.log1p(p.sold)


def pick(products: list[Product], cfg: Config, known_ids: set[str], limit: int) -> list[Product]:
    seen: dict[str, Product] = {}
    for p in products:
        if p.id in known_ids or p.id in seen or not is_good(p, cfg):
            continue
        seen[p.id] = p
    return sorted(seen.values(), key=score, reverse=True)[:limit]
