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
    Formato: {"links": {"MLM123": "https://meli.la/abc", ...}, "discard": ["MLM456", ...]}
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
        for pid in data.get("discard") or []:
            store.discard(str(pid))
        for pid, link in (data.get("links") or {}).items():
            link = str(link or "").strip()
            it = store.items.get(pid)
            if it and link.startswith("http") and link != it.get("permalink") and store.set_link(pid, link):
                n += 1
        f.unlink()
    return n


def affiliate_url(permalink: str, matt_word: str, matt_tool: str) -> str:
    """Link de afiliado armado: página del producto + tus parámetros de afiliado."""
    from urllib.parse import urlencode, urlsplit, urlunsplit

    u = urlsplit(permalink)
    q = urlencode({"matt_word": matt_word, "matt_tool": matt_tool, "forceInApp": "true"})
    return urlunsplit((u.scheme, u.netloc, u.path, q, ""))


def for_channel(link: str, tag: str) -> str:
    """Cambia la etiqueta (matt_word) de un link armado por la del canal, para que el
    panel de afiliados separe los clics por red. Los meli.la no se pueden cambiar y
    se dejan igual (siguen contando en la etiqueta con que se crearon)."""
    from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

    if not tag or not link or "matt_word=" not in link:
        return link
    u = urlsplit(link)
    q = [(k, tag if k == "matt_word" else v) for k, v in parse_qsl(u.query, keep_blank_values=True)]
    return urlunsplit(u._replace(query=urlencode(q)))


def auto_fill(store: Store, matt_word: str, matt_tool: str) -> int:
    """Pone link de afiliado automático a los candidatos que no tengan uno."""
    n = 0
    for it in store.with_status("candidate"):
        if store.set_link(it["id"], affiliate_url(it["permalink"], matt_word, matt_tool)):
            it["link_auto"] = True
            n += 1
    return n
