Write today's script for "{channel}", a faceless daily AI news short.

THE VOICE — every word is spoken in this voice:
{persona}

TARGET: about {seconds} seconds spoken, roughly {words} words total. This is a vertical short. People decide in 2 seconds whether to stay.

STRUCTURE:
- hook: ONE spoken line, max 12 words. Lead with the single most surprising thing from story 1. No "today in AI", no "hey everyone", no "let's get into it". Start mid-thought if it works.
- segments: one per story, in the order given. Each has:
    - headline: 4–8 words, on-screen text, plain and punchy
    - kicker: one short on-screen line (max 10 words) — the "so what" for a normal person
    - spoken: 2–4 short sentences the voice says. Say what happened, then what it means for someone who isn't a developer. Specific over vague. A number if there is one.
    - source: the source name
    - link: the story link
- outro: ONE spoken line, max 10 words, that invites a follow without begging. Can be a dry joke.
- title: the YouTube title, under 70 characters, specific, no clickbait caps, no emoji
- description: 2–3 sentences for the YouTube description
- tags: 8–12 lowercase tags

RULES:
- Short sentences. If a sentence has a comma, consider splitting it.
- No filler: "basically", "actually", "essentially", "in this video", "as you know".
- No exclamation marks. Energy comes from word choice and pace.
- Don't invent details. If the summary doesn't say it, don't say it.
- Spoken text has no markdown, no URLs, no hashtags — it's read aloud.

Reply with ONLY this JSON, nothing else:

{{
  "title": "...",
  "hook": "...",
  "segments": [
    {{"headline": "...", "kicker": "...", "spoken": "...", "source": "...", "link": "..."}}
  ],
  "outro": "...",
  "description": "...",
  "tags": ["..."]
}}

TODAY'S STORIES:
{picks}
