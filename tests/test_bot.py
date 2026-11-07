import csv
import json

from bot import copywriter, links, select
from bot.channels import web
from bot.cli import cmd_fetch, cmd_publish
from bot.config import Config
from bot.meli import Product, parse_result
from bot.store import Store


def raw(i="MLM1", price=219, orig=499, sold=5000, level="5_green", title="Cama para perro"):
    return {
        "id": i, "title": title, "price": price, "original_price": orig,
        "thumbnail": "http://http2.mlstatic.com/D_x-I.jpg", "permalink": f"https://x/{i}",
        "sold_quantity": sold, "seller": {"seller_reputation": {"level_id": level}},
    }


def cfg(tmp_path, **kw):
    c = Config(queries=["cama"], data_dir=str(tmp_path / "data"), out_dir=str(tmp_path / "out"),
               docs_dir=str(tmp_path / "docs"), links_csv=str(tmp_path / "links.csv"),
               fb_page_id="1", fb_token="t", web_url="https://ej.com")
    for k, v in kw.items():
        setattr(c, k, v)
    return c


class FakeClient:
    def __init__(self, results, item_price=None):
        self.results, self.item_price = results, item_price

    def search(self, q, limit=50):
        return [parse_result(r) for r in self.results]

    def get_item(self, i):
        return {"status": "active", "price": self.item_price}


class FakeResp:
    def __init__(self, data=None):
        self.data = data or {}

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


def test_parse_and_discount():
    p = parse_result(raw())
    assert p.discount_pct == 56.1 and p.image.startswith("https://") and p.image.endswith("-O.jpg")
    assert parse_result({"id": "x"}) is None


def test_filters(tmp_path):
    c = cfg(tmp_path)
    ps = [parse_result(raw("A")), parse_result(raw("B", orig=None)), parse_result(raw("C", sold=3)),
          parse_result(raw("D", level="3_yellow")), parse_result(raw("E", price=99999, orig=999999)),
          parse_result(raw("A"))]
    got = select.pick(ps, c, set(), 10)
    assert [p.id for p in got] == ["A"]
    assert select.pick(ps, c, {"A"}, 10) == []


def test_links_roundtrip(tmp_path):
    c = cfg(tmp_path)
    s = Store(f"{c.data_dir}/state.json")
    s.add_candidates([parse_result(raw("A")), parse_result(raw("B"))])
    assert links.write_pending(s, c.links_csv) == 2
    rows = list(csv.DictReader(open(c.links_csv, encoding="utf-8")))
    rows[0]["affiliate_link"] = "https://meli.la/abc"
    rows[1]["affiliate_link"] = rows[1]["permalink"]  # enlace normal: se rechaza
    with open(c.links_csv, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=links.COLUMNS)
        w.writeheader(); w.writerows(rows)
    assert links.import_links(s, c.links_csv) == 1
    assert len(s.with_status("ready")) == 1


def test_copy_fallback_and_validation(tmp_path):
    c = cfg(tmp_path)
    p = parse_result(raw())
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
    client = FakeClient([raw("A"), raw("B", level="1_red")], item_price=219)
    cmd_fetch(c, client)
    s = Store(f"{c.data_dir}/state.json")
    assert list(s.items) == ["A"]
    rows = list(csv.DictReader(open(c.links_csv, encoding="utf-8")))
    rows[0]["affiliate_link"] = "https://meli.la/abc"
    with open(c.links_csv, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=links.COLUMNS)
        w.writeheader(); w.writerows(rows)
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
    client = FakeClient([raw("A")], item_price=300)
    cmd_fetch(c, client)
    s = Store(f"{c.data_dir}/state.json")
    s.set_link("A", "https://meli.la/abc"); s.save()
    http = FakeHttp()
    cmd_publish(c, client, http)
    assert Store(f"{c.data_dir}/state.json").items["A"]["status"] == "stale" and not http.calls


def test_web_escapes(tmp_path):
    c = cfg(tmp_path)
    p = parse_result(raw(title="<script>x</script>"))
    it = {**p.to_dict(), "affiliate_link": "https://a/b?x=1&y=2"}
    html = web.render([it], c)
    assert "<script>x" not in html and "&lt;script&gt;" in html
