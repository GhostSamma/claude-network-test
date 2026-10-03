"""Shared helpers: run context, Claude client, JSON parsing, ffmpeg location."""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent


@dataclass
class Context:
    """Everything a step needs. One per run."""

    config: dict
    run_date: date
    out_dir: Path
    dry_run: bool = False
    log_lines: list[str] = field(default_factory=list)

    def log(self, message: str) -> None:
        line = f"[{self.run_date}] {message}"
        print(line, flush=True)
        self.log_lines.append(line)

    def path(self, *parts: str) -> Path:
        p = self.out_dir.joinpath(*parts)
        p.parent.mkdir(parents=True, exist_ok=True)
        return p

    def save_json(self, name: str, data) -> Path:
        p = self.path(name)
        p.write_text(json.dumps(data, indent=2, ensure_ascii=False))
        return p

    def load_json(self, name: str):
        return json.loads(self.path(name).read_text())


def load_config(path: Path | None = None) -> dict:
    with open(path or ROOT / "config.yaml") as f:
        return yaml.safe_load(f)


def make_context(run_date: date | None = None, dry_run: bool = False, config_path: Path | None = None) -> Context:
    run_date = run_date or date.today()
    config = load_config(config_path)
    out_dir = ROOT / "out" / run_date.isoformat()
    out_dir.mkdir(parents=True, exist_ok=True)
    return Context(config=config, run_date=run_date, out_dir=out_dir, dry_run=dry_run)


# ----- Claude -------------------------------------------------------------

_client = None


def claude():
    """Lazy client. Reads ANTHROPIC_API_KEY from the environment."""
    global _client
    if _client is None:
        import anthropic

        _client = anthropic.Anthropic()
    return _client


def ask_claude(prompt: str, *, model: str, effort: str = "medium", system: str | None = None, max_tokens: int = 8000) -> str:
    """One call, text back. Adaptive thinking is on; effort controls how hard it thinks."""
    kwargs = dict(
        model=model,
        max_tokens=max_tokens,
        thinking={"type": "adaptive"},
        output_config={"effort": effort},
        messages=[{"role": "user", "content": prompt}],
    )
    if system:
        kwargs["system"] = system
    response = claude().messages.create(**kwargs)
    if response.stop_reason == "refusal":
        raise RuntimeError(f"Claude refused: {getattr(response.stop_details, 'explanation', '')}")
    return "".join(block.text for block in response.content if block.type == "text")


def parse_json_block(text: str):
    """Pull one JSON value out of a reply, tolerating a code fence or a sentence around it."""
    fence = re.search(r"```(?:json)?\s*(.*?)```", text, re.S)
    if fence:
        text = fence.group(1)
    start = min((i for i in (text.find("{"), text.find("[")) if i >= 0), default=-1)
    end = max(text.rfind("}"), text.rfind("]"))
    if start < 0 or end < 0:
        raise ValueError(f"No JSON in reply: {text[:200]!r}")
    return json.loads(text[start : end + 1])


# ----- ffmpeg -------------------------------------------------------------


def ffmpeg_exe() -> str:
    """System ffmpeg if present, otherwise the static binary bundled with imageio-ffmpeg."""
    found = shutil.which("ffmpeg")
    if found:
        return found
    import imageio_ffmpeg

    return imageio_ffmpeg.get_ffmpeg_exe()


def run_ffmpeg(args: list[str], *, quiet: bool = True) -> None:
    cmd = [ffmpeg_exe(), "-y", "-hide_banner", "-loglevel", "error" if quiet else "info", *args]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"ffmpeg failed:\n{' '.join(cmd)}\n{result.stderr[-2000:]}")


def media_duration(path: Path) -> float:
    """Seconds of audio/video, read with ffmpeg itself (no ffprobe needed)."""
    cmd = [ffmpeg_exe(), "-hide_banner", "-i", str(path), "-f", "null", "-"]
    result = subprocess.run(cmd, capture_output=True, text=True)
    match = re.search(r"Duration:\s*(\d+):(\d+):(\d+\.?\d*)", result.stderr)
    if not match:
        raise RuntimeError(f"Could not read duration of {path}")
    h, m, s = match.groups()
    return int(h) * 3600 + int(m) * 60 + float(s)


def prompt_text(name: str) -> str:
    return (ROOT / "prompts" / name).read_text()


def getenv_required(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise RuntimeError(f"{name} is not set. Put it in .env or export it.")
    return value
