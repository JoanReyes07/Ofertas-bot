"""Tarjetas de oferta tipo anuncio con la marca Cazaofertas MX (Pillow).

- cuadrada 1080x1080: Facebook y WhatsApp (link directo en el texto)
- vertical 1080x1920: TikTok (código para buscar en la web del perfil)
"""
from __future__ import annotations

import io
from pathlib import Path

import requests
from PIL import Image, ImageDraw, ImageFont, ImageOps

from .meli import Product

FONTS = Path(__file__).parent / "assets" / "fonts"

# Paleta de marca: verdes templados + naranja cálido (amigable y distinta a Mercado Libre)
FOREST = (31, 77, 44)        # #1F4D2C  verde bosque suave: paneles y texto fuerte
INK = (28, 52, 35)           # #1C3423  texto principal
MINT = (234, 246, 230)       # #EAF6E6  fondo
MINT_DEEP = (191, 229, 184)  # #BFE5B8  etiquetas
ORANGE = (240, 122, 43)      # #F07A2B  botones y descuento
WHITE = (255, 255, 255)
MUTED = (120, 140, 125)
SOFT = (196, 222, 200)       # texto secundario sobre verde

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


def brand(d: ImageDraw.ImageDraw, center: tuple[int, int], size: int, light: bool = False) -> None:
    """Logotipo de texto: Caza + ofertas (naranja) + MX."""
    base = WHITE if light else FOREST
    parts = [("Caza", base), ("ofertas", ORANGE), (" MX", base)]
    f = font("ExtraBold", size)
    total = sum(d.textlength(t, font=f) for t, _ in parts)
    x = center[0] - total / 2
    for t, color in parts:
        d.text((x, center[1]), t, font=f, fill=color, anchor="lm")
        x += d.textlength(t, font=f)


def _gradient(W: int, H: int, top: tuple, bottom: tuple) -> Image.Image:
    g = Image.new("RGB", (1, H))
    for y in range(H):
        t = y / max(1, H - 1)
        g.putpixel((0, y), tuple(int(top[i] + (bottom[i] - top[i]) * t) for i in range(3)))
    return g.resize((W, H))


def _paste_product(canvas: Image.Image, img: Image.Image | None, box: tuple[int, int, int, int], radius: int) -> None:
    x0, y0, x1, y1 = box
    d = ImageDraw.Draw(canvas)
    d.rounded_rectangle(box, radius=radius, fill=WHITE)
    if img is None:
        return
    pad = int((x1 - x0) * 0.06)
    fitted = ImageOps.contain(img, (x1 - x0 - 2 * pad, y1 - y0 - 2 * pad), Image.LANCZOS)
    canvas.paste(fitted, (x0 + (x1 - x0 - fitted.width) // 2, y0 + (y1 - y0 - fitted.height) // 2))


def _badge(d: ImageDraw.ImageDraw, pct: float, center: tuple[int, int], r: int) -> None:
    cx, cy = center
    d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=ORANGE)
    d.text((cx, cy - r * 0.12), f"-{pct:.0f}%", font=font("ExtraBold", int(r * 0.6)), fill=WHITE, anchor="mm")
    d.text((cx, cy + r * 0.42), "OFF", font=font("Bold", int(r * 0.28)), fill=WHITE, anchor="mm")


def _pill(d: ImageDraw.ImageDraw, text: str, x: int, y: int, size: int, bg, fg, weight: str = "Bold") -> int:
    """Etiqueta redondeada; devuelve el ancho."""
    f = font(weight, size)
    w = d.textlength(text, font=f) + size * 1.3
    h = int(size * 1.75)
    d.rounded_rectangle([x, y, x + w, y + h], radius=h // 2, fill=bg)
    d.text((x + size * 0.65, y + h // 2), text, font=f, fill=fg, anchor="lm")
    return int(w)


def _arrow_button(d: ImageDraw.ImageDraw, text: str, box: tuple[int, int, int, int]) -> None:
    """Botón píldora naranja con círculo blanco y flecha (estilo de la referencia)."""
    x0, y0, x1, y1 = box
    h = y1 - y0
    d.rounded_rectangle(box, radius=h // 2, fill=ORANGE)
    r = int(h * 0.38)
    cx, cy = x1 - h // 2, y0 + h // 2
    d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=WHITE)
    a = r * 0.45  # flecha dibujada (la fuente no trae el símbolo)
    wd = max(3, h // 18)
    d.line([(cx - a, cy), (cx + a, cy)], fill=ORANGE, width=wd)
    d.line([(cx + a * 0.15, cy - a * 0.7), (cx + a, cy), (cx + a * 0.15, cy + a * 0.7)], fill=ORANGE, width=wd, joint="curve")
    f = font("Bold", int(h * 0.34))
    d.text(((x0 + (cx - r)) / 2, cy), text, font=f, fill=WHITE, anchor="mm")


def _price(d: ImageDraw.ImageDraw, p: Product, x: int, y: int, big: int) -> int:
    """Precio anterior tachado (pequeño, arriba) + precio actual grande. Devuelve la y final."""
    if p.original_price and p.original_price > p.price:
        f_old = font("Medium", int(big * 0.36))
        old = money(p.original_price)
        d.text((x, y), old, font=f_old, fill=SOFT, anchor="lt")
        w = d.textlength(old, font=f_old)
        mid = y + int(big * 0.36 * 0.58)
        d.line([(x - 3, mid), (x + w + 3, mid)], fill=SOFT, width=max(2, big // 32))
        y += int(big * 0.5)
    d.text((x, y), money(p.price), font=font("ExtraBold", big), fill=WHITE, anchor="lt")
    return y + int(big * 1.08)


def render(p: Product, img: Image.Image | None, site_name: str, cta: str, vertical: bool = False,
           code: int = 0) -> Image.Image:
    W, H = (1080, 1920) if vertical else (1080, 1080)
    c = _gradient(W, H, (240, 249, 236), (214, 238, 208))
    d = ImageDraw.Draw(c)
    m = 54 if vertical else 44

    # marca arriba, sobre el fondo menta
    head = 150 if vertical else 92
    if site_name.strip().lower() == "cazaofertas mx":
        brand(d, (W // 2, head // 2 + 10), 60 if vertical else 44)
    else:
        d.text((W // 2, head // 2 + 10), site_name, font=font("ExtraBold", 54 if vertical else 42), fill=FOREST, anchor="mm")

    # foto en tarjeta blanca que "flota" sobre el panel verde
    if vertical:
        img_box, panel_top, radius = (m, head + 20, W - m, head + 20 + 980), head + 760, 64
    else:
        img_box, panel_top, radius = (m + 120, head + 6, W - m - 120, head + 6 + 470), head + 330, 48
    d.rounded_rectangle((0, panel_top, W, H), radius=90 if vertical else 64, fill=FOREST)
    d.rectangle((0, H - 100, W, H), fill=FOREST)
    _paste_product(c, img, img_box, radius)
    if p.discount_pct:
        r = 118 if vertical else 80
        _badge(d, p.discount_pct, (min(img_box[2] - r // 2, W - r - 16), img_box[1] + r // 2 + 6), r)
    if code:
        _pill(d, f"Código {code}", img_box[0] + 26, img_box[1] + 26, 42 if vertical else 28, FOREST, WHITE, "ExtraBold")

    # textos sobre el panel verde
    ts = 54 if vertical else 34
    y = img_box[3] + (54 if vertical else 24)
    f_title = font("SemiBold", ts)
    for line in wrap(d, p.title, f_title, W - 2 * m, 2):
        d.text((m, y), line, font=f_title, fill=WHITE)
        y += int(ts * 1.3)
    y = _price(d, p, m, y + 14, 150 if vertical else 92)
    if p.rank:
        cat = CATEGORY_NAMES.get(p.category, "su categoría")
        _pill(d, f"Top {p.rank} en {cat}", m, y + (6 if vertical else 0), 34 if vertical else 24, MINT_DEEP, INK)

    # botón: no es tienda, solo lleva a la oferta
    bh = 140 if vertical else 92
    by = H - bh - (80 if vertical else 30)
    _arrow_button(d, cta, (m, by, W - m, by + bh))
    return c


def make_cards(p: Product, out_dir: str, site_name: str, http=requests, code: int = 0) -> dict:
    """Genera las dos tarjetas de un producto. Devuelve los nombres de archivo."""
    d = Path(out_dir)
    d.mkdir(parents=True, exist_ok=True)
    img = load_image(p.image, http)
    sq = render(p, img, site_name, "Ver oferta: link en la descripción", code=code)
    tiktok_cta = f"Busca el {code} en mi perfil" if code else "Link en mi perfil"
    vt = render(p, img, site_name, tiktok_cta, vertical=True, code=code)
    sq_path, vt_path = d / f"{p.id}-sq.jpg", d / f"{p.id}-v.jpg"
    sq.save(sq_path, "JPEG", quality=88, optimize=True)
    vt.save(vt_path, "JPEG", quality=88, optimize=True)
    return {"square": sq_path.name, "vertical": vt_path.name}


def make_icon(size: int, maskable: bool = False) -> Image.Image:
    """Ícono de marca: etiqueta naranja con % sobre verde bosque."""
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    if maskable:
        d.rectangle([0, 0, size, size], fill=FOREST)
    else:
        d.rounded_rectangle([0, 0, size - 1, size - 1], radius=size // 4, fill=FOREST)
    s = size * (0.5 if maskable else 0.62)
    o = (size - s) / 2
    d.ellipse([o, o, o + s, o + s], fill=ORANGE)
    d.text((size / 2, size / 2 + s * 0.02), "%", font=font("ExtraBold", int(s * 0.62)), fill=WHITE, anchor="mm")
    return img


def make_og() -> Image.Image:
    """Imagen 1200x630 para la vista previa al compartir la web (WhatsApp, Facebook)."""
    c = _gradient(1200, 630, (240, 249, 236), (214, 238, 208))
    d = ImageDraw.Draw(c)
    icon = make_icon(220)
    c.paste(icon, (110, 205), icon)
    brand(d, (720, 280), 84)
    d.text((720, 380), "Las mejores ofertas de Mercado Libre", font=font("SemiBold", 38), fill=INK, anchor="mm")
    d.text((720, 440), "Busca el código del video", font=font("Medium", 32), fill=MUTED, anchor="mm")
    return c
