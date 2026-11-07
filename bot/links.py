"""CSV de enlaces de afiliado: el bot lo genera, tú pegas el enlace, el bot lo lee."""
from __future__ import annotations

import csv
from pathlib import Path

from .store import Store

COLUMNS = ["id", "title", "price", "descuento_pct", "permalink", "affiliate_link"]


def write_pending(store: Store, path: str) -> int:
    rows = store.with_status("candidate") + store.with_status("ready")
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(COLUMNS)
        for it in rows:
            p = Store.product(it)
            w.writerow([p.id, p.title, f"{p.price:.0f}", p.discount_pct, p.permalink, it.get("affiliate_link", "")])
    return len(rows)


def import_links(store: Store, path: str) -> int:
    p = Path(path)
    if not p.exists():
        return 0
    n = 0
    with open(p, newline="", encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            link = (row.get("affiliate_link") or "").strip()
            pid = (row.get("id") or "").strip()
            if pid and link.startswith("http") and link != (row.get("permalink") or "").strip():
                if store.set_link(pid, link):
                    n += 1
    return n
