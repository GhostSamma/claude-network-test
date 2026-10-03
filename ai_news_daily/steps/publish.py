"""Step 8 — upload to YouTube, or hand you everything to upload by hand.

Always writes upload.json (title, description, tags, file paths). Only hits
YouTube when publish.enabled is true AND the OAuth files exist. See README for
the one-time Google setup.
"""

from __future__ import annotations

from pathlib import Path

from .common import ROOT, Context

SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]


def _metadata(ctx: Context, script: dict, files: dict, thumb: str) -> dict:
    links = "\n".join(f"• {s['headline']} — {s.get('link', '')}" for s in script["segments"] if s.get("link"))
    description = f"{script.get('description', '').strip()}\n\nSources:\n{links}\n\n#AI #ArtificialIntelligence #TechNews"
    return {
        "title": script["title"][:100],
        "description": description[:5000],
        "tags": [t[:30] for t in script.get("tags", [])][:30],
        "short": files["short"],
        "wide": files["wide"],
        "thumbnail": thumb,
        "privacy": ctx.config["publish"]["privacy"],
    }


def _youtube_client():
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from googleapiclient.discovery import build

    token_path = ROOT / "token.json"
    secrets_path = ROOT / "client_secrets.json"
    creds = Credentials.from_authorized_user_file(str(token_path), SCOPES) if token_path.exists() else None
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(str(secrets_path), SCOPES)
            creds = flow.run_local_server(port=0)
        token_path.write_text(creds.to_json())
    return build("youtube", "v3", credentials=creds)


def _upload(ctx: Context, meta: dict, video_path: str) -> str:
    from googleapiclient.http import MediaFileUpload

    yt = _youtube_client()
    body = {
        "snippet": {
            "title": meta["title"],
            "description": meta["description"],
            "tags": meta["tags"],
            "categoryId": ctx.config["publish"]["category_id"],
        },
        "status": {
            "privacyStatus": meta["privacy"],
            "selfDeclaredMadeForKids": ctx.config["publish"]["made_for_kids"],
        },
    }
    media = MediaFileUpload(video_path, chunksize=-1, resumable=True)
    request = yt.videos().insert(part="snippet,status", body=body, media_body=media)
    response = None
    while response is None:
        _, response = request.next_chunk()
    video_id = response["id"]
    yt.thumbnails().set(videoId=video_id, media_body=MediaFileUpload(meta["thumbnail"])).execute()
    return video_id


def run(ctx: Context, script: dict, files: dict, thumb: str) -> dict:
    meta = _metadata(ctx, script, files, thumb)
    ctx.save_json("upload.json", meta)

    cfg = ctx.config["publish"]
    ready = (ROOT / "client_secrets.json").exists()
    if not cfg["enabled"] or ctx.dry_run or not ready:
        why = "dry run" if ctx.dry_run else ("publish.enabled is false" if not cfg["enabled"] else "no client_secrets.json")
        ctx.log(f"publish: skipped ({why}) — upload.json has the title, description and tags. Upload short.mp4 by hand.")
        return {"uploaded": False, "meta": meta}

    video_id = _upload(ctx, meta, files["short"])
    url = f"https://youtube.com/shorts/{video_id}"
    ctx.log(f"publish: uploaded as {meta['privacy']} → {url}")
    meta["url"] = url
    ctx.save_json("upload.json", meta)
    return {"uploaded": True, "meta": meta}
