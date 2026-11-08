"""Comandos: fetch | publish | status | web | media | fbcheck"""
from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from . import copywriter, links, select
from .channels import facebook, files, media, web
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
    got += links.import_inbox(store, cfg.inbox_dir)
    client = client or _client(cfg)
    found = []
    for cat in cfg.categories:
        try:
            found += client.top_sellers(cat, cfg.min_discount)
        except Exception as e:  # una categoría fallida no detiene las demás
            print(f"[aviso] categoría '{cat}' falló: {e}", file=sys.stderr)
    picks = select.pick(found, cfg, store.ids(), cfg.fetch_limit)
    added = store.add_candidates(picks)
    if cfg.auto_links and cfg.matt_word and cfg.matt_tool:
        got += links.auto_fill(store, cfg.matt_word, cfg.matt_tool)
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
    links.import_inbox(store, cfg.inbox_dir)
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
        code = store.assign_code(p.id)
        copy = copywriter.generate(p, link, cfg, code=code, **kw)
        store.items[p.id]["copy"] = copy
        card = media.make_media(store.items[p.id], cfg, http)  # tarjetas, video y textos
        store.items[p.id]["cards"] = card
        if "whatsapp" in cfg.channels:
            wa_entries.append((p, copy))
        if "tiktok" in cfg.channels:
            files.tiktok(p, copy, cfg.out_dir, cfg.web_url)
        store.mark_published(p.id)
        if "facebook" in cfg.channels:
            store.items[p.id]["fb_status"] = "queued"  # se manda después, por tandas
        done += 1
    if wa_entries:
        files.whatsapp(wa_entries, cfg.out_dir, day)
    if "web" in cfg.channels:
        web.build(store.items, cfg)
    media.build(store, cfg, http)
    fb = _facebook_queue(store, cfg, client, kw) if "facebook" in cfg.channels else 0
    store.save()
    print(f"Publicadas: {done} | Facebook: {fb}")


def _hours_since(iso: str) -> float:
    try:
        then = datetime.fromisoformat(iso)
    except (TypeError, ValueError):
        return 1e9
    return (datetime.now(timezone.utc) - then).total_seconds() / 3600


def _facebook_queue(store: Store, cfg: Config, client: MeliClient, kw: dict) -> int:
    """Manda a la Página una tanda pequeña de la cola (las más viejas primero)."""
    queue = sorted((it for it in store.items.values() if it.get("fb_status") == "queued"),
                   key=lambda it: it.get("published_at", ""))
    if not queue:
        return 0
    if not (cfg.fb_page_id and cfg.fb_token):
        print("[aviso] Facebook en cola pero falta FB_PAGE_ID o FB_PAGE_TOKEN", file=sys.stderr)
        return 0
    last = store.meta.get("fb_last_batch", "")
    if last and _hours_since(last) < cfg.fb_min_gap_h:
        print(f"[facebook] tanda anterior hace menos de {cfg.fb_min_gap_h} h; {len(queue)} en cola")
        return 0
    sent = 0
    for it in queue:
        if sent >= cfg.fb_per_run:
            break
        if it["status"] != "published" or _hours_since(it.get("published_at", "")) > cfg.fb_max_age_h:
            it["fb_status"] = "expired"
            continue
        if cfg.verify_price:
            try:
                if not _still_valid(client, it):
                    it["fb_status"] = "skipped"
                    print(f"[facebook] {it['id']} omitido: cambió el precio o ya no está activo")
                    continue
            except Exception as e:
                print(f"[aviso] no pude verificar {it['id']}: {e}", file=sys.stderr)
                continue
        card = it.get("cards") or {}
        sq = media.media_dir(cfg) / "cards" / card["square"] if card.get("square") else None
        text = (it.get("copy") or {}).get("facebook", "")
        try:
            it["fb_post_id"] = facebook.post(Store.product(it), text, it["affiliate_link"], cfg, image_path=sq, **kw)
        except Exception as e:  # probablemente el token: no seguir insistiendo en esta tanda
            print(f"[aviso] Facebook falló para {it['id']}: {e}", file=sys.stderr)
            break
        it["fb_status"] = "posted"
        sent += 1
    if sent:
        store.meta["fb_last_batch"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    return sent


def cmd_fbcheck(cfg: Config, http=None) -> None:
    """Revisa el token de la Página sin publicar nada."""
    http = http or __import__("requests")
    if not (cfg.fb_page_id and cfg.fb_token):
        sys.exit("Falta FB_PAGE_ID o FB_PAGE_TOKEN")
    me = http.get(f"{facebook.GRAPH}/me", params={"fields": "id,name", "access_token": cfg.fb_token}, timeout=30).json()
    if "error" in me:
        sys.exit(f"Token inválido: {me['error'].get('message')}")
    print(f"Token de: {me.get('name')} ({me.get('id')})")
    ok = me.get("id") == cfg.fb_page_id
    print("Coincide con FB_PAGE_ID: " + ("sí" if ok else "NO, revisa el secret"))
    d = http.get(f"{facebook.GRAPH}/debug_token",
                 params={"input_token": cfg.fb_token, "access_token": cfg.fb_token}, timeout=30).json().get("data", {})
    if d:
        exp = d.get("expires_at", 0)
        print("Caduca: " + ("nunca" if not exp else datetime.fromtimestamp(exp, timezone.utc).isoformat()))
        scopes = set(d.get("scopes", []))
        need = {"pages_manage_posts", "pages_read_engagement", "pages_show_list"}
        print("Permisos faltantes: " + (", ".join(sorted(need - scopes)) or "ninguno"))
    if not ok:
        sys.exit(1)


def cmd_media(cfg: Config) -> None:
    """Regenera todo el material (tarjetas, videos, textos) de los productos de la página."""
    store = _store(cfg)
    for it in media.on_page(store):
        it["cards"], it["copy"] = {}, {}  # forzar regeneración (textos incluidos)
    media.MAX_BACKFILL = 10**6
    feed = media.build(store, cfg)
    store.save()
    print(f"Productos con material: {len(feed['items'])}")


def cmd_status(cfg: Config) -> None:
    s = _store(cfg)
    for st in ("candidate", "ready", "published", "stale"):
        print(f"{st}: {len(s.with_status(st))}")


def main(argv: list[str] | None = None) -> None:
    load_env()
    ap = argparse.ArgumentParser(prog="bot")
    ap.add_argument("cmd", choices=["fetch", "publish", "status", "web", "media", "fbcheck"])
    a = ap.parse_args(argv)
    cfg = Config.from_env()
    if a.cmd == "fetch":
        cmd_fetch(cfg)
    elif a.cmd == "publish":
        cmd_publish(cfg)
    elif a.cmd == "media":
        cmd_media(cfg)
    elif a.cmd == "fbcheck":
        cmd_fbcheck(cfg)
    elif a.cmd == "web":
        print(web.build(_store(cfg).items, cfg))
    else:
        cmd_status(cfg)


if __name__ == "__main__":
    main()
