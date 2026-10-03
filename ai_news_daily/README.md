# AI News Daily

One command turns today's AI news into a finished vertical short — scripted, voiced, captioned-on-card, assembled, thumbnailed, and ready to upload.

This file is the handoff. Anyone — or any agent — can run the channel from it.

```
🔍 scout → 🧠 pick → 📝 script → 🎙️ voice → 🎬 visuals → ✂️ assemble → 🖼️ thumbnail → 📤 publish
```

---

## Quick start (10 minutes)

```bash
cd ai_news_daily
pip install -r requirements.txt

# 1. Prove the build works — no keys, no network
python pipeline.py run --dry-run
#    → out/<today>/short.mp4 exists. Open it. Silent audio, real cards, real cuts.

# 2. Add your Anthropic key
echo 'ANTHROPIC_API_KEY=sk-ant-...' > .env

# 3. Make a real one
python pipeline.py run
#    → out/<today>/short.mp4 with real news, real script, real voice
#    → out/<today>/upload.json has the title, description and tags
```

Upload `short.mp4` to YouTube Shorts by hand with the text from `upload.json`. That's a working channel. Automate the upload later (below).

---

## The daily loop

```
python pipeline.py run
```

Then **watch the first 10 seconds.** That's the gate. Thumbs up → upload. Thumbs down → `python pipeline.py from script` regenerates the script and everything after it. Nobody posts without a human watching the hook.

Every run lives in `out/<date>/`:

| File | What |
|---|---|
| `stories.json` | everything scout pulled |
| `pick.json` | the 3 Claude chose, and why |
| `script.json` | the full script — edit it by hand if you want, then `from voice` |
| `timeline.json` | each spoken chunk: audio file, seconds, card |
| `cards/` | one PNG per chunk |
| `short.mp4` | 1080×1920 vertical — Shorts, Reels, TikTok |
| `wide.mp4` | 1920×1080 letterboxed — main YouTube upload |
| `thumb.png` | 1280×720 thumbnail |
| `upload.json` | title, description, tags, privacy |
| `run.log` | what happened |

---

## Resuming from a step

Something off? Don't rerun everything.

```bash
python pipeline.py from script    # new script, same picks
python pipeline.py from voice     # same script, re-voice (after editing script.json)
python pipeline.py from assemble  # re-cut only (after tweaking visuals in config)
```

---

## config.yaml — the only file you edit

**`channel.persona`** — the whole personality. Claude writes every word in this voice. Rewrite it and the channel changes. This is the single highest-leverage line in the project.

**`sources`** — RSS feeds. Add any feed URL. Remove ones that produce junk. No keys.

**`pick.stories_per_video`** — 3 is right for 60–90s. 1 for a single-story deep dive.

**`script.target_seconds`** — 75 is the Shorts sweet spot. Under 60 finishes more often.

**`voice.engine`** — `edge` is free, no key, decent. `elevenlabs` is better and needs `ELEVENLABS_API_KEY` in `.env` plus a `voice_id`.

**`visuals.theme`** — five hex colors. Change them and every card changes.

**`visuals.ken_burns`** — slow zoom on each card. Leave it on; static frames die on retention.

**`publish.enabled`** — flip to `true` once Google is set up (below). Starts `private` so you can check before anyone sees it.

---

## Automatic YouTube upload (one-time setup, ~20 minutes)

1. Go to [console.cloud.google.com](https://console.cloud.google.com) → new project → enable **YouTube Data API v3**
2. Credentials → Create → **OAuth client ID** → Desktop app → download the JSON
3. Save it as `ai_news_daily/client_secrets.json`
4. `pip install google-api-python-client google-auth-oauthlib`
5. In `config.yaml` set `publish.enabled: true`
6. First `python pipeline.py run` opens a browser once to log in. It saves `token.json`. Never again.

Uploads go up as **private**. Watch it, then flip to public in YouTube Studio — or set `publish.privacy: public` once you trust it.

**Daily quota:** YouTube gives 10,000 units/day. One upload costs ~1,600. You get about 6 uploads a day before it stops you. Plenty.

---

## Running it every day on its own

**Mac / Linux** — cron, 8am:
```
0 8 * * * cd /path/to/ai_news_daily && /usr/bin/python3 pipeline.py run >> cron.log 2>&1
```

**Windows** — Task Scheduler → daily → `python pipeline.py run` with "Start in" set to the folder.

**With the human gate kept:** schedule `run` with `publish.enabled: false`. Every morning there's a `short.mp4` waiting. You watch 10 seconds, upload or regenerate. Flip `publish.enabled` on only when you've seen 10 in a row you'd have posted anyway.

---

## Adding a second channel

Copy the folder. Change `config.yaml` — new persona, new sources, new theme. That's a new channel. Same code.

| Channel idea | Change |
|---|---|
| AI tools for small business | persona + sources (Product Hunt, Indie Hackers feeds) |
| Crypto daily | persona + sources + theme |
| Spanish-language AI news | persona says "escribe en español", `voice.edge_voice: es-MX-JorgeNeural` |

---

## What it costs

| | |
|---|---|
| Claude, per video | ~2 calls. Pennies on Opus, less on Sonnet (`pick.model` / `script.model`) |
| Voice | `edge`: free. ElevenLabs: ~$5/mo for a daily short |
| YouTube | free |
| Your time | 10 seconds a day to watch the hook |

---

## When it breaks

**`ANTHROPIC_API_KEY is not set`** → put it in `.env` in this folder.

**`No JSON in reply`** → Claude wrote prose instead of JSON. Rare. Run `from pick` or `from script` again.

**Scout finds 0 stories** → a feed URL changed. Open it in a browser; swap it in `config.yaml`. The run still works with whatever feeds answered.

**edge-tts fails** → it needs a clean internet connection (no corporate proxy). Switch to `elevenlabs` or check the network.

**`ffmpeg failed`** → read the error line. The bundled binary handles 99% of cases; if you have ffmpeg installed system-wide it uses that instead.

**Video looks frozen** → `ken_burns` is off, or the run was `--dry-run` (silent audio makes it feel frozen). Real voice fixes the feel.

---

## v2 — what's next, in order

1. **Word-timed captions** — edge-tts gives word timestamps; burn 3-word caption groups synced to the voice. Biggest retention lever not yet built.
2. **Product screenshots** — scout grabs the og:image from each story; cards show it. Beats text-only.
3. **B-roll** — Pexels API (free) for 3-second clips between cards.
4. **TikTok / Reels upload** — their APIs, same pattern as YouTube.
5. **Weekly roundup** — Friday run pulls the week's `pick.json` files and makes a 3-minute wide cut.

Each is a day of work. Do #1 first.

---

## The one rule

**The machine makes it. A human watches the hook. Then it posts.**

The day you remove the gate is the day the channel posts something embarrassing. Keep the 10 seconds.
