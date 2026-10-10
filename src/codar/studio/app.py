"""Codar Studio — IDE imersiva no terminal (funciona via SSH e em servidores sem interface gráfica).

Layout inspirado no console SENTRY: explorer + radar orbital do pipeline + feed de eventos à
esquerda, editores em abas no centro com painel de problemas/terminal/saída/consultor,
telemetria à direita, barra de intenção e medidor de RAM embaixo.
"""

from __future__ import annotations

import asyncio
import os
import re
import random
import shlex
import shutil
import subprocess
import sys
import time
import urllib.parse
from functools import partial
from pathlib import Path

from rich.text import Text
from textual import on, work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.command import DiscoveryHit, Hit, Hits, Provider
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.suggester import Suggester
from textual.theme import Theme
from textual.widgets import (DataTable, DirectoryTree, Footer, Input, ListItem, ListView, RichLog, Static,
                             TabbedContent, TabPane, TextArea)

from codar import __version__, langs
from codar.advisor import pacotes
from codar.studio import comandos, estado
from codar.studio.backend import StudioBackend
from codar.studio.edits import EditTarget, wants_edit
from codar.studio.explorer import SKIP, Explorer
from codar.studio.terminal import TerminalInput, TerminalPainel
from codar.engine import emmet
from codar.studio.screens import AdviceScreen, CelularScreen, HelpScreen, PromptScreen
from codar.studio.review import ChoiceScreen, ReviewScreen
from codar.studio.widgets import (C, SENTRY, STAGE_COLORS, TITLE, Botao, CodeEditor, OrbitRadar, aplicar_paleta,
                                  gauge, paleta, tema_ansi, tema_editor)
from codar.textutil import looks_like_intent
from codar.vocab import EXAMPLES

STAGE_NAMES = {"0": "S0 COMPILER", "1": "S1 PATTERN", "2:tools": "S2 TOOLS", "2:adapt": "S2 ADAPT", "2:gen": "S2 SLM",
               "2:pseudo": "S2 PSEUDO", "2:edit": "S2 EDIT"}
TS_LANG = {"python": "python", "javascript": "javascript", "typescript": "javascript", "go": "go", "rust": "rust",
           "java": "java", "bash": "bash", "sql": "sql", "html": "html", "css": "css", "yaml": "yaml", "markdown": "markdown"}
EXT_TS = {".json": "json", ".toml": "toml", ".md": "markdown", ".xml": "xml", ".yml": "yaml", ".yaml": "yaml"}


class ArquivosProvider(Provider):
    """Arquivos do projeto na paleta: digite parte do nome (ou do caminho) e Enter abre."""

    async def startup(self) -> None:
        self.arquivos = await asyncio.to_thread(_listar_arquivos, self.app.root)  # type: ignore[attr-defined]

    async def discover(self) -> Hits:
        for rel in self.arquivos[:12]:
            yield DiscoveryHit(rel, partial(self._abrir, rel), help="abrir arquivo")

    async def search(self, query: str) -> Hits:
        matcher = self.matcher(query)
        for rel in self.arquivos:
            score = matcher.match(rel)
            if score > 0:
                yield Hit(score * 0.9, matcher.highlight(rel), partial(self._abrir, rel), help="abrir arquivo")

    async def _abrir(self, rel: str) -> None:
        await self.app.open_file(self.app.root / rel)  # type: ignore[attr-defined]


def _listar_arquivos(raiz: Path, limite: int = 5000) -> list[str]:
    arquivos: list[str] = []
    for pasta, subpastas, nomes in os.walk(raiz):
        subpastas[:] = sorted(d for d in subpastas if d not in SKIP and not d.startswith("."))
        base = Path(pasta).relative_to(raiz)
        arquivos += [(base / n).as_posix() for n in sorted(nomes)]
        if len(arquivos) >= limite:
            break
    return arquivos[:limite]


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


BOTOES_EXPLORER = [("novo_arquivo", "+arquivo"), ("nova_pasta", "+pasta"), ("colar", "colar"), ("recarregar", "↻")]
PILULAS = [("s0", "◎ S0", "toggle_stage(0)"), ("s1", "• S1", "toggle_stage(1)"), ("s2", "✳ S2", "toggle_stage(2)"),
           ("audit", "☉ AUDIT", "toggle_audit"), ("hints", "✎ HINTS", "toggle_hints"), ("estudo", "◆ ESTUDO", "estudo")]
_SENAO = re.compile(r"^\s*(sen[aã]o|caso contr[aá]rio|do contr[aá]rio|else|elif)\b", re.I)
TIPS = [
    "termine a frase com espaço e aperte Enter: a linha vira código",
    "Ctrl+Enter ou Ctrl+G traduz a linha do cursor; com seleção, traduz o bloco",
    "num arquivo .html, escreva ul>li.item*3 e aperte Tab",
    "num arquivo .css, escreva df+jcc+aic e aperte Tab",
    "F1 mostra todos os atalhos",
    "F7 liga o modo estudo: o painel explica cada linha e mostra o próximo passo da trilha de POO",
    "comente '# classe Pessoa com nome e idade' com o modo estudo ligado: o exemplo usa esses nomes",
    "Ctrl+E vai para o explorer: n cria arquivo, p cria pasta, r renomeia, Del apaga",
    "Esc volta para o editor de qualquer lugar; Ctrl+T vai para o terminal",
    "selecione várias linhas de pseudocódigo e aperte Ctrl+G: o bloco inteiro vira código",
    "Ctrl+O abre um arquivo pelo nome; Ctrl+P também acha comandos",
    "F8 abre o consultor: sugestões para o projeto, aplicadas com um clique",
    "a barra de intenção completa o que você já usou: comece a digitar e aperte →",
    "frases que descrevem valores funcionam: 'imprimir o tamanho de pedidos'",
    "pedidos de funcionalidade usam padrões testados: 'criar uma calculadora'",
    "na barra de intenção: 'crie o arquivo main.py', 'crie a pasta src' ou 'abra conta.py'",
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
    COMMANDS = App.COMMANDS | {CodarCommands, ArquivosProvider}
    BINDINGS = [
        Binding("ctrl+s", "save", "Salvar", priority=True),
        # Ctrl+Enter chega como ctrl+enter (kitty, WezTerm, foot…) ou ctrl+j (terminais clássicos); Ctrl+G em qualquer um
        Binding("ctrl+g,ctrl+enter,ctrl+j", "translate_line", "Traduzir", show=False),
        # ir para cada área sem o mouse; Esc volta ao editor
        Binding("ctrl+e", "focus_explorer", "Explorer", priority=True),
        Binding("ctrl+t", "focus_terminal", "Terminal", priority=True),
        Binding("ctrl+l", "focus_intent", "Intenção", priority=True),
        Binding("escape", "focus_editor", "Editor", show=False),
        Binding("ctrl+o", "quick_open", "Abrir", priority=True),
        Binding("ctrl+pagedown", "next_tab", "Próxima aba", show=False, priority=True),
        Binding("ctrl+pageup", "prev_tab", "Aba anterior", show=False, priority=True),
        Binding("f5", "run_file", "Executar", priority=True),
        Binding("f6", "audit_file", "Auditar", show=False, priority=True),
        Binding("ctrl+shift+h", "edit_history", "Histórico de edições", show=False, priority=True),
        Binding("ctrl+shift+g", "project_edit", "Editar projeto", show=False, priority=True),
        Binding("f8", "advise", "Consultor", priority=True),
        Binding("ctrl+n", "new_file", "Novo", show=False, priority=True),
        Binding("ctrl+w", "close_tab", "Fechar aba", show=False, priority=True),
        Binding("ctrl+b", "toggle_left", "Mostrar explorer", show=False, priority=True),
        Binding("f9", "toggle_panel", "Painel", show=False, priority=True),
        Binding("f12", "shell", "Seu shell", show=False, priority=True),
        Binding("f4", "celular", "Celular", priority=True),
        Binding("f7", "estudo", "Estudo", priority=True),
        Binding("shift+f7", "estudo_aplicar", "Aplicar sugestão do estudo", show=False, priority=True),
        Binding("ctrl+q", "quit", "Sair", priority=True),
        Binding("f1", "help", "Ajuda", priority=True),
    ]

    def __init__(self, root: str | Path = ".", lang: str | None = None, local: bool = False) -> None:
        super().__init__()
        self.root = Path(root).expanduser().resolve()
        self.forced_lang = langs.try_resolve(lang).id if lang and langs.try_resolve(lang) else None
        self.backend = StudioBackend(local=local)
        self.stages = {0, 1, 2}
        from codar import config

        self.preview_edits = bool(config.load().get("editing", {}).get("preview", True))
        self.audit_on = True
        self.hints = False
        self.last: dict | None = None
        self.tab_seq = 0
        self.mem: dict = {}
        self.intents: list[str] = []
        self.online = False
        self.streaming = False
        self.rede_srv = None  # prévia na rede ou repasse de servidor (F4: ver no celular)
        self.estudo = False  # modo estudo (F7): o painel ESTUDO acompanha o cursor
        self._estudo_timer = None
        self._estudo_conceito = None
        self._estudo_forcado: str | None = None
        self._estudo_poo = None
        self.sugestao_estudo = None

    # ------------------------------------------------------------------ layout
    def compose(self) -> ComposeResult:
        with Horizontal(id="workspace"):
            with Vertical(id="left"):
                with Horizontal(id="explorer-bar"):
                    for acao, _rotulo in BOTOES_EXPLORER:
                        yield Botao(acao=f"explorer('{acao}')", id=f"eb-{acao}")
                yield Explorer(self.root, id="explorer")
                yield OrbitRadar(id="radar")
                yield RichLog(id="feed", markup=True, wrap=True, max_lines=500, min_width=16)
            with Vertical(id="center"):
                with Horizontal(id="pills-bar"):
                    with Horizontal(id="pills"):
                        for pid, _rotulo, acao in PILULAS:
                            yield Botao(acao=acao, id=f"pill-{pid}")
                    yield Static(id="lang-pill")
                yield Static(self.welcome_text(), id="welcome")
                yield TabbedContent(id="editors")
                with TabbedContent(id="panel", initial="tab-problems"):
                    with TabPane("PROBLEMAS", id="tab-problems"):
                        yield DataTable(id="problems", cursor_type="row")
                    with TabPane("TERMINAL", id="tab-terminal"):
                        self._terminal = TerminalPainel(self.root, id="terminal")
                        yield self._terminal
                    with TabPane("SAÍDA", id="tab-output"):
                        yield RichLog(id="output", markup=True, wrap=True, max_lines=2000, min_width=20)
                    with TabPane("CONSULTOR", id="tab-advisor"):
                        yield ListView(id="advice-list")
                    with TabPane("ESTUDO", id="tab-estudo"):
                        with VerticalScroll(id="estudo"):
                            yield Static(self.estudo_vazio(), id="estudo-corpo")
                            yield Botao(acao="estudo_aplicar", id="estudo-acao")
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
        self.register_theme(Theme(
            name="sentry", primary=SENTRY["orange"], secondary=SENTRY["red"], accent=SENTRY["mint"],
            warning=SENTRY["orange"], error=SENTRY["error"], success=SENTRY["green"], foreground=SENTRY["text"],
            background=SENTRY["bg"], surface=SENTRY["bg"], panel=SENTRY["grid"], dark=True,
            variables={"foreground-muted": SENTRY["dim"], "text-muted": SENTRY["dim"],
                       "block-cursor-background": SENTRY["orange"], "block-cursor-foreground": SENTRY["bg"],
                       "block-cursor-blurred-background": SENTRY["sel"],
                       "block-cursor-blurred-foreground": SENTRY["text"], "block-hover-background": SENTRY["grid"],
                       "input-cursor-background": SENTRY["mint"], "input-cursor-foreground": SENTRY["bg"],
                       "input-selection-background": SENTRY["sel"], "footer-background": SENTRY["panel"],
                       "footer-key-foreground": SENTRY["mint"], "footer-description-foreground": SENTRY["text"],
                       "border": SENTRY["mint"], "border-blurred": SENTRY["orange"]}))
        self.theme_changed_signal.subscribe(self, self._tema_mudou)
        salvo = estado.ler().get("tema")
        self.theme = salvo if salvo and self.get_theme(salvo) else "sentry"
        for wid, title in (("#explorer", "EXPLORER"), ("#radar", "PIPELINE ORBIT"), ("#feed", "SOURCE / EVENT FEED"),
                           ("#editors", "EDITOR"), ("#welcome", "BEM-VINDO"), ("#panel", "PAINEL"), ("#last-card", "LAST TRANSLATION"),
                           ("#telemetry", "TELEMETRIA"), ("#history", "HISTÓRICO"), ("#intent-bar", "")):
            self.query_one(wid).border_title = title
        table = self.query_one("#problems", DataTable)
        table.add_columns("SEV", "ID", "LINHA", "MENSAGEM")
        self.query_one("#hud-meta", Static).update(self.hud_meta())
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

    # ------------------------------------------------------------------ tema
    def get_css_variables(self) -> dict[str, str]:
        """Variáveis $codar-* do studio.tcss: a paleta do tema ativo (o SENTRY ou a derivada de outro tema)."""
        variaveis = super().get_css_variables()
        variaveis.update({f"codar-{k.replace('_', '-')}": v for k, v in paleta(self.current_theme).items()})
        return variaveis

    def _tema_mudou(self, tema: Theme) -> None:
        """Troca de tema (Ctrl+P → "theme"): editor, HUD, terminal e telas acompanham, e a escolha fica salva."""
        aplicar_paleta(paleta(tema))
        self.ansi_theme_dark = self.ansi_theme_light = tema_ansi()
        nome = f"codar-{tema.name}"
        for ed in self.query(CodeEditor):
            ed.register_theme(tema_editor(nome))
            ed.theme = nome
        self.query_one("#hud-meta", Static).update(self.hud_meta())
        self.query_one("#welcome", Static).update(self.welcome_text())
        self.render_pills()
        self.render_last()
        self.render_status()
        self.query_one("#radar", OrbitRadar).refresh()
        if self.mem:
            self.refresh_telemetry()
        if tema.name != estado.ler().get("tema", "sentry"):
            estado.salvar(tema=tema.name)

    @staticmethod
    def hud_meta() -> str:
        return (f"[b {C['mint']}]INTENT → CODE ENCOUNTERS[/]\n[{C['dim']}]SRC ·[/] [{C['green']}]S0 COMPILER · S1 BANK · "
                f"S2 SLM[/]\n[{C['dim']}]OFFLINE · TETO[/] [{C['red']}]{_budget_gb()} GB[/] [{C['dim']}]· v{__version__}[/]")

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
        mark = f"[{C['red']}]▸[/]"
        self.query_one("#feed", RichLog).write(f"{mark} [{C.get(color, color)}]{_esc(text)}[/]")

    def render_pills(self) -> None:
        """Pílulas (clicáveis): menta = ligado, vermelho = desligado. A barra do explorer também é redesenhada aqui."""
        ligado = {"s0": 0 in self.stages, "s1": 1 in self.stages, "s2": 2 in self.stages, "audit": self.audit_on,
                  "hints": self.hints, "estudo": self.estudo}
        for pid, rotulo, _acao in PILULAS:
            self.query_one(f"#pill-{pid}", Botao).update(f"[b {C['mint'] if ligado[pid] else C['red']}] {rotulo} [/]")
        for acao, rotulo in BOTOES_EXPLORER:
            self.query_one(f"#eb-{acao}", Botao).update(f"[b {C['mint']}]{rotulo}[/]")
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
        from textual.css.query import NoMatches

        try:  # chamado também por eventos de foco e do terminal, que podem chegar com a tela já desmontada
            barra = self.query_one("#status", Static)
        except NoMatches:
            return
        m = self.mem
        total, budget = m.get("total_mb", 0.0), m.get("budget_mb", 3072)
        line = Text()
        line.append(" ▶ RUN F5 ", style=f"bold {C['red']}")
        line.append(" ⚑ ADVISE F8 ", style=f"bold {C['red']}")
        line.append(f"  {self.context_hint()} ", style=f"bold {C['cyan']}")
        line.append("  MEMORY BUDGET ", style=C["dim"])
        line.append_text(gauge(total, budget, 26))
        line.append(f" {total:.0f}/{budget} MB ", style=C["mint"])
        if self.rede_srv is not None:
            line.append(f"  ◉ REDE :{self.rede_srv.porta} ", style=f"bold {C['mint']}")
        state = ("● ONLINE", C["mint"]) if self.online else ("○ OFFLINE", C["error"])
        line.append(f"  DAEMON {state[0]} ", style=f"bold {state[1]}")
        line.append("  " + time.strftime("%Y-%b-%d %H:%MZ", time.gmtime()).upper(), style=f"bold {C['mint']}")
        barra.update(line)

    def context_hint(self) -> str:
        """O que dá para fazer agora, de acordo com o foco e a linha do cursor."""
        terminal = self.terminal
        if terminal.sessao is not None and terminal.sessao.esperando:
            return "O PROGRAMA ESPERA ENTRADA · DIGITE NO TERMINAL"
        focused = self.focused
        if isinstance(focused, Input) and focused.id == "intent":
            return "ENTER GERA · → COMPLETA · ESC EDITOR" if focused.value else "DESCREVA O CÓDIGO · ESC EDITOR"
        if isinstance(focused, Explorer):
            return "N NOVO · P PASTA · R RENOMEAR · C/X/V COPIAR · DEL APAGAR · ESC EDITOR"
        if isinstance(focused, TerminalInput):
            if terminal.sessao.rodando():
                return "ENTER ENVIA · CTRL+C INTERROMPE · CTRL+T OUTRO TERMINAL"
            return "ENTER EXECUTA · ↑ HISTÓRICO · CTRL+T OUTRO TERMINAL · F12 SEU SHELL"
        if isinstance(focused, DataTable):
            return "ENTER VAI PARA A LINHA · ESC EDITOR"
        if isinstance(focused, ListView) and focused.id == "advice-list":
            return "ENTER ABRE A SUGESTÃO · ESC EDITOR"
        if isinstance(focused, CodeEditor) and self._dicas_atuais():
            return f"{self._dicas_atuais()[0].curta} · F8 INSTALA"
        if isinstance(focused, CodeEditor):
            row, col = focused.cursor_location
            line = focused.document.get_line(row)
            if focused.selection.start[0] != focused.selection.end[0]:
                r0, r1 = focused.linhas_selecionadas()
                return f"CTRL+G TRADUZ {r1 - r0 + 1} LINHAS (MÁX {self.max_linhas_bloco()}) · TAB INDENTA · CTRL+/ COMENTA"
            if focused.suggestion:
                return "TAB COMPLETA"
            if focused.emmet_kind() and emmet.extract_abbreviation(line[:col]):
                return "TAB EXPANDE"
            if looks_like_intent(line):
                return "CTRL+ENTER TRADUZ · ESPAÇO+ENTER"
            return "CTRL+E EXPLORER · CTRL+T TERMINAL · CTRL+L INTENÇÃO · F1"
        return "ESC EDITOR · F1 AJUDA"

    @on(TextArea.SelectionChanged)
    def _cursor_moved(self) -> None:
        self.render_status()
        self.agendar_estudo()

    def on_descendant_focus(self) -> None:
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
        self.query_one("#telemetry", Static).update(f"[b {C['error']}]DAEMON OFFLINE[/]\n[{C['dim']}]rode: codar start[/]")

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
            rows.append(f"[{C['dim']}]{stage:<9}[/][{C['text']}]n={m['n']} p50={m['p50_ms']}ms[/]")
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
        ed = await self._add_editor(text, str(path), path.name)
        self.verificar_pacotes(ed)

    async def _add_editor(self, text: str, path: str | None, title: str) -> CodeEditor:
        self.tab_seq += 1
        lang = langs.from_path(path) if path else langs.try_resolve(self.current_lang())
        ts = EXT_TS.get(Path(path).suffix.lower()) if path else None
        ts = ts or (TS_LANG.get(lang.id) if lang else None)
        ed = CodeEditor.code_editor(text, language=ts, theme="monokai", soft_wrap=False, id=f"code-{self.tab_seq}")
        ed.path, ed.saved_text = path, text
        ed.lang_id = lang.id if lang else None
        nome = f"codar-{self.theme}"
        ed.register_theme(tema_editor(nome))
        ed.theme = nome
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
            self.agendar_estudo()

    # ------------------------------------------------------------------ modo estudo
    @staticmethod
    def estudo_vazio() -> Text:
        return Text.assemble(("◆ MODO ESTUDO", f"bold {C['mint']}"), ("  F7 liga e desliga\n\n", C["dim"]),
                             ("Com ele ligado, este painel explica o conceito da linha onde está o cursor, com um "
                              "exemplo e um exercício, e acompanha a trilha de orientação a objetos do seu arquivo. "
                              "Comentários também valem: escreva ", C["text"]),
                             ("# classe Pessoa com nome e idade", C["green"]),
                             (" e veja o exemplo com esses nomes. O código é você quem escreve.", C["text"]))

    def action_estudo(self) -> None:
        """F7: liga/desliga o modo estudo. Logo depois de um erro explicado, abre o conceito daquele erro."""
        exp = getattr(self, "ultima_explicacao", None)
        if exp is not None and exp.conceito and not getattr(exp, "estudada", False):
            exp.estudada = True
            self._estudo_forcado = exp.conceito
            self.estudo = True
        else:
            self.estudo = not self.estudo
        panel = self.query_one("#panel", TabbedContent)
        if self.estudo:
            panel.display = True
            panel.active = "tab-estudo"
            self.atualizar_estudo()
        elif panel.active == "tab-estudo":
            panel.active = "tab-terminal"
        self.render_pills()

    def agendar_estudo(self) -> None:
        if not self.estudo:
            return
        if self._estudo_timer is not None:
            self._estudo_timer.stop()
        self._estudo_timer = self.set_timer(0.35, self.atualizar_estudo)

    def atualizar_estudo(self) -> None:
        from rich.console import Group
        from rich.syntax import Syntax

        from codar import estudo

        corpo = self.query_one("#estudo-corpo", Static)
        botao = self.query_one("#estudo-acao", Botao)
        ed = self.current_editor()
        if ed is None:
            corpo.update(self.estudo_vazio())
            botao.display = False
            return
        lang = ed.lang_id
        linha = ed.document.get_line(ed.cursor_location[0])
        achados = estudo.conceitos_da_linha(linha, lang)
        if self._estudo_forcado:
            conceito = estudo.POR_ID.get(self._estudo_forcado)
            self._estudo_forcado = None
        else:
            conceito = achados[0] if achados else self._estudo_conceito
        self._estudo_conceito = conceito
        partes: list = []
        estado = estudo.trilha_poo(ed.text, lang, uso_externo=self._usado_fora(ed))
        if estado is not None:
            self._estudo_poo = (ed, estado)
        elif self._estudo_poo and self._estudo_poo[0] is ed:  # no meio da digitação: mantém o último estado
            estado = self._estudo_poo[1]
        if estado is not None and (estado.feitos["classe"] or (conceito and conceito.trilha == "poo")):
            feitos = [k for k in estudo.TRILHA_POO if estado.feitos[k]]
            total = len(estudo.TRILHA_POO)
            barra = "▰" * len(feitos) + "▱" * (total - len(feitos))
            prox = estado.proximo
            partes.append(Text.assemble(("TRILHA POO ", f"bold {C['red']}"), (barra, C["green"]),
                                        (f" {len(feitos)}/{total}", C["text"]),
                                        (f" · próximo: {estudo.POR_ID[prox].titulo.split(' (')[0].lower()}" if prox
                                         else " · completa", C["dim"])))
            partes.append(Text.assemble(("▶ próximo passo: ", f"bold {C['mint']}"), (estado.passo(lang), C["text"])))
        self.sugestao_estudo = estudo.sugestao_main(self.root, Path(ed.path), ed.text, lang) if ed.path else None
        if self.sugestao_estudo is not None:
            s = self.sugestao_estudo
            partes.append(Text.assemble(("▶ sugestão: ", f"bold {C['orange']}"), (s.motivo + " ", C["text"]),
                                        (f"Shift+F7 cria {s.caminho} comentado, para você completar.", C["dim"])))
            botao.update(f"[b {C['mint']}]▸ criar {s.caminho}[/]")
        if conceito is not None:
            if partes:
                partes.append(Text(""))
            partes.append(Text.assemble(("◆ ", f"bold {C['orange']}"), (conceito.titulo.upper(), f"bold {C['mint']}"),
                                        (f"   {estudo.TRILHAS[conceito.trilha]}", C["dim"])))
            partes.append(Text(conceito.texto, style=C["text"]))
            pessoal = estudo.pelo_comentario(linha, lang) if linha.strip().startswith(("#", "//")) else None
            codigo, lang_ex = pessoal or estudo.exemplo(conceito, lang)
            rotulo = "exemplo com os nomes do seu comentário (para estudar e digitar):" if pessoal else \
                f"exemplo{'' if lang_ex == (lang or 'python') else ' em ' + lang_ex}:"
            partes.append(Text(rotulo, style=C["dim"]))
            partes.append(Syntax(codigo, lang_ex, theme="ansi_dark", background_color=C["bg"], word_wrap=True))
            partes.append(Text.assemble(("✎ pratique: ", f"bold {C['red']}"), (conceito.pratique, C["text"])))
            if len(achados) > 1:
                partes.append(Text("também nesta linha: " + " · ".join(c.titulo for c in achados[1:4]), style=C["dim"]))
        botao.display = self.sugestao_estudo is not None
        corpo.update(Group(*partes) if partes else self.estudo_vazio())

    def _usado_fora(self, ed: CodeEditor) -> bool:
        """A classe do arquivo já é usada (objeto criado) em outro arquivo do projeto, como um main.py?"""
        if not ed.path or ed.lang_id != "python":
            return False
        classes = re.findall(r"^class\s+(\w+)", ed.text, re.M)
        if not classes:
            return False
        for rel in _listar_arquivos(self.root, limite=200):
            caminho = self.root / rel
            if rel.endswith(".py") and caminho != Path(ed.path):
                try:
                    texto = caminho.read_text(encoding="utf-8", errors="ignore")
                except OSError:
                    continue
                if any(re.search(rf"\b{c}\(", texto) for c in classes):
                    return True
        return False

    async def action_estudo_aplicar(self) -> None:
        """Shift+F7: cria o arquivo que o modo estudo sugeriu (main.py comentado) e abre para você completar."""
        s = self.sugestao_estudo
        if s is None:
            self.notify("nenhuma sugestão agora: com o modo estudo (F7) ligado, abra um arquivo com uma classe",
                        severity="warning")
            return
        destino = (self.root / s.caminho).resolve()
        if not destino.exists():
            destino.write_text(s.conteudo, encoding="utf-8")
            self.feed(f"ESTUDO · {s.caminho} criado", "mint")
            self.notify(f"{s.caminho} criado: leia os comentários, troque os valores e rode com F5", title="estudo")
        await self.query_one("#explorer", Explorer).reload()
        await self.open_file(destino)

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

    def request(self, intent: str, mode: str, ed: CodeEditor | None = None, row: int | None = None,
                original: str | None = None, indent: str | None = None) -> None:
        intent = intent.strip("\n") if mode == "block" else intent.strip()
        if not intent.strip():
            return
        if mode != "block":
            if intent in self.intents:
                self.intents.remove(intent)
            self.intents.insert(0, intent)  # o autocompletar da barra sugere primeiro o que você já usou
        before, recuo, unit = self._editor_context(ed, row)
        indent = recuo if indent is None else indent
        if original is None:
            original = ed.document.get_line(row) if ed is not None and row is not None else None
        target = EditTarget.capture(ed.text, mode, ed.cursor_location, (ed.selection.start, ed.selection.end),
                                    row, original) if ed is not None else None
        if target is not None:
            before = target.before
            if mode == "edit":
                line = ed.document.get_line(target.start[0])
                indent = line[:len(line) - len(line.lstrip())]
                self.feed(f"EDIT · substituindo {target.selected.count(chr(10)) + 1} linha(s)", "orange")
        self.feed(f"TX · {intent[:70]}", "text")
        out = self.query_one("#output", RichLog)
        out.write(f"[{C['red']}]▸ INTENÇÃO[/] [{C['text']}]{_esc(intent)}[/]")
        self.streaming = False
        self.translate_worker(intent, self.current_lang(), mode, ed.path if ed else None, before, indent, unit,
                              target, ed.id if ed else None)

    def max_linhas_bloco(self) -> int:
        from codar import config

        return int(config.load()["router"].get("max_block_lines", 30))

    @work(thread=True, group="translate")
    def translate_worker(self, intent, lang, mode, path, before, indent, unit, target, editor_id) -> None:
        from codar.client import RpcError

        def on_delta(d: str) -> None:
            self.call_from_thread(self._delta, d)

        try:
            res = self.backend.translate(intent, lang, file=path, before=before,
                                         after=target.after if target else "",
                                         selected=target.selected if target and mode == "edit" else "", mode=mode,
                                         indent=indent if mode in ("line", "block", "edit") else "",
                                         indent_unit=unit, stages=tuple(sorted(self.stages)), hints=self.hints,
                                         on_delta=on_delta)
        except RpcError as exc:
            self.call_from_thread(self._failed, intent, exc.message, (exc.data or {}).get("candidates") or [])
            return
        except Exception as exc:
            self.call_from_thread(self._failed, intent, f"{type(exc).__name__}: {exc}", [])
            return
        self.call_from_thread(self._apply, res, target, editor_id, indent)

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
        out.write(f"[b {C['error']}]✖ {_esc(message)}[/]")
        for c in cands[:3]:
            out.write(f"[{C['dim']}]  candidato {c['id']} ({c['score']:.2f}) {c['title']}[/]")
        self.notify(message[:120], severity="error", title="não resolvido")

    def _apply(self, res: dict, target: EditTarget | None, editor_id: str | None, indent: str) -> None:
        self.last = res
        self.render_last()
        self.query_one("#radar", OrbitRadar).ping(res["stage"])
        self.feed(f"RX · {STAGE_NAMES.get(res['stage'], res['stage'])} · {res['source'][:30]} · "
                  f"{res['timings'].get('total_ms', 0):.1f}MS", "green")
        hist = self.query_one("#history", ListView)
        hist.insert(0, [ListItem(Static(f"[{STAGE_COLORS.get(res['stage'], C['orange'])}]●[/] "
                                        f"[{C['text']}]{_esc(res['source'][:30])}[/]"))])
        self.query_one("#output", RichLog).write(Text(res["code"], style=C["moon"]))
        if not res.get("complete", True):
            self.notify("resposta incompleta: seu código foi preservado. Selecione um trecho menor ou aumente "
                        "model.max_tokens", severity="warning", timeout=8)
            return
        body = (res.get("annotated_body") if self.hints else None) or res["body"]
        matches = list(self.query(f"#{editor_id}")) if editor_id else []
        if editor_id and not matches:
            self.notify("a aba foi fechada; resultado disponível em SAÍDA", severity="warning")
            return
        ed = matches[0] if matches else None
        if ed is None:
            self.call_later(self._new_buffer_with, res)
            return
        if target is None or ed.text != target.text:
            self.notify("o texto mudou enquanto a IA respondia; resultado mostrado em SAÍDA", severity="warning")
            return
        text, start_row, end_row = target.apply(body, res.get("imports", []), res["lang"], indent)
        if target.mode == "edit" and self.preview_edits:
            self.review_worker(res, target, editor_id, text, start_row, end_row)
            return
        self._commit_edit(res, target, ed, text, start_row, end_row)

    @work(thread=True, group="review")
    def review_worker(self, res, target, editor_id, text, start_row, end_row):
        from codar.editing import validate_change
        from codar import config

        matches = list(self.call_from_thread(lambda: list(self.query(f"#{editor_id}"))))
        ed = matches[0] if matches else None
        name = Path(ed.path).name if ed and ed.path else "buffer" + (langs.LANGS[res["lang"]].exts or (".txt",))[0]
        if ed and ed.path and Path(ed.path).resolve().is_relative_to(self.root):
            name = Path(ed.path).resolve().relative_to(self.root).as_posix()
        native = bool(config.load().get("editing", {}).get("native_validation", True))
        check = validate_change(target.text, text, name, native=native)
        from codar.workspace import Change

        def reviewed(selected):
            if selected is None:
                return
            from codar.workspace import select_hunks

            chosen = select_hunks(Change(name, target.text, text), set(selected)).after
            self.accept_review_worker(res, target, editor_id, chosen, start_row, end_row, name, native)
        self.call_from_thread(self.push_screen, ReviewScreen([Change(name, target.text, text)], [check]), reviewed)

    @work(thread=True, group="review")
    def accept_review_worker(self, res, target, editor_id, text, start_row, end_row, name, native):
        from codar.editing import validate_change

        check = validate_change(target.text, text, name, native=native)
        if check["status"] == "error":
            self.call_from_thread(self.notify, "alteração preservada na prévia: " + check["message"], severity="error", timeout=8)
            return
        def apply():
            matches = list(self.query(f"#{editor_id}"))
            if not matches or matches[0].text != target.text:
                self.notify("o arquivo mudou durante a revisão; código preservado", severity="warning")
                return
            self._commit_edit(res, target, matches[0], text, start_row, end_row)
        self.call_from_thread(apply)

    def _commit_edit(self, res, target, ed, text, start_row, end_row):
        from codar.editing import validate_change
        from codar.workspace import Change, EditStore

        name = Path(ed.path).name if ed.path else "buffer.py"
        if target.mode == "edit":
            checked = validate_change(target.text, text, name, native=False, lang=res["lang"])
            if checked["status"] == "error":
                self.notify("seu código foi preservado: " + checked["message"], severity="error", timeout=8)
                return
        journal = None
        if ed.path and text != target.text:
            try:
                name = Path(ed.path).resolve().relative_to(self.root).as_posix()
                store = EditStore(self.root)
                journal = store.create([Change(name, target.text, text)], "edição no Studio", status="prepared")
            except (OSError, ValueError) as exc:
                self.notify(f"não foi possível guardar o original: {exc}", severity="error")
                return
        ed.replace(text, (0, 0), ed.document.end)  # corpo e imports na mesma operação de desfazer
        if journal:
            try:
                store.commit_buffer(journal["id"])
            except (OSError, ValueError) as exc:
                self.notify(f"original guardado; confirmação do histórico falhou: {exc}", severity="warning")
        end_row = min(end_row, ed.document.line_count - 1)
        ed.move_cursor((end_row, len(ed.document.get_line(end_row))))
        ed.destacar(start_row, end_row)
        ed.focus()
        self._show_findings(res.get("findings", []), start_row)
        if res.get("imports"):
            self.verificar_pacotes(ed)
        for note in res.get("notes", []):
            self.notify(note, title="codar")

    def action_edit_history(self):
        from codar.workspace import EditStore
        from datetime import datetime

        ed = self.current_editor()
        if not ed or not ed.path:
            self.notify("abra um arquivo salvo para consultar suas versões")
            return
        try:
            name = Path(ed.path).resolve().relative_to(self.root).as_posix()
            store = EditStore(self.root)
            entries = store.list(file=name)
        except (OSError, ValueError) as exc:
            self.notify(str(exc), severity="error")
            return
        if not entries:
            self.notify("esse arquivo ainda não tem edições no histórico")
            return
        target = EditTarget.capture(ed.text, "edit", ed.cursor_location, ((0, 0), (0, 0)))
        editor_id = ed.id
        def restore(identity):
            if identity is None:
                return
            record = store.get(identity)
            change = next(c for c in record["changes"] if c["path"] == name)
            text = change["before"] or ""
            res = {"code": text, "body": text, "imports": [], "lang": (langs.from_path(ed.path) or langs.LANGS["python"]).id,
                   "stage": "history", "source": "histórico", "findings": [], "timings": {}, "notes": []}
            self._apply(res, target, editor_id, "")
        self.push_screen(ChoiceScreen("HISTÓRICO · revisar restauração do original desta edição",
                         [(r["id"], f"{datetime.fromtimestamp(r['created']):%d/%m %H:%M} · {r['status']} · {r['intent'][:70]}")
                          for r in entries]), restore)

    async def _new_buffer_with(self, res: dict) -> None:
        lang = langs.LANGS.get(res["lang"])
        ext = lang.exts[0] if lang and lang.exts else ".txt"
        ed = await self._add_editor(res["code"] + "\n", None, f"sem título{ext}")
        ed.saved_text = ""
        self._update_tab_label(ed)
        self._show_findings(res.get("findings", []), 0, absolute=True)

    def action_project_edit(self):
        def files_entered(value):
            if not value:
                return
            names = [name.strip() for name in value.split(",") if name.strip()]
            if not 1 <= len(names) <= 8:
                self.notify("escolha de 1 a 8 arquivos", severity="warning")
                return
            def intent_entered(intent):
                if intent:
                    self.project_edit_worker(names, intent)
            self.push_screen(PromptScreen("O que mudar nesses arquivos?"), intent_entered)
        ed = self.current_editor()
        initial = Path(ed.path).resolve().relative_to(self.root).as_posix() \
            if ed and ed.path and Path(ed.path).resolve().is_relative_to(self.root) else ""
        self.push_screen(PromptScreen("Arquivos relativos ao projeto, separados por vírgula", value=initial), files_entered)

    @work(thread=True, group="project-edit", exclusive=True)
    def project_edit_worker(self, names, intent):
        from codar.workspace import Change

        if self.call_from_thread(self._dirty_project_files, names):
            self.call_from_thread(self.notify, "salve os arquivos escolhidos antes de editar o projeto", severity="warning")
            return
        try:
            proposal = self.backend.call("project.edit", {"root": str(self.root), "files": names, "intent": intent})
        except Exception as exc:
            self.call_from_thread(self.notify, str(exc), severity="error", timeout=8)
            return
        def reviewed(selected):
            if selected:
                self.project_apply_worker(proposal["id"], names, selected)
        self.call_from_thread(self.push_screen, ReviewScreen([Change(**c) for c in proposal["changes"]],
                              proposal["validation"]), reviewed)

    def _dirty_project_files(self, names):
        return any(ed.path and Path(ed.path).resolve().is_relative_to(self.root)
                   and Path(ed.path).resolve().relative_to(self.root).as_posix() in names and ed.dirty
                   for ed in self.query(CodeEditor))

    @work(thread=True, group="project-edit")
    def project_apply_worker(self, identity, names, selected):
        if self.call_from_thread(self._dirty_project_files, names):
            self.call_from_thread(self.notify, "o editor tem alterações novas; arquivos preservados", severity="warning")
            return
        try:
            result = self.backend.call("edits.apply", {"root": str(self.root), "id": identity, "hunks": selected})
        except Exception as exc:
            self.call_from_thread(self.notify, str(exc), severity="error", timeout=8)
            return
        def refresh():
            for change in result.get("applied_changes", []):
                file = self.root / change["path"]
                for ed in self.query(CodeEditor):
                    if ed.path and Path(ed.path).resolve() == file.resolve():
                        if ed.dirty or ed.text != change["before"]:
                            self.notify(f"{change['path']}: disco atualizado; alterações do editor preservadas", severity="warning")
                            continue
                        text = change["after"] or ""
                        ed.replace(text, (0, 0), ed.document.end)
                        ed.saved_text = text
                        self._update_tab_label(ed)
            self.feed("PROJETO · alterações aplicadas e originais guardados", "green")
            self.notify("edição de projeto aplicada; codar edits permite recuperar os originais")
        self.call_from_thread(refresh)

    def action_check_project(self):
        def chosen(action):
            if action:
                self.check_project_worker([] if action == "syntax" else [action])
        self.push_screen(ChoiceScreen("VERIFICAR PROJETO · arquivos salvos",
                         [("syntax", "Verificar sintaxe"), ("analyze", "Executar analisador"), ("test", "Executar testes")]), chosen)

    @work(thread=True, group="project-check", exclusive=True)
    def check_project_worker(self, actions):
        try:
            result = self.backend.call("project.check", {"root": str(self.root), "actions": actions})
        except Exception as exc:
            self.call_from_thread(self.notify, str(exc), severity="error")
            return
        def show():
            out = self.query_one("#output", RichLog)
            self.query_one("#panel", TabbedContent).active = "tab-output"
            for item in result["files"]:
                out.write(Text(f"{item['path']}: {item['status']} {item.get('message', '')}"))
            for item in result["commands"]:
                out.write(Text(" ".join(item["command"]) + "\n" + item["message"]))
            self.notify(f"verificação {'sem erros detectados' if result['ok'] else 'falhou'}; "
                        f"{result['skipped']} não verificadas", severity="information" if result["ok"] else "warning")
        self.call_from_thread(show)

    def action_plugins(self):
        from codar.plugin_loader import discover
        from codar import config

        plugins = discover({}).plugins
        disabled = set(config.load()["plugins"].get("disabled", []))
        choices = [("__install__", "Instalar plugin de pasta local ou Git HTTPS…")]
        choices += [(p.name, f"{p.name} {p.version} · {'desativado' if p.name in disabled else 'erro' if p.errors else 'ativo'}")
                    for p in plugins]
        def selected(name):
            if name == "__install__":
                self.push_screen(PromptScreen("Pasta do plugin ou URL Git HTTPS"),
                                 lambda source: self._plugin_command("install", source) if source else None)
            elif name:
                plugin = next(p for p in plugins if p.name == name)
                options = [("enable" if name in disabled else "disable", "Ativar" if name in disabled else "Desativar"),
                           ("info", "Ver detalhes e erros")]
                if not plugin.builtin:
                    options += [("update", "Atualizar da origem registrada"), ("restore", "Recuperar versão anterior"),
                                ("remove", "Remover e guardar cópia")]
                self.push_screen(ChoiceScreen(name, options), lambda action: self._plugin_command(action, name) if action else None)
        self.push_screen(ChoiceScreen("PLUGINS", choices), selected)

    def _plugin_command(self, action, value):
        self.plugin_command_worker([sys.executable, "-m", "codar", "plugins", action, value])

    @work(thread=True, group="plugins", exclusive=True)
    def plugin_command_worker(self, command):
        from codar.validation import run_command

        result = run_command(command, self.root, 180)
        def show():
            self.query_one("#output", RichLog).write(Text(result["message"]))
            self.query_one("#panel", TabbedContent).active = "tab-output"
            self.notify("operação de plugins concluída" if result["status"] == "ok" else result["message"][-300:],
                        severity="information" if result["status"] == "ok" else "error")
        self.call_from_thread(show)

    def _show_findings(self, findings: list[dict], offset: int, absolute: bool = False, focar: bool = True) -> None:
        table = self.query_one("#problems", DataTable)
        table.clear()
        self._achado_arquivo: dict[str, str] = {}  # erro de outro arquivo: Enter abre o arquivo certo
        sev_color = {"critical": C["error"], "error": C["error"], "warning": C["orange"], "info": C["cyan"]}
        for f in findings:
            line = f["line"] if absolute else offset + max(1, f.get("body_line", f["line"]))
            table.add_row(Text(f["severity"].upper(), style=f"bold {sev_color.get(f['severity'], C['text'])}"),
                          Text(f["id"], style=C["red"]), Text(str(line), style=C["dim"]),
                          Text(f["message"] + (f"  → {f['suggestion']}" if f.get("suggestion") else ""), style=C["text"]),
                          key=f"{f['id']}:{line}:{len(table.rows)}")
            if f.get("file"):
                self._achado_arquivo[f"{f['id']}:{line}:{len(table.rows) - 1}"] = f["file"]
        self.query_one("#panel", TabbedContent).border_subtitle = f"{len(findings)} achado(s)" if findings else "limpo"
        if findings and focar:
            self.query_one("#panel", TabbedContent).active = "tab-problems"

    @on(DataTable.RowSelected, "#problems")
    async def _jump(self, event: DataTable.RowSelected) -> None:
        chave = str(event.row_key.value)
        arquivo = getattr(self, "_achado_arquivo", {}).get(chave)
        if arquivo and Path(arquivo).is_file():
            await self.open_file(Path(arquivo).resolve())
        ed = self.current_editor()
        if ed is None:
            return
        try:
            line = int(chave.split(":")[1])
        except (IndexError, ValueError):
            return
        ed.move_cursor((max(0, line - 1), 0), center=True)
        ed.focus()

    @on(Input.Submitted, "#intent")
    async def _intent(self, event: Input.Submitted) -> None:
        text = event.value
        event.input.value = ""
        pedido = comandos.interpretar(text)
        if pedido is not None:  # "crie o arquivo main.py", "crie a pasta src", "abra conta.py"
            await self.executar_pedido(pedido)
            return
        ed = self.current_editor()
        edit = ed is not None and (ed.selection.start != ed.selection.end or (ed.text.strip() and wants_edit(text)))
        self.request(text, "edit" if edit else "insert", ed, None)

    async def executar_pedido(self, pedido: comandos.PedidoArquivo) -> None:
        explorer = self.query_one("#explorer", Explorer)
        if pedido.acao == "abrir":
            alvo = self._achar_arquivo(pedido.caminhos[0])
            if alvo is None:
                self.notify(f"não achei {pedido.caminhos[0]} no projeto (Ctrl+O busca pelo nome)", severity="warning")
                return
            await self.open_file(alvo)
            return
        for caminho in pedido.caminhos:
            await explorer.criar(self.root, caminho, diretorio=pedido.acao == "criar_pasta")
            self.feed(f"{'PASTA' if pedido.acao == 'criar_pasta' else 'ARQUIVO'} · {caminho}", "green")

    def _achar_arquivo(self, nome: str) -> Path | None:
        direto = (self.root / nome).resolve()
        if direto.is_file():
            return direto
        arquivos = _listar_arquivos(self.root)
        for criterio in (lambda r: Path(r).name == nome, lambda r: r.endswith(nome), lambda r: nome in Path(r).name):
            achado = next((r for r in arquivos if criterio(r)), None)
            if achado:
                return self.root / achado
        return None

    @on(CodeEditor.TranslateLine)
    def _space_enter(self, event: CodeEditor.TranslateLine) -> None:
        line = event.editor.document.get_line(event.row)
        self.request(line.strip(), "line", event.editor, event.row,
                     indent=self._recuo_senao(event.editor, event.row, line))

    def action_translate_line(self) -> None:
        ed = self.current_editor()
        if ed is None:
            self.notify("abra um arquivo (ou use a barra de intenção)", severity="warning")
            return
        if ed.selection.start != ed.selection.end and ed.selection.start[0] != ed.selection.end[0]:
            self.traduzir_bloco(ed)
            return
        row = ed.cursor_location[0]
        line = ed.document.get_line(row)
        if not line.strip():
            return
        self.request(line.strip(), "line", ed, row, indent=self._recuo_senao(ed, row, line))

    def traduzir_bloco(self, ed: CodeEditor) -> None:
        """Várias linhas selecionadas viram um bloco só (se/senão, laços aninhados). O limite de linhas mantém o
        tempo e a RAM previsíveis: cada linha que o compilador não resolve pode ir para a IA."""
        import textwrap

        r0, r1 = ed.linhas_selecionadas()
        linhas = [ed.document.get_line(r) for r in range(r0, r1 + 1)]
        cheias = [t for t in linhas if t.strip()]
        maximo = self.max_linhas_bloco()
        if not cheias:
            return
        if len(cheias) > maximo:
            self.notify(f"{len(cheias)} linhas selecionadas; o máximo por bloco é {maximo}. Traduza em partes "
                        f"(ou ajuste router.max_block_lines no config.toml).", severity="warning", title="bloco grande")
            return
        original = "\n".join(linhas)
        margem = min(len(t) - len(t.lstrip()) for t in cheias)
        recuo = cheias[0][:margem]
        self.request(textwrap.dedent(original), "block", ed, r0, original=original, indent=recuo)

    @staticmethod
    def _recuo_senao(ed: CodeEditor, row: int, linha: str) -> str | None:
        """"senão imprimir …" digitado com a indentação do corpo do if: traduz já alinhado com o if (Python)."""
        if ed.lang_id != "python" or not _SENAO.match(linha):
            return None
        return ed.recuo_alinhado(row, "else")

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
            row("Ctrl+N", "novo arquivo", "Ctrl+E", "explorer (n, p, r…)"),
            row("Ctrl+O", "abrir pelo nome", "Ctrl+L", "descrever o código"),
            row("F8", "consultor do projeto", "F1", "todos os atalhos"), "",
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

    def action_focus_explorer(self) -> None:
        self.query_one("#left").display = True
        explorer = self.query_one("#explorer", Explorer)
        explorer.focus()
        if explorer.cursor_line < 0:
            explorer.cursor_line = 0

    async def action_focus_terminal(self) -> None:
        """Ctrl+T: vai para o terminal; já estando nele, abre outro terminal (o primeiro continua rodando)."""
        panel = self.query_one("#panel", TabbedContent)
        if isinstance(self.focused, TerminalInput) and panel.display:
            await self.terminal.nova_sessao()
            return
        panel.display = True
        panel.active = "tab-terminal"
        self.query_one("#term-input", Input).focus()

    def action_focus_editor(self) -> None:
        """Esc: de qualquer painel, volta para o editor (ou para a intenção, se não há arquivo aberto)."""
        ed = self.current_editor()
        (ed if ed is not None else self.query_one("#intent", Input)).focus()

    def action_quick_open(self) -> None:
        from textual.command import CommandPalette

        self.push_screen(CommandPalette(providers=[ArquivosProvider], placeholder="abrir arquivo: digite parte do nome…"))

    def _trocar_aba(self, passo: int) -> None:
        if isinstance(self.focused, TerminalInput):  # no terminal, troca de terminal
            self.terminal.trocar(passo)
            return
        tabs = self.query_one("#editors", TabbedContent)
        ids = [p.id for p in tabs.query(TabPane) if p.id]
        if not ids:
            return
        i = ids.index(tabs.active) if tabs.active in ids else 0
        tabs.active = ids[(i + passo) % len(ids)]
        ed = self.current_editor()
        if ed is not None:
            ed.focus()

    def action_next_tab(self) -> None:
        self._trocar_aba(1)

    def action_prev_tab(self) -> None:
        self._trocar_aba(-1)

    async def action_explorer(self, acao: str) -> None:
        """Botões da barra do explorer."""
        explorer = self.query_one("#explorer", Explorer)
        if acao == "recarregar":
            await explorer.reload()
            return
        explorer.focus()
        await explorer.run_action(acao)

    def arquivo_movido(self, antigo: Path, novo: Path) -> None:
        """Renomeado ou movido no explorer: as abas abertas passam a apontar para o caminho novo."""
        for ed in self.query(CodeEditor):
            if not ed.path:
                continue
            atual = Path(ed.path)
            if atual == antigo or antigo in atual.parents:
                ed.path = str(novo / atual.relative_to(antigo)) if atual != antigo else str(novo)
                self._update_tab_label(ed)
        self.render_pills()

    def arquivo_apagado(self, caminho: Path) -> None:
        """Apagado no explorer: a aba fica aberta, mas Ctrl+S passa a pedir um nome (não recria o arquivo sozinho)."""
        for ed in self.query(CodeEditor):
            if ed.path and (Path(ed.path) == caminho or caminho in Path(ed.path).parents):
                ed.path = None
                ed.saved_text = ""
                self._update_tab_label(ed)

    def action_toggle_stage(self, stage: int) -> None:
        self.stages ^= {stage}
        if not self.stages:
            self.stages = {stage}
        self.render_pills()

    def action_toggle_audit(self) -> None:
        self.audit_on = not self.audit_on
        self.render_pills()

    @on(TabbedContent.TabActivated, "#panel")
    def _aba_do_painel(self, event: TabbedContent.TabActivated) -> None:
        self.query_one("#panel").set_class(event.pane.id == "tab-estudo", "alto")  # o estudo ganha mais linhas

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
        if self.rede_srv is not None and hasattr(self.rede_srv, "avisar_mudanca"):
            self.rede_srv.avisar_mudanca()  # a página aberta no celular recarrega
        self.verificar_pacotes(ed)
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
        from codar.project import Project
        from codar.validation import default_command

        try:
            project = Project.load(self.root)
            if "run" in project.commands:
                relative = Path(ed.path).resolve().relative_to(self.root).as_posix()
                command = default_command(project, "run", relative)
                self.run_command(subprocess.list2cmdline(command) if os.name == "nt" else shlex.join(command), cwd=self.root)
                return
        except (OSError, ValueError) as exc:
            self.notify(str(exc), severity="error")
            return
        if Path(ed.path).suffix.lower() in (".html", ".htm"):  # "rodar" uma página é abrir a prévia
            self.action_celular()
            return
        lang = langs.from_path(ed.path)
        runner = self._executor(lang, Path(ed.path))
        if not lang or not runner:
            self.notify(f"sem executor configurado para {lang.name if lang else 'este arquivo'}", severity="warning")
            return
        python = pacotes.python_do_projeto(self.root)
        cmd = [part.replace("{file}", ed.path).replace("{python}", python) for part in runner]
        from codar import toolchains

        cmd[0] = shutil.which(cmd[0], path=toolchains.environment(self.terminal.ambiente).get("PATH")) or cmd[0]
        if not shutil.which(cmd[0], path=toolchains.environment(self.terminal.ambiente).get("PATH")):
            tool = "flutter" if runner[0] == "flutter" else lang.id
            self.notify(f"{runner[0]} não encontrado. Rode `codar toolchains install {tool}` no terminal (Ctrl+T)",
                        severity="warning", timeout=8)
            return
        try:  # na tela, o comando curto: "python perguntas.py" em vez dos caminhos completos
            nome = str(Path(ed.path).relative_to(self.root))
        except ValueError:
            nome = Path(ed.path).name
        visivel = [nome if p == "{file}" else "python" if p == "{python}" else p for p in runner]
        juntar = (lambda partes: " ".join(shlex.quote(c) for c in partes)) if os.name != "nt" else subprocess.list2cmdline
        cwd = self.root
        if lang.id == "dart":
            from codar.dart import runner as dart_runner

            _, cwd = dart_runner(Path(ed.path), self.root)
        self.run_command(juntar(cmd), visivel=juntar(visivel), cwd=cwd)

    def _executor(self, lang, arquivo: Path) -> tuple[str, ...] | None:
        """Como rodar o arquivo: TypeScript e JSX com o bun quando ele existe (o Node não entende JSX e só roda .ts
        a partir da 22.18); o resto, pelo executor da linguagem."""
        if lang is None:
            return None
        if lang.id == "dart":
            from codar.dart import runner as dart_runner

            return dart_runner(arquivo, self.root)[0]
        caminho = self.terminal.ambiente.get("PATH")
        if arquivo.suffix in (".ts", ".tsx", ".jsx", ".mts") and shutil.which("bun", path=caminho):
            return ("bun", "{file}")
        if arquivo.suffix in (".ts", ".mts") and not pacotes.node_roda_ts(caminho) and shutil.which("npx", path=caminho):
            return ("npx", "--yes", "tsx", "{file}")
        return lang.runner

    @property
    def terminal(self) -> TerminalPainel:
        return self._terminal

    def run_command(self, cmd: str, visivel: str | None = None, cwd: Path | None = None) -> None:
        self.query_one("#panel", TabbedContent).active = "tab-terminal"
        self.terminal.executar(cmd, visivel, cwd=cwd)

    def process_running(self) -> bool:
        return self.terminal.sessao.rodando()

    def action_stop_process(self) -> None:
        self.terminal.parar()

    def action_terminal(self, numero: int) -> None:
        self.query_one("#panel", TabbedContent).active = "tab-terminal"
        self.terminal.ativar_numero(numero)

    async def action_novo_terminal(self) -> None:
        self.query_one("#panel", TabbedContent).active = "tab-terminal"
        await self.terminal.nova_sessao()

    def action_shell(self) -> None:
        """F12: o seu terminal de verdade (aliases, histórico, menus com setas, vim) no lugar do Studio; exit volta."""
        shell = os.environ.get("SHELL") or ("cmd.exe" if os.name == "nt" else "/bin/sh")
        pasta = self.terminal.sessao.cwd
        try:
            with self.suspend():
                print(f"\n  Seu terminal ({Path(shell).name}) em {pasta}\n  Digite exit para voltar ao CODAR Studio.\n",
                      flush=True)
                subprocess.run([shell], cwd=pasta, env={**os.environ, "CODAR_STUDIO": "1"})
        except Exception as exc:  # suspender não existe em todo terminal (ex.: navegador)
            self.notify(f"não deu para abrir o shell aqui: {exc}", severity="error")
            return
        self.query_one("#explorer", Explorer).reload()

    def terminal_mudou(self) -> None:
        self.render_status()

    def programa_terminou(self, sessao, codigo: int) -> None:
        """Programa terminou: com erro, explica em português (o quê, onde, como corrigir) e marca a linha."""
        self.feed(f"RUN · exit {codigo}", "green" if codigo == 0 else "red")
        if getattr(self, "instalando", None) and sessao.comando == self.instalando["comando"]:
            self.instalando = None
            self.verificar_pacotes(self.current_editor())
        if codigo in (0, 130) or codigo < 0:  # 130 / sinal: interrompido com Ctrl+C
            return
        from codar.explicar import explicar

        exp = explicar(sessao.saida, sessao.cwd)
        if exp is not None:
            self.mostrar_explicacao(sessao, exp)

    def mostrar_explicacao(self, sessao, exp) -> None:
        import textwrap

        log = sessao.log
        largura = max(40, log.size.width - 22)
        onde = f" · linha {exp.linha} de {Path(exp.arquivo).name}" if exp.arquivo and exp.linha else ""
        log.write(Text(f"┌─ ERRO EXPLICADO · {exp.tipo}{onde}", style=f"bold {C['error']}"))
        log.write(Text(f"│ {exp.titulo}", style=f"bold {C['text']}"))
        if exp.trecho:
            log.write(Text(f"│     {exp.trecho.strip()}", style=C["moon"]))
        for rotulo, texto, cor in (("o que aconteceu", exp.oque, C["text"]), ("como corrigir", exp.como, C["mint"])):
            for i, parte in enumerate(textwrap.wrap(texto, largura) or [""]):
                prefixo = f"│ {rotulo + ':':<16} " if i == 0 else "│ " + " " * 17
                log.write(Text.assemble((prefixo, C["dim"]), (parte, cor)))
        log.write(Text("└─ " + ("Enter em PROBLEMAS vai até a linha" if exp.linha else "") +
                       (f" · F7 estuda: {exp.conceito}" if exp.conceito else ""), style=C["dim"]))
        if exp.arquivo and exp.linha:
            self._show_findings([{"severity": "error", "id": exp.tipo, "line": exp.linha, "message": exp.titulo,
                                  "suggestion": exp.como, "file": exp.arquivo}], 0, absolute=True, focar=False)
        self.ultima_explicacao = exp
        self.notify(exp.como, title=f"{exp.tipo}: {exp.titulo}", severity="error", timeout=8)

    def servidor_detectado(self, sessao, url: str) -> None:
        self.feed(f"SERVIDOR · {url}", "cyan")
        self.notify(f"servidor no ar: {url} · F4 abre no celular", title=f"terminal {sessao.numero}")

    # ------------------------------------------------------------------ ver no celular
    def action_celular(self) -> None:
        """F4: ver no celular. Com um servidor rodando no terminal, repassa ele para a rede (ele continua escutando
        só neste computador); senão, mostra a pasta do arquivo aberto (páginas, imagens, gráficos) com recarga ao
        salvar. O endereço tem um código aleatório: só quem recebe o link vê."""
        from codar import rede

        sessao = next((s for s in [self.terminal.sessao, *self.terminal.sessoes] if s.url and s.rodando()), None)
        try:
            if sessao is not None:
                partes = urllib.parse.urlsplit(sessao.url)
                if partes.hostname not in ("localhost", "127.0.0.1", "0.0.0.0", "::1"):  # já está na rede
                    self.push_screen(CelularScreen(f"servidor do terminal {sessao.numero}", sessao.url, sessao.url))
                    return
                if not (isinstance(self.rede_srv, rede.ProxyRede) and self.rede_srv.porta_destino == partes.port):
                    self._parar_rede()
                    self.rede_srv = rede.ProxyRede(partes.port or 80).iniciar()
                caminho = partes.path if partes.path not in ("", "/") else ""
                titulo, url_rede, url_local = (f"repassando o servidor do terminal {sessao.numero}",
                                               self.rede_srv.url_rede.rstrip("/") + (caminho or "/"), sessao.url)
            else:
                ed = self.current_editor()
                pasta = (Path(ed.path).parent if ed is not None and ed.path else self.root).resolve()
                if not (isinstance(self.rede_srv, rede.ServidorPrevia) and self.rede_srv.raiz == pasta):
                    self._parar_rede()
                    self.rede_srv = rede.ServidorPrevia(pasta).iniciar()
                arquivo = Path(ed.path).name if ed is not None and ed.path and Path(ed.path).suffix.lower() in (
                    ".html", ".htm", ".png", ".jpg", ".jpeg", ".svg", ".gif", ".webp") else ""
                try:
                    onde = pasta.relative_to(self.root).as_posix()
                except ValueError:
                    onde = str(pasta)
                titulo = f"prévia de {onde if onde != '.' else self.root.name}/{arquivo}"
                url_rede, url_local = self.rede_srv.url_rede + arquivo, self.rede_srv.url_local + arquivo
        except OSError as exc:
            self.notify(f"não consegui abrir a porta: {exc.strerror or exc}", severity="error")
            return
        self.feed(f"REDE · {url_rede}", "mint")
        self.render_status()
        self.push_screen(CelularScreen(titulo, url_rede, url_local, rede.aviso_firewall(self.rede_srv.porta)),
                         self._celular_fechado)

    def _celular_fechado(self, acao: str | None) -> None:
        if acao == "parar":
            self._parar_rede()
            self.notify("servidor da rede parado", title="celular")

    def _parar_rede(self) -> None:
        if self.rede_srv is not None:
            self.rede_srv.parar()
            self.rede_srv = None
            self.render_status()

    # ------------------------------------------------------------------ consultor de projeto
    # ------------------------------------------------------------------ dicas de pacotes
    def verificar_pacotes(self, ed: CodeEditor | None) -> None:
        if ed is not None and ed.path and ed.lang_id in ("python", "javascript", "typescript"):
            self.pacotes_worker(ed.path, ed.text, ed.lang_id)

    @work(thread=True, exclusive=True, group="pacotes")
    def pacotes_worker(self, caminho: str, codigo: str, lang: str) -> None:
        try:
            lista = pacotes.dicas(self.root, Path(caminho), codigo, lang, self.terminal.ambiente.get("PATH"))
        except Exception:  # dica é ajuda, nunca motivo de erro
            return
        self.call_from_thread(self._mostrar_pacotes, caminho, lista)

    def _mostrar_pacotes(self, caminho: str, lista: list) -> None:
        if not hasattr(self, "dicas_pacotes"):
            self.dicas_pacotes: dict[str, list] = {}
        antigas = {d.id for d in self.dicas_pacotes.get(caminho, [])}
        self.dicas_pacotes[caminho] = lista
        novas = [d for d in lista if d.id not in antigas]
        for d in novas:
            self.feed(f"PACOTE · {d.titulo} · F8 instala", "orange")
        if novas:
            self.notify(f"{novas[0].titulo}. F8 mostra o comando ({novas[0].comando[:60]}) e Enter instala.",
                        title="dica de pacote", severity="warning", timeout=8)
        if getattr(self, "advice", None) is not None:
            self._show_advice({"suggestions": [s for s in self.advice if s.get("source") != "pacotes"]})
        self.render_status()

    def _dicas_atuais(self) -> list:
        ed = self.current_editor()
        return getattr(self, "dicas_pacotes", {}).get(ed.path, []) if ed is not None and ed.path else []

    def action_advise(self) -> None:
        self.query_one("#panel", TabbedContent).active = "tab-advisor"
        self.feed("ADVISOR · analisando o projeto…", "dim")
        self._show_advice({"suggestions": []}, final=False)
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

    def _show_advice(self, report: dict, final: bool = True) -> None:
        lst = self.query_one("#advice-list", ListView)
        lst.clear()
        # pacotes que faltam no arquivo aberto vêm primeiro: são o que trava o programa agora
        self.advice = [d.como_sugestao() for d in self._dicas_atuais()] + \
            [s for s in report["suggestions"] if s.get("source") != "pacotes"]
        colors = {"high": C["red"], "medium": C["orange"], "low": C["cyan"]}
        for s in self.advice:
            opts = " · ".join(o["label"] for o in s["options"])
            lst.append(ListItem(Static(f"[b {colors.get(s['impact'], C['text'])}]▶ {_esc(s['title'])}[/]\n"
                                       f"[{C['text']}]{_esc(s['reason'][:150])}[/]\n[{C['mint']}]{_esc(opts)}[/]")))
        if not final:
            return
        self.feed(f"ADVISOR · {len(self.advice)} sugestão(ões)", "orange" if self.advice else "green")
        if not self.advice:
            lst.append(ListItem(Static(f"[{C['mint']}]✓ nenhuma sugestão — projeto em ordem[/]")))

    @on(ListView.Selected, "#advice-list")
    def _advice_selected(self, event: ListView.Selected) -> None:
        idx = event.list_view.index
        if idx is None or not getattr(self, "advice", None) or idx >= len(self.advice):
            return
        s = self.advice[idx]
        if s.get("source") == "pacotes":  # instala no terminal, à vista (e confere de novo quando terminar)
            self.instalando = s
            self.run_command(s["comando"], cwd=Path(s["cwd"]) if s.get("cwd") else self.root)
            return
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

        escrever = partial(self.call_from_thread, self.terminal.escrever)
        bundle = discover(config.load())
        try:
            title, opt, steps = find_option(self.root, bundle, sid, oid)
            escrever(Text(f"▶ {title} → {opt['label']}", style=f"bold {C['mint']}"))
            apply_steps(self.root, steps, bundle, lambda s: escrever(Text(s, style=C["text"])))
        except ApplyError as exc:
            escrever(Text(f"✖ {exc}", style=f"bold {C['error']}"))
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
            ("Codar: Editar vários arquivos…", "Ctrl+Shift+G — proposta com prévia", self.action_project_edit),
            ("Codar: Histórico de edições", "Ctrl+Shift+H — recuperar uma versão", self.action_edit_history),
            ("Codar: Verificar projeto", "sintaxe, analisadores e testes", self.action_check_project),
            ("Codar: Gerenciar plugins", "instalação, atualização e recuperação", self.action_plugins),
            ("Codar: Abrir no VS Code", "Ctrl+O — alterna para o editor gráfico", self.action_open_vscode),
            ("Codar: Trocar linguagem…", "força a linguagem alvo", self.action_set_lang),
            ("Codar: Salvar último resultado como padrão…", "ensina o banco de padrões", self.action_save_pattern),
            ("Codar: Alternar dicas inline", "comentários 'Dica [ID]' no código", self.action_toggle_hints),
            ("Codar: Alternar auditoria", "liga/desliga a auditoria ao salvar", self.action_toggle_audit),
            ("Codar: Carregar modelo", "pré-aquece o SLM", lambda: self.model_worker("model.load")),
            ("Codar: Descarregar modelo", "devolve a RAM do SLM ao sistema", lambda: self.model_worker("model.unload")),
            ("Codar: Novo arquivo…", "Ctrl+N", self.action_new_file),
            ("Codar: Parar processo do terminal", "encerra o processo do terminal ativo", self.action_stop_process),
            ("Codar: Novo terminal", "Ctrl+T dentro do terminal — o outro continua rodando", self.action_novo_terminal),
            ("Codar: Abrir o meu shell", "F12 — o seu terminal de verdade; exit volta ao Studio", self.action_shell),
            ("Codar: Ver no celular", "F4 — prévia na rede com QR code (ou repassa o servidor do terminal)",
             self.action_celular),
            ("Codar: Parar o servidor da rede", "para a prévia/repasse aberto com F4", self._parar_rede),
            ("Codar: Mostrar/ocultar explorer", "Ctrl+B", self.action_toggle_left),
            ("Codar: Mostrar/ocultar painel", "F9", self.action_toggle_panel),
        ]

    def on_unmount(self) -> None:
        self._parar_rede()
        self.terminal.parar_tudo()
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
