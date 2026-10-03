"""Step 7 — a 1280x720 thumbnail from the title."""

from __future__ import annotations

from PIL import Image, ImageDraw

from .common import Context
from .visuals import FONT_BOLD, _font, _gradient, _hex, _wrap


def run(ctx: Context, script: dict) -> str:
    th = ctx.config["visuals"]["theme"]
    w, h = 1280, 720
    img = _gradient(w, h, th["bg_top"], th["bg_bottom"])
    draw = ImageDraw.Draw(img)

    margin = 70
    draw.rectangle([margin, 90, margin + 12, 190], fill=_hex(th["accent"]))
    draw.text((margin + 36, 96), "TODAY IN AI", font=_font(FONT_BOLD, 40), fill=_hex(th["accent"]))

    font = _font(FONT_BOLD, 96)
    y = 220
    for line in _wrap(draw, script["title"], font, w - margin * 2)[:3]:
        draw.text((margin, y), line, font=font, fill=_hex(th["text"]))
        y += 112

    draw.text((margin, h - 90), ctx.config["channel"]["name"], font=_font(FONT_BOLD, 34), fill=_hex(th["muted"]))

    out = ctx.path("thumb.png")
    img.save(out, "PNG")
    ctx.log(f"thumbnail: {out.name}")
    return str(out)
