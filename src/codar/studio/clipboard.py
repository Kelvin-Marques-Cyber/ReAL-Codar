"""Clipboard local quando disponível; OSC 52 continua atendendo terminais e SSH."""

import os
import shutil
import subprocess
import sys


def copy_text(app, text: str) -> None:
    app.copy_to_clipboard(text)
    argv = None
    data = text.encode("utf-8")
    if os.environ.get("SSH_CONNECTION") or os.environ.get("SSH_TTY"):
        return
    if sys.platform == "darwin" and shutil.which("pbcopy"):
        argv = ["pbcopy"]
    elif os.name == "nt" and shutil.which("clip.exe"):
        argv, data = ["clip.exe"], text.encode("utf-16le")
    elif os.environ.get("WAYLAND_DISPLAY") and shutil.which("wl-copy"):
        argv = ["wl-copy"]
    elif os.environ.get("DISPLAY"):
        if shutil.which("xclip"):
            argv = ["xclip", "-selection", "clipboard"]
        elif shutil.which("xsel"):
            argv = ["xsel", "--clipboard", "--input"]
    if argv:
        try:
            subprocess.run(argv, input=data, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=2)
        except (OSError, subprocess.TimeoutExpired):
            pass
