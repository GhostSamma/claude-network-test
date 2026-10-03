"""Step 1 — pull today's AI news from the RSS sources in config.yaml."""

from __future__ import annotations

import calendar
import re
import time
from datetime import datetime, timedelta, timezone

import feedparser

from .common import ROOT, Context


def _clean(html: str) -> str:
    text = re.sub(r"<[^>]+>", " ", html or "")
    return re.sub(r"\s+", " ", text).strip()


def _published(entry) -> datetime | None:
    for key in ("published_parsed", "updated_parsed"):
        struct = entry.get(key)
        if struct:
            return datetime.fromtimestamp(calendar.timegm(struct), tz=timezone.utc)
    return None


def run(ctx: Context) -> list[dict]:
    if ctx.dry_run:
        stories = __import__("json").loads((ROOT / "fixtures" / "stories.json").read_text())
        ctx.log(f"scout: dry run — using {len(stories)} fixture stories")
        ctx.save_json("stories.json", stories)
        return stories

    cfg = ctx.config
    cutoff = datetime.now(timezone.utc) - timedelta(hours=cfg["scout"]["lookback_hours"])
    seen_links: set[str] = set()
    seen_titles: set[str] = set()
    stories: list[dict] = []

    for source in cfg["sources"]:
        started = time.time()
        feed = feedparser.parse(source["url"])
        count = 0
        for entry in feed.entries:
            when = _published(entry)
            if when and when < cutoff:
                continue
            link = entry.get("link", "")
            title = _clean(entry.get("title", ""))
            key = re.sub(r"[^a-z0-9]", "", title.lower())[:60]
            if not title or link in seen_links or key in seen_titles:
                continue
            seen_links.add(link)
            seen_titles.add(key)
            stories.append(
                {
                    "source": source["name"],
                    "title": title,
                    "link": link,
                    "summary": _clean(entry.get("summary", ""))[:600],
                    "published": when.isoformat() if when else None,
                }
            )
            count += 1
        ctx.log(f"scout: {source['name']:<22} {count:>3} new  ({time.time() - started:.1f}s)")

    stories.sort(key=lambda s: s["published"] or "", reverse=True)
    stories = stories[: cfg["scout"]["max_candidates"]]
    ctx.log(f"scout: {len(stories)} candidates after dedupe + cutoff")
    ctx.save_json("stories.json", stories)
    return stories
