"""Codar Studio — IDE imersiva no terminal (funciona via SSH e em servidores sem interface gráfica).

Layout inspirado no console SENTRY: explorer + radar orbital do pipeline + feed de eventos à
esquerda, editores em abas no centro com painel de problemas/terminal/saída/consultor,
telemetria à direita, barra de intenção e medidor de RAM embaixo.
"""

from __future__ import annotations

import codecs
import os
import random
import select
import shlex
import shutil
import signal
import subprocess
import sys
import time
from pathlib import Path

from rich.text import Text
from textual import on, work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.command import DiscoveryHit, Hit, Hits, Provider
from textual.containers import Horizontal, Vertical
from textual.suggester import Suggester
from textual.theme import Theme
from textual.widgets import (DataTable, DirectoryTree, Footer, Input, ListItem, ListView, RichLog, Static,
                             TabbedContent, TabPane, TextArea)
from textual.widgets.text_area import Selection

from codar import __version__, langs
from codar.studio.backend import StudioBackend
from codar.engine import emmet
from codar.studio.screens import AdviceScreen, HelpScreen, PromptScreen
from codar.studio.widgets import C, SENTRY_THEME, STAGE_COLORS, TITLE, CodeEditor, OrbitRadar, gauge
from codar.textutil import looks_like_intent
from codar.vocab import EXAMPLES

STAGE_NAMES = {"0": "S0 COMPILER", "1": "S1 PATTERN", "2:tools": "S2 TOOLS", "2:adapt": "S2 ADAPT", "2:gen": "S2 SLM",
               "2:pseudo": "S2 PSEUDO"}
TS_LANG = {"python": "python", "javascript": "javascript", "typescript": "javascript", "go": "go", "rust": "rust",
           "java": "java", "bash": "bash", "sql": "sql", "html": "html", "css": "css", "yaml": "yaml", "markdown": "markdown"}
EXT_TS = {".json": "json", ".toml": "toml", ".md": "markdown", ".xml": "xml", ".yml": "yaml", ".yaml": "yaml"}
SKIP = {".git", "node_modules", "__pycache__", ".venv", "venv", ".mypy_cache", ".pytest_cache", "target", "dist", ".codar"}


class Explorer(DirectoryTree):
    def filter_paths(self, paths):
        return [p for p in paths if p.name not in SKIP]


class CodarCommands(Provider):
    async def discover(self) -> Hits:
        for name, help_text, cb in self.app.palette():  # type: ignore[attr-defined]
            yield DiscoveryHit(name, cb, help=help_text)

    async def search(self, query: str) -> Hits:
        matcher = self.matcher(query)
        for name, help_text, cb in self.app.palette():  # type: ignore[attr-defined]
            score = matcher.match(name)
            if score > 0:
                yield Hit(score, matcher.highlight(name), cb, help=help_text)


TERM_IDLE = "$ comando no diretório do projeto (Enter executa)"
TERM_RUNNING = "entrada do programa (Enter envia · Ctrl+C interrompe)"


class TerminalInput(Input):
    """Campo do terminal: com um programa rodando, Ctrl+C interrompe o programa em vez de copiar."""

    BINDINGS = [Binding("ctrl+c", "interromper", "Interromper", show=False, priority=True)]

    def action_interromper(self) -> None:
        studio = self.app
        if isinstance(studio, Studio) and studio.process_running():
            studio.interrupt_process()
        else:
            self.action_copy()


TIPS = [
    "termine a frase com espaço e aperte Enter: a linha vira código",
    "Ctrl+Enter ou Ctrl+G traduz a linha do cursor; com seleção, traduz o bloco",
    "num arquivo .html, escreva ul>li.item*3 e aperte Tab",
    "num arquivo .css, escreva df+jcc+aic e aperte Tab",
    "F1 mostra todos os atalhos",
    "F8 abre o consultor: sugestões para o projeto, aplicadas com um clique",
    "a barra de intenção completa o que você já usou: comece a digitar e aperte →",
    "frases que descrevem valores funcionam: 'imprimir o tamanho de pedidos'",
    "pedidos de funcionalidade usam padrões testados: 'criar uma calculadora'",
]


class IntentSuggester(Suggester):
    """Completa a barra de intenção com o que você já pediu nesta sessão e com frases de exemplo."""

    def __init__(self, app: Studio) -> None:
        super().__init__(use_cache=False, case_sensitive=False)
        self.studio = app

    async def get_suggestion(self, value: str) -> str | None:
        if len(value) < 2:
            return None
        for candidate in [*self.studio.intents, *(e for e, _ in EXAMPLES)]:
            if candidate.casefold().startswith(value) and len(candidate) > len(value):
                return candidate
        return None


class Studio(App):
    TITLE = "codar studio"
    CSS_PATH = str(Path(__file__).with_name("studio.tcss"))
    COMMANDS = App.COMMANDS | {CodarCommands}
    BINDINGS = [
        Binding("ctrl+s", "save", "Salvar"),
        # Ctrl+Enter chega como ctrl+enter (kitty, WezTerm, foot…) ou ctrl+j (terminais clássicos); Ctrl+G em qualquer um
        Binding("ctrl+g,ctrl+enter,ctrl+j", "translate_line", "Traduzir linha"),
        Binding("ctrl+l", "focus_intent", "Intenção"),
        Binding("f5", "run_file", "Executar"),
        Binding("f6", "audit_file", "Auditar"),
        Binding("f8", "advise", "Consultor"),
        Binding("ctrl+o", "open_vscode", "VS Code"),
        Binding("ctrl+n", "new_file", "Novo"),
        Binding("ctrl+w", "close_tab", "Fechar aba"),
        Binding("ctrl+b", "toggle_left", "Explorer", show=False),
        Binding("f9", "toggle_panel", "Painel", show=False),
        Binding("ctrl+q", "quit", "Sair"),
        Binding("f1", "help", "Ajuda"),
    ]

    def __init__(self, root: str | Path = ".", lang: str | None = None, local: bool = False) -> None:
        super().__init__()
        self.root = Path(root).expanduser().resolve()
        self.forced_lang = langs.try_resolve(lang).id if lang and langs.try_resolve(lang) else None
        self.backend = StudioBackend(local=local)
        self.stages = {0, 1, 2}
        self.audit_on = True
        self.hints = False
        self.last: dict | None = None
        self.tab_seq = 0
        self.term_proc: subprocess.Popen | None = None
        self.term_fd: int | None = None  # lado mestre do pseudoterminal do processo em execução
        self.term_waiting = ""  # pergunta do programa esperando entrada (texto sem quebra de linha)
        self.mem: dict = {}
        self.intents: list[str] = []
        self.online = False
        self.streaming = False

    # ------------------------------------------------------------------ layout
    def compose(self) -> ComposeResult:
        with Horizontal(id="workspace"):
            with Vertical(id="left"):
                yield Explorer(self.root, id="explorer")
                yield OrbitRadar(id="radar")
                yield RichLog(id="feed", markup=True, wrap=True, max_lines=500, min_width=16)
            with Vertical(id="center"):
                with Horizontal(id="pills-bar"):
                    yield Static(id="pills")
                    yield Static(id="lang-pill")
                yield Static(self.welcome_text(), id="welcome")
                yield TabbedContent(id="editors")
                with TabbedContent(id="panel", initial="tab-problems"):
                    with TabPane("PROBLEMAS", id="tab-problems"):
                        yield DataTable(id="problems", cursor_type="row")
                    with TabPane("TERMINAL", id="tab-terminal"):
                        yield RichLog(id="term-log", markup=False, wrap=False, max_lines=3000)
                        yield TerminalInput(placeholder=TERM_IDLE, id="term-input")
                    with TabPane("SAÍDA", id="tab-output"):
                        yield RichLog(id="output", markup=True, wrap=True, max_lines=2000, min_width=20)
                    with TabPane("CONSULTOR", id="tab-advisor"):
                        yield ListView(id="advice-list")
            with Vertical(id="right"):
                yield Static(TITLE, id="hud-title")
                yield Static(id="hud-meta")
                yield Static(id="last-card")
                yield Static(id="telemetry")
                yield ListView(id="history")
        with Horizontal(id="intent-bar"):
            yield Static("❯ INTENÇÃO", id="intent-label")
            yield Input(placeholder="descreva o código (Enter gera e insere · → completa · F1 ajuda)", id="intent",
                        suggester=IntentSuggester(self))
        yield Static(id="status")
        yield Footer()

    def on_mount(self) -> None:
        self.register_theme(Theme(name="sentry", primary=C["orange"], secondary=C["red"], accent=C["mint"],
                                  warning=C["orange"], error="#ff3b2f", success=C["green"], foreground=C["text"],
                                  background=C["bg"], surface=C["bg"], panel=C["grid"], dark=True))
        self.theme = "sentry"
        for wid, title in (("#explorer", "EXPLORER"), ("#radar", "PIPELINE ORBIT"), ("#feed", "SOURCE / EVENT FEED"),
                           ("#editors", "EDITOR"), ("#welcome", "BEM-VINDO"), ("#panel", "PAINEL"), ("#last-card", "LAST TRANSLATION"),
                           ("#telemetry", "TELEMETRIA"), ("#history", "HISTÓRICO"), ("#intent-bar", "")):
            self.query_one(wid).border_title = title
        table = self.query_one("#problems", DataTable)
        table.add_columns("SEV", "ID", "LINHA", "MENSAGEM")
        self.query_one("#hud-meta", Static).update(
            f"[b {C['mint']}]INTENT → CODE ENCOUNTERS[/]\n[{C['dim']}]SRC ·[/] [{C['green']}]S0 COMPILER · S1 BANK · S2 SLM[/]\n"
            f"[{C['dim']}]OFFLINE · TETO[/] [{C['red']}]{_budget_gb()} GB[/] [{C['dim']}]· v{__version__}[/]")
        self.render_pills()
        self.render_last()
        self.feed("BOOT · CODAR STUDIO v" + __version__, "red")
        self.feed(f"WORKSPACE · {self.root}", "green")
        self.feed("UPLINK · conectando ao daemon…", "dim")
        self.feed("DICA · " + random.choice(TIPS), "cyan")
        self.set_interval(2.0, self.refresh_telemetry)
        self.set_interval(1.0, self.render_status)
        self.refresh_telemetry()
        self.render_status()
        self.sync_welcome()
        self.query_one("#intent", Input).focus()

    def on_resize(self, event) -> None:
        from textual.css.query import NoMatches

        try:  # o primeiro resize chega antes de o layout estar montado
            w = event.size.width
            self.query_one("#right").display = w >= 118
            self.query_one("#left").display = w >= 84
        except NoMatches:
            pass

    # ------------------------------------------------------------------ HUD
    def feed(self, text: str, color: str = "green") -> None:
        mark = "[#FF4747]▸[/]"
        self.query_one("#feed", RichLog).write(f"{mark} [{C.get(color, color)}]{_esc(text)}[/]")

    def render_pills(self) -> None:
        def pill(label: str, on_: bool, action: str) -> str:
            color = C["mint"] if on_ else C["red"]
            return f"[@click=app.{action}][b {color}] {label} [/][/]"

        t = "  ".join([pill("◎ S0", 0 in self.stages, "toggle_stage(0)"), pill("• S1", 1 in self.stages, "toggle_stage(1)"),
                       pill("✳ S2", 2 in self.stages, "toggle_stage(2)"), pill("☉ AUDIT", self.audit_on, "toggle_audit"),
                       pill("✎ HINTS", self.hints, "toggle_hints")])
        self.query_one("#pills", Static).update(t)
        self.query_one("#lang-pill", Static).update(f"[b {C['red']}]LANG[/] [b {C['mint']}]{self.current_lang().upper()}[/]")

    def render_last(self) -> None:
        r = self.last
        if not r:
            self.query_one("#last-card", Static).update(f"[{C['dim']}]nenhuma tradução ainda\n\n[/][{C['red']}]▶ dica:[/] "
                                                        f"[{C['green']}]escreva uma intenção abaixo e tecle Enter[/]")
            return
        color = STAGE_COLORS.get(r["stage"], C["orange"])
        rows = [f"[b {color}]▶ {STAGE_NAMES.get(r['stage'], r['stage'])}[/]",
                f"[{C['dim']}]FONTE  [/][{C['green']}]{_esc(r['source'][:28])}[/]",
                f"[{C['dim']}]LATÊNCIA [/][{C['mint']}]{r['timings'].get('total_ms', 0):.2f} MS[/]"
                + (f" [{C['cyan']}]CACHE[/]" if r.get("cached") else ""),
                f"[{C['dim']}]CONFIANÇA [/][{C['text']}]{r.get('confidence', 1):.2f}[/]",
                f"[{C['dim']}]AUDITORIA [/]" + (f"[{C['mint']}]✓ limpo[/]" if not r["findings"] else
                                                f"[{C['orange']}]{len(r['findings'])} achado(s)[/]")]
        if r.get("slots"):
            rows.append(f"[{C['dim']}]SLOTS [/][{C['moon']}]" + _esc(", ".join(f"{k}={v}" for k, v in list(r["slots"].items())[:3])) + "[/]")
        self.query_one("#last-card", Static).update("\n".join(rows))

    def render_status(self) -> None:
        m = self.mem
        total, budget = m.get("total_mb", 0.0), m.get("budget_mb", 3072)
        line = Text()
        line.append(" ▶ RUN F5 ", style=f"bold {C['red']}")
        line.append(" ⚑ ADVISE F8 ", style=f"bold {C['red']}")
        line.append(f"  {self.context_hint()} ", style=f"bold {C['cyan']}")
        line.append("  MEMORY BUDGET ", style=C["dim"])
        line.append_text(gauge(total, budget, 26))
        line.append(f" {total:.0f}/{budget} MB ", style=C["mint"])
        state = ("● ONLINE", C["mint"]) if self.online else ("○ OFFLINE", C["red"])
        line.append(f"  DAEMON {state[0]} ", style=f"bold {state[1]}")
        line.append("  " + time.strftime("%Y-%b-%d %H:%MZ", time.gmtime()).upper(), style=f"bold {C['mint']}")
        self.query_one("#status", Static).update(line)

    def context_hint(self) -> str:
        """O que dá para fazer agora, de acordo com o foco e a linha do cursor."""
        if self.term_waiting:
            return "O PROGRAMA ESPERA ENTRADA · DIGITE NO TERMINAL"
        focused = self.focused
        if isinstance(focused, Input) and focused.id == "intent":
            return "ENTER GERA · → COMPLETA" if focused.value else "DESCREVA O CÓDIGO · F1 AJUDA"
        if isinstance(focused, CodeEditor):
            row, col = focused.cursor_location
            line = focused.document.get_line(row)
            if focused.suggestion:
                return "TAB COMPLETA"
            if focused.emmet_kind() and emmet.extract_abbreviation(line[:col]):
                return "TAB EXPANDE"
            if looks_like_intent(line):
                return "CTRL+ENTER TRADUZ · ESPAÇO+ENTER"
            return "CTRL+L INTENÇÃO · F1 AJUDA"
        return "F1 AJUDA"

    @on(TextArea.SelectionChanged)
    def _cursor_moved(self) -> None:
        self.render_status()

    @work(thread=True, exclusive=True, group="telemetry")
    def refresh_telemetry(self) -> None:
        try:
            s = self.backend.stats()
        except Exception as exc:  # daemon fora do ar: tenta de novo no próximo tick
            self.call_from_thread(self._telemetry_offline, str(exc))
            return
        self.call_from_thread(self._telemetry, s)

    def _telemetry_offline(self, err: str) -> None:
        if self.online or not self.mem:
            self.feed(f"UPLINK PERDIDO · {err[:60]}", "red")
        self.online = False
        self.mem = self.mem or {}
        self.query_one("#telemetry", Static).update(f"[b {C['red']}]DAEMON OFFLINE[/]\n[{C['dim']}]rode: codar start[/]")

    def _telemetry(self, s: dict) -> None:
        first = not self.online
        self.online = True
        mem, model, pats = s.get("memory", {}), s.get("model") or {}, s.get("patterns", {})
        self.mem = mem
        if first:
            self.feed(f"UPLINK OK · daemon {s.get('version')} · pid {s.get('pid', '-')}", "green")
            self.feed(f"PATTERN BANK · {pats.get('patterns', 0)} PADRÕES · {len(pats.get('langs', {}))} LINGUAGENS", "green")
            self.feed(f"SLM · {model.get('name', '-')} · {'LOADED' if model.get('loaded') else 'STANDBY'}", "cyan")
        rows = [f"[{C['dim']}]RAM  [/][{C['mint']}]{mem.get('total_mb', 0):.0f}[/][{C['dim']}]/{mem.get('budget_mb', 0)} MB  "
                f"PICO {mem.get('peak_mb', 0):.0f}[/]",
                f"[{C['dim']}]TETO [/][{C['cyan']}]{mem.get('enforcement', '-')}[/]",
                f"[{C['dim']}]SLM  [/][{C['green']}]{_esc(str(model.get('name', '-')))}[/] " +
                (f"[{C['mint']}]●[/]" if model.get("loaded") else f"[{C['orange']}]○[/]"),
                f"[{C['dim']}]BANCO [/][{C['green']}]{pats.get('patterns', 0)} padrões · {s.get('rules', 0)} regras[/]"]
        for stage, m in sorted((s.get("stages") or {}).items()):
            rows.append(f"[{C['dim']}]{stage:<7}[/][{C['text']}]n={m['n']} p50={m['p50_ms']}ms[/]")
        self.query_one("#telemetry", Static).update("\n".join(rows))
        self.render_status()

    # ------------------------------------------------------------------ editores
    def current_editor(self) -> CodeEditor | None:
        tabs = self.query_one("#editors", TabbedContent)
        if not tabs.active:
            return None
        try:
            return tabs.get_pane(tabs.active).query_one(CodeEditor)
        except Exception:
            return None

    def current_lang(self) -> str:
        if self.forced_lang:
            return self.forced_lang
        ed = self.current_editor() if self.is_mounted else None
        lang = langs.from_path(ed.path) if ed and ed.path else None
        return lang.id if lang else "python"

    async def open_file(self, path: Path) -> None:
        tabs = self.query_one("#editors", TabbedContent)
        for pane in tabs.query(TabPane):
            ed = pane.query(CodeEditor).first() if pane.query(CodeEditor) else None
            if ed and ed.path and Path(ed.path) == path:
                tabs.active = pane.id or ""
                ed.focus()
                return
        try:
            text = path.read_text(encoding="utf-8") if path.exists() else ""
        except (UnicodeDecodeError, OSError) as exc:
            self.notify(f"não consegui abrir {path.name}: {exc}", severity="error")
            return
        await self._add_editor(text, str(path), path.name)

    async def _add_editor(self, text: str, path: str | None, title: str) -> CodeEditor:
        self.tab_seq += 1
        lang = langs.from_path(path) if path else langs.try_resolve(self.current_lang())
        ts = EXT_TS.get(Path(path).suffix.lower()) if path else None
        ts = ts or (TS_LANG.get(lang.id) if lang else None)
        ed = CodeEditor.code_editor(text, language=ts, theme="monokai", soft_wrap=False)
        ed.path, ed.saved_text = path, text
        ed.lang_id = lang.id if lang else None
        ed.register_theme(SENTRY_THEME)
        ed.theme = "sentry"
        if lang:
            ed.indent_type = "tabs" if lang.indent == "\t" else "spaces"
            ed.indent_width = 4 if lang.indent == "\t" else len(lang.indent)
        pane = TabPane(title, ed, id=f"ed-{self.tab_seq}")
        tabs = self.query_one("#editors", TabbedContent)
        await tabs.add_pane(pane)
        self.sync_welcome()
        tabs.active = pane.id or ""
        ed.focus()
        self.render_pills()
        return ed

    @on(DirectoryTree.FileSelected)
    async def _file_selected(self, event: DirectoryTree.FileSelected) -> None:
        await self.open_file(Path(event.path))

    @on(TabbedContent.TabActivated, "#editors")
    def _tab_changed(self) -> None:
        self.render_pills()

    @on(CodeEditor.Changed)
    def _editor_changed(self, event: CodeEditor.Changed) -> None:
        ed = event.text_area
        if isinstance(ed, CodeEditor):
            self._update_tab_label(ed)

    def _update_tab_label(self, ed: CodeEditor) -> None:
        pane = next((p for p in ed.ancestors if isinstance(p, TabPane)), None)
        if pane is None or not pane.id:
            return
        name = Path(ed.path).name if ed.path else "sem título"
        tab = self.query_one("#editors", TabbedContent).get_tab(pane.id)
        tab.label = f"● {name}" if ed.dirty else name

    # ------------------------------------------------------------------ tradução
    def _editor_context(self, ed: CodeEditor | None, row: int | None) -> tuple[str, str, str | None]:
        if ed is None:
            return "", "", None
        row = ed.cursor_location[0] if row is None else row
        lines = ed.text.split("\n")
        before = "\n".join(lines[max(0, row - 40):row])
        line = lines[row] if row < len(lines) else ""
        indent = line[: len(line) - len(line.lstrip())]
        unit = "\t" if ed.indent_type == "tabs" else " " * ed.indent_width
        return before, indent, unit

    def request(self, intent: str, mode: str, ed: CodeEditor | None = None, row: int | None = None) -> None:
        intent = intent.strip()
        if not intent:
            return
        if intent in self.intents:
            self.intents.remove(intent)
        self.intents.insert(0, intent)  # o autocompletar da barra sugere primeiro o que você já usou
        before, indent, unit = self._editor_context(ed, row)
        original = ed.document.get_line(row) if ed is not None and row is not None else None
        self.feed(f"TX · {intent[:70]}", "text")
        out = self.query_one("#output", RichLog)
        out.write(f"[{C['red']}]▸ INTENÇÃO[/] [{C['text']}]{_esc(intent)}[/]")
        self.streaming = False
        self.translate_worker(intent, self.current_lang(), mode, ed.path if ed else None, before, indent, unit, row,
                              original, ed.id if ed else None)

    @work(thread=True, group="translate")
    def translate_worker(self, intent, lang, mode, path, before, indent, unit, row, original, editor_id) -> None:
        from codar.client import RpcError

        def on_delta(d: str) -> None:
            self.call_from_thread(self._delta, d)

        try:
            res = self.backend.translate(intent, lang, file=path, before=before, indent=indent if mode == "line" else "",
                                         indent_unit=unit, stages=tuple(sorted(self.stages)), hints=self.hints,
                                         on_delta=on_delta)
        except RpcError as exc:
            self.call_from_thread(self._failed, intent, exc.message, (exc.data or {}).get("candidates") or [])
            return
        except Exception as exc:
            self.call_from_thread(self._failed, intent, f"{type(exc).__name__}: {exc}", [])
            return
        self.call_from_thread(self._apply, res, mode, row, original, editor_id, indent)

    def _delta(self, d: str) -> None:
        out = self.query_one("#output", RichLog)
        if not self.streaming:
            self.streaming = True
            self.query_one("#panel", TabbedContent).active = "tab-output"
            out.write(f"[{C['orange']}]▸ SLM gerando…[/]")
        out.write(Text(d, style=C["dim"]), scroll_end=True)

    def _failed(self, intent: str, message: str, cands: list[dict]) -> None:
        self.feed(f"UNRESOLVED · {message[:60]}", "red")
        out = self.query_one("#output", RichLog)
        out.write(f"[b {C['red']}]✖ {_esc(message)}[/]")
        for c in cands[:3]:
            out.write(f"[{C['dim']}]  candidato {c['id']} ({c['score']:.2f}) {c['title']}[/]")
        self.notify(message[:120], severity="error", title="não resolvido")

    def _apply(self, res: dict, mode: str, row: int | None, original: str | None, editor_id: str | None,
               indent: str) -> None:
        self.last = res
        self.render_last()
        self.query_one("#radar", OrbitRadar).ping(res["stage"])
        self.feed(f"RX · {STAGE_NAMES.get(res['stage'], res['stage'])} · {res['source'][:30]} · "
                  f"{res['timings'].get('total_ms', 0):.1f}MS", "green")
        hist = self.query_one("#history", ListView)
        hist.insert(0, [ListItem(Static(f"[{STAGE_COLORS.get(res['stage'], C['orange'])}]●[/] "
                                        f"[{C['text']}]{_esc(res['source'][:30])}[/]"))])
        code = res.get("annotated") if self.hints and res.get("annotated") else None
        body = code if code else res["body"]
        ed = self.query_one(f"#{editor_id}", CodeEditor) if editor_id else self.current_editor()
        if ed is None:
            self.call_later(self._new_buffer_with, res)
            return
        if mode == "line" and row is not None and original is not None:
            if row >= ed.document.line_count or ed.document.get_line(row) != original:
                self.notify("a linha mudou enquanto a IA respondia; resultado mostrado em SAÍDA", severity="warning")
                self.query_one("#output", RichLog).write(Text(res["code"], style=C["moon"]))
                return
            start, end = (row, 0), (row, len(original))
            ed.replace(body, start, end)
        else:
            r, _c = ed.cursor_location
            line = ed.document.get_line(r)
            base = line[: len(line) - len(line.lstrip())]
            block = "\n".join((base + ln) if ln.strip() else ln for ln in body.split("\n"))
            if line.strip():
                start = (r, len(line))
                ed.insert("\n" + block, start)
                start = (r + 1, 0)
            else:
                start = (r, 0)
                last_line = r == ed.document.line_count - 1
                ed.replace(block + ("\n" if last_line else ""), (r, 0), (r, len(line)))
        n_lines = body.count("\n")
        added = self._hoist_imports(ed, res)
        start = (start[0] + added, 0)
        end_row = start[0] + n_lines
        ed.selection = Selection(start, (end_row, len(ed.document.get_line(end_row))))
        ed.focus()
        self._show_findings(res.get("findings", []), start[0])
        for note in res.get("notes", []):
            self.notify(note, title="codar")

    def _hoist_imports(self, ed: CodeEditor, res: dict) -> int:
        """Insere no topo os imports que faltam (depois do package/shebang/<?php). Retorna quantas linhas entraram."""
        existing = {ln.strip() for ln in ed.text.split("\n")}
        missing = [imp for imp in res.get("imports", []) if imp.strip() not in existing]
        if not missing:
            return 0
        lines = ed.text.split("\n")
        at = 0
        while at < len(lines) and (lines[at].startswith(("#!", "package ", "<?php")) or
                                   (res["lang"] == "python" and lines[at].startswith(("from __future__", '"""')))):
            at += 1
        block = "\n".join(missing) + "\n"
        if at < len(lines) and lines[at].strip() and not any(lines[at].startswith(k) for k in ("import", "from", "use", "#include", "using", "require")):
            block += "\n"
        ed.insert(block, (at, 0))
        return block.count("\n")

    async def _new_buffer_with(self, res: dict) -> None:
        lang = langs.LANGS.get(res["lang"])
        ext = lang.exts[0] if lang and lang.exts else ".txt"
        ed = await self._add_editor(res["code"] + "\n", None, f"sem título{ext}")
        ed.saved_text = ""
        self._update_tab_label(ed)
        self._show_findings(res.get("findings", []), 0, absolute=True)

    def _show_findings(self, findings: list[dict], offset: int, absolute: bool = False) -> None:
        table = self.query_one("#problems", DataTable)
        table.clear()
        sev_color = {"critical": C["red"], "error": C["red"], "warning": C["orange"], "info": C["cyan"]}
        for f in findings:
            line = f["line"] if absolute else offset + max(1, f.get("body_line", f["line"]))
            table.add_row(Text(f["severity"].upper(), style=f"bold {sev_color.get(f['severity'], C['text'])}"),
                          Text(f["id"], style=C["red"]), Text(str(line), style=C["dim"]),
                          Text(f["message"] + (f"  → {f['suggestion']}" if f.get("suggestion") else ""), style=C["text"]),
                          key=f"{f['id']}:{line}:{len(table.rows)}")
        self.query_one("#panel", TabbedContent).border_subtitle = f"{len(findings)} achado(s)" if findings else "limpo"
        if findings:
            self.query_one("#panel", TabbedContent).active = "tab-problems"

    @on(DataTable.RowSelected, "#problems")
    def _jump(self, event: DataTable.RowSelected) -> None:
        ed = self.current_editor()
        if ed is None:
            return
        try:
            line = int(str(event.row_key.value).split(":")[1])
        except (IndexError, ValueError):
            return
        ed.move_cursor((max(0, line - 1), 0))
        ed.focus()

    @on(Input.Submitted, "#intent")
    def _intent(self, event: Input.Submitted) -> None:
        text = event.value
        event.input.value = ""
        self.request(text, "insert", self.current_editor(), None)

    @on(CodeEditor.TranslateLine)
    def _space_enter(self, event: CodeEditor.TranslateLine) -> None:
        line = event.editor.document.get_line(event.row)
        self.request(line.strip(), "line", event.editor, event.row)

    def action_translate_line(self) -> None:
        ed = self.current_editor()
        if ed is None:
            self.notify("abra um arquivo (ou use a barra de intenção)", severity="warning")
            return
        row = ed.cursor_location[0]
        line = ed.document.get_line(row)
        if not line.strip():
            return
        self.request(line.strip(), "line", ed, row)

    @staticmethod
    def welcome_text() -> str:
        """Tela inicial enquanto nenhum arquivo está aberto: o que dá para fazer e frases para experimentar."""
        def row(k1: str, v1: str, k2: str, v2: str) -> str:
            return (f"[b {C['mint']}]{k1:<8}[/] [{C['text']}]{v1:<22}[/]   "
                    f"[b {C['mint']}]{k2:<9}[/] [{C['text']}]{v2:<20}[/]")
        examples = "\n".join(f"[{C['green']}]{e}[/]  [{C['dim']}]{what}[/]" for e, what in EXAMPLES[:3])
        return "\n".join([
            f"[b {C['orange']}]{TITLE}[/]", "",
            f"[{C['text']}]escreva a intenção em pseudocódigo · o CODAR escreve o código[/]", "",
            row("Ctrl+N", "novo arquivo", "Explorer", "Enter abre o arquivo"),
            row("Ctrl+L", "descrever o código", "F1", "todos os atalhos"),
            row("F8", "consultor do projeto", "Ctrl+Q", "sair"), "",
            f"[{C['dim']}]experimente na barra de intenção:[/]", examples,
        ])

    def sync_welcome(self) -> None:
        """Mostra as boas-vindas só quando não há arquivo aberto."""
        tabs = self.query_one("#editors", TabbedContent)
        empty = tabs.tab_count == 0
        self.query_one("#welcome", Static).display = empty
        tabs.display = not empty

    def action_help(self) -> None:
        self.push_screen(HelpScreen())

    def action_focus_intent(self) -> None:
        self.query_one("#intent", Input).focus()

    def action_toggle_stage(self, stage: int) -> None:
        self.stages ^= {stage}
        if not self.stages:
            self.stages = {stage}
        self.render_pills()

    def action_toggle_audit(self) -> None:
        self.audit_on = not self.audit_on
        self.render_pills()

    def action_toggle_hints(self) -> None:
        self.hints = not self.hints
        self.render_pills()

    # ------------------------------------------------------------------ arquivos
    async def action_save(self) -> None:
        ed = self.current_editor()
        if ed is None:
            return
        if not ed.path:
            lang = langs.try_resolve(self.current_lang())
            ext = lang.exts[0] if lang and lang.exts else ".txt"
            self.push_screen(PromptScreen("salvar como (relativo ao projeto)", f"novo{ext}"), self._save_as)
            return
        self._write(ed)

    def _save_as(self, name: str | None) -> None:
        ed = self.current_editor()
        if not name or ed is None:
            return
        path = (self.root / name).resolve()
        ed.path = str(path)
        self._write(ed)
        self.query_one("#explorer", Explorer).reload()

    def _write(self, ed: CodeEditor) -> None:
        path = Path(ed.path)
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(ed.text, encoding="utf-8")
        except OSError as exc:
            self.notify(f"erro ao salvar: {exc}", severity="error")
            return
        ed.saved_text = ed.text
        self._update_tab_label(ed)
        self.feed(f"SAVE · {path.name}", "green")
        if self.audit_on:
            self.action_audit_file()

    def action_new_file(self) -> None:
        self.push_screen(PromptScreen("novo arquivo (relativo ao projeto)", "ex.: src/main.py"), self._new_file)

    async def _new_file(self, name: str | None) -> None:
        if name:
            await self.open_file((self.root / name).resolve())

    async def action_close_tab(self) -> None:
        tabs = self.query_one("#editors", TabbedContent)
        if tabs.active:
            ed = self.current_editor()
            if ed and ed.dirty:
                self.notify("arquivo com alterações não salvas (Ctrl+S); feche de novo para descartar", severity="warning")
                ed.saved_text = ed.text
                return
            await tabs.remove_pane(tabs.active)
            self.sync_welcome()

    def action_toggle_left(self) -> None:
        left = self.query_one("#left")
        left.display = not left.display

    def action_toggle_panel(self) -> None:
        panel = self.query_one("#panel")
        panel.display = not panel.display

    # ------------------------------------------------------------------ auditoria / execução
    def action_audit_file(self) -> None:
        ed = self.current_editor()
        if ed is None:
            return
        lang = langs.from_path(ed.path) if ed.path else langs.try_resolve(self.current_lang())
        if lang is None:
            return
        self.audit_worker(ed.text, lang.id)

    @work(thread=True, exclusive=True, group="audit")
    def audit_worker(self, code: str, lang: str) -> None:
        try:
            res = self.backend.audit(code, lang)
        except Exception as exc:
            self.call_from_thread(self.notify, f"auditoria indisponível: {exc}", severity="error")
            return
        self.call_from_thread(self._show_findings, res["findings"], 0, True)
        self.call_from_thread(self.feed, f"AUDIT · {len(res['findings'])} achado(s) · {res['ms']:.1f}MS",
                              "orange" if res["findings"] else "green")

    async def action_run_file(self) -> None:
        ed = self.current_editor()
        if ed is None or not ed.path:
            self.notify("salve o arquivo antes de executar (Ctrl+S)", severity="warning")
            return
        if ed.dirty:
            self._write(ed)
        lang = langs.from_path(ed.path)
        if not lang or not lang.runner:
            self.notify(f"sem executor configurado para {lang.name if lang else 'este arquivo'}", severity="warning")
            return
        cmd = [part.replace("{file}", ed.path).replace("{python}", sys.executable) for part in lang.runner]
        try:  # na tela, o comando curto: "python perguntas.py" em vez dos caminhos completos
            nome = str(Path(ed.path).relative_to(self.root))
        except ValueError:
            nome = Path(ed.path).name
        visivel = [nome if p == "{file}" else "python" if p == "{python}" else p for p in lang.runner]
        juntar = (lambda partes: " ".join(shlex.quote(c) for c in partes)) if os.name != "nt" else subprocess.list2cmdline
        self.run_command(juntar(cmd), visivel=juntar(visivel))

    @on(Input.Submitted, "#term-input")
    def _term(self, event: Input.Submitted) -> None:
        texto = event.value
        event.input.value = ""
        if self.process_running():  # com um programa rodando, a linha vai para a entrada dele (input(), read…)
            self.send_to_process(texto)
            return
        cmd = texto.strip()
        if cmd == "clear":
            self.query_one("#term-log", RichLog).clear()
        elif cmd:
            self.run_command(cmd)

    def process_running(self) -> bool:
        return self.term_proc is not None and self.term_proc.poll() is None

    def send_to_process(self, texto: str) -> None:
        if self.term_fd is not None:  # pseudoterminal: o próprio terminal ecoa o que foi digitado
            os.write(self.term_fd, (texto + "\n").encode())
        elif self.term_proc is not None and self.term_proc.stdin is not None:  # Windows: pipe, eco manual
            self.term_proc.stdin.write((texto + "\n").encode())
            self.term_proc.stdin.flush()
            self.query_one("#term-log", RichLog).write(Text(self.term_waiting + texto, style=C["text"]))
        self._prompt_waiting("")

    def interrupt_process(self) -> None:
        """Ctrl+C no terminal: SIGINT para o programa (KeyboardInterrupt no Python)."""
        if not self.process_running():
            return
        if os.name == "posix":
            os.killpg(self.term_proc.pid, signal.SIGINT)
        else:
            self.term_proc.terminate()

    def _prompt_waiting(self, pergunta: str) -> None:
        """O programa imprimiu uma pergunta sem quebra de linha e está esperando: mostra a pergunta no campo do
        terminal e põe o cursor lá."""
        campo = self.query_one("#term-input", Input)
        self.term_waiting = pergunta
        if pergunta:
            campo.placeholder = f"{pergunta.strip() or '>'}   ← o programa espera: digite e tecle Enter"
            self.query_one("#panel", TabbedContent).active = "tab-terminal"
            campo.focus()
        else:
            campo.placeholder = TERM_RUNNING if self.process_running() else TERM_IDLE
        self.render_status()

    def run_command(self, cmd: str, visivel: str | None = None) -> None:
        if self.process_running():
            self.notify("já há um programa rodando: Ctrl+C no terminal interrompe", severity="warning")
            return
        self.query_one("#panel", TabbedContent).active = "tab-terminal"
        self.query_one("#term-log", RichLog).write(Text(f"$ {visivel or cmd}", style=f"bold {C['mint']}"))
        self.term_worker(cmd)

    @work(thread=True, group="terminal")
    def term_worker(self, cmd: str) -> None:
        """Roda o comando num pseudoterminal: o programa se comporta como num terminal de verdade (input() mostra a
        pergunta na hora, a saída não fica presa em buffer, Ctrl+C e getpass funcionam). No Windows, pipes."""
        log = self.query_one("#term-log", RichLog)
        t0 = time.monotonic()
        env = {**os.environ, "PYTHONUNBUFFERED": "1", "TERM": "dumb"}
        master = None
        try:
            if os.name == "posix":
                import fcntl
                import pty
                import struct
                import termios

                master, slave = pty.openpty()
                colunas = max(40, log.size.width - 2)
                fcntl.ioctl(slave, termios.TIOCSWINSZ, struct.pack("HHHH", 24, colunas, 0, 0))
                # setsid -c: sessão nova com o pseudoterminal como terminal de controle (Ctrl+C, getpass)
                argv = ["setsid", "-c", "sh", "-c", cmd] if shutil.which("setsid") else ["sh", "-c", cmd]
                self.term_proc = subprocess.Popen(argv, cwd=self.root, stdin=slave, stdout=slave, stderr=slave,
                                                  env=env, close_fds=True, start_new_session=argv[0] != "setsid")
                os.close(slave)
            else:
                self.term_proc = subprocess.Popen(cmd, shell=True, cwd=self.root, stdin=subprocess.PIPE,
                                                  stdout=subprocess.PIPE, stderr=subprocess.STDOUT, env=env, bufsize=0)
        except OSError as exc:
            if master is not None:
                os.close(master)
            self.call_from_thread(log.write, Text(str(exc), style=C["red"]))
            return
        self.term_fd = master
        self.call_from_thread(self._prompt_waiting, "")
        decoder = codecs.getincrementaldecoder("utf-8")(errors="replace")
        pendente = ""  # texto depois da última quebra de linha (a pergunta de um input(), por exemplo)
        avisado = ""
        ociosos = 0
        while True:
            chunk = self._read_output(master, 0.15)
            if chunk is None:  # nada chegou: se sobrou texto sem quebra de linha, o programa está esperando
                if pendente and pendente != avisado and self.process_running():
                    avisado = pendente
                    self.call_from_thread(self._prompt_waiting, pendente)
                if not self.process_running():  # terminou, mas um filho em segundo plano segura o terminal
                    ociosos += 1
                    if ociosos > 6:
                        break
                continue
            if not chunk:
                break
            texto = pendente + decoder.decode(chunk).replace("\r\n", "\n")
            *linhas, pendente = texto.split("\n")
            for linha in linhas:  # "\r" sozinho (barras de progresso): fica o que foi escrito por último
                self.call_from_thread(log.write, Text.from_ansi(linha.rsplit("\r", 1)[-1], style=C["text"]))
            if linhas and avisado:
                avisado = ""
                self.call_from_thread(self._prompt_waiting, "")
        code = self.term_proc.wait()
        if pendente.strip():
            self.call_from_thread(log.write, Text.from_ansi(pendente, style=C["text"]))
        if master is not None:
            os.close(master)
        self.term_fd = None
        self.call_from_thread(self._prompt_waiting, "")
        style = C["mint"] if code == 0 else C["red"]
        self.call_from_thread(log.write, Text(f"[exit {code} · {time.monotonic() - t0:.2f}s]", style=f"bold {style}"))
        self.call_from_thread(self.feed, f"RUN · exit {code}", "green" if code == 0 else "red")

    def _read_output(self, master: int | None, timeout: float) -> bytes | None:
        """Bytes disponíveis da saída do programa; None se nada chegou no prazo; b"" no fim."""
        if master is not None:
            pronto, _, _ = select.select([master], [], [], timeout)
            if not pronto:
                return None
            try:
                return os.read(master, 4096)
            except OSError:  # EIO: o programa terminou e fechou o terminal
                return b""
        assert self.term_proc is not None and self.term_proc.stdout is not None
        return self.term_proc.stdout.read1(4096) if hasattr(self.term_proc.stdout, "read1") else \
            self.term_proc.stdout.read(1)

    def action_stop_process(self) -> None:
        if self.process_running():
            if os.name == "posix":
                os.killpg(self.term_proc.pid, signal.SIGTERM)  # o sh e o programa que ele iniciou
            else:
                self.term_proc.terminate()

    # ------------------------------------------------------------------ consultor de projeto
    def action_advise(self) -> None:
        self.query_one("#panel", TabbedContent).active = "tab-advisor"
        self.feed("ADVISOR · analisando o projeto…", "dim")
        self.advise_worker()

    @work(thread=True, exclusive=True, group="advise")
    def advise_worker(self) -> None:
        try:
            report = self.backend.advise(self.root)
        except Exception:
            from codar import config
            from codar.advisor import scan_project
            from codar.plugin_loader import discover

            report = scan_project(self.root, discover(config.load()).advice)
        self.call_from_thread(self._show_advice, report)

    def _show_advice(self, report: dict) -> None:
        lst = self.query_one("#advice-list", ListView)
        lst.clear()
        self.advice = report["suggestions"]
        colors = {"high": C["red"], "medium": C["orange"], "low": C["cyan"]}
        for s in self.advice:
            opts = " · ".join(o["label"] for o in s["options"])
            lst.append(ListItem(Static(f"[b {colors.get(s['impact'], C['text'])}]▶ {_esc(s['title'])}[/]\n"
                                       f"[{C['text']}]{_esc(s['reason'][:150])}[/]\n[{C['mint']}]{_esc(opts)}[/]")))
        self.feed(f"ADVISOR · {len(self.advice)} sugestão(ões)", "orange" if self.advice else "green")
        if not self.advice:
            lst.append(ListItem(Static(f"[{C['mint']}]✓ nenhuma sugestão — projeto em ordem[/]")))

    @on(ListView.Selected, "#advice-list")
    def _advice_selected(self, event: ListView.Selected) -> None:
        idx = event.list_view.index
        if idx is None or not getattr(self, "advice", None) or idx >= len(self.advice):
            return
        s = self.advice[idx]
        self.push_screen(AdviceScreen(s), lambda oid, s=s: self._accept_advice(s, oid))

    def _accept_advice(self, s: dict, oid: str | None) -> None:
        if not oid:
            return
        self.query_one("#panel", TabbedContent).active = "tab-terminal"
        self.apply_worker(s["id"], oid)

    @work(thread=True, exclusive=True, group="advise")
    def apply_worker(self, sid: str, oid: str) -> None:
        from codar import config
        from codar.advisor.apply import ApplyError, apply_steps, find_option
        from codar.plugin_loader import discover

        log = self.query_one("#term-log", RichLog)
        bundle = discover(config.load())
        try:
            title, opt, steps = find_option(self.root, bundle, sid, oid)
            self.call_from_thread(log.write, Text(f"▶ {title} → {opt['label']}", style=f"bold {C['mint']}"))
            apply_steps(self.root, steps, bundle, lambda s: self.call_from_thread(log.write, Text(s, style=C["text"])))
        except ApplyError as exc:
            self.call_from_thread(log.write, Text(f"✖ {exc}", style=f"bold {C['red']}"))
            self.call_from_thread(self.feed, f"ADVISOR · falhou: {str(exc)[:50]}", "red")
            return
        self.call_from_thread(self.feed, f"ADVISOR · aplicado: {opt['label']}", "green")
        self.call_from_thread(self.notify, f"aplicado: {opt['label']}", title="consultor")
        self.call_from_thread(self.query_one("#explorer", Explorer).reload)
        self.advise_worker()

    # ------------------------------------------------------------------ integrações
    def action_open_vscode(self) -> None:
        import shutil

        ed = self.current_editor()
        code = shutil.which("code") or shutil.which("codium")
        if not code:
            self.notify("CLI `code` não encontrada no PATH", severity="error")
            return
        target = f"{ed.path}:{ed.cursor_location[0] + 1}:{ed.cursor_location[1] + 1}" if ed and ed.path else str(self.root)
        flag = "-r" if os.environ.get("TERM_PROGRAM") == "vscode" else "-n"
        subprocess.Popen([code, flag, "-g", target] if ed and ed.path else [code, flag, target],
                         stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        self.feed("VSCODE · alternando para o editor gráfico", "cyan")

    def action_set_lang(self) -> None:
        self.push_screen(PromptScreen("linguagem (py, js, ts, go, rs, java, cs, c, cpp, sh, ps1, lua, rb, php)",
                                      value=self.current_lang()), self._set_lang)

    def _set_lang(self, value: str | None) -> None:
        lang = langs.try_resolve(value) if value else None
        if lang:
            self.forced_lang = lang.id
            self.render_pills()

    def action_save_pattern(self) -> None:
        if not self.last:
            self.notify("gere algo antes de salvar como padrão", severity="warning")
            return
        self.push_screen(PromptScreen("id do novo padrão (ex.: meu.cliente_api)"), self._save_pattern)

    def _save_pattern(self, pid: str | None) -> None:
        if pid and self.last:
            self.pattern_worker(pid, dict(self.last))

    @work(thread=True)
    def pattern_worker(self, pid: str, res: dict) -> None:
        intent = next((h["intent"] for h in self._history() if h.get("preview", "")[:60] == res["code"][:60]), pid)
        try:
            self.backend.call("patterns.add", {"id": pid, "title": intent[:80], "lang": res["lang"], "code": res["code"],
                                               "keywords": intent})
            self.call_from_thread(self.notify, f"padrão {pid} salvo no banco", title="aprendizado")
            self.call_from_thread(self.feed, f"LEARN · {pid}", "mint")
        except Exception as exc:
            self.call_from_thread(self.notify, str(exc), severity="error")

    def _history(self) -> list[dict]:
        try:
            return self.backend.call("history", {"limit": 50})
        except Exception:
            return []

    @work(thread=True)
    def model_worker(self, method: str) -> None:
        try:
            info = self.backend.call(method)
            self.call_from_thread(self.feed, f"SLM · {info.get('name')} · {'LOADED' if info.get('loaded') else 'UNLOADED'}",
                                  "cyan")
        except Exception as exc:
            self.call_from_thread(self.notify, str(exc), severity="error")

    def palette(self) -> list[tuple[str, str, object]]:
        return [
            ("Codar: Traduzir linha atual", "Ctrl+G — a linha vira código no lugar", self.action_translate_line),
            ("Codar: Auditar arquivo", "F6 — segredos, segurança, desempenho, memória", self.action_audit_file),
            ("Codar: Executar arquivo", "F5 — roda no terminal integrado", self.action_run_file),
            ("Codar: Consultor de projeto", "F8 — sugestões com opções executáveis", self.action_advise),
            ("Codar: Abrir no VS Code", "Ctrl+O — alterna para o editor gráfico", self.action_open_vscode),
            ("Codar: Trocar linguagem…", "força a linguagem alvo", self.action_set_lang),
            ("Codar: Salvar último resultado como padrão…", "ensina o banco de padrões", self.action_save_pattern),
            ("Codar: Alternar dicas inline", "comentários 'Dica [ID]' no código", self.action_toggle_hints),
            ("Codar: Alternar auditoria", "liga/desliga a auditoria ao salvar", self.action_toggle_audit),
            ("Codar: Carregar modelo", "pré-aquece o SLM", lambda: self.model_worker("model.load")),
            ("Codar: Descarregar modelo", "devolve a RAM do SLM ao sistema", lambda: self.model_worker("model.unload")),
            ("Codar: Novo arquivo…", "Ctrl+N", self.action_new_file),
            ("Codar: Parar processo do terminal", "encerra o processo em execução", self.action_stop_process),
            ("Codar: Mostrar/ocultar explorer", "Ctrl+B", self.action_toggle_left),
            ("Codar: Mostrar/ocultar painel", "F9", self.action_toggle_panel),
        ]

    def on_unmount(self) -> None:
        self.action_stop_process()
        self.backend.close()


def _budget_gb() -> str:
    from codar import config

    mb = int(config.load()["memory"]["budget_mb"])
    return f"{mb / 1024:g}"


def _esc(text: str) -> str:
    return str(text).replace("[", "\\[")


def run_studio(path: str = ".", lang: str | None = None, local: bool = False) -> int:
    Studio(path, lang, local).run()
    return 0
