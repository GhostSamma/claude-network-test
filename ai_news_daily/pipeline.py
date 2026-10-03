#!/usr/bin/env python3
"""AI News Daily — one command, one video.

    python pipeline.py run              # today's video, every step
    python pipeline.py run --dry-run    # no network, no keys: fixture stories, silent audio — proves the build
    python pipeline.py run --date 2026-10-02
    python pipeline.py scout            # just pull the news and stop
    python pipeline.py from script      # re-run from the script step using what's already in out/<date>/

Every run writes to out/<date>/. Re-running a step overwrites that step's files only.
"""

from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path

# .env support without a dependency: KEY=value lines, no quotes needed
_env = Path(__file__).resolve().parent / ".env"
if _env.exists():
    import os

    for line in _env.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))

from steps import assemble, pick, publish, scout, script, thumbnail, visuals, voice  # noqa: E402
from steps.common import make_context  # noqa: E402

STEPS = ["scout", "pick", "script", "voice", "visuals", "assemble", "thumbnail", "publish"]


def run_pipeline(ctx, start: str = "scout") -> None:
    start_at = STEPS.index(start)
    ctx.log(f"run: {ctx.config['channel']['name']} — starting at '{start}'" + (" (DRY RUN)" if ctx.dry_run else ""))

    stories = scout.run(ctx) if start_at <= 0 else ctx.load_json("stories.json")
    if start == "scout" and "--only" in sys.argv:
        return
    picked = pick.run(ctx, stories) if start_at <= 1 else ctx.load_json("pick.json")
    scr = script.run(ctx, picked) if start_at <= 2 else ctx.load_json("script.json")
    timeline = voice.run(ctx, scr) if start_at <= 3 else ctx.load_json("timeline.json")
    timeline = visuals.run(ctx, scr, timeline) if start_at <= 4 else timeline
    files = assemble.run(ctx, timeline) if start_at <= 5 else {"short": str(ctx.path("short.mp4")), "wide": str(ctx.path("wide.mp4"))}
    thumb = thumbnail.run(ctx, scr) if start_at <= 6 else str(ctx.path("thumb.png"))
    result = publish.run(ctx, scr, files, thumb)

    ctx.path("run.log").write_text("\n".join(ctx.log_lines) + "\n")
    ctx.log("done.")
    ctx.log(f"  short:  {files['short']}")
    ctx.log(f"  wide:   {files['wide']}")
    ctx.log(f"  thumb:  {thumb}")
    ctx.log(f"  meta:   {ctx.path('upload.json')}")
    if result.get("uploaded"):
        ctx.log(f"  url:    {result['meta']['url']}")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    run_p = sub.add_parser("run", help="full pipeline")
    run_p.add_argument("--date", type=date.fromisoformat, default=None)
    run_p.add_argument("--dry-run", action="store_true", help="no network, no API keys")

    scout_p = sub.add_parser("scout", help="pull the news and stop")
    scout_p.add_argument("--date", type=date.fromisoformat, default=None)

    from_p = sub.add_parser("from", help="resume from a step using files already in out/<date>/")
    from_p.add_argument("step", choices=STEPS[1:])
    from_p.add_argument("--date", type=date.fromisoformat, default=None)
    from_p.add_argument("--dry-run", action="store_true")

    args = ap.parse_args()
    ctx = make_context(run_date=args.date, dry_run=getattr(args, "dry_run", False))

    if args.cmd == "run":
        run_pipeline(ctx)
    elif args.cmd == "scout":
        scout.run(ctx)
    elif args.cmd == "from":
        run_pipeline(ctx, start=args.step)


if __name__ == "__main__":
    main()
