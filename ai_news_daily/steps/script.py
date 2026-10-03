"""Step 3 — Claude writes the script in the channel's voice."""

from __future__ import annotations

import json

from .common import ROOT, Context, ask_claude, parse_json_block, prompt_text


def run(ctx: Context, pick: dict) -> dict:
    cfg = ctx.config["script"]

    if ctx.dry_run:
        script = json.loads((ROOT / "fixtures" / "script.json").read_text())
        ctx.log(f"script: dry run — fixture script, {len(script['segments'])} segments")
        ctx.save_json("script.json", script)
        return script

    picks_text = "\n\n".join(
        f"STORY {i + 1}: {p['story']['title']}\n"
        f"Source: {p['story']['source']}\n"
        f"Angle: {p.get('angle', '')}\n"
        f"Summary: {p['story']['summary']}\n"
        f"Link: {p['story']['link']}"
        for i, p in enumerate(pick["picks"])
    )
    prompt = prompt_text("script.md").format(
        channel=ctx.config["channel"]["name"],
        persona=ctx.config["channel"]["persona"].strip(),
        seconds=cfg["target_seconds"],
        words=int(cfg["target_seconds"] * 2.6),  # ~2.6 words/sec at a brisk read
        picks=picks_text,
    )
    reply = ask_claude(prompt, model=cfg["model"], effort=cfg["effort"], max_tokens=6000)
    script = parse_json_block(reply)

    spoken_words = sum(len(s["spoken"].split()) for s in script["segments"])
    spoken_words += len(script["hook"].split()) + len(script["outro"].split())
    ctx.log(f"script: \"{script['title']}\" — {len(script['segments'])} segments, ~{spoken_words} words")
    ctx.save_json("script.json", script)
    return script
