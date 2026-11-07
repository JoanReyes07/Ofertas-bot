"""Video vertical diario "Top ofertas de hoy" para TikTok (sin audio: el sonido
de moda se elige dentro de TikTok, que además le da más alcance)."""
from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw

from .cards import NAVY, WHITE, YELLOW, font

W, H = 1080, 1920


def _intro(n: int, day_label: str) -> Image.Image:
    c = Image.new("RGB", (W, H), YELLOW)
    d = ImageDraw.Draw(c)
    d.text((W // 2, 700), f"TOP {n}", font=font("ExtraBold", 230), fill=NAVY, anchor="mm")
    d.text((W // 2, 900), "OFERTAS DE HOY", font=font("ExtraBold", 96), fill=NAVY, anchor="mm")
    d.text((W // 2, 1030), "en Mercado Libre", font=font("SemiBold", 60), fill=NAVY, anchor="mm")
    d.rounded_rectangle([W // 2 - 260, 1140, W // 2 + 260, 1240], radius=50, fill=NAVY)
    d.text((W // 2, 1190), day_label, font=font("Bold", 50), fill=YELLOW, anchor="mm")
    return c


def _outro(web_url: str) -> Image.Image:
    c = Image.new("RGB", (W, H), NAVY)
    d = ImageDraw.Draw(c)
    d.text((W // 2, 760), "¿Te gustó alguna?", font=font("ExtraBold", 90), fill=WHITE, anchor="mm")
    d.text((W // 2, 900), "Los links están", font=font("Bold", 80), fill=YELLOW, anchor="mm")
    d.text((W // 2, 1000), "en mi perfil", font=font("Bold", 80), fill=YELLOW, anchor="mm")
    d.text((W // 2, 1160), "Los precios pueden cambiar", font=font("Medium", 46), fill=WHITE, anchor="mm")
    if web_url:
        d.text((W // 2, 1260), web_url.replace("https://", ""), font=font("Medium", 36), fill=WHITE, anchor="mm")
    return c


def _with_number(card: Image.Image, i: int, n: int) -> Image.Image:
    c = card.copy()
    d = ImageDraw.Draw(c)
    d.rounded_rectangle([40, 190, 220, 290], radius=50, fill=NAVY)
    d.text((130, 240), f"{i}/{n}", font=font("ExtraBold", 54), fill=YELLOW, anchor="mm")
    return c


def _zoom(img: Image.Image, t: float, amount: float = 0.05) -> Image.Image:
    """Acercamiento suave (efecto Ken Burns), t de 0 a 1."""
    s = 1 + amount * t
    w, h = int(W * s), int(H * s)
    big = img.resize((w, h), Image.BILINEAR)
    x, y = (w - W) // 2, (h - H) // 2
    return big.crop((x, y, x + W, y + H))


def build(card_paths: list[str], out_path: str, day_label: str, web_url: str = "",
          fps: int = 24, per_card: float = 3.0) -> str:
    """Arma el MP4 a partir de las tarjetas verticales (1080x1920)."""
    import imageio_ffmpeg

    cards = [Image.open(p).convert("RGB").resize((W, H)) for p in card_paths]
    n = len(cards)
    scenes = [(_intro(n, day_label), 1.8, 0.03)]
    scenes += [(_with_number(c, i + 1, n), per_card, 0.06) for i, c in enumerate(cards)]
    scenes += [(_outro(web_url), 2.5, 0.0)]

    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    writer = imageio_ffmpeg.write_frames(
        out_path, (W, H), fps=fps, codec="libx264", pix_fmt_out="yuv420p", macro_block_size=8,
        output_params=["-movflags", "+faststart", "-crf", "24", "-preset", "veryfast"],
    )
    writer.send(None)
    for img, secs, zoom in scenes:
        frames = max(1, int(secs * fps))
        for k in range(frames):
            frame = _zoom(img, k / frames, zoom) if zoom else img
            writer.send(frame.tobytes())
    writer.close()
    return out_path
