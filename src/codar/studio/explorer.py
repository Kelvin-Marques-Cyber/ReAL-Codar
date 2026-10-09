"""Explorer do Studio: a árvore do projeto com as operações de arquivo pelo teclado, como no VS Code.

    Enter/→ abre · ← fecha a pasta · n novo arquivo · p nova pasta · r (F2) renomear · d duplicar
    c copiar · x recortar · v colar · y copiar caminho · Del apagar (vai para a lixeira) · Esc volta ao editor

Botão direito abre o mesmo menu. Arrastar arquivos do gerenciador de arquivos para o terminal cola o caminho deles;
com o explorer em foco, isso copia os arquivos para a pasta selecionada.
"""

from __future__ import annotations

import shlex
import shutil
import time
from pathlib import Path
from urllib.parse import unquote, urlparse

from textual import events
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, DirectoryTree, Label, OptionList, Static
from textual.widgets.option_list import Option

from codar.studio.screens import PromptScreen
from codar.studio.widgets import C

SKIP = {".git", "node_modules", "__pycache__", ".venv", "venv", ".mypy_cache", ".pytest_cache", "target", "dist", ".codar"}
LIXEIRA = Path(".codar") / "lixeira"
# Cor do marcador de cada tipo de arquivo (chaves da paleta C)
TIPO_COR = {".py": "mint", ".pyw": "mint", ".ipynb": "mint", ".js": "text", ".mjs": "text", ".cjs": "text",
            ".jsx": "text", ".ts": "blue", ".tsx": "blue", ".html": "red", ".htm": "red", ".css": "cyan",
            ".scss": "cyan", ".json": "orange", ".toml": "orange", ".yaml": "orange", ".yml": "orange",
            ".md": "moon", ".txt": "moon", ".sh": "green", ".ps1": "green", ".go": "cyan", ".rs": "orange",
            ".java": "red", ".c": "blue", ".cpp": "blue", ".h": "blue", ".lua": "blue", ".rb": "red", ".php": "blue",
            ".sql": "cyan", ".png": "orange", ".jpg": "orange", ".jpeg": "orange", ".svg": "orange", ".csv": "green"}
# (ação, tecla, rótulo): menu de contexto, barra do explorer e ajuda
ACOES = [("abrir", "Enter", "Abrir"), ("novo_arquivo", "n", "Novo arquivo"), ("nova_pasta", "p", "Nova pasta"),
         ("renomear", "r", "Renomear"), ("duplicar", "d", "Duplicar"), ("copiar", "c", "Copiar"),
         ("recortar", "x", "Recortar"), ("colar", "v", "Colar aqui"), ("copiar_caminho", "y", "Copiar caminho"),
         ("apagar", "Del", "Apagar")]


def nome_livre(pasta: Path, nome: str, diretorio: bool = False) -> Path:
    """`pasta/nome`, ou `nome_copia.ext`, `nome_copia2.ext`… se já existir."""
    alvo = pasta / nome
    if not alvo.exists():
        return alvo
    base, ext = (nome, "") if diretorio else (Path(nome).stem, Path(nome).suffix)
    n = 1
    while True:
        alvo = pasta / f"{base}_copia{n if n > 1 else ''}{ext}"
        if not alvo.exists():
            return alvo
        n += 1


def caminhos_colados(texto: str) -> list[Path]:
    """Arquivos que o terminal cola ao arrastar do gerenciador de arquivos: '/a b/c.png', /a\\ b/c.png, file:///…"""
    partes: list[str] = []
    for linha in texto.splitlines():
        try:
            partes += shlex.split(linha)
        except ValueError:
            partes += linha.split()
    caminhos = []
    for parte in partes:
        if parte.startswith("file://"):
            parte = unquote(urlparse(parte).path)
        p = Path(parte).expanduser()
        if p.is_absolute() and p.exists():
            caminhos.append(p)
    return caminhos


def copiar(origem: Path, destino: Path) -> None:
    if origem.is_dir():
        shutil.copytree(origem, destino, ignore=shutil.ignore_patterns(*SKIP))
    else:
        shutil.copy2(origem, destino)


class Explorer(DirectoryTree):
    ICON_NODE = "▸ "
    ICON_NODE_EXPANDED = "▾ "
    ICON_FILE = "• "
    BINDINGS = [
        Binding("right", "expandir", "Abrir", show=False),
        Binding("home", "primeiro", "Topo", show=False),
        Binding("end", "ultimo", "Fim", show=False),
        Binding("pageup", "pagina(-1)", "Página acima", show=False),
        Binding("pagedown", "pagina(1)", "Página abaixo", show=False),
        Binding("left", "recolher", "Fechar pasta", show=False),
        Binding("n", "novo_arquivo", "Novo"),
        Binding("p", "nova_pasta", "Pasta"),
        Binding("r,f2", "renomear", "Renomear"),
        Binding("d", "duplicar", "Duplicar", show=False),
        Binding("c", "copiar", "Copiar"),
        Binding("x", "recortar", "Recortar", show=False),
        Binding("v", "colar", "Colar"),
        Binding("y", "copiar_caminho", "Caminho", show=False),
        Binding("delete", "apagar", "Apagar"),
        Binding("shift+f10,m", "menu", "Menu", show=False),
    ]
    area: tuple[str, Path] | None = None  # ("copiar" | "recortar", caminho): vale entre recargas da árvore

    def filter_paths(self, paths):
        return [p for p in paths if p.name not in SKIP]

    def render_label(self, node, base_style, style):
        texto = super().render_label(node, base_style, style)
        if self.is_mounted and node.data is not None:
            if node._allow_expand:
                texto.stylize(f"bold {C['orange']}", 0, 1)
            else:
                texto.stylize(C[TIPO_COR.get(Path(node.data.path).suffix.lower(), "dim")], 0, 1)
        return texto

    # ------------------------------------------------------------------ onde agir
    @property
    def raiz(self) -> Path:
        return Path(self.path).resolve()

    def selecionado(self) -> Path | None:
        node = self.cursor_node
        return Path(node.data.path) if node is not None and node.data is not None else None

    def pasta_alvo(self) -> Path:
        """Pasta onde criar ou colar: a selecionada, ou a do arquivo selecionado."""
        p = self.selecionado()
        if p is None:
            return self.raiz
        return p if p.is_dir() else p.parent

    def rel(self, p: Path) -> str:
        try:
            r = p.resolve().relative_to(self.raiz).as_posix()
        except ValueError:
            return str(p)
        return "." if r == "." else r

    def dentro(self, p: Path) -> bool:
        try:
            p.resolve().relative_to(self.raiz)
            return True
        except ValueError:
            return False

    def avisar(self, texto: str, erro: bool = False) -> None:
        self.app.notify(texto, severity="error" if erro else "information", title="explorer")

    async def mostrar(self, alvo: Path) -> None:
        """Recarrega a árvore e põe o cursor em `alvo`, abrindo as pastas do caminho."""
        await self.reload()
        try:
            partes = alvo.resolve().relative_to(self.raiz).parts
        except ValueError:
            return
        node = self.root
        for parte in partes:
            if not node.is_expanded:
                await self.reload_node(node)
            node = next((c for c in node.children if c.data is not None and Path(c.data.path).name == parte), None)
            if node is None:
                return
        _ = self._tree_lines  # linhas recalculadas antes de mover o cursor
        self.move_cursor(node)

    # ------------------------------------------------------------------ navegação
    def action_expandir(self) -> None:
        node = self.cursor_node
        if node is None:
            return
        if node.allow_expand and not node.is_expanded:
            node.expand()
        elif node.allow_expand and node.children:
            self.move_cursor(node.children[0])
        elif not node.allow_expand:
            self.select_node(node)  # arquivo: abre no editor

    def action_recolher(self) -> None:
        node = self.cursor_node
        if node is None:
            return
        if node.allow_expand and node.is_expanded:
            node.collapse()
        elif node.parent is not None:
            self.move_cursor(node.parent)

    def action_primeiro(self) -> None:
        self.cursor_line = 0

    def action_ultimo(self) -> None:
        self.cursor_line = self.last_line

    def action_pagina(self, passo: int) -> None:
        altura = max(1, self.scrollable_content_region.height - 1)
        self.cursor_line = max(0, min(self.last_line, self.cursor_line + passo * altura))

    def action_abrir(self) -> None:
        node = self.cursor_node
        if node is not None:
            self.select_node(node)

    # ------------------------------------------------------------------ criar, renomear, apagar
    def action_novo_arquivo(self) -> None:
        pasta = self.pasta_alvo()
        self.app.push_screen(PromptScreen(f"novo arquivo em {self.rel(pasta)}/",
                                          "ex.: main.py  (com / cria pastas: src/app.py)"),
                             lambda nome: self.criar(pasta, nome, diretorio=False))

    def action_nova_pasta(self) -> None:
        pasta = self.pasta_alvo()
        self.app.push_screen(PromptScreen(f"nova pasta em {self.rel(pasta)}/", "ex.: src  ou  assets/img"),
                             lambda nome: self.criar(pasta, nome, diretorio=True))

    async def criar(self, pasta: Path, nome: str | None, diretorio: bool) -> None:
        if not nome:
            return
        alvo = (pasta / nome.strip().strip("/")).resolve()
        if not self.dentro(alvo) or alvo == self.raiz:
            self.avisar(f"{nome}: fora do projeto", erro=True)
            return
        if alvo.exists():
            self.avisar(f"{self.rel(alvo)} já existe")
            if alvo.is_file():
                await self.app.open_file(alvo)  # type: ignore[attr-defined]
            return
        try:
            if diretorio:
                alvo.mkdir(parents=True)
            else:
                alvo.parent.mkdir(parents=True, exist_ok=True)
                alvo.touch()
        except OSError as exc:
            self.avisar(f"não consegui criar {nome}: {exc.strerror or exc}", erro=True)
            return
        await self.mostrar(alvo)
        self.avisar(f"criado: {self.rel(alvo)}{'/' if diretorio else ''}")
        if not diretorio:
            await self.app.open_file(alvo)  # type: ignore[attr-defined]

    def action_renomear(self) -> None:
        p = self.selecionado()
        if p is None or p.resolve() == self.raiz:
            return
        stem = len(p.name) if p.is_dir() or not p.suffix else len(p.stem)
        self.app.push_screen(PromptScreen(f"renomear {self.rel(p)} para", value=p.name, selecionar=stem),
                             lambda nome: self._renomear(p, nome))

    async def _renomear(self, p: Path, nome: str | None) -> None:
        if not nome or nome == p.name:
            return
        alvo = (p.parent / nome).resolve()
        if not self.dentro(alvo):
            self.avisar(f"{nome}: fora do projeto", erro=True)
            return
        if alvo.exists():
            self.avisar(f"{self.rel(alvo)} já existe", erro=True)
            return
        try:
            alvo.parent.mkdir(parents=True, exist_ok=True)
            p.rename(alvo)
        except OSError as exc:
            self.avisar(f"não consegui renomear: {exc.strerror or exc}", erro=True)
            return
        self.app.arquivo_movido(p, alvo)  # type: ignore[attr-defined]
        await self.mostrar(alvo)

    def action_apagar(self) -> None:
        p = self.selecionado()
        if p is None or p.resolve() == self.raiz:
            return
        tipo = "a pasta" if p.is_dir() else "o arquivo"
        self.app.push_screen(ConfirmScreen(f"Apagar {tipo} {self.rel(p)}?",
                                           f"Vai para {LIXEIRA.as_posix()}/ no projeto; dá para recuperar de lá."),
                             lambda ok: self._apagar(p) if ok else None)

    async def _apagar(self, p: Path) -> None:
        destino = self.raiz / LIXEIRA / time.strftime("%Y%m%d-%H%M%S")
        try:
            destino.mkdir(parents=True, exist_ok=True)
            shutil.move(str(p), str(nome_livre(destino, p.name, p.is_dir())))
        except OSError as exc:
            self.avisar(f"não consegui apagar: {exc.strerror or exc}", erro=True)
            return
        self.app.arquivo_apagado(p)  # type: ignore[attr-defined]
        await self.reload()
        self.avisar(f"apagado: {self.rel(p)} (está em {LIXEIRA.as_posix()}/)")

    # ------------------------------------------------------------------ copiar e colar
    def action_copiar(self) -> None:
        p = self.selecionado()
        if p is not None and p.resolve() != self.raiz:
            Explorer.area = ("copiar", p)
            self.avisar(f"copiado: {self.rel(p)} · v cola na pasta selecionada")

    def action_recortar(self) -> None:
        p = self.selecionado()
        if p is not None and p.resolve() != self.raiz:
            Explorer.area = ("recortar", p)
            self.avisar(f"recortado: {self.rel(p)} · v move para a pasta selecionada")

    async def action_duplicar(self) -> None:
        p = self.selecionado()
        if p is not None and p.resolve() != self.raiz:
            await self._colar(p, p.parent, mover=False)

    async def action_colar(self) -> None:
        if Explorer.area is None:
            self.avisar("nada copiado: c copia, x recorta (ou arraste arquivos do gerenciador para o terminal)")
            return
        modo, origem = Explorer.area
        if not origem.exists():
            Explorer.area = None
            self.avisar(f"{origem.name} não existe mais", erro=True)
            return
        await self._colar(origem, self.pasta_alvo(), mover=modo == "recortar")
        if modo == "recortar":
            Explorer.area = None

    async def _colar(self, origem: Path, pasta: Path, mover: bool) -> None:
        if origem.is_dir() and (pasta.resolve() == origem.resolve() or origem.resolve() in pasta.resolve().parents):
            self.avisar("não dá para pôr uma pasta dentro dela mesma", erro=True)
            return
        if mover and origem.parent.resolve() == pasta.resolve():
            return
        destino = nome_livre(pasta, origem.name, origem.is_dir())
        try:
            if mover:
                shutil.move(str(origem), str(destino))
            else:
                copiar(origem, destino)
        except OSError as exc:
            self.avisar(f"não consegui {'mover' if mover else 'copiar'}: {exc.strerror or exc}", erro=True)
            return
        if mover:
            self.app.arquivo_movido(origem, destino)  # type: ignore[attr-defined]
        await self.mostrar(destino)
        self.avisar(f"{'movido' if mover else 'copiado'}: {self.rel(destino)}")

    def action_copiar_caminho(self) -> None:
        p = self.selecionado()
        if p is not None:
            self.app.copy_to_clipboard(self.rel(p))
            self.avisar(f"caminho copiado: {self.rel(p)}")

    async def _on_paste(self, event: events.Paste) -> None:
        """Arquivos arrastados do gerenciador de arquivos (o terminal cola o caminho): copia para a pasta selecionada."""
        caminhos = caminhos_colados(event.text)
        if not caminhos:
            return
        event.stop()
        pasta = self.pasta_alvo()
        for origem in caminhos:
            await self._colar(origem, pasta, mover=False)

    # ------------------------------------------------------------------ menu (botão direito, Shift+F10 ou m)
    async def _on_click(self, event: events.Click) -> None:
        if event.button == 3 and "line" in event.style.meta:
            self.cursor_line = event.style.meta["line"]
            self.action_menu(event.screen_x, event.screen_y)
            return
        await super()._on_click(event)

    def action_menu(self, x: int | None = None, y: int | None = None) -> None:
        if x is None or y is None:
            regiao = self.region
            x, y = regiao.x + 4, regiao.y + max(0, self.cursor_line - self.scroll_offset.y) + 1
        p = self.selecionado()
        titulo = self.rel(p) if p is not None else "."
        opcoes = [(a, t, r) for a, t, r in ACOES if a != "colar" or Explorer.area is not None]
        self.app.push_screen(MenuScreen(titulo, opcoes, x, y), self._menu_escolhido)

    async def _menu_escolhido(self, acao: str | None) -> None:
        if acao:
            await self.run_action(acao)


class MenuScreen(ModalScreen[str | None]):
    """Menu de contexto do explorer, aberto onde o mouse clicou. Setas + Enter escolhem, Esc fecha."""

    BINDINGS = [("escape", "fechar", "Fechar")]

    def __init__(self, titulo: str, opcoes: list[tuple[str, str, str]], x: int, y: int) -> None:
        super().__init__()
        self.titulo, self.opcoes, self.pos = titulo, opcoes, (x, y)

    def compose(self):
        lista = OptionList(*[Option(f"{rotulo:<16}[{C['dim']}]{tecla:>5}[/]", id=acao)
                             for acao, tecla, rotulo in self.opcoes], id="menu-lista")
        lista.border_title = self.titulo[-24:]
        yield lista

    def on_mount(self) -> None:
        lista = self.query_one(OptionList)
        largura, altura = 28, len(self.opcoes) + 2
        x = max(0, min(self.pos[0], self.app.size.width - largura))
        y = max(0, min(self.pos[1], self.app.size.height - altura))
        lista.styles.offset = (x, y)
        lista.focus()

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        self.dismiss(event.option.id)

    def on_click(self, event: events.Click) -> None:
        if event.widget is self:  # clique fora do menu
            self.dismiss(None)

    def action_fechar(self) -> None:
        self.dismiss(None)


class ConfirmScreen(ModalScreen[bool]):
    """Pergunta sim/não. Enter ou s confirma; Esc ou n cancela."""

    BINDINGS = [("escape,n", "nao", "Não"), ("s,y,enter", "sim", "Sim")]

    def __init__(self, pergunta: str, detalhe: str = "") -> None:
        super().__init__()
        self.pergunta, self.detalhe = pergunta, detalhe

    def compose(self):
        with Vertical(id="confirm-card"):
            yield Label(self.pergunta, id="confirm-title")
            if self.detalhe:
                yield Static(self.detalhe, id="confirm-detail")
            with Horizontal(id="confirm-buttons"):
                yield Static(f"[b {C['mint']}]Enter[/] [{C['text']}]confirma · [/][b {C['mint']}]Esc[/] "
                             f"[{C['text']}]cancela[/]", id="confirm-keys")
                yield Button("✓ Sim", id="confirm-sim", classes="accept")
                yield Button("✗ Não", id="confirm-nao", classes="reject")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        self.dismiss(event.button.id == "confirm-sim")

    def action_sim(self) -> None:
        self.dismiss(True)

    def action_nao(self) -> None:
        self.dismiss(False)
