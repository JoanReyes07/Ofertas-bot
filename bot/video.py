"""Video vertical corto por producto para TikTok (sin audio: el sonido de moda
se elige dentro de TikTok, que además le da más alcance)."""
from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw

from .cards import FOREST, MINT, MINT_DEEP, ACCENT, WHITE, brand, font

W, H = 1080, 1920          # lienzo de diseño (igual que la tarjeta vertical)
OUT_W, OUT_H = 720, 1280   # tamaño del MP4: suficiente para TikTok y pesa poco


def _intro(discount: float, code: int = 0) -> Image.Image:
    c = Image.new("RGB", (W, H), FOREST)
    d = ImageDraw.Draw(c)
    brand(d, (W // 2, 260), 66, light=True)
    d.text((W // 2, 600), "OFERTA", font=font("ExtraBold", 170), fill=WHITE, anchor="mm")
    if discount:
        d.ellipse([W // 2 - 290, 720, W // 2 + 290, 1300], fill=ACCENT)
        d.text((W // 2, 970), f"-{discount:.0f}%", font=font("ExtraBold", 190), fill=FOREST, anchor="mm")
        d.text((W // 2, 1140), "OFF", font=font("Bold", 80), fill=FOREST, anchor="mm")
    d.text((W // 2, 1420), "en Mercado Libre", font=font("SemiBold", 64), fill=MINT_DEEP, anchor="mm")
    if code:
        label = f"Código {code}"
        f = font("ExtraBold", 72)
        w = d.textlength(label, font=f)
        d.rounded_rectangle([W // 2 - w / 2 - 50, 1530, W // 2 + w / 2 + 50, 1650], radius=60, fill=MINT)
        d.text((W // 2, 1590), label, font=f, fill=FOREST, anchor="mm")
    return c


def _zoom(img: Image.Image, t: float, amount: float) -> Image.Image:
    """Acercamiento suave (efecto Ken Burns), t de 0 a 1."""
    s = 1 + amount * t
    w, h = int(W * s), int(H * s)
    big = img.resize((w, h), Image.BILINEAR)
    x, y = (w - W) // 2, (h - H) // 2
    return big.crop((x, y, x + W, y + H))


def _ease(t: float) -> float:
    """Movimiento que frena suave al llegar (ease-out cúbico)."""
    t = min(1.0, max(0.0, t))
    return 1 - (1 - t) ** 3


def _alpha(layer: Image.Image, a: float) -> Image.Image:
    out = layer.copy()
    out.putalpha(layer.getchannel("A").point(lambda v: int(v * a)))
    return out


def _reel_layers(p, img, cierre: str, extra: str = "") -> dict:
    from PIL import ImageFilter, ImageOps

    from .cards import INK, MUTED, money, wrap

    # foto en tarjeta blanca con sombra
    s, pad = 900, 60
    foto = Image.new("RGBA", (s + 80, s + 80), (0, 0, 0, 0))
    sombra = Image.new("RGBA", foto.size, (0, 0, 0, 0))
    ImageDraw.Draw(sombra).rounded_rectangle((40, 52, 40 + s, 52 + s), radius=70, fill=(30, 60, 30, 70))
    foto = Image.alpha_composite(foto, sombra.filter(ImageFilter.GaussianBlur(22)))
    ImageDraw.Draw(foto).rounded_rectangle((40, 40, 40 + s, 40 + s), radius=70, fill=WHITE)
    if img is not None:
        f = ImageOps.contain(img, (s - 2 * pad, s - 2 * pad), Image.LANCZOS).convert("RGBA")
        foto.alpha_composite(f, (40 + (s - f.width) // 2, 40 + (s - f.height) // 2))
    # nombre (hasta 3 líneas, centrado)
    nombre = Image.new("RGBA", (W, 260), (0, 0, 0, 0))
    d = ImageDraw.Draw(nombre)
    fn = font("Bold", 66)
    lines = wrap(d, p.title, fn, W - 140, 3)
    y = (260 - len(lines) * 84) // 2
    for line in lines:
        d.text((W // 2, y + 42), line, font=fn, fill=INK, anchor="mm")
        y += 84
    # precio: anterior tachado + actual grande
    precio = Image.new("RGBA", (W, 280), (0, 0, 0, 0))
    d = ImageDraw.Draw(precio)
    if p.original_price and p.original_price > p.price:
        fo = font("Medium", 58)
        old = money(p.original_price)
        d.text((W // 2, 40), old, font=fo, fill=MUTED, anchor="mm")
        w = d.textlength(old, font=fo)
        d.line((W // 2 - w / 2 - 6, 44, W // 2 + w / 2 + 6, 44), fill=MUTED, width=5)
    d.text((W // 2, 170), money(p.price), font=font("ExtraBold", 170), fill=INK, anchor="mm")
    # cierre: logo + píldora con el texto del link
    logo = Image.new("RGBA", (W, 200), (0, 0, 0, 0))
    brand(ImageDraw.Draw(logo), (W // 2, 100), 112)
    link = Image.new("RGBA", (W, 170), (0, 0, 0, 0))
    d = ImageDraw.Draw(link)
    fl = font("Bold", 52)
    while d.textlength(cierre, font=fl) > W - 200 and fl.size > 30:
        fl = font("Bold", fl.size - 2)
    w = d.textlength(cierre, font=fl) + 110
    d.rounded_rectangle((W / 2 - w / 2, 25, W / 2 + w / 2, 145), radius=60, fill=FOREST)
    d.text((W // 2, 85), cierre, font=fl, fill=WHITE, anchor="mm")
    # gancho: sello "-58%" en la esquina de la foto, visible desde el primer cuadro
    badge = Image.new("RGBA", (360, 360), (0, 0, 0, 0))
    if p.discount_pct:
        d = ImageDraw.Draw(badge)
        d.ellipse((10, 18, 350, 358), fill=(30, 60, 30, 60))  # sombra
        d.ellipse((10, 10, 350, 350), fill=ACCENT, outline=WHITE, width=10)
        d.text((180, 165), f"-{p.discount_pct:.0f}%", font=font("ExtraBold", 118), fill=FOREST, anchor="mm")
        d.text((180, 255), "HOY", font=font("Bold", 52), fill=FOREST, anchor="mm")
    # segunda línea del cierre: "o busca el 12 en cazaofertasmx.github.io"
    web = Image.new("RGBA", (W, 120), (0, 0, 0, 0))
    if extra:
        d = ImageDraw.Draw(web)
        fe = font("SemiBold", 46)
        while d.textlength(extra, font=fe) > W - 120 and fe.size > 28:
            fe = font("SemiBold", fe.size - 2)
        d.text((W // 2, 60), extra, font=fe, fill=INK, anchor="mm")
    return {"foto": foto, "nombre": nombre, "precio": precio, "logo": logo, "link": link,
            "badge": badge, "web": web}


# línea de tiempo del Reel, en segundos (diseño del usuario, 2026-11-09).
# Ajuste del 2026-11-11: solo el 15% veía 3 s, así que el descuento, la foto y el precio
# ya se ven en el primer cuadro (entran con un empujón corto) y el nombre llega después.
REEL_T = {"foto": (0.0, 0.35), "badge": (0.0, 0.45), "precio": (0.0, 0.35), "nombre": (0.35, 0.9),
          "fade": (5.0, 5.8), "logo": (5.8, 6.4), "link": (6.3, 6.9), "web": (6.7, 7.3)}
REEL_TOTAL = 8.4


def build_reel(p, img, out_path: str, cierre: str = "Link en la descripción del video",
               fps: int = 30, extra: str = "") -> str:
    """Reel 1080x1920 (~8 s). Desde el primer cuadro: foto, sello con el descuento y precio
    (entran con un empujón corto); luego el nombre por la izquierda; todo se desvanece y
    cierra con el logo, el texto del link y, si hay, "o busca el N en la web"."""
    import imageio_ffmpeg

    from .cards import _gradient

    fondo = _gradient(W, H, (236, 243, 226), (214, 230, 194)).convert("RGBA")
    L = _reel_layers(p, img, cierre, extra)

    def prog(t, key):
        a, b = REEL_T[key]
        return _ease((t - a) / (b - a))

    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    writer = imageio_ffmpeg.write_frames(
        out_path, (W, H), fps=fps, codec="libx264", pix_fmt_out="yuv420p", macro_block_size=8,
        output_params=["-movflags", "+faststart", "-crf", "23", "-preset", "veryfast"],
    )
    writer.send(None)
    fx = (W - L["foto"].width) // 2
    for k in range(int(REEL_TOTAL * fps)):
        t = k / fps
        fr = fondo.copy()
        # foto y precio visibles desde t=0: solo se acomodan 120 px
        fr.alpha_composite(L["foto"], (fx, int(230 + 120 * (1 - prog(t, "foto")))))
        fr.alpha_composite(L["precio"], (int(160 * (1 - prog(t, "precio"))), 1490))
        if (a := prog(t, "nombre")) > 0:
            fr.alpha_composite(L["nombre"], (int(-W * (1 - a)), 1210))
        # sello: aparece grande y se asienta (efecto "pop")
        k = 1.25 - 0.25 * prog(t, "badge")
        b = L["badge"].resize((int(360 * k), int(360 * k)), Image.BILINEAR)
        fr.alpha_composite(b, (int(850 - b.width / 2), int(285 - b.height / 2)))
        a0, a1 = REEL_T["fade"]
        if t > a0:
            fr = Image.blend(fr, fondo, min(1.0, (t - a0) / (a1 - a0)))
        if (a := prog(t, "logo")) > 0:
            fr.alpha_composite(_alpha(L["logo"], a), (0, int(760 + 60 * (1 - a))))
        if (a := prog(t, "link")) > 0:
            fr.alpha_composite(_alpha(L["link"], a), (0, int(990 + 60 * (1 - a))))
        if (a := prog(t, "web")) > 0:
            fr.alpha_composite(_alpha(L["web"], a), (0, int(1170 + 40 * (1 - a))))
        writer.send(fr.convert("RGB").tobytes())
    writer.close()
    return out_path


AUDIO_DIR = Path(__file__).parent / "assets" / "audio"


def pick_audio(seed: int = 0) -> Path | None:
    """Pista de fondo para los Reels (bot/assets/audio/*.mp3|m4a|wav). Con varias, se rotan."""
    pistas = sorted(p for p in AUDIO_DIR.glob("*") if p.suffix.lower() in (".mp3", ".m4a", ".aac", ".wav"))
    return pistas[seed % len(pistas)] if pistas else None


def add_audio(video_path: str, audio_path: str, fade: float = 1.0) -> str:
    """Mezcla la pista en el video: se recorta (o repite) al largo del video y baja al final."""
    import subprocess

    import imageio_ffmpeg

    tmp = str(Path(video_path).with_suffix(".tmp.mp4"))
    start_fade = max(0.0, REEL_TOTAL - fade)
    subprocess.run([imageio_ffmpeg.get_ffmpeg_exe(), "-y", "-loglevel", "error",
                    "-i", video_path, "-stream_loop", "-1", "-i", audio_path,
                    "-map", "0:v", "-map", "1:a", "-c:v", "copy", "-c:a", "aac", "-b:a", "128k",
                    "-af", f"afade=t=out:st={start_fade}:d={fade}", "-shortest",
                    "-movflags", "+faststart", tmp],
                   check=True, stdin=subprocess.DEVNULL, timeout=120)
    Path(tmp).replace(video_path)
    return video_path


def build_product(card_path: str, out_path: str, discount: float = 0.0, fps: int = 24, code: int = 0) -> str:
    """MP4 de ~6 s: intro con el descuento y la tarjeta con zoom."""
    import imageio_ffmpeg

    card = Image.open(card_path).convert("RGB").resize((W, H))
    scenes = [(_intro(discount, code), 1.5, 0.04), (card, 5.0, 0.07)]

    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    writer = imageio_ffmpeg.write_frames(
        out_path, (OUT_W, OUT_H), fps=fps, codec="libx264", pix_fmt_out="yuv420p", macro_block_size=8,
        output_params=["-movflags", "+faststart", "-crf", "27", "-preset", "veryfast"],
    )
    writer.send(None)
    for img, secs, zoom in scenes:
        frames = max(1, int(secs * fps))
        for k in range(frames):
            frame = _zoom(img, k / frames, zoom) if zoom else img
            writer.send(frame.resize((OUT_W, OUT_H), Image.BILINEAR).tobytes())
    writer.close()
    return out_path
