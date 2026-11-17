"""Git no Studio: o painel GIT (Alt+G) com o que mudou, diferenças trecho a trecho, commit, branches, histórico e
conflitos; marcas de linhas novas, alteradas e apagadas na margem do editor; o status de cada arquivo no explorer.

Na lista do painel: Enter mostra as diferenças do arquivo (num conflito, abre a resolução), s prepara, u desprepara,
d descarta, o abre o arquivo e a prepara tudo. Na tela de diferenças, s, u e d valem para o trecho escolhido. A
mensagem mais Enter faz o commit do que está preparado. Pull, push e fetch rodam no terminal integrado, onde a senha e
o progresso aparecem. Mudanças feitas por fora (git no terminal, outro programa) são percebidas pelo índice e pelo HEAD,
e os editores sem alterações não salvas recarregam o arquivo do disco.
"""

from __future__ import annotations

import shlex
import threading
from pathlib import Path

from rich.text import Text
from textual import work
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Input, Label, OptionList, Static, TabbedContent
from textual.widgets.option_list import Option
from textual.worker import get_current_worker

from codar.i18n import tr
from codar.ide import git
from codar.ide.git import Diferenca, ErroGit, Estado, Mudanca, Repositorio, Trecho
from codar.studio.widgets import ASCII, C, Botao, CodeEditor

ATALHOS = [Binding("alt+g", "git_painel", tr("Controle de versão (Git)"), show=False, priority=True)]
LIMITE_MARCAS = 20000  # linhas; acima disso a margem não mostra alterações (o diff ficaria lento a cada tecla)
LIMITE_LINHAS_TRECHO = 2000  # linhas mostradas de um trecho enorme (um arquivo novo gigante, por exemplo)
LIMITE_DETALHES = 400_000  # caracteres de um commit mostrados no histórico
_COR = {"M": "cyan", "T": "cyan", "A": "green", "N": "green", "D": "error", "R": "blue", "C": "blue", "!": "error"}
TECLAS_LISTA = "Enter diferenças · s prepara · u desprepara · d descarta · o abre · a prepara tudo"
_AUSENTE = object()


def _letra(m: Mudanca, chave: str) -> str:
    """A letra de status: ! conflito, N novo (não rastreado), senão a do lado mostrado (índice ou trabalho)."""
    if m.conflito:
        return "!"
    if m.nova:
        return "N"
    return m.indice if chave == "p" else m.trabalho


def _rotulo_item(m: Mudanca, chave: str) -> Text:
    letra = _letra(m, chave)
    texto = Text.assemble((f" {letra} ", f"bold {C[_COR.get(letra, 'text')]}"), " ", m.caminho)
    if m.origem:
        texto.append(f"  ← {m.origem}", style=C["dim"])
    return texto


def _texto_trecho(trecho: Trecho) -> Text:
    """Um trecho do diff com o número da linha (no arquivo novo) à esquerda: + verde, - vermelho."""
    texto = Text(trecho.cabecalho, style=f"bold {C['blue']}")
    numero = trecho.inicio_novo + 1
    for linha in trecho.linhas[:LIMITE_LINHAS_TRECHO]:
        linha = linha.rstrip("\r")
        texto.append("\n")
        if linha.startswith("+"):
            texto.append(f"{numero:>5} ", style=C["dim"])
            texto.append(linha, style=C["green"])
            numero += 1
        elif linha.startswith("-"):
            texto.append("      ")
            texto.append(linha, style=C["error"])
        elif linha.startswith("\\"):
            texto.append("      " + linha, style=C["dim"])
        else:
            texto.append(f"{numero:>5} ", style=C["dim"])
            texto.append(linha)
            numero += 1
    if len(trecho.linhas) > LIMITE_LINHAS_TRECHO:
        texto.append("\n      " + tr("… mais {n} linhas neste trecho").format(n=len(trecho.linhas) - LIMITE_LINHAS_TRECHO),
                     style=C["dim"])
    return texto


class ListaGit(OptionList):
    """A lista de alterações do painel GIT; as teclas agem sobre o arquivo destacado."""

    BINDINGS = [
        Binding("s", "app.git_item('preparar')", tr("Preparar"), show=False),
        Binding("u", "app.git_item('despreparar')", tr("Despreparar"), show=False),
        Binding("d", "app.git_item('descartar')", tr("Descartar"), show=False),
        Binding("o", "app.git_item('abrir')", tr("Abrir"), show=False),
        Binding("a", "app.git_preparar_tudo", tr("Preparar tudo"), show=False),
    ]


class DiffScreen(ModalScreen[int | None]):
    """Diferenças de um arquivo, trecho por trecho. Devolve a linha (a partir de 0) para abrir no editor, ou None."""

    DEFAULT_CSS = """
    DiffScreen { align: center middle; background: $codar-bg 75%; }
    #diff-card { width: 150; max-width: 98%; height: 94%; border: round $codar-orange; padding: 0 1; }
    #diff-titulo { height: 1; color: $codar-orange; text-style: bold; }
    #diff-teclas { height: 1; color: $codar-dim; }
    #diff-trechos { height: 1fr; background: $codar-bg; }
    /* o trecho escolhido ganha só um fundo discreto: as cores do diff continuam legíveis */
    #diff-trechos > .option-list--option-highlighted, #diff-trechos:focus > .option-list--option-highlighted {
        background: $codar-sel; color: $codar-text; text-style: none;
    }
    """
    BINDINGS = [
        Binding("escape,q", "fechar", tr("Fechar")),
        Binding("s", "preparar", tr("Preparar o trecho")),
        Binding("u", "despreparar", tr("Despreparar o trecho")),
        Binding("d", "descartar", tr("Descartar o trecho")),
        Binding("t", "alternar", tr("Preparado / não preparado")),
        Binding("o", "abrir", tr("Abrir no editor")),
    ]

    def __init__(self, repo: Repositorio, caminho: str, preparada: bool = False, ao_mudar=None) -> None:
        super().__init__()
        self.repo, self.caminho, self.preparada = repo, caminho, preparada
        self.ao_mudar = ao_mudar or (lambda recarregar: None)
        self.diff: Diferenca | None = None
        self.nova = False

    def compose(self):
        with Vertical(id="diff-card"):
            yield Label(id="diff-titulo")
            yield Static(id="diff-teclas")
            yield OptionList(id="diff-trechos")

    def on_mount(self) -> None:
        self.carregar()
        self.query_one("#diff-trechos", OptionList).focus()

    def carregar(self, manter: int = 0) -> None:
        try:
            self.nova = not self.preparada and any(m.nova and m.caminho == self.caminho
                                                    for m in self.repo.estado().mudancas)
            self.diff = self.repo.diferenca(self.caminho, self.preparada, nova=self.nova)
        except ErroGit as exc:
            self.diff = None
            self.notify(str(exc), severity="error", timeout=8)
        if self.nova:
            lado = tr("ARQUIVO NOVO (não rastreado)")
            teclas = tr("s prepara o arquivo · Enter/o abre no editor · Esc fecha")
        elif self.preparada:
            lado = tr("PREPARADO (último commit → índice)")
            teclas = tr("u desprepara o trecho · t mostra o não preparado · Enter/o abre no editor · Esc fecha")
        else:
            lado = tr("NÃO PREPARADO (índice → arquivo)")
            teclas = tr("s prepara o trecho · d descarta o trecho · t mostra o preparado · Enter/o abre no editor · Esc fecha")
        self.query_one("#diff-titulo", Label).update(f"DIFF · {self.caminho} · {lado}")
        self.query_one("#diff-teclas", Static).update(teclas)
        lista = self.query_one("#diff-trechos", OptionList)
        lista.clear_options()
        if self.diff is None or not self.diff.trechos:
            vazio = (tr("arquivo binário: o git não mostra trechos") if self.diff is not None and self.diff.binario
                     else tr("sem diferenças deste lado (t alterna entre preparado e não preparado)"))
            lista.add_option(Option(Text(vazio, style=C["dim"]), disabled=True))
            return
        lista.add_options([Option(_texto_trecho(t), id=str(i)) for i, t in enumerate(self.diff.trechos)])
        lista.highlighted = min(manter, len(self.diff.trechos) - 1)

    def _indice(self) -> int | None:
        lista = self.query_one("#diff-trechos", OptionList)
        if self.diff is None or not self.diff.trechos or lista.highlighted is None:
            return None
        return min(lista.highlighted, len(self.diff.trechos) - 1)

    def _aplicar(self, operacao, recarregar: bool = False) -> None:
        indice = self._indice()
        if indice is None:
            return
        try:
            operacao(self.diff, [indice])
        except ErroGit as exc:
            self.notify(str(exc), severity="error", timeout=10)
        self.ao_mudar(recarregar)
        self.carregar(manter=indice)

    def action_preparar(self) -> None:
        if self.preparada:
            self.notify(tr("este lado já está preparado; u desprepara o trecho"))
            return
        self._aplicar(self.repo.preparar_trechos)

    def action_despreparar(self) -> None:
        if not self.preparada:
            self.notify(tr("t mostra o que está preparado; lá, u desprepara o trecho"))
            return
        self._aplicar(self.repo.despreparar_trechos)

    def action_descartar(self) -> None:
        if self.preparada:
            self.notify(tr("desprepare o trecho (u) antes de descartá-lo"))
            return
        if self.nova:
            self.notify(tr("arquivo novo: d na lista do painel GIT o move para a lixeira"), severity="warning")
            return
        if self._indice() is None:
            return
        from codar.studio.explorer import ConfirmScreen

        def confirmado(ok: bool) -> None:
            if ok:
                self._aplicar(self.repo.descartar_trechos, recarregar=True)

        self.app.push_screen(ConfirmScreen(tr("Descartar este trecho de {arquivo}?").format(arquivo=self.caminho),
                                           tr("O trecho volta ao que está preparado. O git não guarda o texto "
                                              "descartado; Ctrl+Z no editor ainda o recupera se o arquivo estiver "
                                              "aberto.")), confirmado)

    def action_alternar(self) -> None:
        self.preparada = not self.preparada
        self.carregar()

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        event.stop()
        self.action_abrir()

    def action_abrir(self) -> None:
        indice = self._indice()
        self.dismiss(self.diff.trechos[indice].inicio_novo if indice is not None else 0)

    def action_fechar(self) -> None:
        self.dismiss(None)


class ConflitoScreen(ModalScreen[bool]):
    """Resolve os blocos <<<<<<< ======= >>>>>>> de um arquivo, um por um. Cada escolha vai para o arquivo na hora
    (aplicar); z desfaz a última. Devolve True quando não sobra nenhum conflito."""

    DEFAULT_CSS = """
    ConflitoScreen { align: center middle; background: $codar-bg 75%; }
    #conflito-card { width: 140; max-width: 98%; height: 92%; border: round $codar-error; padding: 0 1; }
    #conflito-titulo { height: 1; color: $codar-orange; text-style: bold; }
    #conflito-teclas { height: 1; color: $codar-dim; }
    #conflito-blocos { height: 1fr; background: $codar-bg; }
    #conflito-blocos > .option-list--option-highlighted, #conflito-blocos:focus > .option-list--option-highlighted {
        background: $codar-sel; color: $codar-text; text-style: none;
    }
    """
    BINDINGS = [
        Binding("escape,q", "fechar", tr("Fechar")),
        Binding("1,a", "resolver('nosso')", tr("Manter o atual")),
        Binding("2,e", "resolver('deles')", tr("Aceitar o que entra")),
        Binding("3,m", "resolver('ambos')", tr("Manter os dois")),
        Binding("z", "desfazer", tr("Desfazer")),
    ]

    def __init__(self, nome: str, texto: str, aplicar) -> None:
        super().__init__()
        self.nome, self.texto, self.aplicar = nome, texto, aplicar
        self.anteriores: list[str] = []

    def compose(self):
        with Vertical(id="conflito-card"):
            yield Label(tr("CONFLITO · {arquivo}").format(arquivo=self.nome), id="conflito-titulo")
            yield Static(tr("1/a mantém o atual · 2/e aceita o que entra · 3/m mantém os dois · z desfaz · Esc fecha"),
                         id="conflito-teclas")
            yield OptionList(id="conflito-blocos")

    def on_mount(self) -> None:
        self.carregar()
        self.query_one("#conflito-blocos", OptionList).focus()

    def carregar(self, manter: int = 0) -> None:
        blocos = git.conflitos_no_texto(self.texto)
        lista = self.query_one("#conflito-blocos", OptionList)
        lista.clear_options()
        if not blocos:
            lista.add_option(Option(Text(tr("Nenhum conflito restante. Esc fecha e oferece marcar como resolvido."),
                                         style=C["mint"]), disabled=True))
            return
        for i, bloco in enumerate(blocos):
            texto = Text(tr("CONFLITO {n} de {total} · linhas {inicio}-{fim}").format(
                n=i + 1, total=len(blocos), inicio=bloco.inicio + 1, fim=bloco.fim + 1), style=f"bold {C['orange']}")
            texto.append("\n" + tr("ATUAL ({rotulo}) · 1 mantém").format(rotulo=bloco.rotulo_nosso or "HEAD"),
                         style=f"bold {C['cyan']}")
            for linha in bloco.nosso or ("",):
                texto.append("\n  " + linha.rstrip("\r"), style=C["cyan"])
            texto.append("\n" + tr("ENTRANDO ({rotulo}) · 2 aceita").format(rotulo=bloco.rotulo_deles or "?"),
                         style=f"bold {C['green']}")
            for linha in bloco.deles or ("",):
                texto.append("\n  " + linha.rstrip("\r"), style=C["green"])
            lista.add_option(Option(texto, id=str(i)))
        lista.highlighted = min(manter, len(blocos) - 1)

    def action_resolver(self, escolha: str) -> None:
        lista = self.query_one("#conflito-blocos", OptionList)
        blocos = git.conflitos_no_texto(self.texto)
        if not blocos or lista.highlighted is None:
            return
        indice = min(lista.highlighted, len(blocos) - 1)
        self.anteriores.append(self.texto)
        self.texto = git.resolver_conflito(self.texto, indice, escolha)
        self.aplicar(self.texto)
        self.carregar(manter=indice)

    def action_desfazer(self) -> None:
        if self.anteriores:
            self.texto = self.anteriores.pop()
            self.aplicar(self.texto)
            self.carregar()

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        event.stop()

    def action_fechar(self) -> None:
        self.dismiss(not git.conflitos_no_texto(self.texto))


class ControleVersaoMixin:
    """Parte do Studio que conversa com o git."""

    def _git_init(self) -> None:
        self._repo: Repositorio | None = None
        self._git_estado: Estado | None = None
        self._git_erro: str | None = None
        self._git_dir: Path | None = None
        self._git_assinatura: tuple | None = None
        self._git_originais: dict[str, str | None] = {}  # conteúdo no índice, base das marcas da margem
        self._git_timers: dict[str, object] = {}
        self._git_itens: dict[str, tuple[str, Mudanca]] = {}  # id da opção na lista -> (grupo, mudança)
        self._git_avisados: set[Path] = set()
        self._git_recarregar_pendente = False  # sobrevive a uma leitura de estado cancelada por outra mais nova
        self._git_trava = threading.Lock()  # uma operação de escrita por vez (o índice tem trava própria)

    # ------------------------------------------------------------------ painel
    def compor_git(self):
        with Horizontal(id="git-tools"):
            yield Botao(tr("↻ ATUALIZAR"), acao="git_atualizar_tudo", id="git-refresh")
            yield Botao(tr("✓ COMMIT"), acao="git_commit", id="git-commit")
            yield Botao(tr("⎇ BRANCH") if not ASCII else "BRANCH", acao="git_branch", id="git-branch")
            yield Botao(tr("≡ HISTÓRICO"), acao="git_historico", id="git-log")
            yield Botao(tr("↓ PULL"), acao="git_pull", id="git-pull")
            yield Botao(tr("↑ PUSH"), acao="git_push", id="git-push")
        yield Static(tr("Procurando o repositório git…"), id="git-status")
        yield Input(placeholder=tr("mensagem do commit (Enter faz o commit do que está preparado)"), id="git-message")
        yield ListaGit(id="git-changes")

    def git_montar(self) -> None:
        self._git_abrir()
        self.set_interval(2.0, self._git_vigiar)

    def _git_abrir(self) -> None:
        self._repo = Repositorio.abrir(self.root)
        self._git_dir = None
        if self._repo is not None:
            if (self.root / ".codar").is_dir():  # lixeira de versões antigas, sem o .gitignore da pasta
                from codar.project import pasta_local

                pasta_local(self.root)
            try:
                self._git_dir = self._repo.pasta_git()
            except ErroGit:
                self._git_dir = self._repo.raiz / ".git"
        self._git_assinatura = self._git_ler_assinatura()
        self._git_originais.clear()
        self.git_atualizar()

    def _git_ler_assinatura(self) -> tuple | None:
        """O que muda quando alguém usa o git: índice, HEAD, reflog, merge e fetch. Barato o bastante para cada 2 s."""
        if self._git_dir is None:
            return None
        valores = []
        for nome in ("index", "HEAD", "logs/HEAD", "MERGE_HEAD", "FETCH_HEAD", "packed-refs"):
            try:
                valores.append((self._git_dir / nome).stat().st_mtime_ns)
            except OSError:
                valores.append(None)
        return tuple(valores)

    def _git_vigiar(self) -> None:
        if self._repo is None:
            if (self.root / ".git").exists():  # git init feito no terminal
                self._git_abrir()
            return
        assinatura = self._git_ler_assinatura()
        if assinatura != self._git_assinatura:
            self._git_assinatura = assinatura
            self._git_originais.clear()
            self.git_atualizar(recarregar=True)

    def git_atualizar(self, recarregar: bool = False) -> None:
        if recarregar:
            self._git_recarregar_pendente = True
        self._git_worker_estado(self._repo)

    def action_git_atualizar_tudo(self) -> None:
        self._git_originais.clear()
        self.git_atualizar(recarregar=True)

    @work(thread=True, group="git-estado", exclusive=True, exit_on_error=False)
    def _git_worker_estado(self, repo: Repositorio | None) -> None:
        estado, erro = None, None
        if repo is not None:
            try:
                estado = repo.estado()
            except ErroGit as exc:
                erro = str(exc)
        if not get_current_worker().is_cancelled:
            self.call_from_thread(self._git_mostrar, repo, estado, erro)

    def _git_mostrar(self, repo: Repositorio | None, estado: Estado | None, erro: str | None) -> None:
        from textual.css.query import NoMatches

        if repo is not self._repo:
            return  # resposta de um repositório anterior (git init no meio do caminho)
        self._git_estado, self._git_erro = estado, erro
        try:  # a resposta da thread pode chegar com o Studio já fechando
            self._git_mostrar_status()
            self._git_mostrar_lista()
        except NoMatches:
            return
        self._git_decorar_explorer()
        if self._git_recarregar_pendente:
            self._git_recarregar_pendente = False
            self._git_recarregar_editores()
        for ed in self.query(CodeEditor):
            self._git_marcar(ed, 0)
        self.render_status()

    def _git_mostrar_status(self) -> None:
        status = self.query_one("#git-status", Static)
        estado = self._git_estado
        if self._repo is None:
            from shutil import which

            status.update(Text(tr("git não encontrado: instale o git para usar o controle de versão") if which("git")
                               is None else tr("Esta pasta não está num repositório git. Paleta (Ctrl+P) → "
                                               "Git: iniciar repositório."), style=C["dim"]))
            return
        if estado is None:
            status.update(Text(self._git_erro or tr("lendo o estado do repositório…"),
                               style=C["error"] if self._git_erro else C["dim"]))
            return
        texto = Text()
        texto.append(f"{'git:' if ASCII else '⎇'} {estado.branch or tr('HEAD destacado') + ' ' + (estado.commit or '')[:7]}",
                     style=f"bold {C['mint']}")
        if estado.upstream:
            texto.append(f" → {estado.upstream}", style=C["dim"])
            if estado.a_frente or estado.atras:
                texto.append(f" ↑{estado.a_frente} ↓{estado.atras}", style=f"bold {C['orange']}")
        elif estado.branch:
            texto.append("  " + tr("sem remoto (↑ PUSH publica)"), style=C["dim"])
        if estado.em_merge:
            texto.append("  " + tr("MERGE EM ANDAMENTO: resolva os conflitos e faça o commit (ou paleta → Git: "
                                   "abortar merge)"), style=f"bold {C['error']}")
        alteradas = sum(1 for m in estado.mudancas if (m.alterada or m.nova) and not m.conflito)
        preparadas = sum(1 for m in estado.mudancas if m.preparada)
        texto.append("  · " + tr("{a} alterado(s) · {p} preparado(s)").format(a=alteradas, p=preparadas),
                     style=C["text"])
        if estado.mudancas:
            texto.append("  · " + tr(TECLAS_LISTA), style=C["dim"])
        status.update(texto)

    def _git_mostrar_lista(self) -> None:
        lista = self.query_one("#git-changes", OptionList)
        anterior = lista.highlighted_option.id if lista.highlighted_option is not None else None
        lista.clear_options()
        self._git_itens = {}
        estado = self._git_estado
        if self._repo is None or estado is None:
            return
        grupos = [(tr("CONFLITOS"), "c", [m for m in estado.mudancas if m.conflito]),
                  (tr("PREPARADAS"), "p", [m for m in estado.mudancas if m.preparada]),
                  (tr("ALTERAÇÕES"), "t", [m for m in estado.mudancas if m.alterada or m.nova])]
        opcoes = []
        for titulo, chave, itens in grupos:
            if not itens:
                continue
            opcoes.append(Option(Text(f"{titulo} ({len(itens)})", style=f"bold {C['orange']}"), disabled=True))
            for m in itens:
                identidade = f"{chave}:{m.caminho}"
                self._git_itens[identidade] = (chave, m)
                opcoes.append(Option(_rotulo_item(m, chave), id=identidade))
        if not opcoes:
            opcoes.append(Option(Text(tr("Nada para commitar: a árvore de trabalho está limpa."), style=C["dim"]),
                                 disabled=True))
        lista.add_options(opcoes)
        ids = [o.id for o in opcoes]
        if anterior in ids:
            lista.highlighted = ids.index(anterior)
        elif self._git_itens:
            lista.highlighted = next(i for i, o in enumerate(opcoes) if o.id)

    def _git_decorar_explorer(self) -> None:
        from codar.studio.explorer import Explorer

        arquivos: dict[Path, tuple[str, str]] = {}
        pastas: set[Path] = set()
        if self._repo is not None and self._git_estado is not None:
            raiz = self._repo.raiz
            for m in self._git_estado.mudancas:
                letra = _letra(m, "t" if m.alterada or m.nova or m.conflito else "p")
                alvo = raiz / m.caminho
                arquivos[alvo] = (letra, _COR.get(letra, "text"))
                for pai in alvo.parents:
                    if pai == raiz or raiz not in pai.parents:
                        break
                    pastas.add(pai)
        for explorer in self.query(Explorer):
            explorer.decorar_git(arquivos, pastas)

    def git_rotulo(self) -> str:
        """Segmento da barra de status: branch, commits a enviar/receber e quantos arquivos mudaram."""
        estado = self._git_estado
        if self._repo is None or estado is None:
            return ""
        partes = [f"{'git:' if ASCII else '⎇ '}{estado.branch or (estado.commit or '?')[:7]}"]
        if estado.a_frente:
            partes.append(f"↑{estado.a_frente}")
        if estado.atras:
            partes.append(f"↓{estado.atras}")
        if estado.conflitos:
            partes.append(f"!{len(estado.conflitos)}")
        elif estado.mudancas:
            partes.append(f"•{len({m.caminho for m in estado.mudancas})}")
        return " ".join(partes)

    def on_tabbed_content_tab_activated(self, event: TabbedContent.TabActivated) -> None:
        if event.tabbed_content.id == "panel" and event.pane.id == "tab-git":
            self.git_atualizar()

    def action_git_painel(self) -> None:
        painel = self.query_one("#panel", TabbedContent)
        painel.display = True
        painel.active = "tab-git"
        self.git_atualizar()
        self.query_one("#git-changes", OptionList).focus()

    # ------------------------------------------------------------------ editores
    def _git_editor_de(self, caminho: Path) -> CodeEditor | None:
        for ed in self.query(CodeEditor):
            if ed.path and Path(ed.path).resolve() == caminho.resolve():
                return ed
        return None

    def git_documento_aberto(self, ed: CodeEditor) -> None:
        self._git_marcar(ed, 0)

    def git_documento_alterado(self, ed: CodeEditor) -> None:
        if self._repo is not None:  # fora de um repositório, nem o temporizador por tecla
            self._git_marcar(ed, .4)

    def git_documento_salvo(self, ed: CodeEditor) -> None:
        if self._repo is not None:
            self.git_atualizar()

    def git_documento_fechado(self, ed: CodeEditor) -> None:
        if timer := self._git_timers.pop(ed.id, None):
            timer.stop()

    def _git_marcar(self, ed: CodeEditor, atraso: float) -> None:
        if timer := self._git_timers.pop(ed.id, None):
            timer.stop()
        if atraso <= 0:
            self._git_marcar_agora(ed)
        else:
            self._git_timers[ed.id] = self.set_timer(atraso, lambda: self._git_marcar_agora(ed))

    def _git_marcar_agora(self, ed: CodeEditor) -> None:
        self._git_timers.pop(ed.id, None)
        if not ed.is_mounted:
            return
        rel = None
        if self._repo is not None and self._git_estado is not None and ed.path:
            try:
                rel = self._repo.relativo(ed.path)
            except ValueError:  # fora do repositório
                rel = None
        if rel is None or ed.document.line_count > LIMITE_MARCAS:
            if ed.marcas_git:
                ed.marcas_git = {}
                ed.refresh()
            return
        novos = {m.caminho for m in self._git_estado.mudancas if m.nova}
        self._git_worker_marcas(self._repo, ed.id, rel, ed.text, rel in novos)

    @work(thread=True, group="git-marcas", exit_on_error=False)
    def _git_worker_marcas(self, repo: Repositorio, editor_id: str, rel: str, texto: str, novo: bool) -> None:
        original = self._git_originais.get(rel, _AUSENTE)
        if original is _AUSENTE:
            original = self._git_originais[rel] = repo.original(rel)
        if original is None:  # fora do índice: novo (todas as linhas) ou ignorado (nenhuma)
            marcas = git.marcas_de_linha(None, texto) if novo else {}
        else:
            marcas = git.marcas_de_linha(original, texto)
        self.call_from_thread(self._git_aplicar_marcas, editor_id, texto, marcas)

    def _git_aplicar_marcas(self, editor_id: str, texto: str, marcas: dict[int, str]) -> None:
        for ed in self.query(f"#{editor_id}"):
            if isinstance(ed, CodeEditor) and ed.text == texto and ed.marcas_git != marcas:
                ed.marcas_git = marcas
                ed.refresh()

    def _git_recarregar_editores(self) -> None:
        """Depois de descartar, trocar de branch, pull ou merge: abas sem alterações não salvas mostram o disco."""
        from codar.studio.linguagem import substituir_texto

        for ed in self.query(CodeEditor):
            if not ed.path:
                continue
            caminho = Path(ed.path)
            try:
                disco = caminho.read_bytes()
            except OSError:
                continue  # apagado: a aba fica com o texto, e Ctrl+S recria o arquivo
            if disco == getattr(ed, "disk_baseline", None):
                continue
            try:
                texto = caminho.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                continue
            if ed.dirty:
                if caminho not in self._git_avisados:
                    self._git_avisados.add(caminho)
                    self.notify(tr("{arquivo} mudou no disco; suas alterações não salvas continuam na aba (Ctrl+S "
                                   "grava por cima)").format(arquivo=caminho.name), severity="warning", timeout=8)
                continue
            self._git_avisados.discard(caminho)
            ed.saved_text, ed.disk_baseline = texto, disco
            substituir_texto(ed, texto)
            self._update_tab_label(ed)

    # ------------------------------------------------------------------ operações
    def _git_repo_ou_aviso(self) -> Repositorio | None:
        if self._repo is None:
            self.notify(tr("esta pasta não está num repositório git (paleta → Git: iniciar repositório)"),
                        severity="warning")
        return self._repo

    @work(thread=True, group="git-op", exit_on_error=False)
    def _git_op(self, rotulo: str, funcao, args: tuple = (), recarregar: bool = False, depois=None) -> None:
        try:
            with self._git_trava:
                resultado = funcao(*args)
        except (ErroGit, OSError) as exc:
            self.call_from_thread(self._git_falhou, rotulo, exc)
            return
        self.call_from_thread(self._git_depois, recarregar, depois, resultado)

    def _git_falhou(self, rotulo: str, exc: Exception) -> None:
        self.notify(f"{rotulo}: {exc}", severity="error", timeout=10)
        self.feed(f"GIT · {rotulo}: {str(exc).splitlines()[0][:80] if str(exc) else 'erro'}", "red")
        self.git_atualizar()

    def _git_depois(self, recarregar: bool, depois=None, resultado=None) -> None:
        self._git_originais.clear()
        self._git_assinatura = self._git_ler_assinatura()
        if depois is not None:
            depois(resultado)
        self.git_atualizar(recarregar=recarregar)

    def _git_mudou(self, recarregar: bool) -> None:
        """A tela de diferenças mudou o índice ou o arquivo."""
        self._git_depois(recarregar)

    def _git_item(self) -> tuple[str, Mudanca] | None:
        lista = self.query_one("#git-changes", OptionList)
        opcao = lista.highlighted_option
        return self._git_itens.get(opcao.id) if opcao is not None and opcao.id else None

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        if event.option_list.id != "git-changes" or not event.option.id:
            return
        item = self._git_itens.get(event.option.id)
        if item is None or self._repo is None:
            return
        chave, m = item
        if chave == "c":
            self._git_resolver_conflito(m)
        else:
            self.git_diferencas(m.caminho, preparada=chave == "p")

    def action_git_item(self, acao: str) -> None:
        item, repo = self._git_item(), self._repo
        if item is None or repo is None:
            return
        chave, m = item
        nome = m.caminho
        if acao == "abrir":
            self.run_worker(self._git_abrir_arquivo(nome, None), exit_on_error=False)
        elif acao == "preparar":
            if chave == "p" and not m.alterada:
                self.notify(tr("{arquivo} já está preparado").format(arquivo=nome))
                return
            if chave == "c" and self._git_tem_marcas(repo.absoluto(nome)):
                from codar.studio.explorer import ConfirmScreen

                self.push_screen(ConfirmScreen(tr("{arquivo} ainda tem marcas de conflito. Marcar como resolvido "
                                                  "assim mesmo?").format(arquivo=nome),
                                               tr("Enter na lista abre a resolução bloco a bloco.")),
                                 lambda ok: ok and self._git_op(tr("preparar"), repo.preparar, ([nome],)))
                return
            self._git_op(tr("preparar"), repo.preparar, ([nome],))
        elif acao == "despreparar":
            if chave != "p":
                self.notify(tr("{arquivo} não está preparado").format(arquivo=nome))
                return
            self._git_op(tr("despreparar"), repo.despreparar, ([nome, *([m.origem] if m.origem else [])],))
        elif acao == "descartar":
            self._git_descartar(repo, chave, m)

    def _git_descartar(self, repo: Repositorio, chave: str, m: Mudanca) -> None:
        from codar.studio.explorer import ConfirmScreen, LIXEIRA, nome_livre, pasta_lixeira

        if chave == "c":
            self.notify(tr("conflito: Enter resolve; para desistir do merge, paleta → Git: abortar merge"),
                        severity="warning")
            return
        if chave == "p" and not m.alterada:
            self.notify(tr("{arquivo} só tem alterações preparadas: desprepare (u) antes de descartar")
                        .format(arquivo=m.caminho), severity="warning")
            return
        if m.nova:
            def mover(ok: bool) -> None:
                if ok:
                    destino = nome_livre(pasta_lixeira(self.root), Path(m.caminho).name)
                    self._git_op(tr("descartar"), repo.mover_nao_rastreado, (m.caminho, destino), recarregar=True,
                                 depois=lambda _: self._git_apos_lixeira(m.caminho))
            self.push_screen(ConfirmScreen(tr("Mover o arquivo novo {arquivo} para a lixeira?").format(arquivo=m.caminho),
                                           tr("Ele ainda não está no git; fica em {lixeira}/, de onde dá para "
                                              "recuperar.").format(lixeira=LIXEIRA.as_posix())), mover)
            return

        def descartar(ok: bool) -> None:
            if ok:
                self._git_op(tr("descartar"), repo.descartar, ([m.caminho],), recarregar=True)
        self.push_screen(ConfirmScreen(tr("Descartar as alterações de {arquivo}?").format(arquivo=m.caminho),
                                       tr("O arquivo volta ao que está preparado (ou ao último commit). O git não "
                                          "guarda o que for descartado.")), descartar)

    def _git_apos_lixeira(self, caminho: str) -> None:
        from codar.studio.explorer import Explorer

        if self._repo is not None:
            self.arquivo_apagado(self._repo.raiz / caminho)  # a aba aberta deixa de apontar para o arquivo
        for explorer in self.query(Explorer):
            self.run_worker(explorer.reload(), exit_on_error=False)

    def action_git_preparar_tudo(self) -> None:
        if repo := self._git_repo_ou_aviso():
            self._git_op(tr("preparar tudo"), repo.preparar_tudo)

    async def _git_abrir_arquivo(self, caminho: str, linha: int | None) -> None:
        if self._repo is None:
            return
        alvo = self._repo.absoluto(caminho)
        if not alvo.is_file():
            self.notify(tr("{arquivo} não existe mais no disco").format(arquivo=caminho), severity="warning")
            return
        await self.open_file(alvo)
        ed = self.current_editor()
        if ed is None:
            return
        if linha is not None:
            ed.move_cursor((max(0, min(linha, ed.document.line_count - 1)), 0), center=True)
        ed.focus()

    def git_diferencas(self, caminho: str, preparada: bool = False) -> None:
        repo = self._repo
        if repo is None:
            return
        ed = self._git_editor_de(repo.absoluto(caminho))
        if ed is not None and ed.dirty:
            self.notify(tr("{arquivo} tem alterações não salvas: o git compara o que está no disco (Ctrl+S salva)")
                        .format(arquivo=Path(caminho).name), severity="warning", timeout=6)

        def fechada(linha: int | None) -> None:
            if linha is not None:
                self.run_worker(self._git_abrir_arquivo(caminho, linha), exit_on_error=False)
            else:
                self.query_one("#git-changes", OptionList).focus()

        self.push_screen(DiffScreen(repo, caminho, preparada, ao_mudar=self._git_mudou), fechada)

    def action_git_diff_atual(self) -> None:
        repo, ed = self._git_repo_ou_aviso(), self.current_editor()
        if repo is None:
            return
        if ed is None or not ed.path:
            self.notify(tr("abra um arquivo do repositório"), severity="warning")
            return
        try:
            rel = repo.relativo(ed.path)
            mudancas = [m for m in repo.estado().mudancas if m.caminho == rel]
        except (ValueError, ErroGit) as exc:
            self.notify(str(exc) if isinstance(exc, ErroGit) else tr("o arquivo está fora do repositório"),
                        severity="warning")
            return
        if not mudancas:
            self.notify(tr("{arquivo} não tem alterações no git").format(arquivo=Path(rel).name))
            return
        if mudancas[0].conflito:
            self._git_resolver_conflito(mudancas[0])
            return
        self.git_diferencas(rel, preparada=not (mudancas[0].alterada or mudancas[0].nova))

    # ------------------------------------------------------------------ conflitos
    @staticmethod
    def _git_tem_marcas(caminho: Path) -> bool:
        try:
            return bool(git.conflitos_no_texto(caminho.read_text(encoding="utf-8", errors="replace")))
        except OSError:
            return False

    def _git_resolver_conflito(self, m: Mudanca) -> None:
        from codar.studio.explorer import ConfirmScreen

        repo = self._repo
        caminho = repo.absoluto(m.caminho)
        ed = self._git_editor_de(caminho)
        try:
            if ed is not None:
                texto = ed.text
            else:
                with open(caminho, encoding="utf-8", newline="") as arquivo:  # mantém \r\n de arquivos do Windows
                    texto = arquivo.read()
        except (OSError, UnicodeDecodeError) as exc:
            self.notify(tr("não consegui ler {arquivo}: {erro}").format(arquivo=m.caminho, erro=exc), severity="error")
            return

        def marcar(ok: bool) -> None:
            if ok:
                self._git_op(tr("marcar como resolvido"), repo.preparar, ([m.caminho],),
                             depois=lambda _: self.notify(tr("{arquivo} resolvido; faça o commit para concluir o merge")
                                                          .format(arquivo=m.caminho)))
            else:
                self.git_atualizar()

        if not git.conflitos_no_texto(texto):
            self.push_screen(ConfirmScreen(tr("{arquivo} não tem mais marcas de conflito. Marcar como resolvido?")
                                           .format(arquivo=m.caminho), tr("Prepara o arquivo (git add).")), marcar)
            return

        def fechada(resolvido: bool) -> None:
            if resolvido:
                self.push_screen(ConfirmScreen(tr("Todos os conflitos de {arquivo} resolvidos. Marcar como resolvido?")
                                               .format(arquivo=m.caminho), tr("Prepara o arquivo (git add).")), marcar)
            else:
                self.git_atualizar()

        self.push_screen(ConflitoScreen(m.caminho, texto, lambda novo: self._git_gravar(caminho, novo)), fechada)

    def _git_gravar(self, caminho: Path, texto: str) -> None:
        """Grava a resolução: na aba aberta (e salva, porque o git lê o disco) ou direto no arquivo."""
        from codar.studio.linguagem import substituir_texto
        from codar.studio.saving import write_buffer

        ed = self._git_editor_de(caminho)
        if ed is not None:
            substituir_texto(ed, texto)
            self._write(ed)
            return
        try:
            write_buffer(caminho, texto)
        except (OSError, ValueError) as exc:
            self.notify(tr("erro ao salvar: {erro}").format(erro=exc), severity="error")

    def action_git_abortar_merge(self) -> None:
        from codar.studio.explorer import ConfirmScreen

        repo = self._git_repo_ou_aviso()
        if repo is None:
            return
        if self._git_estado is not None and not self._git_estado.em_merge:
            self.notify(tr("não há merge em andamento"))
            return
        self.push_screen(ConfirmScreen(tr("Abortar o merge?"),
                                       tr("Os arquivos voltam ao estado de antes do merge; resoluções feitas até "
                                          "aqui se perdem.")),
                         lambda ok: ok and self._git_op(tr("abortar merge"), repo.abortar_merge, recarregar=True))

    # ------------------------------------------------------------------ commit
    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id == "git-message":
            self.action_git_commit()

    def action_git_commit(self, emendar: bool = False) -> None:
        from codar.studio.explorer import ConfirmScreen

        repo = self._git_repo_ou_aviso()
        if repo is None:
            return
        campo = self.query_one("#git-message", Input)
        mensagem = campo.value.strip()
        if not mensagem and not emendar:
            self.action_git_painel()
            campo.focus()
            self.notify(tr("escreva a mensagem do commit e tecle Enter"), severity="warning")
            return
        sujos = [ed for ed in self.query(CodeEditor) if ed.path and ed.dirty
                 and Path(ed.path).resolve().is_relative_to(repo.raiz)]
        if sujos:
            def salvar(ok: bool) -> None:
                if ok:
                    for ed in sujos:
                        self._write(ed)
                self._git_commit_preparado(repo, mensagem, emendar)

            nomes = ", ".join(Path(ed.path).name for ed in sujos[:6]) + (" …" if len(sujos) > 6 else "")
            self.push_screen(ConfirmScreen(tr("Salvar {n} arquivo(s) antes do commit?").format(n=len(sujos)),
                                           tr("{nomes}. O commit usa o que está no disco.").format(nomes=nomes)),
                             salvar)
            return
        self._git_commit_preparado(repo, mensagem, emendar)

    def _git_commit_preparado(self, repo: Repositorio, mensagem: str, emendar: bool) -> None:
        from codar.studio.explorer import ConfirmScreen

        try:
            estado = repo.estado()
        except ErroGit as exc:
            self.notify(str(exc), severity="error")
            return
        if estado.conflitos:
            self.notify(tr("resolva os conflitos antes do commit (Enter no arquivo, no painel GIT)"), severity="warning")
            self.action_git_painel()
            return
        if emendar or estado.em_merge or any(m.preparada for m in estado.mudancas):
            self._git_op(tr("commit"), repo.commit, (mensagem, emendar), depois=self._git_commit_feito)
            return
        if not any(m.alterada or m.nova for m in estado.mudancas):
            self.notify(tr("nada para commitar: a árvore de trabalho está limpa"))
            return

        def tudo(ok: bool) -> None:
            if ok:
                self._git_op(tr("commit"), _preparar_e_commitar, (repo, mensagem), depois=self._git_commit_feito)

        self.push_screen(ConfirmScreen(tr("Nada preparado. Preparar todas as alterações e fazer o commit?"),
                                       tr("Inclui os arquivos novos (git add --all).")), tudo)

    def _git_commit_feito(self, curto: str) -> None:
        self.query_one("#git-message", Input).value = ""
        self.notify(tr("commit {hash} criado").format(hash=curto))
        self.feed(f"GIT · commit {curto}", "green")

    def action_git_emendar(self) -> None:
        from codar.studio.explorer import ConfirmScreen

        repo = self._git_repo_ou_aviso()
        if repo is None or not repo.tem_commits():
            return
        mensagem = self.query_one("#git-message", Input).value.strip()
        self.push_screen(ConfirmScreen(tr("Emendar o último commit com o que está preparado?"),
                                       (tr("A mensagem passa a ser: {mensagem}").format(mensagem=mensagem) if mensagem
                                        else tr("A mensagem continua a mesma.")) + " "
                                       + tr("Se o commit já foi enviado (push), emendar reescreve o histórico.")),
                         lambda ok: ok and self.action_git_commit(emendar=True))

    # ------------------------------------------------------------------ branches e histórico
    def action_git_branch(self) -> None:
        from codar.studio.review import ChoiceScreen

        repo = self._git_repo_ou_aviso()
        if repo is None:
            return
        try:
            branches = repo.branches()
        except ErroGit as exc:
            self.notify(str(exc), severity="error")
            return
        atual = next((b.nome for b in branches if b.atual), None)
        opcoes = [("+", tr("+ criar branch a partir de {atual}…").format(atual=atual or "HEAD"))]
        opcoes += [(f"l:{b.nome}", ("● " if b.atual else "  ") + b.nome + (f"  → {b.upstream}" if b.upstream else ""))
                   for b in branches if not b.remoto]
        opcoes += [(f"r:{b.nome}", f"  {b.nome}  " + tr("(remoto)")) for b in branches if b.remoto]

        def criar(nome: str | None) -> None:
            if nome:
                self._git_op(tr("criar branch"), repo.criar_branch, (nome,),
                             depois=lambda _: self.notify(tr("branch {nome} criada").format(nome=nome)))

        def escolhida(identidade: str | None) -> None:
            if identidade is None:
                return
            if identidade == "+":
                from codar.studio.screens import PromptScreen

                self.push_screen(PromptScreen(tr("nome da nova branch"), "ex.: feature/login"), criar)
                return
            tipo, nome = identidade.split(":", 1)
            if tipo == "l" and nome == atual:
                self.notify(tr("você já está em {nome}").format(nome=nome))
                return
            local = nome.split("/", 1)[1] if tipo == "r" and "/" in nome else nome  # git switch cria o rastreamento
            self._git_op(tr("trocar de branch"), repo.trocar_branch, (local,), recarregar=True,
                         depois=lambda _: self.notify(tr("agora em {nome}").format(nome=local)))

        self.push_screen(ChoiceScreen(tr("BRANCHES · Enter troca · Esc cancela"), opcoes), escolhida)

    def action_git_historico(self, do_arquivo: bool = False) -> None:
        from codar.studio.review import ChoiceScreen
        from codar.studio.screens import TerminalOutputScreen

        repo = self._git_repo_ou_aviso()
        if repo is None:
            return
        caminho = None
        if do_arquivo:
            ed = self.current_editor()
            try:
                caminho = repo.relativo(ed.path) if ed is not None and ed.path else None
            except ValueError:
                caminho = None
            if caminho is None:
                self.notify(tr("abra um arquivo do repositório"), severity="warning")
                return
        try:
            commits = repo.historico(300, caminho)
        except ErroGit as exc:
            self.notify(str(exc), severity="error")
            return
        if not commits:
            self.notify(tr("ainda não há commits") if caminho is None else tr("{arquivo} não tem commits")
                        .format(arquivo=caminho))
            return

        def escolhido(identidade: str | None) -> None:
            if not identidade:
                return
            try:
                texto = repo.detalhes(identidade)
            except ErroGit as exc:
                self.notify(str(exc), severity="error")
                return
            if len(texto) > LIMITE_DETALHES:
                texto = texto[:LIMITE_DETALHES] + "\n\n" + tr("… (cortado: use git show {hash} no terminal)").format(
                    hash=identidade)
            self.push_screen(TerminalOutputScreen(texto, f"commit {identidade}"))

        titulo = tr("HISTÓRICO") + (f" · {caminho}" if caminho else "") + " · " + tr("Enter mostra o commit")
        self.push_screen(ChoiceScreen(titulo, [(c.hash, f"{c.hash}  {c.data}  {c.autor[:18]:<18}  {c.assunto}")
                                               for c in commits]), escolhido)

    def action_git_historico_arquivo(self) -> None:
        self.action_git_historico(do_arquivo=True)

    # ------------------------------------------------------------------ rede (no terminal)
    def _git_terminal(self, comando: str) -> None:
        if repo := self._git_repo_ou_aviso():
            self.run_command(comando, cwd=repo.raiz)

    def action_git_pull(self) -> None:
        self._git_terminal("git pull --no-edit")

    def action_git_fetch(self) -> None:
        self._git_terminal("git fetch --all --prune")

    def action_git_push(self) -> None:
        repo = self._git_repo_ou_aviso()
        if repo is None:
            return
        estado = self._git_estado
        if estado is None or estado.branch is None:
            self.notify(tr("HEAD destacado: crie ou troque de branch antes do push"), severity="warning")
            return
        if estado.upstream:
            self._git_terminal("git push")
            return
        try:
            remotos = repo.remotos()
        except ErroGit as exc:
            self.notify(str(exc), severity="error")
            return
        if not remotos:
            self.notify(tr("nenhum remoto configurado: no terminal, git remote add origin <url>"), severity="warning")
            return
        remoto = "origin" if "origin" in remotos else remotos[0]
        self._git_terminal(f"git push -u {shlex.quote(remoto)} {shlex.quote(estado.branch)}")

    def git_programa_terminou(self) -> None:
        """Um comando do terminal terminou (pode ter sido git pull, um formatador...): relê o estado."""
        if self._repo is None and (self.root / ".git").exists():
            self._git_abrir()
        elif self._repo is not None:
            self._git_assinatura = self._git_ler_assinatura()
            self._git_originais.clear()
            self.git_atualizar(recarregar=True)

    def action_git_iniciar(self) -> None:
        from codar.studio.explorer import ConfirmScreen

        if self._repo is not None:
            self.notify(tr("já é um repositório git: {raiz}").format(raiz=self._repo.raiz))
            return

        def criar(ok: bool) -> None:
            if not ok:
                return
            try:
                Repositorio.iniciar(self.root)
            except ErroGit as exc:
                self.notify(str(exc), severity="error")
                return
            self._git_abrir()
            self.notify(tr("repositório git criado em {raiz}").format(raiz=self.root))

        self.push_screen(ConfirmScreen(tr("Criar um repositório git em {raiz}?").format(raiz=self.root),
                                       tr("Roda git init nesta pasta.")), criar)

    def git_comandos_paleta(self) -> list[tuple[str, str, object]]:
        return [
            ("Git: painel de controle de versão", "Alt+G — alterações, preparadas e conflitos", self.action_git_painel),
            ("Git: commit do que está preparado", "mensagem no painel GIT + Enter", self.action_git_commit),
            ("Git: emendar o último commit", "junta o que está preparado ao último commit", self.action_git_emendar),
            ("Git: preparar tudo", "git add --all", self.action_git_preparar_tudo),
            ("Git: diferenças do arquivo atual", "trecho a trecho: s prepara, u desprepara, d descarta",
             self.action_git_diff_atual),
            ("Git: trocar ou criar branch", "lista local e remota", self.action_git_branch),
            ("Git: histórico do projeto", "commits com o diff de cada um", self.action_git_historico),
            ("Git: histórico do arquivo atual", "segue renomeações", self.action_git_historico_arquivo),
            ("Git: pull", "no terminal integrado", self.action_git_pull),
            ("Git: push", "no terminal; publica a branch se ainda não tem remoto", self.action_git_push),
            ("Git: buscar do remoto (fetch)", "atualiza ↑ e ↓ sem mexer nos arquivos", self.action_git_fetch),
            ("Git: abortar merge", "volta ao estado de antes do merge", self.action_git_abortar_merge),
            ("Git: iniciar repositório", "git init na pasta do projeto", self.action_git_iniciar),
        ]


def _preparar_e_commitar(repo: Repositorio, mensagem: str) -> str:
    repo.preparar_tudo()
    return repo.commit(mensagem)
