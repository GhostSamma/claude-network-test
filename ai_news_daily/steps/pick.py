"""Step 2 — Claude ranks the candidates and picks the ones worth a video."""

from __future__ import annotations

import json

from .common import ROOT, Context, ask_claude, parse_json_block, prompt_text


def run(ctx: Context, stories: list[dict]) -> dict:
    cfg = ctx.config["pick"]

    if ctx.dry_run:
        pick = json.loads((ROOT / "fixtures" / "pick.json").read_text())
        ctx.log(f"pick: dry run — {len(pick['picks'])} fixture picks")
        ctx.save_json("pick.json", pick)
        return pick

    numbered = "\n".join(
        f"{i + 1}. [{s['source']}] {s['title']}\n   {s['summary'][:300]}\n   {s['link']}"
        for i, s in enumerate(stories)
    )
    prompt = prompt_text("pick.md").format(
        n=cfg["stories_per_video"],
        persona=ctx.config["channel"]["persona"].strip(),
        stories=numbered,
    )
    reply = ask_claude(prompt, model=cfg["model"], effort=cfg["effort"], max_tokens=4000)
    pick = parse_json_block(reply)

    # Attach the full story records so later steps don't need the index.
    for p in pick["picks"]:
        p["story"] = stories[int(p["index"]) - 1]
    ctx.log("pick: " + " | ".join(p["story"]["title"][:50] for p in pick["picks"]))
    ctx.save_json("pick.json", pick)
    return pick
