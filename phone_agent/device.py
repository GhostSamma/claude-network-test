"""Thin, synchronous wrapper around the Android Debug Bridge.

Everything here shells out to `adb`. No root required -- the device just needs
USB debugging (or wireless debugging) turned on and this host authorised.
"""

from __future__ import annotations

import re
import shutil
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path

# `input text` treats these as syntax rather than literal characters.
_TEXT_ESCAPES = str.maketrans(
    {c: "\\" + c for c in "\\()<>|;&*~\"'`$?[]{}"}
)

_UI_DUMP_REMOTE = "/sdcard/phone_agent_dump.xml"


class AdbError(RuntimeError):
    """Raised when an adb invocation fails or adb itself is missing."""


@dataclass(frozen=True)
class DeviceInfo:
    serial: str
    state: str

    @property
    def is_ready(self) -> bool:
        return self.state == "device"


class Device:
    """A single attached Android device.

    >>> d = Device()                    # first ready device
    >>> d.tap(540, 1200)
    >>> d.ui_dump()                     # raw uiautomator XML
    """

    def __init__(self, serial: str | None = None, adb: str = "adb", timeout: float = 30.0):
        self.adb = adb
        self.timeout = timeout
        self.serial = serial or self._default_serial()

    # ----- process plumbing -------------------------------------------------

    def _argv(self, args: list[str]) -> list[str]:
        base = [self.adb]
        if self.serial:
            base += ["-s", self.serial]
        return base + args

    def _run(self, args: list[str], *, binary: bool = False, timeout: float | None = None):
        if shutil.which(self.adb) is None:
            raise AdbError(
                f"{self.adb!r} not found on PATH. Install platform-tools: "
                "https://developer.android.com/tools/releases/platform-tools"
            )
        try:
            proc = subprocess.run(
                self._argv(args),
                capture_output=True,
                timeout=timeout if timeout is not None else self.timeout,
            )
        except subprocess.TimeoutExpired as exc:
            raise AdbError(f"adb {' '.join(args)} timed out after {exc.timeout}s") from exc
        if proc.returncode != 0:
            stderr = proc.stderr.decode("utf-8", "replace").strip()
            raise AdbError(f"adb {' '.join(args)} failed ({proc.returncode}): {stderr}")
        return proc.stdout if binary else proc.stdout.decode("utf-8", "replace")

    def shell(self, command: str, *, binary: bool = False, timeout: float | None = None):
        """Run a shell command on the device and return its stdout."""
        return self._run(["shell", command], binary=binary, timeout=timeout)

    # ----- discovery --------------------------------------------------------

    @classmethod
    def list_devices(cls, adb: str = "adb") -> list[DeviceInfo]:
        if shutil.which(adb) is None:
            raise AdbError(f"{adb!r} not found on PATH.")
        out = subprocess.run([adb, "devices"], capture_output=True, timeout=30)
        lines = out.stdout.decode("utf-8", "replace").splitlines()[1:]
        devices = []
        for line in lines:
            parts = line.split()
            if len(parts) >= 2:
                devices.append(DeviceInfo(serial=parts[0], state=parts[1]))
        return devices

    def _default_serial(self) -> str | None:
        ready = [d for d in self.list_devices(self.adb) if d.is_ready]
        if not ready:
            raise AdbError(
                "No ready device. Check `adb devices` -- if it says 'unauthorized', "
                "accept the debugging prompt on the phone."
            )
        if len(ready) > 1:
            names = ", ".join(d.serial for d in ready)
            raise AdbError(f"Multiple devices attached ({names}); pass serial= to pick one.")
        return ready[0].serial

    @classmethod
    def connect(cls, address: str, adb: str = "adb", **kwargs) -> "Device":
        """Attach over wireless debugging, e.g. Device.connect('192.168.1.5:5555')."""
        result = subprocess.run([adb, "connect", address], capture_output=True, timeout=30)
        text = result.stdout.decode("utf-8", "replace")
        if "connected" not in text:
            raise AdbError(f"Could not connect to {address}: {text.strip()}")
        return cls(serial=address, adb=adb, **kwargs)

    # ----- input ------------------------------------------------------------

    def tap(self, x: int, y: int) -> None:
        self.shell(f"input tap {int(x)} {int(y)}")

    def swipe(self, x1: int, y1: int, x2: int, y2: int, duration_ms: int = 300) -> None:
        self.shell(f"input swipe {int(x1)} {int(y1)} {int(x2)} {int(y2)} {int(duration_ms)}")

    def long_press(self, x: int, y: int, duration_ms: int = 800) -> None:
        self.swipe(x, y, x, y, duration_ms)

    def type_text(self, text: str) -> None:
        """Type literal text. Spaces become %s, shell metacharacters are escaped."""
        escaped = text.translate(_TEXT_ESCAPES).replace(" ", "%s")
        self.shell(f"input text {escaped}")

    def key(self, keycode: str | int) -> None:
        """Press a key, by name ('ENTER', 'BACK', 'HOME') or numeric keycode."""
        code = keycode if isinstance(keycode, int) else f"KEYCODE_{str(keycode).upper().removeprefix('KEYCODE_')}"
        self.shell(f"input keyevent {code}")

    # ----- app + screen -----------------------------------------------------

    def launch(self, package: str) -> None:
        self.shell(f"monkey -p {package} -c android.intent.category.LAUNCHER 1")

    def stop(self, package: str) -> None:
        self.shell(f"am force-stop {package}")

    def current_app(self) -> str | None:
        """Best-effort package name of the foreground activity."""
        out = self.shell("dumpsys window 2>/dev/null | grep -E 'mCurrentFocus|mFocusedApp'")
        match = re.search(r"([A-Za-z][\w.]+)/[\w.$]+", out)
        return match.group(1) if match else None

    def screen_size(self) -> tuple[int, int]:
        out = self.shell("wm size")
        match = re.search(r"(\d+)x(\d+)\s*$", out.strip().splitlines()[-1])
        if not match:
            raise AdbError(f"Could not parse screen size from: {out!r}")
        return int(match.group(1)), int(match.group(2))

    def is_screen_on(self) -> bool:
        out = self.shell("dumpsys power | grep -E 'mWakefulness='")
        return "Awake" in out

    def wake(self) -> None:
        if not self.is_screen_on():
            self.key("WAKEUP")

    def screenshot(self, path: str | Path | None = None) -> bytes:
        """Capture the screen as PNG bytes, optionally writing them to `path`."""
        png = self._run(["exec-out", "screencap", "-p"], binary=True)
        if path is not None:
            Path(path).write_bytes(png)
        return png

    # ----- UI hierarchy -----------------------------------------------------

    def ui_dump(self, retries: int = 2) -> str:
        """Return the current window's uiautomator XML.

        uiautomator intermittently fails while the UI is animating, so this
        retries a couple of times before giving up.
        """
        last_error: Exception | None = None
        for attempt in range(retries + 1):
            try:
                self.shell(f"uiautomator dump {_UI_DUMP_REMOTE}", timeout=max(self.timeout, 30))
                xml = self.shell(f"cat {_UI_DUMP_REMOTE}")
                if "<hierarchy" in xml:
                    return xml
                last_error = AdbError(f"uiautomator returned no hierarchy: {xml.strip()[:200]}")
            except AdbError as exc:
                last_error = exc
            if attempt < retries:
                time.sleep(0.6)
        raise AdbError(f"uiautomator dump failed after {retries + 1} attempts: {last_error}")
