"""Step 5 — one card image per spoken chunk, sized for vertical video.

Cards keep everything inside the platform safe zone (nothing in the bottom
~25%, nothing hugging the right edge) so the UI never covers the text.
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from .common import Context

FONT_BOLD = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
FONT_REG = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"


def _font(path: str, size: int) -> ImageFont.FreeTypeFont:
    try:
        return ImageFont.truetype(path, size)
    except OSError:
        return ImageFont.load_default(size)


def _hex(color: str) -> tuple[int, int, int]:
    color = color.lstrip("#")
    return tuple(int(color[i : i + 2], 16) for i in (0, 2, 4))


def _gradient(w: int, h: int, top: str, bottom: str) -> Image.Image:
    img = Image.new("RGB", (w, h))
    t, b = _hex(top), _hex(bottom)
    px = img.load()
    for y in range(h):
        f = y / max(1, h - 1)
        row = tuple(int(t[i] + (b[i] - t[i]) * f) for i in range(3))
        for x in range(w):
            px[x, y] = row
    return img


def _wrap(draw: ImageDraw.ImageDraw, text: str, font, max_width: int) -> list[str]:
    words, lines, line = text.split(), [], ""
    for word in words:
        trial = f"{line} {word}".strip()
        if draw.textlength(trial, font=font) <= max_width:
            line = trial
        else:
            if line:
                lines.append(line)
            line = word
    if line:
        lines.append(line)
    return lines


def _card(ctx: Context, *, kicker: str, headline: str, body: str, footer: str, out: Path) -> None:
    v = ctx.config["visuals"]
    th = v["theme"]
    w, h = v["width"], v["height"]
    img = _gradient(w, h, th["bg_top"], th["bg_bottom"])
    draw = ImageDraw.Draw(img)

    margin = int(w * 0.08)
    max_w = w - margin * 2 - int(w * 0.06)  # extra room on the right for the UI column
    y = int(h * 0.18)                        # top safe zone

    # accent bar
    draw.rectangle([margin, y, margin + 14, y + 110], fill=_hex(th["accent"]))

    kicker_font = _font(FONT_BOLD, 40)
    draw.text((margin + 40, y + 6), kicker.upper(), font=kicker_font, fill=_hex(th["accent"]))

    y += 150
    head_font = _font(FONT_BOLD, 88)
    for line in _wrap(draw, headline, head_font, max_w):
        draw.text((margin, y), line, font=head_font, fill=_hex(th["text"]))
        y += 104

    if body:
        y += 40
        body_font = _font(FONT_REG, 50)
        for line in _wrap(draw, body, body_font, max_w)[:4]:
            draw.text((margin, y), line, font=body_font, fill=_hex(th["muted"]))
            y += 66

    # footer sits above the bottom safe zone (bottom 25% stays empty)
    foot_font = _font(FONT_BOLD, 36)
    draw.text((margin, int(h * 0.72)), footer, font=foot_font, fill=_hex(th["muted"]))

    img.save(out, "PNG")


def run(ctx: Context, script: dict, timeline: list[dict]) -> list[dict]:
    channel = ctx.config["channel"]
    footer = f"{channel['name']}  ·  {channel['handle']}"
    segs = {f"{i:02d}_seg": s for i, s in enumerate(script["segments"], start=1)}

    for chunk in timeline:
        out = ctx.path("cards", f"{chunk['id']}.png")
        if chunk["id"] == "00_hook":
            _card(ctx, kicker="today in AI", headline=script["title"], body="", footer=footer, out=out)
        elif chunk["id"] == "99_outro":
            _card(ctx, kicker="that's the day", headline="Follow for tomorrow's drop", body="", footer=footer, out=out)
        else:
            seg = segs[chunk["id"]]
            _card(ctx, kicker=seg.get("source", ""), headline=seg["headline"], body=seg.get("kicker", ""), footer=footer, out=out)
        chunk["card"] = str(out)

    ctx.log(f"visuals: {len(timeline)} cards at {ctx.config['visuals']['width']}x{ctx.config['visuals']['height']}")
    ctx.save_json("timeline.json", timeline)
    return timeline
