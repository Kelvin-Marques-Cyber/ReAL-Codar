"""Depurador no Studio (DAP): breakpoints na margem, execução passo a passo, pilha, variáveis e console.

Ctrl+F5 depura o arquivo atual: Python pelo debugpy; C, C++ e Rust são compilados com informações de depuração e
rodam no GDB (modo DAP, versão 14 ou mais nova). Durante a depuração, as teclas seguem o VS Code: F5 continua,
F10 passa por cima, F11 entra, Shift+F11 sai e Shift+F5 para. Fora dela, F5 executa e F10 completa, como antes.
"""

from __future__ import annotations

import asyncio
import shlex
import subprocess
from pathlib import Path

from rich.text import Text
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.widgets import Input, OptionList, RichLog, Static, TabbedContent, Tree
from textual.widgets.option_list import Option

from codar.i18n import tr
from codar.ide import dap
from codar.ide.dap import ErroDAP, Quadro, SessaoDAP
from codar.studio import estado
from codar.studio.widgets import C, Botao, CodeEditor

ATALHOS = [
    Binding("ctrl+f5", "dap_iniciar", tr("Depurar"), show=False, priority=True),
    Binding("alt+b", "dap_breakpoint", tr("Breakpoint"), show=False, priority=True),
    Binding("f11", "dap_entrar", tr("Entrar"), show=False, priority=True),
    Binding("shift+f11", "dap_sair", tr("Sair da função"), show=False, priority=True),
    Binding("shift+f5", "dap_parar", tr("Parar depuração"), show=False, priority=True),
]
_FALHAS = (ErroDAP, ConnectionError, OSError, asyncio.TimeoutError)
_LINGUAGENS = "Python, C, C++ e Rust"


class DepuracaoMixin:
    """Parte do Studio que conversa com o depurador."""

    def _dap_init(self) -> None:
        self._sessao: SessaoDAP | None = None
        self._quadros: list[Quadro] = []
        self._quadro_atual: int | None = None
        self._dap_arquivo: Path | None = None
        self._dap_pendente = ("", None)  # saída sem quebra de linha ainda (texto, cor)
        self._dap_timer = None
        guardados = estado.ler().get("breakpoints", {}).get(str(self.root), {})
        # Breakpoints de arquivos fechados; os dos abertos ficam no próprio editor (que os desloca ao editar).
        self._breakpoints: dict[Path, set[int]] = {(self.root / rel).resolve(): set(linhas)
                                                    for rel, linhas in guardados.items() if isinstance(linhas, list)}

    # ------------------------------------------------------------------ painel
    def compor_depuracao(self):
        with Horizontal(id="debug-tools"):
            yield Botao(tr("▶ DEPURAR Ctrl+F5"), acao="dap_iniciar", id="debug-start")
            yield Botao(tr("⏵ CONTINUAR F5"), acao="dap_continuar", id="debug-continue")
            yield Botao(tr("⤼ PASSAR F10"), acao="dap_passar", id="debug-over")
            yield Botao(tr("↓ ENTRAR F11"), acao="dap_entrar", id="debug-in")
            yield Botao(tr("↑ SAIR ⇧F11"), acao="dap_sair", id="debug-out")
            yield Botao(tr("■ PARAR ⇧F5"), acao="dap_parar", id="debug-stop")
        yield Static(tr("Ctrl+F5 depura o arquivo atual ({linguagens}). Alt+B ou clique na margem: breakpoint.")
                     .format(linguagens=_LINGUAGENS), id="debug-status")
        with Horizontal(id="debug-body"):
            with Vertical(id="debug-stack-box"):
                yield Static(tr("PILHA"), classes="debug-title")
                yield OptionList(id="debug-stack")
            with Vertical(id="debug-vars-box"):
                yield Static(tr("VARIÁVEIS"), classes="debug-title")
                yield Tree(tr("variáveis"), id="debug-vars")
            with Vertical(id="debug-console-box"):
                yield Static(tr("CONSOLE"), classes="debug-title")
                yield RichLog(id="debug-console", wrap=True, markup=False, max_lines=3000)
                yield Input(placeholder=tr("avaliar expressão no quadro atual (Enter)"), id="debug-eval")

    def dap_montar(self) -> None:
        arvore = self.query_one("#debug-vars", Tree)
        arvore.show_root = False
        arvore.root.expand()

    def dap_ativo(self) -> bool:
        return self._sessao is not None and not self._sessao.terminou

    def _dap_status(self, texto: str, cor: str = "text") -> None:
        self.query_one("#debug-status", Static).update(Text(texto, style=C.get(cor, C["text"])))

    def _dap_console(self, texto: str, cor: str | None = None) -> None:
        self._dap_descarregar()
        self.query_one("#debug-console", RichLog).write(Text(texto.rstrip("\n"), style=C.get(cor, C["text"]) if cor else ""))

    def _dap_saida(self, texto: str, cor: str | None) -> None:
        """Saída do programa chega em pedaços (print("a", 1) vira três eventos): junta até a quebra de linha."""
        pendente, cor_pendente = self._dap_pendente
        if pendente and cor_pendente != cor:
            self._dap_descarregar()
            pendente = ""
        *linhas, resto = (pendente + texto).split("\n")
        log = self.query_one("#debug-console", RichLog)
        for linha in linhas:
            log.write(Text(linha, style=C.get(cor, C["text"]) if cor else ""))
        self._dap_pendente = (resto, cor)
        if self._dap_timer is not None:
            self._dap_timer.stop()
        self._dap_timer = self.set_timer(.2, self._dap_descarregar) if resto else None

    def _dap_descarregar(self) -> None:
        texto, cor = self._dap_pendente
        self._dap_pendente = ("", None)
        if self._dap_timer is not None:
            self._dap_timer.stop()
            self._dap_timer = None
        if texto:
            self.query_one("#debug-console", RichLog).write(Text(texto, style=C.get(cor, C["text"]) if cor else ""))

    def _dap_mostrar_painel(self) -> None:
        painel = self.query_one("#panel", TabbedContent)
        painel.display = True
        painel.active = "tab-depurar"
        if not painel.has_class("maximizado"):
            painel.add_class("alto")

    # ------------------------------------------------------------------ breakpoints
    def _salvar_breakpoints(self) -> None:
        todos = {p: set(l) for p, l in self._breakpoints.items()}
        for ed in self.query(CodeEditor):
            if ed.path:
                todos[Path(ed.path).resolve()] = set(ed.breakpoints)
        guardados = {}
        for caminho, linhas in todos.items():
            if linhas and caminho.is_relative_to(self.root):
                guardados[caminho.relative_to(self.root).as_posix()] = sorted(linhas)
        por_projeto = {k: v for k, v in estado.ler().get("breakpoints", {}).items() if k != str(self.root)}
        if guardados:
            por_projeto[str(self.root)] = guardados
        estado.salvar(breakpoints=dict(list(por_projeto.items())[-50:]))

    def dap_documento_aberto(self, ed: CodeEditor) -> None:
        if ed.path:
            ed.breakpoints = set(self._breakpoints.pop(Path(ed.path).resolve(), set()))

    def dap_documento_salvo(self, ed: CodeEditor) -> None:
        """Ao salvar, os breakpoints deslocados pela edição são guardados e reenviados à depuração em curso."""
        if ed.breakpoints or Path(ed.path).resolve() in self._breakpoints:
            self._salvar_breakpoints()
        if self.dap_ativo() and ed.path:
            self.run_worker(self._dap_enviar_breakpoints(ed), group="dap-bp", exit_on_error=False)

    def dap_documento_fechado(self, ed: CodeEditor) -> None:
        if ed.path and ed.breakpoints:
            self._breakpoints[Path(ed.path).resolve()] = set(ed.breakpoints)

    def _alternar_breakpoint(self, ed: CodeEditor, linha: int) -> None:
        if not ed.path:
            self.notify(tr("salve o arquivo antes de marcar breakpoints"), severity="warning")
            return
        ed.breakpoints ^= {linha}
        ed.refresh()
        self._salvar_breakpoints()
        if self.dap_ativo():
            self.run_worker(self._dap_enviar_breakpoints(ed), group="dap-bp", exit_on_error=False)

    async def _dap_enviar_breakpoints(self, ed: CodeEditor) -> None:
        try:
            await self._sessao.definir_breakpoints(Path(ed.path), sorted(ed.breakpoints))
        except _FALHAS as exc:
            self._dap_console(f"breakpoints: {exc}", "error")

    def action_dap_breakpoint(self) -> None:
        ed = self.current_editor()
        if ed is not None:
            self._alternar_breakpoint(ed, ed.cursor_location[0])

    def on_code_editor_margem_clicada(self, event: CodeEditor.MargemClicada) -> None:
        self._alternar_breakpoint(event.editor, event.linha)

    def _todos_breakpoints(self) -> dict[Path, list[int]]:
        todos = {p: sorted(l) for p, l in self._breakpoints.items() if l}
        for ed in self.query(CodeEditor):
            if ed.path and ed.breakpoints:
                todos[Path(ed.path).resolve()] = sorted(ed.breakpoints)
        return todos

    # ------------------------------------------------------------------ iniciar e parar
    async def action_dap_iniciar(self) -> None:
        if self.dap_ativo():
            self.notify(tr("já há uma depuração em andamento (Shift+F5 para)"), severity="warning")
            return
        ed = self.current_editor()
        if ed is None or not ed.path or not ed.lang_id:
            self.notify(tr("abra e salve o arquivo que deseja depurar"), severity="warning")
            return
        if ed.dirty:
            self._write(ed)
        from codar import toolchains
        from codar.advisor.pacotes import python_do_projeto

        env = toolchains.environment(project=self.root)
        caminho = Path(ed.path).resolve()
        plano = dap.plano(ed.lang_id, caminho, self.root, python=python_do_projeto(self.root), env=env)
        if plano is None:
            self.notify(tr("o depurador integrado atende {linguagens}; use F5 para executar este arquivo")
                        .format(linguagens=_LINGUAGENS), severity="warning")
            return
        if plano.falta:
            if plano.instalar:
                from codar.studio.explorer import ConfirmScreen

                comando = shlex.join(plano.instalar)
                self.push_screen(ConfirmScreen(tr("Instalar o depurador no ambiente do projeto?"),
                                               f"{plano.falta}.\n\n{comando}"),
                                 lambda sim: self.run_command(comando) if sim else None)
                return
            self.notify(tr("não dá para depurar agora: {motivo}").format(motivo=plano.falta), severity="error")
            return
        self._dap_mostrar_painel()
        self.query_one("#debug-console", RichLog).clear()
        self._dap_limpar_parada()
        if plano.compilar:
            self._dap_status(tr("compilando {arquivo} com informações de depuração…").format(arquivo=caminho.name), "cyan")
            try:
                resultado = await asyncio.to_thread(subprocess.run, plano.compilar, cwd=self.root, env=env,
                                                    capture_output=True, text=True, timeout=180)
            except (OSError, subprocess.TimeoutExpired) as exc:
                self._dap_status(tr("a compilação falhou: {erro}").format(erro=exc), "error")
                return
            if resultado.returncode:
                self._dap_console(resultado.stdout + resultado.stderr, "error")
                self._dap_status(tr("a compilação falhou; veja o console"), "error")
                return
        self._dap_arquivo = caminho
        self._sessao = SessaoDAP(plano.adaptador, self.root, env, ao_evento=self._dap_evento)
        self._dap_status(tr("iniciando {adaptador}…").format(adaptador=Path(plano.adaptador[0]).name), "cyan")
        try:
            await self._sessao.iniciar(plano.adapter_id, plano.lancamento, self._todos_breakpoints(),
                                       configurar_antes=plano.configurar_antes)
        except _FALHAS as exc:
            self._sessao = None
            self._dap_status(tr("a depuração não começou: {erro}").format(erro=str(exc).splitlines()[0]), "error")
            self._dap_console(str(exc), "error")
            return
        self.feed(f"DEBUG · {caminho.name}", "orange")
        if not self._sessao.terminou and self._sessao.parado_em is None:
            self._dap_status(tr("executando {arquivo}… (F5 continua quando parar)").format(arquivo=caminho.name), "mint")

    async def action_dap_parar(self) -> None:
        if self._sessao is None:
            return
        sessao, self._sessao = self._sessao, None
        await sessao.encerrar()
        self._dap_terminou(tr("depuração interrompida"))

    def dap_encerrar_agora(self) -> None:
        if self._sessao is not None:
            self._sessao.processo.terminar_agora()

    # ------------------------------------------------------------------ eventos do adaptador
    def _dap_evento(self, nome: str, corpo: dict) -> None:
        if nome == "output":
            categoria = corpo.get("category") or "console"
            self._dap_saida(str(corpo.get("output", "")), {"stderr": "error", "console": "dim",
                                                          "important": "orange"}.get(categoria))
        elif nome == "stopped":
            self.run_worker(self._dap_parou(str(corpo.get("reason") or ""), str(corpo.get("description") or "")),
                            group="dap-parou", exclusive=True, exit_on_error=False)
        elif nome == "continued":
            self._dap_limpar_parada()
            self._dap_status(tr("executando…"), "mint")
        elif nome in ("terminated", "exited"):
            sessao = self._sessao
            if sessao is not None and (nome == "terminated" or sessao.terminou):
                codigo = sessao.codigo_saida
                self._sessao = None
                self.run_worker(sessao.encerrar(), group="dap-fim", exit_on_error=False)
                self._dap_terminou(tr("o programa terminou") + (f" (código {codigo})" if codigo is not None else ""))
            elif nome == "exited" and sessao is not None:
                self._dap_status(tr("o programa terminou (código {codigo})").format(codigo=corpo.get("exitCode")), "dim")

    def _dap_terminou(self, mensagem: str) -> None:
        self._dap_descarregar()
        self._dap_limpar_parada()
        self._quadros = []
        self.query_one("#debug-stack", OptionList).clear_options()
        self.query_one("#debug-vars", Tree).root.remove_children()
        self._dap_status(mensagem, "dim")
        self.query_one("#panel", TabbedContent).remove_class("alto")
        self.feed("DEBUG · " + mensagem, "dim")

    def _dap_limpar_parada(self) -> None:
        for ed in self.query(CodeEditor):
            if ed.linha_depuracao is not None:
                ed.linha_depuracao = None
                ed.refresh()

    async def _dap_parou(self, motivo: str, descricao: str) -> None:
        sessao = self._sessao
        if sessao is None:
            return
        self._dap_descarregar()
        try:
            self._quadros = await sessao.pilha()
        except _FALHAS as exc:
            self._dap_status(tr("parado, mas a pilha não veio: {erro}").format(erro=exc), "error")
            return
        lista = self.query_one("#debug-stack", OptionList)
        lista.clear_options()
        lista.add_options([Option(Text(f"{q.nome}  {q.caminho.name if q.caminho else '?'}:{q.linha + 1}"), id=str(i))
                           for i, q in enumerate(self._quadros)])
        motivos = {"breakpoint": tr("breakpoint"), "step": tr("passo"), "exception": tr("exceção"),
                   "pause": tr("pausa"), "entry": tr("início")}
        topo = self._quadros[0] if self._quadros else None
        onde = f"{topo.caminho.name if topo and topo.caminho else '?'}:{topo.linha + 1 if topo else '?'}"
        self._dap_status(tr("PARADO · {motivo} · {onde} · F5 continua · F10 passa · F11 entra")
                         .format(motivo=motivos.get(motivo, motivo or "?"), onde=onde) + (f" · {descricao}" if descricao else ""),
                         "orange")
        self._dap_mostrar_painel()
        if topo is not None:
            await self._dap_selecionar(0, focar_editor=True)

    async def _dap_selecionar(self, indice: int, focar_editor: bool = False) -> None:
        quadro = self._quadros[indice]
        self._quadro_atual = quadro.id
        self._dap_limpar_parada()
        if quadro.caminho is not None and quadro.caminho.is_file():
            await self.open_file(quadro.caminho.resolve())
            ed = self.current_editor()
            if ed is not None:
                linha = min(quadro.linha, ed.document.line_count - 1)
                ed.linha_depuracao = linha
                ed.move_cursor((linha, 0), center=True)
                ed.refresh()
                if focar_editor:
                    ed.focus()
        await self._dap_variaveis(quadro.id)

    async def _dap_variaveis(self, quadro: int) -> None:
        arvore = self.query_one("#debug-vars", Tree)
        arvore.root.remove_children()
        try:
            escopos = await self._sessao.escopos(quadro)
        except _FALHAS as exc:
            arvore.root.add_leaf(Text(f"{exc}", style=C["error"]))
            return
        for i, escopo in enumerate(escopos):
            no = arvore.root.add(Text(escopo.nome, style=f"bold {C['orange']}"), data=escopo.referencia)
            if i == 0 and not escopo.caro:
                await self._dap_filhos(no)
                no.expand()

    async def _dap_filhos(self, no) -> None:
        if no.data is None or getattr(no, "_carregado", False):
            return
        no._carregado = True
        try:
            variaveis = await self._sessao.variaveis(no.data)
        except _FALHAS as exc:
            no.add_leaf(Text(str(exc), style=C["error"]))
            return
        for v in variaveis:
            rotulo = Text.assemble((v.nome, C["cyan"]), (" = ", C["dim"]), (v.valor[:200], C["text"]),
                                   ((f"  {v.tipo}", C["dim"]) if v.tipo else ("", "")))
            if v.referencia:
                no.add(rotulo, data=v.referencia)
            else:
                no.add_leaf(rotulo)

    def on_tree_node_expanded(self, event: Tree.NodeExpanded) -> None:
        if event.node.tree.id == "debug-vars" and self.dap_ativo():
            self.run_worker(self._dap_filhos(event.node), group="dap-vars", exit_on_error=False)

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        if event.option_list.id == "debug-stack" and self.dap_ativo() and event.option.id is not None:
            self.run_worker(self._dap_selecionar(int(event.option.id)), group="dap-quadro", exclusive=True,
                            exit_on_error=False)

    async def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id != "debug-eval":
            return
        expressao = event.value.strip()
        event.input.value = ""
        if not expressao:
            return
        if not self.dap_ativo() or self._sessao.parado_em is None:
            self._dap_console(tr("a avaliação funciona com o programa parado"), "dim")
            return
        self._dap_console(f"› {expressao}", "cyan")
        try:
            self._dap_console("  " + await self._sessao.avaliar(expressao, self._quadro_atual))
        except _FALHAS as exc:
            self._dap_console(f"  {exc}", "error")

    # ------------------------------------------------------------------ passos
    async def _dap_passo(self, nome: str) -> None:
        if not self.dap_ativo():
            return
        if self._sessao.parado_em is None and nome != "pausar":
            self.notify(tr("o programa está executando; ele precisa parar num breakpoint"), severity="warning")
            return
        try:
            await getattr(self._sessao, nome)()
        except _FALHAS as exc:
            self._dap_console(f"{nome}: {exc}", "error")

    async def action_dap_continuar(self) -> None:
        await self._dap_passo("continuar")

    async def action_dap_passar(self) -> None:
        await self._dap_passo("proximo")

    async def action_dap_entrar(self) -> None:
        await self._dap_passo("entrar")

    async def action_dap_sair(self) -> None:
        await self._dap_passo("sair")
