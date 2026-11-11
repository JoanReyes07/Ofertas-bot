"""Plan de Facebook (acordado con el usuario el 2026-11-09).

- Reels: uno por producto, por tandas (cfg.fb_per_run por corrida, con pausa mínima
  cfg.fb_min_gap_h). Primero los que más se pueden vender.
- Muro: un solo post al día, "Top 5 ofertas de hoy" (mayor descuento).
- Historias: una vez al día, las cfg.fb_stories ofertas que más se pueden vender.

Nada de esto toca la web: la web sigue publicando todo junto.
"""
from __future__ import annotations

import shutil
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable
from zoneinfo import ZoneInfo

import requests

from . import cards, plantillas, video
from .channels import facebook
from .config import Config
from .meli import Product
from .store import Store

TZ = ZoneInfo("America/Mexico_City")
MAX_COMMENT_TRIES = 3


def sales_score(p: Product) -> float:
    """Qué tan probable es que se venda: más vendido en su categoría, descuento
    y precio de compra impulsiva (hasta $1,000, y más aún hasta $500)."""
    s = p.discount_pct
    if p.rank:
        s += max(0, 21 - p.rank) * 2
    if p.price <= 1000:
        s += 15
    if p.price <= 500:
        s += 10
    return s


def hours_since(iso: str) -> float:
    try:
        then = datetime.fromisoformat(iso)
    except (TypeError, ValueError):
        return 1e9
    return (datetime.now(timezone.utc) - then).total_seconds() / 3600


def _warn(msg: str) -> None:
    print(f"[aviso] {msg}", file=sys.stderr)


class _Plan:
    def __init__(self, store: Store, cfg: Config, valid: Callable[[dict], bool], http):
        self.store, self.cfg, self.valid, self.http = store, cfg, valid, http
        self._checked: dict[str, bool] = {}
        self._imgs: dict = {}
        self.tmp = Path(tempfile.mkdtemp(prefix="fb_"))

    # --- utilidades ---
    def ok(self, it: dict) -> bool:
        """¿Sigue vigente la oferta? (se revisa una sola vez por corrida)."""
        pid = it["id"]
        if pid not in self._checked:
            if not self.cfg.verify_price:
                self._checked[pid] = True
            else:
                try:
                    self._checked[pid] = bool(self.valid(it))
                except Exception as e:
                    _warn(f"no pude verificar {pid}: {e}")
                    self._checked[pid] = False
        return self._checked[pid]

    def img(self, p: Product):
        if p.id not in self._imgs:
            self._imgs[p.id] = cards.load_image(p.image, self.http)
        return self._imgs[p.id]

    def recent(self) -> list[dict]:
        return [it for it in self.store.items.values()
                if it.get("status") == "published" and it.get("affiliate_link")
                and hours_since(it.get("published_at", "")) <= self.cfg.fb_max_age_h]

    def web(self) -> str:
        return self.cfg.public_url.rstrip("/")

    def datos(self, it: dict, n: int = 0) -> dict:
        """Marcadores de la plantilla, con el link etiquetado para Facebook."""
        return plantillas.datos(it, self.web(), n, self.cfg.tag("facebook"))

    def web_host(self) -> str:
        """Dominio de la web real (no el link corto: ese pierde el #código)."""
        return self.cfg.web_url.replace("https://", "").replace("http://", "").rstrip("/")

    # --- muro: Top 5 del día ---
    def top5(self, day: str) -> int:
        ranked = sorted(self.recent(), key=lambda it: -Store.product(it).discount_pct)
        picks = []
        for it in ranked:
            if len(picks) == 5:
                break
            if self.ok(it):
                picks.append(it)
        if len(picks) < 5:
            print(f"[facebook] Top 5: solo hay {len(picks)} ofertas vigentes; se intenta en la siguiente corrida")
            return 0
        web = self.web()
        web_text = web.replace("https://", "").replace("http://", "")
        img = cards.render_top5([(Store.product(it), int(it.get("code") or 0)) for it in picks],
                                {it["id"]: self.img(Store.product(it)) for it in picks}, web_text)
        path = self.tmp / "top5.jpg"
        img.save(path, "JPEG", quality=90)
        lista = "\n\n".join(plantillas.texto("top5_linea", **self.datos(it, n))
                            for n, it in enumerate(picks, 1))
        caption = plantillas.texto("top5", int(day.replace("-", "")), lista=lista, web=web)
        try:
            pid = facebook.photo(str(path), caption, self.cfg, http=self.http)
        except Exception as e:
            _warn(f"Facebook Top 5 falló: {e}")
            return 0
        self.store.meta["fb_top5_day"] = day
        self.store.meta["fb_top5"] = {"post_id": pid, "ids": [it["id"] for it in picks]}
        return 1

    # --- historias: las que más se pueden vender ---
    def stories(self, day: str) -> int:
        ranked = sorted(self.recent(), key=lambda it: -sales_score(Store.product(it)))
        sent = 0
        for it in ranked:
            if sent >= self.cfg.fb_stories:
                break
            if not self.ok(it):
                continue
            p, code = Store.product(it), int(it.get("code") or 0)
            boton = plantillas.texto("historia_boton", code, **self.datos(it))
            path = self.tmp / f"story-{p.id}.jpg"
            cards.render(p, self.img(p), self.cfg.site_name, boton, vertical=True, code=code).save(
                path, "JPEG", quality=88)
            try:
                it["fb_story_id"] = facebook.story(str(path), self.cfg, http=self.http)
            except Exception as e:
                _warn(f"Facebook historia falló para {p.id}: {e}")
                break
            sent += 1
        if sent:
            self.store.meta["fb_stories_day"] = day
        return sent

    # --- Reels por tandas ---
    def reels(self) -> int:
        queue = [it for it in self.store.items.values() if it.get("fb_status") == "queued"]
        live = []
        for it in queue:
            if it.get("status") != "published" or hours_since(it.get("published_at", "")) > self.cfg.fb_max_age_h:
                it["fb_status"] = "expired"
            else:
                live.append(it)
        if not live:
            return 0
        last = self.store.meta.get("fb_last_batch", "")
        if last and hours_since(last) < self.cfg.fb_min_gap_h:
            print(f"[facebook] tanda anterior hace menos de {self.cfg.fb_min_gap_h} h; {len(live)} Reels en cola")
            return 0
        live.sort(key=lambda it: -sales_score(Store.product(it)))
        sent = 0
        cierre = plantillas.texto("reel_cierre")
        for it in live:
            if sent >= self.cfg.fb_per_run:
                break
            if not self.ok(it):
                it["fb_status"] = "skipped"
                print(f"[facebook] {it['id']} omitido: cambió el precio o ya no está activo")
                continue
            p, code = Store.product(it), int(it.get("code") or 0)
            d = self.datos(it)
            extra = (plantillas.texto("reel_cierre_web", codigo=code, web=self.web_host())
                     if code and self.web_host() else "")
            mp4 = self.tmp / f"reel-{p.id}.mp4"
            try:
                video.build_reel(p, self.img(p), str(mp4), cierre=cierre, extra=extra)
            except Exception as e:
                _warn(f"no pude generar el Reel de {p.id}: {e}")
                it["fb_status"] = "skipped"
                continue
            audio = video.pick_audio(code)
            if audio:
                try:
                    video.add_audio(str(mp4), str(audio))
                except Exception as e:  # sin audio también sirve
                    _warn(f"no pude agregar el audio al Reel de {p.id}: {e}")
            try:
                vid = facebook.reel(str(mp4), plantillas.texto("reel", code, **d), self.cfg, http=self.http)
            except Exception as e:  # probablemente el token: no seguir insistiendo en esta tanda
                _warn(f"Facebook Reel falló para {p.id}: {e}")
                break
            it.update(fb_status="posted", fb_post_id=vid, fb_reel_id=vid)
            if self.cfg.fb_reel_comment:
                it["fb_comment_tries"] = 0
                self.comment(it)
            sent += 1
        if sent:
            self.store.meta["fb_last_batch"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
        return sent

    def comment(self, it: dict) -> None:
        """Comenta el link en el Reel. Si falla (el Reel aún se procesa), se reintenta en otra corrida."""
        msg = plantillas.texto("reel_comentario", **self.datos(it))
        try:
            facebook.comment(it["fb_reel_id"], msg, self.cfg, http=self.http)
            it.pop("fb_comment_tries", None)
            it["fb_comment"] = "ok"
        except Exception as e:
            it["fb_comment_tries"] = it.get("fb_comment_tries", 0) + 1
            if it["fb_comment_tries"] >= MAX_COMMENT_TRIES:
                it.pop("fb_comment_tries", None)
                it["fb_comment"] = f"falló: {str(e)[:200]}"  # queda registrado en state.json
            _warn(f"no pude comentar el link en el Reel de {it['id']}: {e}")

    def pending_comments(self) -> None:
        for it in self.store.items.values():
            if it.get("fb_reel_id") and "fb_comment_tries" in it and it["fb_comment_tries"] > 0:
                self.comment(it)


def run(store: Store, cfg: Config, valid: Callable[[dict], bool], http=requests) -> dict:
    out = {"reels": 0, "top5": 0, "stories": 0}
    if not (cfg.fb_page_id and cfg.fb_token):
        if any(it.get("fb_status") == "queued" for it in store.items.values()):
            _warn("Facebook en cola pero falta FB_PAGE_ID o FB_PAGE_TOKEN")
        return out
    plan = _Plan(store, cfg, valid, http)
    day = datetime.now(TZ).strftime("%Y-%m-%d")
    try:
        if cfg.fb_top5 and store.meta.get("fb_top5_day") != day:
            out["top5"] = plan.top5(day)
        if cfg.fb_stories > 0 and store.meta.get("fb_stories_day") != day:
            out["stories"] = plan.stories(day)
        if cfg.fb_reel_comment:
            plan.pending_comments()
        out["reels"] = plan.reels()
    finally:
        shutil.rmtree(plan.tmp, ignore_errors=True)
    return out
