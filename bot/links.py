"""CSV de enlaces de afiliado: el bot lo genera, tú pegas el enlace, el bot lo lee."""
from __future__ import annotations

import csv
import json
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


def import_inbox(store: Store, inbox_dir: str) -> int:
    """Lee los envíos de la app (data/inbox/*.json) y los borra al procesarlos.

    Cada envío es un archivo nuevo, así que nunca choca con los cambios del bot
    aunque la app envíe mientras el bot está corriendo.
    Formato: {"links": {"MLM123": "https://meli.la/abc", ...}}
    """
    d = Path(inbox_dir)
    if not d.is_dir():
        return 0
    n = 0
    for f in sorted(d.glob("*.json")):
        try:
            data = json.loads(f.read_text(encoding="utf-8-sig"))
        except (OSError, ValueError):
            print(f"[aviso] envío ilegible, se descarta: {f.name}")
            f.unlink(missing_ok=True)
            continue
        for pid, link in (data.get("links") or {}).items():
            link = str(link or "").strip()
            it = store.items.get(pid)
            if it and link.startswith("http") and link != it.get("permalink") and store.set_link(pid, link):
                n += 1
        f.unlink()
    return n
