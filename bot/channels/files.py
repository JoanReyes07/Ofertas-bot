"""Canales sin API de publicación: WhatsApp y TikTok. Deja todo listo para copiar y pegar."""
from __future__ import annotations

from pathlib import Path

from ..meli import Product


def whatsapp(entries: list[tuple[Product, dict]], out_dir: str, day: str) -> str:
    d = Path(out_dir) / "whatsapp"
    d.mkdir(parents=True, exist_ok=True)
    f = d / f"{day}.txt"
    blocks = []
    for p, c in entries:
        blocks.append(f"{c['whatsapp']}\n\nImagen: {p.image}")
    with open(f, "a", encoding="utf-8") as fh:
        fh.write(("\n\n" + "-" * 30 + "\n\n").join(blocks) + "\n\n" + "-" * 30 + "\n\n")
    return str(f)


def tiktok(p: Product, c: dict, out_dir: str, web_url: str = "") -> str:
    d = Path(out_dir) / "tiktok"
    d.mkdir(parents=True, exist_ok=True)
    f = d / f"{p.id}.md"
    bio = f"Pon en tu bio: {web_url}" if web_url else "Pon en tu bio el enlace a tu web de ofertas."
    f.write_text(
        f"# {p.title}\n\nPrecio: ${p.price:,.0f} | Descuento: {p.discount_pct:.0f}%\n\n"
        f"## Guion (20 s)\n{c['tiktok_script']}\n\n## Texto del video\n{c['tiktok_caption']}\n\n"
        f"## Material\n- Imagen del producto: {p.image}\n- {bio}\n"
        "- Muestra el precio tachado en pantalla y di que puede cambiar.\n",
        encoding="utf-8",
    )
    return str(f)
