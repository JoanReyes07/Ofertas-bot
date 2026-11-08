import csv
import json

from bot import copywriter, links, select
from bot.channels import web
from bot.cli import cmd_fetch, cmd_publish
from bot.config import Config
from bot.meli import BLOCKED_CATEGORIES, MeliClient, Product, best_offer, parse_offer
from bot.store import Store


def prod(i="MLM1", price=219, orig=499, rank=3, level="5_green", title="Cama para perro"):
    """Producto ya armado, como lo devuelve MeliClient.top_sellers."""
    return Product(
        id=i, title=title, price=price, original_price=orig,
        image="https://http2.mlstatic.com/D_x-F.jpg", permalink=f"https://www.mercadolibre.com.mx/p/{i}",
        rank=rank, seller_level=level, item_id=f"{i}000",
    )


def cfg(tmp_path, **kw):
    c = Config(categories=["MLM1574"], data_dir=str(tmp_path / "data"), out_dir=str(tmp_path / "out"),
               docs_dir=str(tmp_path / "docs"), links_csv=str(tmp_path / "links.csv"), inbox_dir=str(tmp_path / "inbox"),
               fb_page_id="1", fb_token="t", web_url="https://ej.com")
    for k, v in kw.items():
        setattr(c, k, v)
    return c


class FakeClient:
    def __init__(self, results, item_price=None):
        self.results, self.item_price = results, item_price

    def top_sellers(self, cat, min_discount=0):
        return list(self.results)

    def current_offer(self, pid):
        return {"price": self.item_price} if self.item_price is not None else None


class FakeResp:
    def __init__(self, data=None, status=200):
        self.data = data or {}
        self.status_code = status

    def raise_for_status(self):
        pass

    def json(self):
        return self.data


class FakeHttp:
    def __init__(self):
        self.calls = []

    def post(self, url, **kw):
        self.calls.append(url)
        return FakeResp({"post_id": "p1"})


class FakeApi:
    """Simula la API de ML con las rutas que usa MeliClient.top_sellers."""

    def __init__(self):
        self.gets = []

    def get(self, url, params=None, **kw):
        path = url.replace("https://api.mercadolibre.com", "")
        self.gets.append(path)
        routes = {
            "/highlights/MLM/category/MLM1574": {"content": [
                {"id": "MLMP1", "type": "PRODUCT"}, {"id": "MLM55", "type": "ITEM"},
                {"id": "MLMP2", "type": "PRODUCT"}, {"id": "MLMP3", "type": "PRODUCT"}]},
            "/products/MLMP1/items": {"results": [
                {"item_id": "I1", "price": 258, "original_price": 399, "seller_id": 7}]},
            "/products/MLMP2/items": {"results": [
                {"item_id": "I2", "price": 100, "original_price": None, "seller_id": 7}]},
            "/products/MLMP1": {"id": "MLMP1", "name": "Ganchos", "pictures": [{"url": "https://img/1.jpg"}]},
            "/users/7": {"seller_reputation": {"level_id": "5_green"}},
        }
        if path in routes:
            return FakeResp(routes[path])
        return FakeResp({}, status=404)  # MLMP3: sin publicaciones activas


def write_link(path, link_for_first):
    rows = list(csv.DictReader(open(path, encoding="utf-8")))
    rows[0]["affiliate_link"] = link_for_first
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=links.COLUMNS)
        w.writeheader()
        w.writerows(rows)
    return rows


def test_parse_and_discount():
    product = {"id": "MLM9", "name": "Set 50 ganchos", "permalink": "",
               "pictures": [{"url": "http://http2.mlstatic.com/D_a-F.jpg"}]}
    offer = best_offer({"results": [{"item_id": "MLM4", "price": 258, "original_price": 399, "seller_id": 7}]})
    p = parse_offer(product, offer, "5_green", rank=2, category="MLM1574")
    assert p.discount_pct == 35.3 and p.image.startswith("https://") and p.item_id == "MLM4"
    assert p.permalink == "https://www.mercadolibre.com.mx/p/MLM9" and p.rank == 2
    assert parse_offer({"id": "x"}, {}) is None
    assert best_offer({"results": []}) is None and best_offer(None) is None


def test_client_top_sellers():
    api = FakeApi()
    c = MeliClient(http=api)
    got = c.top_sellers("MLM1574", min_discount=30)
    assert [(p.id, p.rank, p.seller_level) for p in got] == [("MLMP1", 1, "5_green")]
    assert "/products/MLMP2" not in api.gets  # sin descuento: no pide detalles
    assert not any("MLM55" in g for g in api.gets)  # ITEM ajeno: se salta
    assert c.current_offer("MLMP1")["price"] == 258 and c.current_offer("MLMP3") is None
    assert all(c.top_sellers(b) == [] for b in BLOCKED_CATEGORIES)


def test_filters(tmp_path):
    c = cfg(tmp_path, max_rank=10)
    ps = [prod("A"), prod("B", orig=None), prod("C", rank=15), prod("D", level="3_yellow"),
          prod("E", price=99999, orig=999999), prod("A")]
    got = select.pick(ps, c, set(), 10)
    assert [p.id for p in got] == ["A"]
    assert select.pick(ps, c, {"A"}, 10) == []
    # a igual descuento, gana el más vendido
    ranked = select.pick([prod("X", rank=9), prod("Y", rank=1)], c, set(), 10)
    assert [p.id for p in ranked] == ["Y", "X"]


def test_links_roundtrip(tmp_path):
    c = cfg(tmp_path)
    s = Store(f"{c.data_dir}/state.json")
    s.add_candidates([prod("A"), prod("B")])
    assert links.write_pending(s, c.links_csv) == 2
    rows = list(csv.DictReader(open(c.links_csv, encoding="utf-8")))
    rows[0]["affiliate_link"] = "https://meli.la/abc"
    rows[1]["affiliate_link"] = rows[1]["permalink"]  # enlace normal: se rechaza
    with open(c.links_csv, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=links.COLUMNS)
        w.writeheader()
        w.writerows(rows)
    assert links.import_links(s, c.links_csv) == 1
    assert len(s.with_status("ready")) == 1


def test_copy_fallback_and_validation(tmp_path):
    c = cfg(tmp_path)
    p = prod()
    out = copywriter.generate(p, "https://meli.la/abc", c)  # sin clave: plantilla
    assert "https://meli.la/abc" in out["facebook"] and "$219" in out["whatsapp"]
    assert copywriter.DISCLOSURE in out["facebook"]

    class Bad:  # modelo que olvida el enlace
        def post(self, *a, **k):
            body = {k2: "texto sin datos" for k2 in copywriter.KEYS}
            return FakeResp({"content": [{"text": json.dumps(body)}]})

    c.anthropic_key = "k"
    out = copywriter.generate(p, "https://meli.la/abc", c, http=Bad())
    assert "https://meli.la/abc" in out["whatsapp"]  # cayó a plantilla


def test_full_flow(tmp_path):
    c = cfg(tmp_path)
    client = FakeClient([prod("A"), prod("B", level="1_red")], item_price=219)
    cmd_fetch(c, client)
    s = Store(f"{c.data_dir}/state.json")
    assert list(s.items) == ["A"]
    write_link(c.links_csv, "https://meli.la/abc")
    http = FakeHttp()
    cmd_publish(c, client, http)
    s = Store(f"{c.data_dir}/state.json")
    assert s.items["A"]["status"] == "published" and s.items["A"]["fb_post_id"] == "p1"
    assert "photos" in http.calls[0]
    html = (tmp_path / "docs" / "index.html").read_text(encoding="utf-8")
    assert "https://meli.la/abc" in html and 'rel="sponsored' in html
    assert list((tmp_path / "out" / "whatsapp").glob("*.txt")) and (tmp_path / "out" / "tiktok" / "A.md").exists()
    # segunda corrida no duplica
    cmd_publish(c, client, http)
    assert len(http.calls) == 1


def test_price_changed_is_skipped(tmp_path):
    c = cfg(tmp_path)
    client = FakeClient([prod("A")], item_price=300)
    cmd_fetch(c, client)
    s = Store(f"{c.data_dir}/state.json")
    s.set_link("A", "https://meli.la/abc")
    s.save()
    http = FakeHttp()
    cmd_publish(c, client, http)
    assert Store(f"{c.data_dir}/state.json").items["A"]["status"] == "stale" and not http.calls


def test_no_active_offer_is_skipped(tmp_path):
    c = cfg(tmp_path)
    client = FakeClient([prod("A")], item_price=None)  # producto sin publicaciones activas
    cmd_fetch(c, client)
    s = Store(f"{c.data_dir}/state.json")
    s.set_link("A", "https://meli.la/abc")
    s.save()
    cmd_publish(c, client, FakeHttp())
    assert Store(f"{c.data_dir}/state.json").items["A"]["status"] == "stale"


def test_web_escapes(tmp_path):
    c = cfg(tmp_path)
    p = prod(title="<script>x</script>")
    it = {**p.to_dict(), "affiliate_link": "https://a/b?x=1&y=2"}
    html = web.render([it], c)
    assert "<script>x" not in html and "&lt;script&gt;" in html


def test_inbox_from_app(tmp_path):
    c = cfg(tmp_path)
    client = FakeClient([prod("A"), prod("B")], item_price=219)
    cmd_fetch(c, client)
    inbox = tmp_path / "inbox"
    inbox.mkdir()
    (inbox / "1.json").write_text(json.dumps({"links": {
        "A": "https://meli.la/abc",
        "B": "https://www.mercadolibre.com.mx/p/B",  # enlace normal: se ignora
        "Z": "https://meli.la/zzz",  # producto desconocido: se ignora
    }}), encoding="utf-8")
    (inbox / "2.json").write_text("{roto", encoding="utf-8")
    cmd_fetch(c, client)  # un fetch posterior no pierde el enlace
    s = Store(f"{c.data_dir}/state.json")
    assert s.items["A"]["status"] == "ready" and s.items["B"]["status"] == "candidate"
    assert not list(inbox.glob("*.json"))  # envíos consumidos
    assert "https://meli.la/abc" in (tmp_path / "links.csv").read_text(encoding="utf-8")
    http = FakeHttp()
    cmd_publish(c, client, http)
    assert Store(f"{c.data_dir}/state.json").items["A"]["status"] == "published"


def test_media_per_product(tmp_path):
    from PIL import Image

    from bot import cards

    c = cfg(tmp_path)
    out = cards.make_cards(prod("A"), str(tmp_path / "cards"), "Ofertas", http=FakeHttp())  # sin red
    assert Image.open(tmp_path / "cards" / out["square"]).size == (1080, 1080)
    assert Image.open(tmp_path / "cards" / out["vertical"]).size == (1080, 1920)
    client = FakeClient([prod("A"), prod("B", orig=999)], item_price=219)
    cmd_fetch(c, client)
    s = Store(f"{c.data_dir}/state.json")
    for pid in ("A", "B"):
        s.set_link(pid, f"https://meli.la/{pid}")
    s.save()
    cmd_publish(c, client, FakeHttp())
    docs = tmp_path / "docs"
    feed = json.loads((docs / "media" / "feed.json").read_text(encoding="utf-8"))
    assert len(feed["items"]) == 2
    for it in feed["items"]:
        names = [f["name"] for f in it["files"]]
        assert names == ["facebook.jpg", "tiktok.jpg", "tiktok.mp4", "textos.txt"]
        assert all((docs / f["url"]).exists() for f in it["files"])
        assert it["folder"].endswith(it["id"])
        txt = (docs / it["files"][3]["url"]).read_text(encoding="utf-8")
        assert it["link"] in txt and it["code"] and f"CÓDIGO {it['code']}" in txt  # link directo + código
    assert (docs / "media" / "video" / "A.mp4").stat().st_size > 5000


def test_auto_links(tmp_path):
    assert links.affiliate_url("https://www.mercadolibre.com.mx/p/MLM9", "yo123", "777") == (
        "https://www.mercadolibre.com.mx/p/MLM9?matt_word=yo123&matt_tool=777&forceInApp=true")
    client = FakeClient([prod("A"), prod("B")], item_price=219)
    off = cfg(tmp_path / "off", matt_word="yo123", matt_tool="777")  # apagado: no toca nada
    cmd_fetch(off, client)
    assert not Store(f"{off.data_dir}/state.json").with_status("ready")
    on = cfg(tmp_path / "on", auto_links=True, matt_word="yo123", matt_tool="777")
    cmd_fetch(on, client)
    s = Store(f"{on.data_dir}/state.json")
    assert {i["id"] for i in s.with_status("ready")} == {"A", "B"}
    assert s.items["A"]["affiliate_link"].endswith("matt_word=yo123&matt_tool=777&forceInApp=true")


def test_discard_from_app(tmp_path):
    c = cfg(tmp_path)
    client = FakeClient([prod("A"), prod("B")], item_price=219)
    cmd_fetch(c, client)
    inbox = tmp_path / "inbox"
    inbox.mkdir()
    (inbox / "1.json").write_text(json.dumps({"discard": ["B"], "links": {"A": "https://meli.la/a"}}), encoding="utf-8")
    cmd_fetch(c, client)  # B ya no vuelve aunque siga en los más vendidos
    s = Store(f"{c.data_dir}/state.json")
    assert s.items["B"]["status"] == "discarded" and s.items["A"]["status"] == "ready"
    ids = [r["id"] for r in csv.DictReader(open(tmp_path / "links.csv", encoding="utf-8"))]
    assert "B" not in ids and "A" in ids


def test_facebook_queue_batches(tmp_path):
    """La web publica todo junto; Facebook va de 5 en 5 y respeta la pausa entre tandas."""
    c = cfg(tmp_path, fb_per_run=5)
    ids = [f"M{i}" for i in range(8)]
    client = FakeClient([prod(i) for i in ids], item_price=219)
    s = Store(f"{c.data_dir}/state.json")
    s.add_candidates([prod(i) for i in ids])
    for i in ids:
        s.set_link(i, f"https://meli.la/{i}")
    s.items["OLD"] = {**s.items["M0"], "id": "OLD", "status": "published", "published_at": "2020-01-01T00:00:00+00:00"}
    s.save()
    http = FakeHttp()
    cmd_publish(c, client, http)
    s = Store(f"{c.data_dir}/state.json")
    assert len(s.with_status("published")) == 9 and len(http.calls) == 5  # web: todas; FB: 5
    assert "fb_status" not in s.items["OLD"]  # lo ya publicado antes no entra a la cola
    cmd_publish(c, client, http)  # inmediata: todavía en pausa
    assert len(http.calls) == 5
    s.meta["fb_last_batch"] = "2020-01-01T00:00:00+00:00"
    s.save()
    cmd_publish(c, client, http)  # ya pasó la pausa: manda las 3 restantes
    s = Store(f"{c.data_dir}/state.json")
    assert len(http.calls) == 8 and all(s.items[i]["fb_status"] == "posted" for i in ids)


def test_facebook_queue_expires_old(tmp_path):
    c = cfg(tmp_path)
    client = FakeClient([prod("A")], item_price=219)
    s = Store(f"{c.data_dir}/state.json")
    s.add_candidates([prod("A")])
    s.items["A"].update(status="published", fb_status="queued", published_at="2020-01-01T00:00:00+00:00")
    s.save()
    http = FakeHttp()
    cmd_publish(c, client, http)
    assert not http.calls and Store(f"{c.data_dir}/state.json").items["A"]["fb_status"] == "expired"
