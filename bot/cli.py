"""Comandos: fetch | publish | status | web"""
from __future__ import annotations

import argparse
import sys
from datetime import datetime
from zoneinfo import ZoneInfo

from . import copywriter, links, select
from .channels import facebook, files, web
from .config import Config, load_env
from .meli import MeliClient
from .store import Store


def _store(cfg: Config) -> Store:
    return Store(f"{cfg.data_dir}/state.json")


def _client(cfg: Config) -> MeliClient:
    return MeliClient(cfg.meli_client_id, cfg.meli_client_secret, cfg.meli_site)


def cmd_fetch(cfg: Config, client: MeliClient | None = None) -> None:
    store = _store(cfg)
    got = links.import_links(store, cfg.links_csv)  # no pisar enlaces que ya pegaste
    client = client or _client(cfg)
    found = []
    for cat in cfg.categories:
        try:
            found += client.top_sellers(cat, cfg.min_discount)
        except Exception as e:  # una categoría fallida no detiene las demás
            print(f"[aviso] categoría '{cat}' falló: {e}", file=sys.stderr)
    picks = select.pick(found, cfg, store.ids(), cfg.fetch_limit)
    added = store.add_candidates(picks)
    store.save()
    pending = links.write_pending(store, cfg.links_csv)
    print(f"Enlaces importados: {got} | candidatos nuevos: {added} | pendientes en {cfg.links_csv}: {pending}")


def _still_valid(client: MeliClient, it: dict) -> bool:
    offer = client.current_offer(it["id"])
    if not offer:  # sin publicaciones activas
        return False
    return abs(float(offer["price"]) - it["price"]) <= it["price"] * 0.02


def cmd_publish(cfg: Config, client: MeliClient | None = None, http=None) -> None:
    store = _store(cfg)
    links.import_links(store, cfg.links_csv)
    day = datetime.now(ZoneInfo("America/Mexico_City")).strftime("%Y-%m-%d")
    client = client or _client(cfg)
    kw = {"http": http} if http else {}
    wa_entries, done = [], 0
    for it in store.with_status("ready")[: cfg.publish_limit]:
        p = Store.product(it)
        if cfg.verify_price:
            try:
                if not _still_valid(client, it):
                    store.mark_stale(p.id)
                    print(f"[omitido] {p.id}: cambió el precio o ya no está activo")
                    continue
            except Exception as e:
                print(f"[aviso] no pude verificar {p.id}: {e}", file=sys.stderr)
                continue
        link = it["affiliate_link"]
        copy = copywriter.generate(p, link, cfg, **kw)
        fb_id = ""
        if "facebook" in cfg.channels:
            try:
                fb_id = facebook.post(p, copy["facebook"], link, cfg, **kw)
            except Exception as e:
                print(f"[aviso] Facebook falló para {p.id}: {e}", file=sys.stderr)
        if "whatsapp" in cfg.channels:
            wa_entries.append((p, copy))
        if "tiktok" in cfg.channels:
            files.tiktok(p, copy, cfg.out_dir, cfg.web_url)
        store.mark_published(p.id, fb_id)
        done += 1
    if wa_entries:
        files.whatsapp(wa_entries, cfg.out_dir, day)
    if "web" in cfg.channels:
        web.build(store.items, cfg)
    store.save()
    print(f"Publicadas: {done}")


def cmd_status(cfg: Config) -> None:
    s = _store(cfg)
    for st in ("candidate", "ready", "published", "stale"):
        print(f"{st}: {len(s.with_status(st))}")


def main(argv: list[str] | None = None) -> None:
    load_env()
    ap = argparse.ArgumentParser(prog="bot")
    ap.add_argument("cmd", choices=["fetch", "publish", "status", "web"])
    a = ap.parse_args(argv)
    cfg = Config.from_env()
    if a.cmd == "fetch":
        cmd_fetch(cfg)
    elif a.cmd == "publish":
        cmd_publish(cfg)
    elif a.cmd == "web":
        print(web.build(_store(cfg).items, cfg))
    else:
        cmd_status(cfg)


if __name__ == "__main__":
    main()
