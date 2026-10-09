"""Widgets do Codar Studio: editor com gatilho espaço+Enter, radar orbital do pipeline, cartões HUD."""

from __future__ import annotations

import math
import os
import re
import time
from dataclasses import dataclass
from pathlib import Path

from rich.segment import Segment
from rich.style import Style
from rich.text import Text
from textual import events
from textual.binding import Binding
from textual.message import Message
from textual.strip import Strip

from codar import langs
from codar.engine import emmet
from codar.textutil import looks_like_intent
from codar.vocab import KEYWORDS, PSEUDO_WORDS
from textual.widget import Widget
from textual.widgets import Static, TextArea
from textual.widgets.text_area import Selection, TextAreaTheme

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

# Pares que fecham sozinhos, como no VS Code: "(" vira "()" com o cursor no meio
PARES = {"(": ")", "[": "]", "{": "}", '"': '"', "'": "'", "`": "`"}
_FECHA_ANTES = set(" \t)]};:,.=>")  # só fecha se depois do cursor vier um destes (ou o fim da linha)
_COM_CRASE = {"javascript", "typescript", "markdown", "bash", "go", "sql"}
_PREFIXO_STR = set("fFrRbBuU")  # f"…", r"…", b"…" em Python
_TAGS_VAZIAS = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "param", "source", "track",
                "wbr", "!doctype"}
_ABRE_TAG = re.compile(r"(?:^|[^\w.$])<([A-Za-z!][\w:.-]*)(?:\s[^<>]*)?$")  # "<div class='x'" (não pega Array<T)
_SAI_BLOCO_PY = re.compile(r"^\s*(return|pass|break|continue|raise)\b")
_ALINHA_PY = re.compile(r"^\s*(else|elif|except|finally)\b[^:]*:\s*$")
_ABRIDORES = {"else": ("if", "elif", "for", "while", "try", "except"), "elif": ("if", "elif"),
              "except": ("try", "except"), "finally": ("try", "except", "else")}
COMENTARIO_BLOCO = {"html": ("<!--", "-->"), "css": ("/*", "*/")}


def _sem_comentario(texto: str, marcador: str) -> str:
    """O texto sem o comentário do fim da linha (ignora o marcador dentro de aspas)."""
    aspas = None
    for i, ch in enumerate(texto):
        if aspas:
            if ch == aspas and texto[i - 1] != "\\":
                aspas = None
        elif ch in "\"'":
            aspas = ch
        elif marcador and texto.startswith(marcador, i):
            return texto[:i]
    return texto


def _recuo(texto: str) -> str:
    return texto[: len(texto) - len(texto.lstrip())]


def _sobrepor(strip: Strip, marcas: dict[int, tuple[str, Style]], destaque: tuple[int, Style] | None) -> Strip:
    """Troca células de espaço por marcas (pontinhos de indentação) e pinta o fundo a partir de uma coluna."""
    largura = strip.cell_length
    cortes = {c for x in marcas for c in (x, x + 1)}
    if destaque:
        cortes.add(destaque[0])
    cortes = sorted(c for c in cortes if 0 < c < largura)
    pecas = strip.divide([*cortes, largura])
    saida, pos = [], 0
    for peca in pecas:
        tamanho = peca.cell_length
        if pos in marcas and tamanho == 1 and peca.text == " ":
            ch, estilo = marcas[pos]
            seg = next(iter(peca))
            peca = Strip([Segment(ch, (seg.style or Style()) + estilo)], 1)
        if destaque and pos >= destaque[0]:
            peca = Strip([Segment(t, (st or Style()) + destaque[1], c) for t, st, c in peca], tamanho)
        saida.append(peca)
        pos += tamanho
    return Strip.join(saida)


class CodeEditor(TextArea):
    """TextArea do Studio: espaço+Enter traduz a linha, Tab expande abreviações (HTML/CSS/JSX) e aceita a
    sugestão do autocompletar (palavras do arquivo, da linguagem e do pseudocódigo)."""

    class TranslateLine(Message):
        def __init__(self, editor: CodeEditor, row: int) -> None:
            super().__init__()
            self.editor = editor
            self.row = row

    BINDINGS = [
        Binding("ctrl+a", "select_all", "Selecionar tudo", show=False),
        Binding("ctrl+underscore,ctrl+slash", "comentar", "Comentar", show=False),
        Binding("alt+up", "mover_linhas(-1)", "Subir linha", show=False),
        Binding("alt+down", "mover_linhas(1)", "Descer linha", show=False),
        Binding("alt+shift+down", "duplicar_linhas(1)", "Duplicar linha", show=False),
        Binding("alt+shift+up", "duplicar_linhas(0)", "Duplicar linha", show=False),
    ]

    def __init__(self, *args, path: str | None = None, space_enter: bool = True, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.path = path
        self.space_enter = space_enter
        self.saved_text = self.text
        self.lang_id: str | None = None
        self.autocomplete = True
        self.guias = True  # pontinhos na indentação
        self._auto: set[tuple[int, int]] = set()  # fechamentos postos pelo editor: (linha, distância até o fim)
        self._destaque: tuple[int, int] | None = None  # linhas recém-inseridas, com fundo realçado por um instante

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

    # ------------------------------------------------------------------ teclado (comportamento do VS Code)
    async def _on_key(self, event: events.Key) -> None:
        tratou = False
        if not self.read_only:
            tecla = event.key
            if tecla == "tab":
                tratou = self._tab()
            elif tecla == "shift+tab":
                self.indentar_linhas(-1)
                tratou = True
            elif tecla == "enter":
                tratou = self._enter()
            elif tecla == "backspace":
                tratou = self._apagar_par()
            elif tecla == "escape":  # limpa seleção e sugestão; não tira o foco do editor
                self.suggestion = ""
                self.move_cursor(self.selection.end)
                tratou = True
            elif event.is_printable and event.character:
                tratou = self._digitar(event.character)
        if tratou:
            event.stop()
            event.prevent_default()
            self._restart_blink()
            return
        await super()._on_key(event)

    def _tab(self) -> bool:
        if self.suggestion:
            self.insert(self.suggestion)
            self.suggestion = ""
            return True
        if self.expand_abbreviation():
            return True
        sel = self.selection
        if sel.start[0] != sel.end[0]:
            self.indentar_linhas(1)
            return True
        return False

    def _enter(self) -> bool:
        row, col = self.cursor_location
        linha = self.document.get_line(row)
        vazio = self.selection.start == self.selection.end
        if self.space_enter and vazio and col == len(linha) and linha.endswith(" ") and looks_like_intent(linha):
            self.post_message(self.TranslateLine(self, row))
            return True
        self.nova_linha()
        return True

    @property
    def unidade(self) -> str:
        return "\t" if self.indent_type == "tabs" else " " * self.indent_width

    def _comentario(self) -> str:
        lang = langs.LANGS.get(self.lang_id or "")
        return lang.comment if lang and lang.id not in COMENTARIO_BLOCO else ""

    def nova_linha(self) -> None:
        """Enter: mantém a indentação, entra um nível depois de ':' (Python) e de ( [ {, abre o bloco entre {} e
        <tag></tag>, sai um nível depois de return/pass/break, e não deixa espaços sobrando em linha vazia."""
        inicio, fim = sorted((self.selection.start, self.selection.end))
        row, col = inicio
        linha = self.document.get_line(row)
        antes, depois = linha[:col], self.document.get_line(fim[0])[fim[1]:]
        base = _recuo(antes) if not antes.strip() else _recuo(linha)
        codigo = _sem_comentario(antes, self._comentario()).rstrip()
        extra, fechar = "", ""
        unidade = self.unidade
        if self.lang_id == "python" and codigo.endswith(":"):
            extra = unidade
        elif codigo[-1:] in ("(", "[", "{"):
            extra = unidade
            if depois.lstrip()[:1] == PARES[codigo[-1]]:
                fechar = "\n" + base
        elif self.emmet_kind() in ("html", "jsx") and codigo.endswith(">") and depois.lstrip().startswith("</"):
            extra, fechar = unidade, "\n" + base
        elif self.lang_id == "python" and _SAI_BLOCO_PY.match(antes) and not depois.strip():
            base = base[: -len(unidade)] if base.endswith(unidade) else base[: max(0, len(base) - len(unidade))]
        if not antes.strip() and not depois.strip():
            inicio = (row, 0)  # linha só com espaços: ela fica vazia e a indentação passa para a de baixo
        self._replace_via_keyboard("\n" + base + extra + fechar, inicio, fim)
        self.move_cursor((row + 1, len(base + extra)))

    def _pode_fechar(self, ch: str, antes: str, depois: str) -> bool:
        if self.lang_id is None:  # texto puro: nada fecha sozinho
            return False
        if ch == "`" and self.lang_id not in _COM_CRASE:
            return False
        if ch in "\"'" and self.lang_id == "markdown" or ch == "'" and self.lang_id == "rust":
            return False
        if depois and depois not in _FECHA_ANTES:
            return False
        if ch in "\"'`":
            anterior = antes[-1:]
            prefixo = (self.lang_id == "python" and anterior in _PREFIXO_STR
                       and not (antes[-2:-1].isalnum() or antes[-2:-1] == "_"))
            if anterior and (anterior.isalnum() or anterior == "_") and not prefixo:
                return False
            if anterior == ch or antes.count(ch) % 2:  # terceira aspa de \"\"\" ou fechando uma string aberta
                return False
        return True

    def _digitar(self, ch: str) -> bool:
        sel = self.selection
        row, col = self.cursor_location
        linha = self.document.get_line(row)
        if sel.start != sel.end:
            if ch in PARES and self.lang_id is not None:  # envolve a seleção: (texto), "texto"
                a, b = sorted((sel.start, sel.end))
                miolo = self.get_text_range(a, b)
                self.replace(ch + miolo + PARES[ch], a, b, maintain_selection_offset=False)
                self.selection = Selection((a[0], a[1] + 1), (b[0], b[1] + (1 if a[0] == b[0] else 0)))
                return True
            return False
        antes, depois = linha[:col], linha[col:col + 1]
        if ch in PARES.values() and depois == ch and (row, len(linha) - col) in self._auto:
            self._auto.discard((row, len(linha) - col))  # digitou o fechamento que o editor pôs: só passa por cima
            self.move_cursor((row, col + 1))
            return True
        if ch in PARES and self._pode_fechar(ch, antes, depois):
            self._replace_via_keyboard(ch + PARES[ch], (row, col), (row, col))
            self.move_cursor((row, col + 1))
            self._auto.add((row, len(linha) + 1 - col))
            return True
        if ch == ">" and self.emmet_kind() in ("html", "jsx") and not antes.endswith("/"):
            m = _ABRE_TAG.search(antes)
            if m and m.group(1).lower() not in _TAGS_VAZIAS and not linha[col:].lstrip().startswith(f"</{m.group(1)}"):
                self._replace_via_keyboard(f"></{m.group(1)}>", (row, col), (row, col))
                self.move_cursor((row, col + 1))
                return True
        if ch == ":" and self.lang_id == "python":
            self._replace_via_keyboard(":", (row, col), (row, col))
            nova = self.document.get_line(row)
            m = _ALINHA_PY.match(nova)
            recuo = self.recuo_alinhado(row, m.group(1)) if m else None
            if recuo is not None and recuo != _recuo(nova):
                self.replace(recuo, (row, 0), (row, len(_recuo(nova))))
                self.move_cursor((row, len(self.document.get_line(row))))
            return True
        return False

    def recuo_alinhado(self, row: int, palavra: str) -> str | None:
        """Indentação certa para else/elif/except/finally na linha `row`: a do if/try correspondente. None quando a
        pessoa já recuou por conta própria (fica como está) ou não há bloco compatível acima."""
        linha = self.document.get_line(row)
        atual = len(_recuo(linha))
        anteriores = [self.document.get_line(r) for r in range(row - 1, -1, -1)]
        anteriores = [t for t in anteriores if t.strip()]
        if not anteriores or atual < len(_recuo(anteriores[0])):
            return None
        for texto in anteriores:
            if len(_recuo(texto)) < atual:
                chave = re.match(r"\s*(\w+)", texto)
                return _recuo(texto) if chave and chave.group(1) in _ABRIDORES.get(palavra, ()) else None
        return None

    def _apagar_par(self) -> bool:
        if self.selection.start != self.selection.end:
            return False
        row, col = self.cursor_location
        linha = self.document.get_line(row)
        if 0 < col < len(linha) and linha[col - 1] in PARES and linha[col] == PARES[linha[col - 1]]:
            self._delete_via_keyboard((row, col - 1), (row, col + 1))  # (|) -> |
            return True
        antes = linha[:col]
        if col and not antes.strip() and self.indent_type == "spaces" and " " * col == antes:
            n = (col - 1) % self.indent_width + 1  # na indentação, apaga um nível inteiro
            self._delete_via_keyboard((row, col - n), (row, col))
            return True
        return False

    def watch_selection(self, anterior: Selection, atual: Selection) -> None:
        if anterior.end[0] != atual.end[0]:
            self._auto.clear()

    # ------------------------------------------------------------------ linhas inteiras
    def linhas_selecionadas(self) -> tuple[int, int]:
        """(primeira, última) linha da seleção; uma seleção que termina no começo de uma linha não a inclui."""
        (r0, _c0), (r1, c1) = sorted((self.selection.start, self.selection.end))
        if r1 > r0 and c1 == 0:
            r1 -= 1
        return r0, r1

    def _trocar_linhas(self, r0: int, r1: int, novas: list[str]) -> None:
        self.replace("\n".join(novas), (r0, 0), (r1, len(self.document.get_line(r1))))

    def indentar_linhas(self, passo: int) -> None:
        """Tab com várias linhas selecionadas entra um nível; Shift+Tab sai um nível (com ou sem seleção)."""
        sel = self.selection
        r0, r1 = self.linhas_selecionadas()
        unidade = self.unidade
        antigas = [self.document.get_line(r) for r in range(r0, r1 + 1)]
        novas = []
        for t in antigas:
            if passo > 0:
                novas.append(unidade + t if t.strip() else t)
            elif t.startswith(unidade):
                novas.append(t[len(unidade):])
            else:
                novas.append(t[min(len(_recuo(t)), len(unidade)):] if not t.startswith("\t") else t[1:])
        self._trocar_linhas(r0, r1, novas)
        delta = {r: len(novas[r - r0]) - len(antigas[r - r0]) for r in range(r0, r1 + 1)}

        def ajustar(loc: tuple[int, int]) -> tuple[int, int]:
            r, c = loc
            return (r, max(0, c + delta.get(r, 0))) if r in delta else loc

        self.selection = Selection(ajustar(sel.start), ajustar(sel.end))

    def action_comentar(self) -> None:
        """Ctrl+/: comenta ou descomenta as linhas (o comentário da linguagem; <!-- --> no HTML, /* */ no CSS)."""
        lang = langs.LANGS.get(self.lang_id or "")
        if lang is None or self.read_only:
            return
        abre, fecha = COMENTARIO_BLOCO.get(lang.id, (lang.comment, ""))
        sel = self.selection
        r0, r1 = self.linhas_selecionadas()
        antigas = [self.document.get_line(r) for r in range(r0, r1 + 1)]
        cheias = [t for t in antigas if t.strip()]
        if not cheias:
            return
        comentadas = all(t.lstrip().startswith(abre) for t in cheias)
        margem = min(len(_recuo(t)) for t in cheias)
        novas = []
        for t in antigas:
            if not t.strip():
                novas.append(t)
            elif comentadas:
                i = t.index(abre)
                resto = t[i + len(abre):]
                resto = resto[1:] if resto.startswith(" ") else resto
                if fecha and resto.rstrip().endswith(fecha):
                    resto = resto.rstrip()[: -len(fecha)].rstrip()
                novas.append(t[:i] + resto)
            else:
                novas.append(t[:margem] + abre + " " + t[margem:] + (" " + fecha if fecha else ""))
        self._trocar_linhas(r0, r1, novas)
        delta = {r: len(novas[r - r0]) - len(antigas[r - r0]) for r in range(r0, r1 + 1)}
        self.selection = Selection(*[(r, max(0, c + delta.get(r, 0))) for r, c in (sel.start, sel.end)])

    def action_mover_linhas(self, passo: int) -> None:
        """Alt+↑ / Alt+↓: move a linha (ou as linhas selecionadas) para cima ou para baixo."""
        if self.read_only:
            return
        sel = self.selection
        r0, r1 = self.linhas_selecionadas()
        if (passo < 0 and r0 == 0) or (passo > 0 and r1 >= self.document.line_count - 1):
            return
        bloco = [self.document.get_line(r) for r in range(r0, r1 + 1)]
        if passo < 0:
            self._trocar_linhas(r0 - 1, r1, bloco + [self.document.get_line(r0 - 1)])
        else:
            self._trocar_linhas(r0, r1 + 1, [self.document.get_line(r1 + 1)] + bloco)
        self.selection = Selection((sel.start[0] + passo, sel.start[1]), (sel.end[0] + passo, sel.end[1]))

    def action_duplicar_linhas(self, abaixo: int = 1) -> None:
        """Alt+Shift+↓: duplica a linha (ou as linhas selecionadas); o cursor vai para a cópia."""
        if self.read_only:
            return
        sel = self.selection
        r0, r1 = self.linhas_selecionadas()
        bloco = "\n".join(self.document.get_line(r) for r in range(r0, r1 + 1))
        self.insert("\n" + bloco, (r1, len(self.document.get_line(r1))), maintain_selection_offset=False)
        n = (r1 - r0 + 1) if abaixo else 0
        self.selection = Selection((sel.start[0] + n, sel.start[1]), (sel.end[0] + n, sel.end[1]))

    # ------------------------------------------------------------------ desenho: indentação e destaque
    def destacar(self, r0: int, r1: int, segundos: float = 1.2) -> None:
        """Realça por um instante as linhas que a tradução acabou de inserir (sem selecioná-las)."""
        self._destaque = (r0, r1)
        self.refresh()
        self.set_timer(segundos, self._fim_destaque)

    def _fim_destaque(self) -> None:
        self._destaque = None
        self.refresh()

    def render_line(self, y: int) -> Strip:
        strip = super().render_line(y)
        if not self.text:
            return strip
        scroll_x, scroll_y = self.scroll_offset
        try:
            linha, secao = self.wrapped_document._offset_to_line_info[scroll_y + y]
        except IndexError:
            return strip
        marcas: dict[int, tuple[str, Style]] = {}
        if self.guias and secao == 0:
            texto = self.document.get_line(linha)
            cur_r, cur_c = self.cursor_location
            nivel, fraco = Style(color=C["guide"]), Style(color=C["guide_faint"])
            col = 0
            for i, ch in enumerate(texto):
                if ch not in " \t":
                    break
                x = self.gutter_width + col - scroll_x
                if x >= self.gutter_width and not (linha == cur_r and i == cur_c):
                    if ch == "\t":
                        marcas[x] = ("→", fraco)
                    else:
                        marcas[x] = ("·", nivel if col % self.indent_width == 0 else fraco)
                col += self.indent_width - col % self.indent_width if ch == "\t" else 1
        destaque = None
        if self._destaque and self._destaque[0] <= linha <= self._destaque[1]:
            destaque = (self.gutter_width, Style(bgcolor=C["flash"]))
        if not marcas and not destaque:
            return strip
        return _sobrepor(strip, marcas, destaque)


class Botao(Static):
    """Texto clicável que executa uma ação do app (pílulas S0/S1, barra do explorer). Diferente de um link [@click],
    mantém as cores do próprio texto, que acompanham o tema."""

    def __init__(self, texto: str = "", acao: str = "", **kwargs) -> None:
        super().__init__(texto, **kwargs)
        self.acao = acao

    async def on_click(self, event: events.Click) -> None:
        event.stop()
        await self.app.run_action(self.acao)


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
