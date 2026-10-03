"""Step 6 — stitch cards + audio into a vertical short and a 16:9 wide cut."""

from __future__ import annotations

from pathlib import Path

from .common import Context, run_ffmpeg


def _segment_video(ctx: Context, card: Path, audio: Path, seconds: float, out: Path, *, w: int, h: int) -> None:
    v = ctx.config["visuals"]
    fps = v["fps"]
    frames = max(1, int(seconds * fps))
    if v.get("ken_burns"):
        # slow push-in so a still card never reads as frozen
        vf = (
            f"scale={w * 2}:{h * 2},"
            f"zoompan=z='min(zoom+0.0006,1.10)':d={frames}:x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':s={w}x{h}:fps={fps},"
            f"format=yuv420p"
        )
    else:
        vf = f"scale={w}:{h},format=yuv420p"

    run_ffmpeg(
        [
            "-loop", "1", "-framerate", str(fps), "-i", str(card),
            "-i", str(audio),
            "-vf", vf,
            "-t", f"{seconds:.2f}",
            "-c:v", "libx264", "-preset", "veryfast", "-tune", "stillimage", "-r", str(fps),
            "-c:a", "aac", "-b:a", "160k", "-ar", "44100",
            "-shortest", "-movflags", "+faststart",
            str(out),
        ]
    )


def _concat(parts: list[Path], out: Path) -> None:
    listing = out.with_suffix(".txt")
    listing.write_text("".join(f"file '{p.as_posix()}'\n" for p in parts))
    run_ffmpeg(["-f", "concat", "-safe", "0", "-i", str(listing), "-c", "copy", str(out)])


def _build(ctx: Context, timeline: list[dict], *, w: int, h: int, name: str) -> Path:
    parts = []
    for chunk in timeline:
        part = ctx.path("parts", f"{name}_{chunk['id']}.mp4")
        _segment_video(ctx, Path(chunk["card"]), Path(chunk["audio"]), chunk["seconds"], part, w=w, h=h)
        parts.append(part)
    final = ctx.path(f"{name}.mp4")
    _concat(parts, final)
    return final


def run(ctx: Context, timeline: list[dict]) -> dict:
    v = ctx.config["visuals"]
    short = _build(ctx, timeline, w=v["width"], h=v["height"], name="short")
    ctx.log(f"assemble: short  → {short.name}  ({short.stat().st_size // 1024} KB)")

    # Wide cut: same cards, letterboxed into 16:9. Fine for the main YouTube upload.
    wide = ctx.path("wide.mp4")
    run_ffmpeg(
        [
            "-i", str(short),
            "-vf", "scale=-2:1080,pad=1920:1080:(ow-iw)/2:(oh-ih)/2:color=#0f0f12",
            "-c:v", "libx264", "-preset", "veryfast", "-c:a", "copy", "-movflags", "+faststart",
            str(wide),
        ]
    )
    ctx.log(f"assemble: wide   → {wide.name}  ({wide.stat().st_size // 1024} KB)")
    return {"short": str(short), "wide": str(wide)}
