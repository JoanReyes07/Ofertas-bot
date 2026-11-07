"""Tarjetas de oferta tipo anuncio (Pillow).

- cuadrada 1080x1080: Facebook y WhatsApp
- vertical 1080x1920: TikTok (y cuadros del video diario)
"""
from __future__ import annotations

import io
from pathlib import Path

import requests
from PIL import Image, ImageDraw, ImageFont, ImageOps

from .meli import Product

FONTS = Path(__file__).parent / "assets" / "fonts"
YELLOW = (255, 230, 0)
NAVY = (45, 50, 119)
INK = (29, 29, 31)
MUTED = (120, 124, 135)
GREEN = (0, 166, 80)
RED = (232, 35, 52)
WHITE = (255, 255, 255)
BG = (245, 246, 250)

CATEGORY_NAMES = {
    "MLM1574": "Hogar", "MLM1000": "Electrónica", "MLM1575": "Electrodomésticos",
    "MLM1246": "Belleza", "MLM1071": "Mascotas", "MLM1276": "Deportes", "MLM1132": "Juguetes",
    "MLM1648": "Computación", "MLM1051": "Celulares", "MLM1144": "Videojuegos",
    "MLM1430": "Ropa y calzado", "MLM186863": "Herramientas", "MLM1384": "Bebés",
    "MLM1039": "Cámaras", "MLM3937": "Joyas y relojes", "MLM1403": "Alimentos y bebidas",
    "MLM1368": "Papelería", "MLM187772": "Salud",
}


def font(weight: str, size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(str(FONTS / f"Poppins-{weight}.ttf"), size)


def money(x: float) -> str:
    return f"${x:,.0f}"


def load_image(url: str, http=requests) -> Image.Image | None:
    if not url:
        return None
    # Mercado Libre: "-O" es la imagen original (más grande que "-F" o "-I")
    for u in dict.fromkeys([url.replace("-F.", "-O.").replace("-I.", "-O."), url]):
        img = _download(u, http)
        if img is not None:
            return img
    return None


def _download(url: str, http) -> Image.Image | None:
    try:
        r = http.get(url, timeout=30)
        r.raise_for_status()
        return Image.open(io.BytesIO(r.content)).convert("RGB")
    except Exception:
        return None


def wrap(draw: ImageDraw.ImageDraw, text: str, f: ImageFont.FreeTypeFont, width: int, max_lines: int) -> list[str]:
    words, lines, cur = text.split(), [], ""
    for w in words:
        test = f"{cur} {w}".strip()
        if draw.textlength(test, font=f) <= width:
            cur = test
            continue
        if cur:
            lines.append(cur)
        cur = w
        if len(lines) == max_lines:
            break
    if cur and len(lines) < max_lines:
        lines.append(cur)
    if len(lines) == max_lines and " ".join(lines) != " ".join(words):
        last = lines[-1]
        while last and draw.textlength(last + "…", font=f) > width:
            last = last[:-1].rstrip()
        lines[-1] = last + "…"
    return lines


def _paste_product(canvas: Image.Image, img: Image.Image | None, box: tuple[int, int, int, int]) -> None:
    x0, y0, x1, y1 = box
    d = ImageDraw.Draw(canvas)
    d.rounded_rectangle(box, radius=36, fill=WHITE)
    if img is None:
        return
    pad = 40
    fitted = ImageOps.contain(img, (x1 - x0 - 2 * pad, y1 - y0 - 2 * pad), Image.LANCZOS)
    canvas.paste(fitted, (x0 + (x1 - x0 - fitted.width) // 2, y0 + (y1 - y0 - fitted.height) // 2))


def _badge(canvas: Image.Image, pct: float, center: tuple[int, int], r: int) -> None:
    d = ImageDraw.Draw(canvas)
    cx, cy = center
    d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=RED)
    d.text((cx, cy - r * 0.12), f"-{pct:.0f}%", font=font("ExtraBold", int(r * 0.62)), fill=WHITE, anchor="mm")
    d.text((cx, cy + r * 0.42), "OFF", font=font("Bold", int(r * 0.28)), fill=WHITE, anchor="mm")


def _price_block(d: ImageDraw.ImageDraw, p: Product, x: int, y: int, big: int) -> int:
    """Precio actual grande y, a su derecha, el anterior tachado. Devuelve la y final."""
    f_new = font("ExtraBold", big)
    base = y + int(big * 0.78)  # línea base del texto
    d.text((x, base), money(p.price), font=f_new, fill=INK, anchor="ls")
    if p.original_price and p.original_price > p.price:
        f_old = font("Medium", int(big * 0.4))
        old = money(p.original_price)
        ox = x + d.textlength(money(p.price), font=f_new) + big * 0.28
        d.text((ox, base), old, font=f_old, fill=MUTED, anchor="ls")
        w = d.textlength(old, font=f_old)
        mid = base - int(big * 0.4 * 0.36)
        d.line([(ox - 4, mid), (ox + w + 4, mid)], fill=MUTED, width=max(3, big // 28))
    return base + int(big * 0.3)


def render(p: Product, img: Image.Image | None, site_name: str, cta: str, vertical: bool = False) -> Image.Image:
    W, H = (1080, 1920) if vertical else (1080, 1080)
    c = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(c)

    # franja superior
    band = 150 if vertical else 110
    d.rectangle([0, 0, W, band], fill=YELLOW)
    d.text((W // 2, band // 2), site_name.upper(), font=font("ExtraBold", 52 if vertical else 44), fill=NAVY, anchor="mm")

    m = 48
    if vertical:
        img_box = (m, band + 60, W - m, band + 60 + 900)
        title_y, title_size, big = img_box[3] + 50, 58, 150
    else:
        img_box = (m, band + 30, W - m, band + 30 + 470)
        title_y, title_size, big = img_box[3] + 22, 40, 100
    _paste_product(c, img, img_box)
    if p.discount_pct:
        r = 120 if vertical else 86
        _badge(c, p.discount_pct, (img_box[2] - r + 10, img_box[1] + r - 10), r)

    f_title = font("SemiBold", title_size)
    for line in wrap(d, p.title, f_title, W - 2 * m, 2):
        d.text((m, title_y), line, font=f_title, fill=INK)
        title_y += int(title_size * 1.3)

    y = _price_block(d, p, m, title_y + 4, big) + (40 if vertical else 18)

    # etiqueta de popularidad
    if p.rank:
        cat = CATEGORY_NAMES.get(p.category, "su categoría")
        tag = f"#{p.rank} más vendido en {cat}"
        f_tag = font("Bold", 36 if vertical else 30)
        tw = d.textlength(tag, font=f_tag)
        th = 64 if vertical else 54
        d.rounded_rectangle([m, y, m + tw + 44, y + th], radius=th // 2, fill=GREEN)
        d.text((m + 22, y + th // 2), tag, font=f_tag, fill=WHITE, anchor="lm")

    # llamada a la acción
    fh = 130 if vertical else 96
    d.rectangle([0, H - fh, W, H], fill=NAVY)
    d.text((W // 2, H - fh // 2), cta, font=font("Bold", 46 if vertical else 38), fill=YELLOW, anchor="mm")
    return c


def make_cards(p: Product, out_dir: str, site_name: str, http=requests) -> dict:
    """Genera las dos tarjetas de un producto. Devuelve rutas relativas a out_dir."""
    d = Path(out_dir)
    d.mkdir(parents=True, exist_ok=True)
    img = load_image(p.image, http)
    sq = render(p, img, site_name, "Toca el link de la descripción")
    vt = render(p, img, site_name, "Link en la descripción", vertical=True)
    sq_path, vt_path = d / f"{p.id}-sq.jpg", d / f"{p.id}-v.jpg"
    sq.save(sq_path, "JPEG", quality=88, optimize=True)
    vt.save(vt_path, "JPEG", quality=88, optimize=True)
    return {"square": sq_path.name, "vertical": vt_path.name}
