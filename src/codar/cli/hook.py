"""Hook global do SO: `codar hook trigger` traduz a linha onde está o cursor em QUALQUER aplicativo.

Capturar teclas globalmente fica a cargo do próprio SO (atalho do GNOME/KDE, Hammerspoon no macOS,
Start-CodarHotkey no Windows): é o caminho seguro e funciona no Wayland, onde apps não podem
interceptar o teclado. O trigger então: seleciona a linha -> copia -> traduz -> cola -> restaura o clipboard.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
import time

from codar import config, langs


def _run(cmd: list[str], data: str | None = None) -> str:
    r = subprocess.run(cmd, input=data, capture_output=True, text=True, timeout=5)
    return r.stdout


class Backend:
    name = "?"

    def select_line(self) -> None: ...
    def copy(self) -> None: ...
    def paste(self) -> None: ...
    def get_clip(self) -> str: return ""
    def set_clip(self, text: str) -> None: ...
    def window_title(self) -> str: return ""


class X11(Backend):
    name = "x11"

    def __init__(self) -> None:
        self.clip = ["xclip", "-selection", "clipboard"] if shutil.which("xclip") else ["xsel", "--clipboard"]

    def _key(self, *keys: str) -> None:
        subprocess.run(["xdotool", "key", "--clearmodifiers", *keys], check=False)

    def select_line(self): self._key("Home", "shift+End")
    def copy(self): self._key("ctrl+c")
    def paste(self): self._key("ctrl+v")
    def get_clip(self): return _run(self.clip + (["-o"] if self.clip[0] == "xclip" else ["--output"]))
    def set_clip(self, text): _run(self.clip + (["-i"] if self.clip[0] == "xclip" else ["--input"]), text)
    def window_title(self): return _run(["xdotool", "getactivewindow", "getwindowname"]).strip()


class Wayland(Backend):
    name = "wayland"

    def __init__(self) -> None:
        self.typer = "wtype" if shutil.which("wtype") else "ydotool"

    def _combo(self, mod: str | None, key: str) -> None:
        if self.typer == "wtype":
            cmd = ["wtype"] + (["-M", mod] if mod else []) + ["-k", key] + (["-m", mod] if mod else [])
        else:  # ydotool usa keycodes evdev: 29=ctrl 42=shift 102=home 107=end 46=c 47=v
            codes = {"ctrl": 29, "shift": 42, "Home": 102, "End": 107, "c": 46, "v": 47}
            seq = ([f"{codes[mod]}:1"] if mod else []) + [f"{codes[key]}:1", f"{codes[key]}:0"] + \
                ([f"{codes[mod]}:0"] if mod else [])
            cmd = ["ydotool", "key", *seq]
        subprocess.run(cmd, check=False)

    def select_line(self):
        self._combo(None, "Home")
        self._combo("shift", "End")

    def copy(self): self._combo("ctrl", "c")
    def paste(self): self._combo("ctrl", "v")
    def get_clip(self): return _run(["wl-paste", "--no-newline"])
    def set_clip(self, text): _run(["wl-copy"], text)


class MacOS(Backend):
    name = "macos"

    def _osa(self, script: str) -> str:
        return _run(["osascript", "-e", script])

    def select_line(self):
        self._osa('tell application "System Events" to key code 123 using {command down}')
        self._osa('tell application "System Events" to key code 124 using {command down, shift down}')

    def copy(self): self._osa('tell application "System Events" to keystroke "c" using {command down}')
    def paste(self): self._osa('tell application "System Events" to keystroke "v" using {command down}')
    def get_clip(self): return _run(["pbpaste"])
    def set_clip(self, text): _run(["pbcopy"], text)

    def window_title(self):
        return self._osa('tell application "System Events" to get name of first window of '
                         '(first application process whose frontmost is true)').strip()


def detect() -> Backend | None:
    if sys.platform == "darwin":
        return MacOS()
    if sys.platform.startswith("linux"):
        if os.environ.get("WAYLAND_DISPLAY") and shutil.which("wl-copy") and (shutil.which("wtype") or shutil.which("ydotool")):
            return Wayland()
        if os.environ.get("DISPLAY") and shutil.which("xdotool") and (shutil.which("xclip") or shutil.which("xsel")):
            return X11()
    return None


def lang_from_title(title: str) -> str | None:
    for m in re.finditer(r"[\w.-]+\.(\w{1,5})\b", title):
        lg = langs.from_path(m.group(0))
        if lg:
            return lg.id
    return None


def trigger(lang: str | None) -> int:
    from codar.client import Client, RpcError

    be = detect()
    if be is None:
        print("codar hook: instale xdotool+xclip (X11), wtype/ydotool+wl-clipboard (Wayland); "
              "no Windows use Start-CodarHotkey do módulo PowerShell", file=sys.stderr)
        return 1
    cfg = config.load()
    saved = be.get_clip() if cfg["hook"].get("restore_clipboard", True) else None
    be.select_line()
    time.sleep(0.05)
    be.copy()
    time.sleep(0.15)
    intent = be.get_clip().strip()
    if not intent or intent == (saved or "").strip():
        return 1
    lang = lang or cfg["hook"].get("lang") or lang_from_title(be.window_title()) or "python"
    try:
        with Client.connect() as c:
            res = c.translate(intent, lang, audit=False)
    except (RpcError, OSError) as exc:
        _notify(f"codar: {exc}")
        return 3
    be.set_clip(res["code"])
    time.sleep(0.05)
    be.paste()
    if saved is not None:
        time.sleep(0.3)
        be.set_clip(saved)
    return 0


def _notify(msg: str) -> None:
    if shutil.which("notify-send"):
        subprocess.run(["notify-send", "codar", msg], check=False)
    else:
        print(msg, file=sys.stderr)


INSTALL = """Atalho global (o SO captura a tecla e chama `codar hook trigger`):

GNOME (X11/Wayland):
  gsettings set org.gnome.settings-daemon.plugins.media-keys custom-keybindings \\
    "['/org/gnome/settings-daemon/plugins/media-keys/custom-keybindings/codar/']"
  gsettings set org.gnome.settings-daemon.plugins.media-keys.custom-keybinding:/org/gnome/settings-daemon/plugins/media-keys/custom-keybindings/codar/ name 'codar'
  gsettings set org.gnome.settings-daemon.plugins.media-keys.custom-keybinding:/org/gnome/settings-daemon/plugins/media-keys/custom-keybindings/codar/ command '{exe} hook trigger'
  gsettings set org.gnome.settings-daemon.plugins.media-keys.custom-keybinding:/org/gnome/settings-daemon/plugins/media-keys/custom-keybindings/codar/ binding '<Primary><Alt>space'
  (se já houver outros atalhos personalizados, inclua-os na lista do primeiro comando)

KDE Plasma: Configurações > Atalhos > Adicionar comando: '{exe} hook trigger'
Ferramentas: X11 -> xdotool + xclip | Wayland -> wtype (ou ydotool) + wl-clipboard

Windows (PowerShell): Import-Module Codar; Start-CodarHotkey   (Ctrl+Alt+Espaço, RegisterHotKey nativo)
macOS: clients/hooks/hammerspoon.lua em ~/.hammerspoon/init.lua (Cmd+Alt+Espaço)
"""


def cmd_hook(args) -> int:
    if args.action == "install":
        exe = shutil.which("codar") or f"{sys.executable} -m codar"
        print(INSTALL.format(exe=exe))
        return 0
    return trigger(args.lang)
