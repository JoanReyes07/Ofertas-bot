"""Video vertical corto por producto para TikTok (sin audio: el sonido de moda
se elige dentro de TikTok, que además le da más alcance)."""
from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw

from .cards import NAVY, RED, WHITE, YELLOW, font

W, H = 1080, 1920          # lienzo de diseño (igual que la tarjeta vertical)
OUT_W, OUT_H = 720, 1280   # tamaño del MP4: suficiente para TikTok y pesa poco


def _intro(discount: float) -> Image.Image:
    c = Image.new("RGB", (W, H), YELLOW)
    d = ImageDraw.Draw(c)
    d.text((W // 2, 640), "OFERTA", font=font("ExtraBold", 170), fill=NAVY, anchor="mm")
    if discount:
        d.ellipse([W // 2 - 290, 760, W // 2 + 290, 1340], fill=RED)
        d.text((W // 2, 1010), f"-{discount:.0f}%", font=font("ExtraBold", 190), fill=WHITE, anchor="mm")
        d.text((W // 2, 1180), "OFF", font=font("Bold", 80), fill=WHITE, anchor="mm")
    d.text((W // 2, 1480), "en Mercado Libre", font=font("SemiBold", 64), fill=NAVY, anchor="mm")
    return c


def _zoom(img: Image.Image, t: float, amount: float) -> Image.Image:
    """Acercamiento suave (efecto Ken Burns), t de 0 a 1."""
    s = 1 + amount * t
    w, h = int(W * s), int(H * s)
    big = img.resize((w, h), Image.BILINEAR)
    x, y = (w - W) // 2, (h - H) // 2
    return big.crop((x, y, x + W, y + H))


def build_product(card_path: str, out_path: str, discount: float = 0.0, fps: int = 24) -> str:
    """MP4 de ~6 s: intro con el descuento y la tarjeta con zoom."""
    import imageio_ffmpeg

    card = Image.open(card_path).convert("RGB").resize((W, H))
    scenes = [(_intro(discount), 1.2, 0.04), (card, 5.0, 0.07)]

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
