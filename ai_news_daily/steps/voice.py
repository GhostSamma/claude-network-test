"""Step 4 — turn every spoken chunk into audio.

Produces one mp3 per chunk (hook, each segment, outro) so the visuals can be
timed to each one. Engine is picked in config: `edge` is free and needs no key;
`elevenlabs` needs ELEVENLABS_API_KEY.
"""

from __future__ import annotations

import asyncio
from pathlib import Path

from .common import Context, getenv_required, media_duration, run_ffmpeg


def chunks_from_script(script: dict) -> list[tuple[str, str]]:
    """(chunk_id, spoken text) in playback order."""
    out = [("00_hook", script["hook"])]
    for i, seg in enumerate(script["segments"], start=1):
        out.append((f"{i:02d}_seg", seg["spoken"]))
    out.append(("99_outro", script["outro"]))
    return out


def _silence(path: Path, seconds: float) -> None:
    """Placeholder audio for dry runs — right length, no voice."""
    run_ffmpeg(["-f", "lavfi", "-i", "anullsrc=r=24000:cl=mono", "-t", f"{seconds:.2f}", "-q:a", "9", str(path)])


async def _edge(text: str, path: Path, voice: str, rate: str) -> None:
    import edge_tts

    await edge_tts.Communicate(text, voice, rate=rate).save(str(path))


def _elevenlabs(text: str, path: Path, voice_id: str) -> None:
    import requests

    key = getenv_required("ELEVENLABS_API_KEY")
    r = requests.post(
        f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}",
        headers={"xi-api-key": key, "Content-Type": "application/json"},
        json={"text": text, "model_id": "eleven_multilingual_v2"},
        timeout=120,
    )
    r.raise_for_status()
    path.write_bytes(r.content)


def run(ctx: Context, script: dict) -> list[dict]:
    cfg = ctx.config["voice"]
    engine = cfg["engine"]
    timeline: list[dict] = []

    for chunk_id, text in chunks_from_script(script):
        path = ctx.path("voice", f"{chunk_id}.mp3")
        if ctx.dry_run:
            # ~2.6 words a second, floor of 2s so even a short card is readable
            _silence(path, max(2.0, len(text.split()) / 2.6))
        elif engine == "edge":
            asyncio.run(_edge(text, path, cfg["edge_voice"], cfg["rate"]))
        elif engine == "elevenlabs":
            _elevenlabs(text, path, cfg["elevenlabs_voice_id"])
        else:
            raise ValueError(f"Unknown voice engine {engine!r}")

        seconds = media_duration(path)
        timeline.append({"id": chunk_id, "text": text, "audio": str(path), "seconds": round(seconds, 2)})

    total = sum(t["seconds"] for t in timeline)
    ctx.log(f"voice: {len(timeline)} chunks, {total:.0f}s total ({'silence' if ctx.dry_run else engine})")
    ctx.save_json("timeline.json", timeline)
    return timeline
