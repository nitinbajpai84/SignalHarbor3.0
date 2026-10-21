"""Make the installable-app icons from the existing logo mark (ui/public/brand/signal-harbor-mark-512.png); nothing is downloaded.
Writes pwa-192.png, pwa-512.png (the mark on white) and pwa-maskable-512.png (the mark inside the central 60%, which a phone may crop to a circle)."""
from pathlib import Path

from PIL import Image

BRAND = Path(__file__).resolve().parents[1] / "ui" / "public" / "brand"


def icon(size: int, fill: float) -> Image.Image:
    mark = Image.open(BRAND / "signal-harbor-mark-512.png").convert("RGBA")
    mark = mark.crop(mark.getbbox())
    scale = size * fill / max(mark.size)
    mark = mark.resize((max(1, round(mark.width * scale)), max(1, round(mark.height * scale))), Image.LANCZOS)
    out = Image.new("RGBA", (size, size), (255, 255, 255, 255))
    out.alpha_composite(mark, ((size - mark.width) // 2, (size - mark.height) // 2))
    return out.convert("RGB")


if __name__ == "__main__":
    icon(192, 0.84).save(BRAND / "pwa-192.png")
    icon(512, 0.84).save(BRAND / "pwa-512.png")
    icon(512, 0.58).save(BRAND / "pwa-maskable-512.png")
