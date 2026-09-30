"""Where a watcher sends its alerts."""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import urllib.request
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol


class Notifier(Protocol):
    def send(self, title: str, message: str) -> None: ...


@dataclass
class ConsoleNotifier:
    stream: object = sys.stdout

    def send(self, title: str, message: str) -> None:
        stamp = datetime.now().strftime("%H:%M:%S")
        print(f"[{stamp}] {title}: {message}", file=self.stream, flush=True)


@dataclass
class WebhookNotifier:
    """POST a JSON body to any URL -- Slack, Discord, your own server."""

    url: str
    timeout: float = 10.0

    def send(self, title: str, message: str) -> None:
        payload = json.dumps(
            {"title": title, "message": message, "text": f"{title}: {message}"}
        ).encode()
        request = urllib.request.Request(
            self.url, data=payload, headers={"Content-Type": "application/json"}
        )
        urllib.request.urlopen(request, timeout=self.timeout).close()


@dataclass
class NtfyNotifier:
    """Push to a phone via ntfy.sh -- no account, just pick a topic name."""

    topic: str
    server: str = "https://ntfy.sh"
    timeout: float = 10.0

    def send(self, title: str, message: str) -> None:
        request = urllib.request.Request(
            f"{self.server.rstrip('/')}/{self.topic}",
            data=message.encode("utf-8"),
            headers={"Title": title},
        )
        urllib.request.urlopen(request, timeout=self.timeout).close()


@dataclass
class DesktopNotifier:
    """Local desktop popup via notify-send (Linux) or osascript (macOS)."""

    def send(self, title: str, message: str) -> None:
        if shutil.which("notify-send"):
            subprocess.run(["notify-send", title, message], check=False)
        elif shutil.which("osascript"):
            script = f'display notification {json.dumps(message)} with title {json.dumps(title)}'
            subprocess.run(["osascript", "-e", script], check=False)
        else:
            ConsoleNotifier().send(title, message)


@dataclass
class MultiNotifier:
    """Fan out to several notifiers; one failure never blocks the others."""

    notifiers: list[Notifier]

    def send(self, title: str, message: str) -> None:
        for notifier in self.notifiers:
            try:
                notifier.send(title, message)
            except Exception as exc:  # noqa: BLE001 - alerting must not crash the watcher
                print(f"notifier {type(notifier).__name__} failed: {exc}", file=sys.stderr)


def from_spec(spec: str) -> Notifier:
    """Build a notifier from a CLI-friendly string.

    console | desktop | ntfy:mytopic | webhook:https://...
    """
    kind, _, value = spec.partition(":")
    kind = kind.strip().lower()
    if kind == "console":
        return ConsoleNotifier()
    if kind == "desktop":
        return DesktopNotifier()
    if kind == "ntfy":
        if not value:
            raise ValueError("ntfy notifier needs a topic, e.g. ntfy:my-alerts")
        return NtfyNotifier(topic=value)
    if kind == "webhook":
        if not value:
            raise ValueError("webhook notifier needs a URL, e.g. webhook:https://...")
        return WebhookNotifier(url=value)
    raise ValueError(f"Unknown notifier {spec!r}. Use console, desktop, ntfy:TOPIC or webhook:URL.")
