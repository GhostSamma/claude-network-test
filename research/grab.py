#!/usr/bin/env python3
"""Pull a YouTube video's timestamped transcript. No dependencies."""
import json, re, sys, urllib.request

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36")


def get(url, timeout=30):
    req = urllib.request.Request(url, headers={
        "User-Agent": UA, "Accept-Language": "en-US,en;q=0.9"})
    return urllib.request.urlopen(req, timeout=timeout).read().decode("utf-8", "replace")


def vid_id(s):
    s = s.strip()
    m = re.search(r'(?:v=|youtu\.be/|shorts/|embed/)([A-Za-z0-9_-]{11})', s)
    if m:
        return m.group(1)
    if re.fullmatch(r'[A-Za-z0-9_-]{11}', s):
        return s
    return None


def stamp(sec):
    sec = int(sec)
    h, m, s = sec // 3600, (sec % 3600) // 60, sec % 60
    return "%d:%02d:%02d" % (h, m, s) if h else "%d:%02d" % (m, s)


def tracks(vid):
    """Caption tracks YouTube advertises on the watch page."""
    html = get("https://www.youtube.com/watch?v=" + vid)
    m = re.search(r'"captionTracks":(\[.*?\])', html)
    if not m:
        return []
    try:
        return json.loads(m.group(1).replace("\\u0026", "&"))
    except Exception:
        return []


def rank(t):
    """Real English captions first, then English auto-generated, then anything."""
    lc = t.get("languageCode") or ""
    return (0 if lc.startswith("en") else 1, 1 if t.get("kind") == "asr" else 0)


def transcript(vid):
    """Returns (segments, note) or (None, reason). segments = [(start_sec, text), ...]"""
    try:
        ts = tracks(vid)
    except Exception as e:
        return None, "watch page fetch failed: %s" % str(e)[:120]
    if not ts:
        return None, "no caption tracks on the watch page (captions likely disabled)"
    t = sorted(ts, key=rank)[0]
    url = (t.get("baseUrl") or "").replace("\\u0026", "&")
    if not url:
        return None, "caption track had no baseUrl"
    try:
        body = get(url + "&fmt=json3")
    except Exception as e:
        return None, "timedtext fetch failed: %s" % str(e)[:120]
    if not body.strip():
        return None, "timedtext returned empty"
    try:
        d = json.loads(body)
    except Exception:
        return None, "timedtext was not json3"
    out = []
    for ev in d.get("events", []) or []:
        txt = "".join(s.get("utf8", "") for s in (ev.get("segs") or []))
        txt = " ".join(txt.split())
        if txt:
            out.append((float(ev.get("tStartMs", 0)) / 1000.0, txt))
    if not out:
        return None, "caption track parsed but had no text"
    return out, "%s%s" % (t.get("languageCode"), " auto" if t.get("kind") == "asr" else "")


def main():
    if len(sys.argv) < 2:
        print("usage: python grab.py <url-or-11-char-id> [out.txt]")
        raise SystemExit(2)
    vid = vid_id(sys.argv[1])
    if not vid:
        raise SystemExit("could not parse a video id from: %s" % sys.argv[1])
    segs, note = transcript(vid)
    if segs is None:
        print("FAIL  %s  ->  %s" % (vid, note))
        raise SystemExit(1)
    lines = ["# transcript %s  [%s]  %d segments" % (vid, note, len(segs)), ""]
    for start, text in segs:
        lines.append("[%s] %s" % (stamp(start), text))
    body = "\n".join(lines) + "\n"
    if len(sys.argv) > 2:
        open(sys.argv[2], "w", encoding="utf-8").write(body)
        print("WROTE %s  (%d segments, %s)" % (sys.argv[2], len(segs), note))
    else:
        print(body)


if __name__ == "__main__":
    main()
