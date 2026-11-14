"""Drives the OtterWorks Desktop WPF window through UI Automation (no app-side test hooks)."""

from __future__ import annotations

import ctypes
import ctypes.wintypes
import os
import subprocess
import time
from collections.abc import Callable
from pathlib import Path
from typing import TypeVar

import uiautomation as auto
from PIL import ImageGrab

WINDOW_TITLE = "OtterWorks Desktop"
T = TypeVar("T")


def session_store_path() -> Path:
    return Path(os.environ["APPDATA"]) / "OtterWorks" / "session.dat"


def wait_until(predicate: Callable[[], T], timeout: float = 15.0, message: str = "condition") -> T:
    deadline = time.monotonic() + timeout
    while True:
        result = predicate()
        if result:
            return result
        if time.monotonic() > deadline:
            raise TimeoutError(f"timed out waiting for {message}")
        time.sleep(0.2)


class DesktopApp:
    def __init__(self, process: subprocess.Popen, window: auto.WindowControl) -> None:
        self.process = process
        self.window = window

    @classmethod
    def start(cls, exe: Path) -> DesktopApp:
        process = subprocess.Popen([str(exe)], cwd=str(exe.parent))
        window = auto.WindowControl(
            searchDepth=1,
            Name=WINDOW_TITLE,
            Compare=lambda control, _depth: control.ProcessId == process.pid,
        )
        if not window.Exists(maxSearchSeconds=30, searchIntervalSeconds=0.25):
            process.kill()
            raise TimeoutError(f"{exe} did not show its main window")
        return cls(process, window)

    # ---- reading ----

    def texts(self) -> list[str]:
        names: list[str] = []
        for control, _depth in auto.WalkControl(self.window, maxDepth=0xFFFF):
            # Collapsed/hidden WPF elements stay in the UIA tree but report IsOffscreen; skip them.
            if control.ControlTypeName == "TextControl" and control.Name and not control.IsOffscreen:
                names.append(control.Name)
        return names

    def has_text(self, text: str) -> bool:
        # Inline Runs are exposed with XAML inter-element whitespace; compare collapsed.
        return " ".join(text.split()) in (" ".join(t.split()) for t in self.texts())

    def wait_for_text(self, text: str, timeout: float = 15.0) -> None:
        wait_until(lambda: self.has_text(text), timeout, f"text {text!r}; visible: {self.texts()}")

    def wait_for_text_prefix(self, prefix: str, timeout: float = 15.0) -> str:
        return wait_until(
            lambda: next((t for t in self.texts() if t.startswith(prefix)), None),
            timeout,
            f"text starting {prefix!r}",
        )

    def is_busy(self) -> bool:
        # Collapsed WPF elements stay in the UIA tree with an empty, offscreen rectangle.
        bar = self.window.ProgressBarControl(searchDepth=0xFFFF)
        return bar.Exists(0, 0) and not bar.IsOffscreen and bar.BoundingRectangle.width() > 0

    def wait_idle(self, timeout: float = 15.0) -> None:
        wait_until(lambda: not self.is_busy(), timeout, "busy indicator to clear")
        time.sleep(0.4)

    def heading(self) -> str:
        for title in ("Create account", "Sign in", "Documents"):
            if self.window.TextControl(searchDepth=0xFFFF, Name=title).Exists(0, 0):
                return title
        return ""

    # ---- input ----

    def fill(self, *values: str) -> None:
        """Fills the screen's edit boxes (text and password) in visual order."""
        edits = [c for c, _ in auto.WalkControl(self.window, maxDepth=0xFFFF) if c.ControlTypeName == "EditControl"]
        assert len(edits) >= len(values), f"expected {len(values)} edit boxes, found {len(edits)}"
        for edit, value in zip(edits, values):
            if edit.IsPassword:
                edit.SetFocus()
                edit.SendKeys("{Ctrl}a{Del}", waitTime=0.05)
                edit.SendKeys(value, interval=0.01, waitTime=0.1)
            else:
                edit.GetValuePattern().SetValue(value)
        # ValuePattern writes are not input events, so WPF's CommandManager would not
        # re-query CanExecute; a bare Shift keystroke is a real input event that does.
        edits[len(values) - 1].SetFocus()
        auto.SendKeys("{Shift}", waitTime=0.2)

    def click(self, name: str) -> None:
        button = self.window.ButtonControl(searchDepth=0xFFFF, Name=name)
        if not button.Exists(10, 0.2):
            raise LookupError(f"button {name!r} not found; visible text: {self.texts()}")
        wait_until(lambda: button.IsEnabled, 10, f"button {name!r} to be enabled")
        button.GetInvokePattern().Invoke()

    # ---- lifecycle ----

    def screenshot(self, path: Path) -> None:
        self.window.SetActive()
        self.window.SetTopmost(True)
        time.sleep(0.5)
        rect = self.window.BoundingRectangle
        ImageGrab.grab(bbox=(rect.left, rect.top, rect.right, rect.bottom), all_screens=True).save(path)
        self.window.SetTopmost(False)

    def close(self, timeout: float = 15.0) -> None:
        self.window.GetWindowPattern().Close()
        self.process.wait(timeout)

    def kill(self) -> None:
        if self.process.poll() is None:
            self.process.kill()
            self.process.wait(10)


class _DataBlob(ctypes.Structure):
    _fields_ = [("cbData", ctypes.wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_char))]


def dpapi_unprotect(data: bytes) -> bytes:
    """CryptUnprotectData for the current user, i.e. what the client's ProtectedData.Unprotect does."""
    buffer = ctypes.create_string_buffer(data, len(data))
    blob_in = _DataBlob(len(data), ctypes.cast(buffer, ctypes.POINTER(ctypes.c_char)))
    blob_out = _DataBlob()
    if not ctypes.windll.crypt32.CryptUnprotectData(
        ctypes.byref(blob_in), None, None, None, None, 0, ctypes.byref(blob_out)
    ):
        raise ctypes.WinError()
    try:
        return ctypes.string_at(blob_out.pbData, blob_out.cbData)
    finally:
        ctypes.windll.kernel32.LocalFree(blob_out.pbData)
