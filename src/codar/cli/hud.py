"""Estética "mission control" para a CLI (paleta inspirada no console SENTRY).

Fundo quase preto, texto âmbar, rótulos em pílula vermelha, dados em verde/menta, molduras laranja.
Degrada para 256/16 cores e respeita NO_COLOR / terminais sem cor (pipes).
"""

from __future__ import annotations

import os
import shutil
import sys
import time

PALETTE = {
    "bg": (5, 4, 10), "text": (240, 179, 42), "dim": (107, 85, 31), "line": (122, 90, 20), "red": (255, 71, 71),
    "orange": (242, 101, 0), "mint": (71, 255, 169), "green": (84, 255, 138), "cyan": (57, 214, 200),
    "blue": (95, 123, 255), "moon": (207, 214, 230),
}
_ANSI16 = {"text": 33, "dim": 90, "line": 33, "red": 91, "orange": 31, "mint": 96, "green": 92, "cyan": 36,
           "blue": 94, "moon": 37, "bg": 30}


def _enable_windows_vt() -> bool:
    if os.name != "nt":
        return True
    try:
        import ctypes

        kernel32 = ctypes.windll.kernel32  # type: ignore[attr-defined]
        handle = kernel32.GetStdHandle(-11)
        mode = ctypes.c_uint32()
        if kernel32.GetConsoleMode(handle, ctypes.byref(mode)):
            return bool(kernel32.SetConsoleMode(handle, mode.value | 0x0004))
    except Exception:
        return False
    return False


def color_mode(stream=None) -> str:
    stream = stream or sys.stdout
    if os.environ.get("NO_COLOR") or os.environ.get("CODAR_NO_COLOR"):
        return "none"
    if not (os.environ.get("FORCE_COLOR") or (hasattr(stream, "isatty") and stream.isatty())):
        return "none"
    if not _enable_windows_vt():
        return "none"
    if os.environ.get("COLORTERM", "").lower() in ("truecolor", "24bit") or os.environ.get("WT_SESSION") \
            or os.environ.get("TERM_PROGRAM") in ("vscode", "iTerm.app", "WezTerm"):
        return "truecolor"
    if "256" in os.environ.get("TERM", ""):
        return "256"
    return "16"


def _rgb256(r: int, g: int, b: int) -> int:
    return 16 + 36 * round(r / 255 * 5) + 6 * round(g / 255 * 5) + round(b / 255 * 5)


class Hud:
    def __init__(self, stream=None) -> None:
        self.stream = stream or sys.stdout
        self.mode = color_mode(self.stream)
        self.ascii = os.environ.get("TERM") == "linux" or os.environ.get("CODAR_ASCII") == "1"

    @property
    def width(self) -> int:
        return max(40, min(shutil.get_terminal_size((100, 24)).columns, 120))

    def c(self, text: str, color: str = "text", bold: bool = False, dim: bool = False) -> str:
        if self.mode == "none":
            return text
        r, g, b = PALETTE[color]
        if self.mode == "truecolor":
            code = f"38;2;{r};{g};{b}"
        elif self.mode == "256":
            code = f"38;5;{_rgb256(r, g, b)}"
        else:
            code = str(_ANSI16[color])
        pre = ("1;" if bold else "") + ("2;" if dim else "")
        return f"\x1b[{pre}{code}m{text}\x1b[0m"

    def pill(self, label: str, color: str = "red", frame: str = "orange") -> str:
        l, r = ("[", "]") if self.ascii else ("▕", "▏")
        return self.c(l, frame) + self.c(f" {label.upper()} ", color, bold=True) + self.c(r, frame)

    def kv(self, key: str, value: str, color: str = "green") -> str:
        return self.c(key.upper(), "dim") + " " + self.c(value, color)

    def bullet(self, text: str, color: str = "green", mark: str = "▸") -> str:
        return self.c(mark if not self.ascii else ">", "red") + " " + self.c(text, color)

    def bar(self, value: float, maximum: float, width: int = 24, warn: float = 0.8, crit: float = 0.92) -> str:
        frac = 0.0 if maximum <= 0 else max(0.0, min(1.0, value / maximum))
        fill = int(round(frac * width))
        color = "red" if frac >= crit else "orange" if frac >= warn else "mint"
        full, empty, knob = ("#", "-", "o") if self.ascii else ("━", "─", "●")
        knob_pos = min(fill, width - 1)
        cells = [self.c(full, color) if i < knob_pos else self.c(knob, "mint", bold=True) if i == knob_pos
                 else self.c(empty, "line") for i in range(width)]
        return "".join(cells)

    def rule(self, title: str = "", color: str = "orange") -> str:
        line = "-" if self.ascii else "─"
        if not title:
            return self.c(line * self.width, color)
        head = self.pill(title) + " "
        return head + self.c(line * max(4, self.width - len(title) - 6), color)

    def panel(self, title: str, rows: list[str], width: int | None = None) -> str:
        width = width or self.width
        tl, tr, bl, br, h, v = ("+", "+", "+", "+", "-", "|") if self.ascii else ("╭", "╮", "╰", "╯", "─", "│")
        label = f" {title.upper()} "
        top = self.c(tl + h, "orange") + self.c(label, "red", bold=True) + self.c(h * max(0, width - len(label) - 3) + tr, "orange")
        out = [top]
        for row in rows:
            visible = _visible_len(row)
            pad = max(0, width - 4 - visible)
            out.append(self.c(v, "orange") + " " + row + " " * pad + " " + self.c(v, "orange"))
        out.append(self.c(bl + h * (width - 2) + br, "orange"))
        return "\n".join(out)

    def wrap(self, text: str, color: str = "text", width: int | None = None, indent: str = "",
             bold: bool = False) -> list[str]:
        """Quebra texto puro em linhas que cabem num painel e só então colore."""
        import textwrap

        width = (width or self.width) - 4 - len(indent)
        lines = textwrap.wrap(text, max(20, width)) or [""]
        return [indent + self.c(ln, color, bold=bold) for ln in lines]

    def clock(self) -> str:
        return time.strftime("%Y-%b-%d %H:%MZ", time.gmtime()).upper()

    def banner(self) -> str:
        art = BANNER_ASCII if self.ascii else BANNER
        lines = [self.c(ln, "mint", bold=True) for ln in art.strip("\n").split("\n")]
        tag = self.c("INTENT → CODE CONSOLE", "red", bold=True) + self.c("  ·  OFFLINE · ≤3GB RAM · ", "dim") + \
            self.c(self.clock(), "mint")
        return "\n".join(lines + [tag])


def _visible_len(s: str) -> int:
    import re

    return len(re.sub(r"\x1b\[[0-9;]*m", "", s))


BANNER = r"""
 ▄████▄   ▒█████  ▓█████▄  ▄▄▄       ██▀███
▒██▀ ▀█  ▒██▒  ██▒▒██▀ ██▌▒████▄    ▓██ ▒ ██▒
▒▓█    ▄ ▒██░  ██▒░██   █▌▒██  ▀█▄  ▓██ ░▄█ ▒
▒▓▓▄ ▄██▒▒██   ██░░▓█▄   ▌░██▄▄▄▄██ ▒██▀▀█▄
▒ ▓███▀ ░░ ████▓▒░░▒████▓  ▓█   ▓██▒░██▓ ▒██▒
"""

BANNER_ASCII = r"""
  ____ ___  ____    _    ____
 / ___/ _ \|  _ \  / \  |  _ \
| |  | | | | | | |/ _ \ | |_) |
| |__| |_| | |_| / ___ \|  _ <
 \____\___/|____/_/   \_\_| \_\
"""

STAGE_COLOR = {"0": "mint", "1": "green", "2:tools": "cyan", "2:adapt": "blue", "2:gen": "orange", "2:pseudo": "cyan"}
STAGE_LABEL = {"0": "S0 COMPILER", "1": "S1 PATTERN", "2:tools": "S2 TOOLS", "2:adapt": "S2 ADAPT", "2:gen": "S2 SLM",
               "2:pseudo": "S2 PSEUDO"}
SEV_COLOR = {"info": "cyan", "warning": "orange", "error": "red", "critical": "red"}
