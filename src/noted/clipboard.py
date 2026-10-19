"""Cross-platform clipboard integration for noted."""

import shutil
import subprocess
import sys
from typing import Any, Optional

def copy_to_clipboard(text: str, app: Optional[Any] = None) -> bool:
    """Copies text to the system clipboard across macOS, Windows, and Linux.

    Supports:
    - macOS: native pbcopy
    - Windows: native clip.exe or powershell Set-Clipboard
    - Linux / Wayland: wl-copy
    - Linux / X11: xclip or xsel
    - OSC 52 terminal clipboard sequence (forwarded over SSH/remote terminal via app)
    - pyperclip fallback if installed

    Returns True if copying succeeded via at least one mechanism.
    """
    if not text:
        text = ""

    success = False

    # 1. Native platform clipboard commands
    if sys.platform == "darwin":
        if shutil.which("pbcopy"):
            try:
                p = subprocess.Popen(["pbcopy"], stdin=subprocess.PIPE, stderr=subprocess.DEVNULL)
                p.communicate(text.encode("utf-8"))
                if p.returncode == 0:
                    success = True
            except Exception:
                pass
    elif sys.platform == "win32":
        # Windows clip.exe
        if shutil.which("clip"):
            try:
                p = subprocess.Popen(["clip"], stdin=subprocess.PIPE, stderr=subprocess.DEVNULL)
                p.communicate(text.encode("utf-16le"))
                if p.returncode == 0:
                    success = True
            except Exception:
                pass
        if not success:
            # PowerShell Set-Clipboard fallback
            try:
                p = subprocess.Popen(
                    ["powershell", "-NoProfile", "-Command", "Set-Clipboard", "-Value", "$input"],
                    stdin=subprocess.PIPE,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
                p.communicate(text.encode("utf-8"))
                if p.returncode == 0:
                    success = True
            except Exception:
                pass
    else:
        # Linux / BSD
        if shutil.which("wl-copy"):
            try:
                p = subprocess.Popen(["wl-copy"], stdin=subprocess.PIPE, stderr=subprocess.DEVNULL)
                p.communicate(text.encode("utf-8"))
                if p.returncode == 0:
                    success = True
            except Exception:
                pass

        if not success and shutil.which("xclip"):
            try:
                p = subprocess.Popen(
                    ["xclip", "-selection", "clipboard"],
                    stdin=subprocess.PIPE,
                    stderr=subprocess.DEVNULL,
                )
                p.communicate(text.encode("utf-8"))
                if p.returncode == 0:
                    success = True
            except Exception:
                pass

        if not success and shutil.which("xsel"):
            try:
                p = subprocess.Popen(
                    ["xsel", "--clipboard", "--input"],
                    stdin=subprocess.PIPE,
                    stderr=subprocess.DEVNULL,
                )
                p.communicate(text.encode("utf-8"))
                if p.returncode == 0:
                    success = True
            except Exception:
                pass

    # 2. Pyperclip fallback if available
    if not success:
        try:
            import pyperclip
            pyperclip.copy(text)
            success = True
        except Exception:
            pass

    # 3. Textual OSC 52 terminal clipboard integration (propagates over SSH / remote terminal)
    if app is not None and hasattr(app, "copy_to_clipboard"):
        try:
            app.copy_to_clipboard(text)
            # If OSC 52 was called, count as at least partial success for remote TUI
            success = True
        except Exception:
            pass

    return success
