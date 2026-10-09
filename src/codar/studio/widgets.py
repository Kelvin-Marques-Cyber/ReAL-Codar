"""Widgets do Codar Studio: editor com gatilho espaço+Enter, radar orbital do pipeline, cartões HUD."""

from __future__ import annotations

import math
import os
import re
import time
from dataclasses import dataclass
from pathlib import Path

from rich.style import Style
from rich.text import Text
from textual import events
from textual.message import Message

from codar.engine import emmet
from codar.textutil import looks_like_intent
from codar.vocab import KEYWORDS, PSEUDO_WORDS
from textual.widget import Widget
from textual.widgets import TextArea
from textual.widgets.text_area import TextAreaTheme

# Paleta do SENTRY. O Studio inteiro lê as cores de C, que acompanha o tema ativo (Ctrl+P → tema): aplicar_paleta()
# troca os valores no lugar, então quem importou C vê as cores novas no próximo desenho.
SENTRY = {"bg": "#05040A", "panel": "#0B0915", "grid": "#0F0C1C", "text": "#f0b32a", "dim": "#6b551f", "line": "#7a5a14",
          "red": "#FF4747", "orange": "#F26500", "mint": "#47FFA9", "green": "#54ff8a", "cyan": "#39d6c8",
          "blue": "#5f7bff", "moon": "#cfd6e6", "sel": "#3a2c0a", "error": "#ff3b2f", "guide": "#4a3c16",
          "guide_faint": "#241d0b", "flash": "#0f2a1f"}
C = dict(SENTRY)
STAGE_COLORS: dict[str, str] = {}
ASCII = os.environ.get("TERM") == "linux" or os.environ.get("CODAR_ASCII") == "1"


def paleta(tema) -> dict[str, str]:
    """Cores do Studio para um tema do Textual. O SENTRY tem as suas; nos outros, cada cor vem do papel que cumpre:
    primária = molduras, secundária = rótulos e palavras-chave, destaque = dados e atalhos, sucesso = textos."""
    if tema is None or tema.name == "sentry":
        return dict(SENTRY)
    from textual.color import Color

    def cor(valor: str | None, padrao: str) -> Color:
        return Color.parse(valor or padrao)

    try:
        fundo = cor(tema.background, "#121212" if tema.dark else "#efefef")
        texto = cor(tema.foreground, "#e0e0e0" if tema.dark else "#1e1e1e")
        primaria = cor(tema.primary, "#0178D4")
        secundaria = cor(tema.secondary, tema.primary)
        destaque = cor(tema.accent, tema.primary)
        sucesso = cor(tema.success, "#4EBF71")
        return {"bg": fundo.hex6, "panel": cor(tema.surface, fundo.blend(texto, 0.04).hex6).hex6,
                "grid": fundo.blend(texto, 0.07).hex6, "text": texto.hex6, "dim": fundo.blend(texto, 0.45).hex6,
                "line": fundo.blend(primaria, 0.55).hex6, "red": secundaria.hex6, "orange": primaria.hex6,
                "mint": destaque.hex6, "green": sucesso.hex6, "cyan": destaque.blend(sucesso, 0.5).hex6,
                "blue": primaria.blend(secundaria, 0.5).hex6, "moon": texto.blend(destaque, 0.2).hex6,
                "sel": fundo.blend(primaria, 0.3).hex6, "error": cor(tema.error, "#ff3b2f").hex6,
                "guide": fundo.blend(texto, 0.3).hex6, "guide_faint": fundo.blend(texto, 0.13).hex6,
                "flash": fundo.blend(sucesso, 0.18).hex6}
    except Exception:  # tema com cores que não são RGB (ex.: textual-ansi): fica o SENTRY
        return dict(SENTRY)


def aplicar_paleta(nova: dict[str, str]) -> None:
    C.update(nova)
    STAGE_COLORS.update({"0": C["mint"], "1": C["green"], "2:tools": C["cyan"], "2:adapt": C["blue"],
                         "2:gen": C["orange"], "2:pseudo": C["cyan"]})


aplicar_paleta(SENTRY)


def tema_editor(nome: str) -> TextAreaTheme:
    """Tema do editor (realce de sintaxe, cursor, seleção) com a paleta ativa."""
    return TextAreaTheme(
        name=nome,
        base_style=Style(color=C["text"], bgcolor=C["bg"]),
        gutter_style=Style(color=C["dim"], bgcolor=C["bg"]),
        cursor_style=Style(color=C["bg"], bgcolor=C["mint"]),
        cursor_line_style=Style(bgcolor=C["grid"]),
        cursor_line_gutter_style=Style(color=C["mint"], bgcolor=C["grid"]),
        bracket_matching_style=Style(bgcolor=C["sel"], bold=True),
        selection_style=Style(bgcolor=C["sel"]),
        syntax_styles={
            "keyword": Style(color=C["red"], bold=True), "keyword.operator": Style(color=C["red"]),
            "conditional": Style(color=C["red"], bold=True), "repeat": Style(color=C["red"], bold=True),
            "exception": Style(color=C["red"], bold=True), "include": Style(color=C["red"]),
            "string": Style(color=C["green"]), "string.documentation": Style(color=C["dim"], italic=True),
            "comment": Style(color=C["dim"], italic=True), "number": Style(color=C["cyan"]),
            "float": Style(color=C["cyan"]), "boolean": Style(color=C["orange"], bold=True),
            "constant": Style(color=C["orange"]), "constant.builtin": Style(color=C["orange"]),
            "function": Style(color=C["mint"]), "function.call": Style(color=C["mint"]),
            "method": Style(color=C["mint"]), "method.call": Style(color=C["mint"]),
            "type": Style(color=C["blue"]), "type.builtin": Style(color=C["blue"]), "class": Style(color=C["blue"]),
            "operator": Style(color=C["text"]), "variable.parameter": Style(color=C["moon"]),
            "property": Style(color=C["moon"]), "punctuation.bracket": Style(color=C["line"]),
            "punctuation.delimiter": Style(color=C["line"]), "tag": Style(color=C["red"]),
            "heading": Style(color=C["mint"], bold=True), "link": Style(color=C["cyan"], underline=True),
            "json.label": Style(color=C["mint"]), "yaml.field": Style(color=C["mint"]),
            "toml.type": Style(color=C["mint"]), "regex.operator": Style(color=C["red"]),
            "inline_code": Style(color=C["green"]),
        },
    )


def tema_ansi():
    """Cores ANSI dos programas no terminal integrado (vermelho, verde… de `ls --color`, pytest, git) na paleta."""
    from rich.terminal_theme import TerminalTheme
    from textual.color import Color

    def rgb(nome: str, clarear: float = 0.0) -> tuple[int, int, int]:
        c = Color.parse(C[nome])
        if clarear:
            c = c.blend(Color.parse(C["moon"]), clarear)
        return c.r, c.g, c.b

    normais = [rgb("panel"), rgb("red"), rgb("green"), rgb("text"), rgb("blue"), rgb("orange"), rgb("cyan"),
               rgb("moon")]
    claras = [rgb("dim"), rgb("red", .25), rgb("green", .25), rgb("text", .25), rgb("blue", .25), rgb("orange", .25),
              rgb("cyan", .25), rgb("moon")]
    return TerminalTheme(rgb("bg"), rgb("text"), normais, claras)

_WORD_BEFORE = re.compile(r"[^\W\d]\w*$")
_WORDS = re.compile(r"[^\W\d]\w{2,}")


class CodeEditor(TextArea):
    """TextArea do Studio: espaço+Enter traduz a linha, Tab expande abreviações (HTML/CSS/JSX) e aceita a
    sugestão do autocompletar (palavras do arquivo, da linguagem e do pseudocódigo)."""

    class TranslateLine(Message):
        def __init__(self, editor: CodeEditor, row: int) -> None:
            super().__init__()
            self.editor = editor
            self.row = row

    def __init__(self, *args, path: str | None = None, space_enter: bool = True, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.path = path
        self.space_enter = space_enter
        self.saved_text = self.text
        self.lang_id: str | None = None
        self.autocomplete = True

    @property
    def dirty(self) -> bool:
        return self.text != self.saved_text

    # ------------------------------------------------------------------ autocompletar
    def update_suggestion(self) -> None:
        self.suggestion = ""
        if not self.autocomplete or self.read_only or self.selection.start != self.selection.end:
            return
        row, col = self.cursor_location
        line = self.document.get_line(row)
        if line[col:].strip(" )]}\"'"):  # só no fim da linha (ou antes de fechamentos)
            return
        m = _WORD_BEFORE.search(line[:col])
        if not m or len(m.group(0)) < 2:
            return
        prefix = m.group(0)
        best = self.complete(prefix, row)
        if best:
            self.suggestion = best[len(prefix):]

    def complete(self, prefix: str, row: int) -> str | None:
        """Melhor palavra que começa com `prefix`: do próprio arquivo (as mais frequentes perto do cursor),
        depois palavras-chave da linguagem, depois o vocabulário de pseudocódigo."""
        start, end = max(0, row - 300), min(self.document.line_count, row + 300)
        counts: dict[str, int] = {}
        for r in range(start, end):
            text = self.document.get_line(r)
            for w in _WORDS.findall(text):
                if r == row and text.endswith(prefix) and w == prefix:
                    continue
                counts[w] = counts.get(w, 0) + 1
        buffer_words = sorted((w for w in counts if w.startswith(prefix) and w != prefix),
                              key=lambda w: (-counts[w], len(w)))
        if buffer_words:
            return buffer_words[0]
        for pool in (KEYWORDS.get(self.lang_id or "", ()), PSEUDO_WORDS):
            hits = sorted((w for w in pool if w.startswith(prefix) and w != prefix), key=len)
            if not hits:
                low = prefix.lower()
                hits = sorted((w for w in pool if w.lower().startswith(low) and w.lower() != low), key=len)
                if hits:  # mantém a caixa digitada: "Imp" -> "Imprimir"
                    return prefix + hits[0][len(prefix):]
            if hits:
                return hits[0]
        return None

    # ------------------------------------------------------------------ Emmet
    def emmet_kind(self) -> str | None:
        suffix = Path(self.path).suffix.lower() if self.path else ""
        if suffix in (".html", ".htm", ".vue", ".svelte") or (not suffix and self.lang_id == "html"):
            return "html"
        if suffix in (".css", ".scss", ".less") or (not suffix and self.lang_id == "css"):
            return "css"
        if suffix in (".jsx", ".tsx"):
            return "jsx"
        return None

    def expand_abbreviation(self) -> bool:
        """Tab depois de "ul>li*3": troca a abreviação pelo HTML e põe o cursor no primeiro lugar a preencher."""
        kind = self.emmet_kind()
        if kind is None or self.selection.start != self.selection.end:
            return False
        row, col = self.cursor_location
        line = self.document.get_line(row)
        found = emmet.extract_abbreviation(line[:col])
        if found is None:
            return False
        start, abbr = found
        unit = "\t" if self.indent_type == "tabs" else " " * self.indent_width
        if kind == "css":
            code = emmet.expand_css(abbr)
        elif kind == "jsx":
            code = emmet.expand(abbr, unit, jsx=True) if emmet.jsx_candidate(abbr) else None
        else:
            code = emmet.expand(abbr, unit)
        if code is None:
            return False
        base = line[: len(line) - len(line.lstrip())]
        text = code.replace("\n", "\n" + base)
        self.replace(text, (row, start), (row, col))
        offset = emmet.first_stop(text)
        before = text[:offset]
        new_row = row + before.count("\n")
        new_col = (start if "\n" not in before else 0) + len(before.rsplit("\n", 1)[-1])
        self.move_cursor((new_row, new_col))
        return True

    async def _on_key(self, event: events.Key) -> None:
        if event.key == "tab" and not self.read_only:
            if self.suggestion:
                event.stop()
                event.prevent_default()
                self.insert(self.suggestion)
                self.suggestion = ""
                return
            if self.expand_abbreviation():
                event.stop()
                event.prevent_default()
                return
        if event.key == "enter" and self.space_enter and not self.read_only:
            row, col = self.cursor_location
            line = self.document.get_line(row)
            if col == len(line) and line.endswith(" ") and looks_like_intent(line):
                event.stop()
                event.prevent_default()
                self.post_message(self.TranslateLine(self, row))
                return
        await super()._on_key(event)


@dataclass
class Satellite:
    stage: str
    born: float
    phase: float


class OrbitRadar(Widget):
    """Radar do pipeline: S0/S1/S2 são órbitas; cada tradução vira um satélite na sua órbita."""

    DEFAULT_CSS = "OrbitRadar { height: 11; }"
    BRAILLE = ((0x01, 0x08), (0x02, 0x10), (0x04, 0x20), (0x40, 0x80))

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self.sats: list[Satellite] = []
        self._timer = None

    def on_mount(self) -> None:
        self._timer = self.set_interval(1 / 6, self._tick, pause=True)

    def ping(self, stage: str) -> None:
        self.sats.append(Satellite(stage, time.monotonic(), (len(self.sats) * 1.7) % (2 * math.pi)))
        self.sats = self.sats[-14:]
        if self._timer:
            self._timer.resume()
        self.refresh()

    def _tick(self) -> None:
        now = time.monotonic()
        self.sats = [s for s in self.sats if now - s.born < 30]
        if not self.sats and self._timer:
            self._timer.pause()
        self.refresh()

    def render(self) -> Text:
        w, h = max(10, self.size.width), max(4, self.size.height)
        rings = {"0": 0.32, "1": 0.62, "2": 0.92}
        cx, cy = w, h * 2  # centro em coordenadas de pontos (2x4 por célula)
        if ASCII:
            return self._render_ascii(w, h, rings)
        dots: dict[tuple[int, int], int] = {}
        colors: dict[tuple[int, int], str] = {}
        rx_max, ry_max = w - 1, h * 2 - 1
        for key, frac in rings.items():
            rx, ry = rx_max * frac, ry_max * frac
            steps = int(2 * math.pi * max(rx, ry))
            for k in range(steps):
                a = 2 * math.pi * k / steps
                if k % 3:  # órbitas pontilhadas
                    continue
                self._dot(dots, colors, cx + rx * math.cos(a), cy + ry * math.sin(a), C["line"])
        now = time.monotonic()
        for s in self.sats:
            ring = rings["0" if s.stage == "0" else "1" if s.stage == "1" else "2"]
            speed = {"0": 2.4, "1": 1.4}.get(s.stage, 0.7)
            a = s.phase + (now - s.born) * speed
            x, y = cx + rx_max * ring * math.cos(a), cy + ry_max * ring * math.sin(a)
            color = STAGE_COLORS.get(s.stage, C["orange"])
            for dx, dy in ((0, 0), (1, 0), (0, 1), (1, 1)):
                self._dot(dots, colors, x + dx, y + dy, color)
        self._dot(dots, colors, cx, cy, C["mint"])
        text = Text()
        for row in range(h):
            for col in range(w):
                bits = dots.get((col, row), 0)
                ch = chr(0x2800 + bits) if bits else " "
                text.append(ch, Style(color=colors.get((col, row), C["line"])))
            if row < h - 1:
                text.append("\n")
        return text

    def _dot(self, dots, colors, x: float, y: float, color: str) -> None:
        xi, yi = int(round(x)), int(round(y))
        if xi < 0 or yi < 0:
            return
        cell = (xi // 2, yi // 4)
        if cell[0] >= self.size.width or cell[1] >= self.size.height:
            return
        dots[cell] = dots.get(cell, 0) | self.BRAILLE[yi % 4][xi % 2]
        if color != C["line"] or cell not in colors:
            colors[cell] = color

    def _render_ascii(self, w: int, h: int, rings: dict[str, float]) -> Text:
        grid = [[" "] * w for _ in range(h)]
        cx, cy = w / 2, h / 2
        for frac in rings.values():
            for k in range(0, 360, 12):
                a = math.radians(k)
                x, y = int(cx + (w / 2 - 1) * frac * math.cos(a)), int(cy + (h / 2 - 0.5) * frac * math.sin(a))
                if 0 <= x < w and 0 <= y < h:
                    grid[y][x] = "."
        now = time.monotonic()
        for s in self.sats:
            frac = rings["0" if s.stage == "0" else "1" if s.stage == "1" else "2"]
            a = s.phase + (now - s.born)
            x, y = int(cx + (w / 2 - 1) * frac * math.cos(a)), int(cy + (h / 2 - 0.5) * frac * math.sin(a))
            if 0 <= x < w and 0 <= y < h:
                grid[y][x] = "o"
        grid[int(cy)][int(cx)] = "*"
        return Text("\n".join("".join(r) for r in grid), Style(color=C["text"]))


TITLE = ("╔═╗╔═╗╔╦╗╔═╗╦═╗\n║  ║ ║ ║║╠═╣╠╦╝\n╚═╝╚═╝═╩╝╩ ╩╩╚═") if not ASCII else \
    ("  ___ ___  ___   _   ___ \n / __/ _ \\|   \\ /_\\ | _ \\\n| (_| (_) | |) / _ \\|   /\n \\___\\___/|___/_/ \\_\\_|_\\")


def gauge(value: float, maximum: float, width: int = 22) -> Text:
    frac = 0.0 if maximum <= 0 else max(0.0, min(1.0, value / maximum))
    color = C["red"] if frac >= 0.92 else C["orange"] if frac >= 0.8 else C["mint"]
    fill = int(round(frac * width))
    knob = min(fill, width - 1)
    full, empty, kn = ("#", "-", "o") if ASCII else ("━", "─", "●")
    t = Text()
    t.append(full * knob, Style(color=color))
    t.append(kn, Style(color=C["mint"], bold=True))
    t.append(empty * (width - knob - 1), Style(color=C["line"]))
    return t
