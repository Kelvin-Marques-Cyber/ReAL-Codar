"""Servidores de linguagem (LSP) no Studio: diagnósticos enquanto você digita, definição, referências, informações,
renomear, formatar e completar.

Os servidores são programas instalados à parte (pylsp, pyright, typescript-language-server, gopls, rust-analyzer,
clangd...). Alguns executam código do projeto para analisá-lo, como os scripts de build do Rust; por isso só começam
depois que o projeto é marcado como confiável (Alt+L), e a escolha fica guardada por projeto.
"""

from __future__ import annotations

import asyncio
import os
import re
from pathlib import Path

from textual.binding import Binding

from codar.i18n import tr
from codar.ide import lsp
from codar.ide.lsp import ErroLSP, GerenteLSP, Local
from codar.studio import estado
from codar.studio.widgets import CodeEditor

ATALHOS = [
    Binding("alt+l", "lsp_ativar", tr("Servidores de linguagem"), show=False, priority=True),
    Binding("alt+d", "lsp_definicao", tr("Ir para a definição"), show=False, priority=True),
    Binding("alt+u,shift+f12", "lsp_referencias", tr("Referências"), show=False, priority=True),
    Binding("alt+h", "lsp_informacoes", tr("Informações do símbolo"), show=False, priority=True),
    Binding("alt+r", "lsp_renomear", tr("Renomear símbolo"), show=False, priority=True),
    Binding("alt+f,alt+shift+f", "lsp_formatar", tr("Formatar documento"), show=False, priority=True),
    Binding("ctrl+space", "complete_symbol", tr("Completar"), show=False, priority=True),
]
_ORDEM = {"error": 0, "warning": 1, "info": 2, "hint": 3}
_FALHAS = (ErroLSP, ConnectionError, OSError, asyncio.TimeoutError)


def substituir_texto(ed: CodeEditor, novo: str) -> None:
    """Troca o texto do editor numa única edição (um Ctrl+Z desfaz), mantendo o cursor onde dá."""
    if novo == ed.text:
        return
    row, col = ed.cursor_location
    ed.replace(novo, (0, 0), ed.document.end)
    row = min(row, ed.document.line_count - 1)
    ed.cursor_location = (row, min(col, len(ed.document.get_line(row))))


class LinguagemMixin:
    """Parte do Studio que conversa com os servidores de linguagem."""

    def _lsp_init(self) -> None:
        self._lsp: GerenteLSP | None = None
        self._lsp_diags: dict[Path, list] = {}
        self._lsp_timers: dict[str, object] = {}
        self._lsp_avisos: set[str] = set()
        self._ultima_auditoria: tuple[str, list] | None = None

    # ------------------------------------------------------------------ configuração e confiança
    @staticmethod
    def _lsp_cfg() -> dict:
        from codar import config

        return config.load().get("lsp", {}) or {}

    def lsp_confiavel(self) -> bool:
        cfg = self._lsp_cfg()
        if cfg.get("enabled", True) is False:
            return False
        return bool(cfg.get("trust_all")) or str(self.root) in estado.ler().get("lsp_confiaveis", [])

    def _lsp_gerente(self) -> GerenteLSP:
        if self._lsp is None:
            from codar import toolchains
            from codar.advisor.pacotes import python_do_projeto

            env = toolchains.environment(project=self.root)
            pastas = [self.root / p for p in (".venv/bin", "venv/bin", ".venv/Scripts", "venv/Scripts", "node_modules/.bin")]
            env["PATH"] = os.pathsep.join([str(p) for p in pastas if p.is_dir()] + [env.get("PATH", "")])
            self._lsp = GerenteLSP(self.root, env=env, servidores=self._lsp_cfg().get("servers") or None,
                                   ao_diagnosticar=self._lsp_diagnosticos,
                                   configuracao=lsp.configuracao_padrao(python_do_projeto(self.root)))
        return self._lsp

    def _lsp_sugerir(self, lang: str) -> None:
        """Uma vez por linguagem: há um servidor instalado, mas o projeto ainda não foi marcado como confiável."""
        if lang in self._lsp_avisos or self._lsp_cfg().get("enabled", True) is False:
            return
        comando = self._lsp_gerente().comando(lang)
        if comando:
            self._lsp_avisos.add(lang)
            self.notify(tr("{servidor} disponível. Alt+L ativa diagnósticos, definição e referências neste projeto.")
                        .format(servidor=Path(comando[0]).name), timeout=8)

    def action_lsp_ativar(self) -> None:
        if self.lsp_confiavel():
            from codar.studio.explorer import ConfirmScreen

            self.push_screen(ConfirmScreen(tr("Desativar os servidores de linguagem neste projeto?"),
                                           tr("Diagnósticos, definição e referências deixam de funcionar até ativar de novo.")),
                             self._lsp_desativar)
            return
        if self._lsp_cfg().get("enabled", True) is False:
            self.notify(tr("Servidores de linguagem desligados na configuração ([lsp] enabled = false)."), severity="warning")
            return
        gerente = self._lsp_gerente()
        achados = []
        for lang in sorted(lsp.SERVIDORES):
            if comando := gerente.comando(lang):
                achados.append(f"{lang}: {Path(comando[0]).name}")
        from codar.studio.explorer import ConfirmScreen

        detalhe = ("\n".join(achados) if achados else tr("Nenhum servidor instalado ainda (ex.: pip install python-lsp-server)."))
        detalhe += "\n\n" + tr("Os servidores analisam o código do projeto e alguns executam scripts de build "
                               "(rust-analyzer, gopls). Ative só em projetos em que você confia.")
        self.push_screen(ConfirmScreen(tr("Ativar os servidores de linguagem neste projeto?"), detalhe), self._lsp_confirmar)

    def _lsp_confirmar(self, sim: bool | None) -> None:
        if not sim:
            return
        confiaveis = [p for p in estado.ler().get("lsp_confiaveis", []) if p != str(self.root)]
        estado.salvar(lsp_confiaveis=[*confiaveis, str(self.root)][-200:])
        self.feed("LSP · projeto marcado como confiável", "cyan")
        for ed in self.query(CodeEditor):
            self.lsp_documento_aberto(ed)
        self.render_status()

    def _lsp_desativar(self, sim: bool | None) -> None:
        if not sim:
            return
        estado.salvar(lsp_confiaveis=[p for p in estado.ler().get("lsp_confiaveis", []) if p != str(self.root)])
        gerente, self._lsp = self._lsp, None
        self._lsp_diags.clear()
        for ed in self.query(CodeEditor):
            ed.marcas_diagnostico, ed.mensagens_diagnostico = {}, {}
            ed.refresh()
        if gerente is not None:
            self.run_worker(gerente.encerrar(), group="lsp", exit_on_error=False)
        self._lsp_atualizar_problemas()
        self.feed("LSP · servidores encerrados", "dim")
        self.render_status()

    # ------------------------------------------------------------------ documentos
    def lsp_documento_aberto(self, ed: CodeEditor) -> None:
        if not ed.path or not ed.lang_id:
            return
        if not self.lsp_confiavel():
            self._lsp_sugerir(ed.lang_id)
            return
        self.run_worker(self._lsp_abrir(ed), group="lsp", exit_on_error=False)

    async def _lsp_abrir(self, ed: CodeEditor) -> None:
        caminho, lang, texto = Path(ed.path), ed.lang_id, ed.text
        gerente = self._lsp_gerente()
        try:
            cliente = await gerente.abrir(caminho, lang, texto)
        except _FALHAS as exc:
            self.notify(tr("servidor de linguagem: {erro}").format(erro=exc), severity="error")
            return
        if cliente is None:
            motivo = gerente.estado().get(lsp.grupo(lang), "")
            if motivo and ("motivo:" + lang) not in self._lsp_avisos:
                self._lsp_avisos.add("motivo:" + lang)
                self.feed(f"LSP · {lang}: {motivo.splitlines()[0][:120]}", "dim")
            return
        self.feed(f"LSP · {cliente.nome} · {caminho.name}", "cyan")
        if ed.is_mounted and ed.text != texto:  # digitou enquanto o servidor iniciava
            await gerente.alterar(caminho, ed.text)
        self.render_status()

    def lsp_documento_alterado(self, ed: CodeEditor) -> None:
        if self._lsp is None or not ed.path or not self._lsp.aberto(Path(ed.path)):
            return
        if timer := self._lsp_timers.pop(ed.id, None):
            timer.stop()
        self._lsp_timers[ed.id] = self.set_timer(.3, lambda: self._lsp_enviar(ed))

    def _lsp_enviar(self, ed: CodeEditor) -> None:
        self._lsp_timers.pop(ed.id, None)
        if self._lsp is not None and ed.is_mounted and ed.path:
            self.run_worker(self._lsp_seguro(self._lsp.alterar(Path(ed.path), ed.text)), group="lsp",
                            exit_on_error=False)

    def lsp_documento_salvo(self, ed: CodeEditor) -> None:
        if self._lsp is not None and ed.path and self._lsp.aberto(Path(ed.path)):
            self.run_worker(self._lsp_seguro(self._lsp.salvar(Path(ed.path), ed.text)), group="lsp", exit_on_error=False)
        elif ed.path and self.lsp_confiavel():
            self.lsp_documento_aberto(ed)  # arquivo novo salvo pela primeira vez

    def lsp_documento_fechado(self, ed: CodeEditor) -> None:
        if not ed.path:
            return
        caminho = Path(ed.path).resolve()
        if timer := self._lsp_timers.pop(ed.id, None):
            timer.stop()
        if any(o is not ed and o.path and Path(o.path).resolve() == caminho for o in self.query(CodeEditor)):
            return
        self._lsp_diags.pop(caminho, None)
        if self._lsp is not None and self._lsp.aberto(caminho):
            self.run_worker(self._lsp_seguro(self._lsp.fechar(caminho)), group="lsp", exit_on_error=False)

    async def _lsp_seguro(self, corrotina) -> None:
        try:
            await corrotina
        except _FALHAS as exc:
            if "conexao" not in self._lsp_avisos:
                self._lsp_avisos.add("conexao")
                self.notify(tr("o servidor de linguagem parou: {erro}. Alt+L duas vezes reinicia.").format(erro=exc),
                            severity="warning")

    def lsp_encerrar_agora(self) -> None:
        """Na saída do Studio: termina os servidores sem esperar o protocolo de encerramento."""
        if self._lsp is None:
            return
        for estado_servidor in self._lsp._estados.values():
            if estado_servidor.cliente is not None:
                estado_servidor.cliente.processo.terminar_agora()

    # ------------------------------------------------------------------ diagnósticos
    def _editores_de(self, caminho: Path) -> list[CodeEditor]:
        return [ed for ed in self.query(CodeEditor) if ed.path and Path(ed.path).resolve() == caminho]

    def _lsp_diagnosticos(self, caminho: Path, diags: list) -> None:
        if not self.lsp_confiavel():
            return  # diagnóstico atrasado de um servidor que está sendo encerrado
        caminho = Path(caminho).resolve()
        self._lsp_diags[caminho] = diags
        marcas, mensagens = {}, {}
        for d in sorted(diags, key=lambda d: _ORDEM.get(d.severidade, 9), reverse=True):
            marcas[d.intervalo.linha] = d.severidade  # a mais grave da linha fica por último
            mensagens[d.intervalo.linha] = d.mensagem
        for ed in self._editores_de(caminho):
            ed.marcas_diagnostico, ed.mensagens_diagnostico = marcas, mensagens
            ed.refresh()
        atual = self.current_editor()
        if atual is not None and atual.path and Path(atual.path).resolve() == caminho:
            self._lsp_atualizar_problemas()
        self.render_status()

    def _lsp_linhas(self, caminho: Path) -> list[dict]:
        return [{"severity": "info" if d.severidade in ("info", "hint") else d.severidade,
                 "id": ":".join(x for x in (d.fonte, d.codigo) if x) or "LSP",
                 "line": d.intervalo.linha + 1, "message": d.mensagem, "file": str(caminho)}
                for d in self._lsp_diags.get(caminho, [])]

    def _lsp_atualizar_problemas(self) -> None:
        """PROBLEMAS do arquivo ativo: diagnósticos do servidor e, se houver, a última auditoria (F6) dele."""
        ed = self.current_editor()
        if ed is None or not ed.path:
            return
        caminho = Path(ed.path).resolve()
        auditoria = self._ultima_auditoria[1] if self._ultima_auditoria and self._ultima_auditoria[0] == str(caminho) else []
        linhas = self._lsp_linhas(caminho)
        if linhas or auditoria or caminho in self._lsp_diags:
            self._show_findings(linhas + auditoria, 0, absolute=True, focar=False)

    def mostrar_auditoria(self, caminho: str | None, achados: list[dict]) -> None:
        """F6: a auditoria aparece junto dos diagnósticos do servidor do mesmo arquivo."""
        alvo = Path(caminho).resolve() if caminho else None
        self._ultima_auditoria = (str(alvo), achados) if alvo else None
        self._show_findings(achados + (self._lsp_linhas(alvo) if alvo else []), 0, True)

    def lsp_rotulo(self) -> str:
        ed = self.current_editor()
        if ed is None or not ed.path or not ed.lang_id or self._lsp_cfg().get("enabled", True) is False:
            return ""
        if not self.lsp_confiavel():
            return "LSP ALT+L" if self._lsp_gerente().comando(ed.lang_id) else ""
        if self._lsp is not None and self._lsp.aberto(Path(ed.path)):
            cliente = self._lsp._do_documento(Path(ed.path))
            erros = sum(d.severidade == "error" for d in self._lsp_diags.get(Path(ed.path).resolve(), []))
            return f"LSP {cliente.nome}" + (f" ✗{erros}" if erros else " ✓")
        return ""

    # ------------------------------------------------------------------ ações
    def _lsp_alvo(self) -> tuple[CodeEditor, Path, int, int] | None:
        ed = self.current_editor()
        if ed is None or not ed.path:
            self.notify(tr("abra um arquivo salvo para usar o servidor de linguagem"), severity="warning")
            return None
        if not self.lsp_confiavel():
            self.notify(tr("Alt+L ativa os servidores de linguagem neste projeto"), severity="warning")
            return None
        caminho = Path(ed.path)
        if self._lsp is None or not self._lsp.aberto(caminho):
            motivo = self._lsp.estado().get(lsp.grupo(ed.lang_id or ""), "") if self._lsp else ""
            self.notify(tr("nenhum servidor de linguagem acompanha {arquivo}").format(arquivo=caminho.name)
                        + (f": {motivo.splitlines()[0][:160]}" if motivo else ""), severity="warning")
            return None
        row, col = ed.cursor_location
        return ed, caminho, row, col

    async def _lsp_pedir(self, nome: str, ed: CodeEditor, caminho: Path, *args):
        try:
            await self._lsp.alterar(caminho, ed.text)  # o servidor precisa ver o que está na tela agora
            return await getattr(self._lsp, nome)(caminho, *args)
        except _FALHAS as exc:
            self.notify(tr("servidor de linguagem: {erro}").format(erro=exc), severity="error")
            return None

    def _rel(self, caminho: Path) -> str:
        try:
            return str(Path(caminho).resolve().relative_to(self.root))
        except ValueError:
            return str(caminho)

    def _linha_de(self, caminho: Path, linha: int) -> str:
        for ed in self._editores_de(Path(caminho).resolve()):
            return ed.document.get_line(linha) if linha < ed.document.line_count else ""
        try:
            return lsp.linhas(Path(caminho).read_text(encoding="utf-8", errors="replace"))[linha]
        except (OSError, IndexError):
            return ""

    async def _lsp_ir(self, local: Local) -> None:
        if not local.caminho.is_file():
            self.notify(tr("{arquivo} não existe no disco").format(arquivo=local.caminho), severity="warning")
            return
        await self.open_file(local.caminho.resolve())
        ed = self.current_editor()
        if ed is not None:
            linha = min(local.intervalo.linha, ed.document.line_count - 1)
            ed.move_cursor((linha, min(local.intervalo.coluna, len(ed.document.get_line(linha)))), center=True)
            ed.focus()
        if not local.caminho.resolve().is_relative_to(self.root):
            self.notify(tr("arquivo fora do projeto: {arquivo}").format(arquivo=local.caminho), timeout=6)

    def _lsp_escolher(self, titulo: str, locais: list[Local]) -> None:
        from codar.studio.review import ChoiceScreen

        opcoes = [(str(i), f"{self._rel(l.caminho)}:{l.intervalo.linha + 1}  "
                           f"{self._linha_de(l.caminho, l.intervalo.linha).strip()[:90]}") for i, l in enumerate(locais)]

        def escolhido(ident):
            if ident is not None:
                self.run_worker(self._lsp_ir(locais[int(ident)]), group="lsp-ir", exit_on_error=False)
        self.push_screen(ChoiceScreen(titulo, opcoes, searchable=len(opcoes) > 8), escolhido)

    async def action_lsp_definicao(self) -> None:
        if not (alvo := self._lsp_alvo()):
            return
        ed, caminho, row, col = alvo
        locais = await self._lsp_pedir("definicao", ed, caminho, row, col)
        if locais is None:
            return
        if not locais:
            self.notify(tr("definição não encontrada para o símbolo do cursor"), severity="warning")
        elif len(locais) == 1:
            await self._lsp_ir(locais[0])
        else:
            self._lsp_escolher(tr("DEFINIÇÕES · Enter abre"), locais)

    async def action_lsp_referencias(self) -> None:
        if not (alvo := self._lsp_alvo()):
            return
        ed, caminho, row, col = alvo
        locais = await self._lsp_pedir("referencias", ed, caminho, row, col)
        if locais is None:
            return
        if not locais:
            self.notify(tr("nenhuma referência encontrada"), severity="warning")
            return
        arquivos = len({l.caminho for l in locais})
        self._lsp_escolher(tr("REFERÊNCIAS · {n} em {a} arquivo(s) · Enter abre").format(n=len(locais), a=arquivos), locais)

    async def action_lsp_informacoes(self) -> None:
        if not (alvo := self._lsp_alvo()):
            return
        ed, caminho, row, col = alvo
        texto = await self._lsp_pedir("informacoes", ed, caminho, row, col)
        if texto is None:
            return
        assinatura = await self._lsp_pedir("assinatura", ed, caminho, row, col) or ""
        corpo = "\n\n".join(t for t in (assinatura, texto) if t)
        if not corpo:
            self.notify(tr("o servidor não tem informações sobre o símbolo do cursor"), severity="warning")
            return
        from codar.studio.screens import TerminalOutputScreen

        self.push_screen(TerminalOutputScreen(corpo, tr("INFORMAÇÕES · {arquivo}:{linha}").format(
            arquivo=caminho.name, linha=row + 1)))

    def action_lsp_renomear(self) -> None:
        if not (alvo := self._lsp_alvo()):
            return
        ed, caminho, row, col = alvo
        linha = ed.document.get_line(row)
        inicio = re.search(r"[\w$]*$", linha[:col]).start()
        fim = col + re.match(r"[\w$]*", linha[col:]).end()
        atual = linha[inicio:fim]
        if not atual:
            self.notify(tr("ponha o cursor sobre o nome a renomear"), severity="warning")
            return
        from codar.studio.screens import PromptScreen

        def novo_nome(nome):
            if nome and nome != atual:
                self.run_worker(self._lsp_renomear(ed, caminho, row, inicio, atual, nome), group="lsp-renomear",
                                exclusive=True, exit_on_error=False)
        self.push_screen(PromptScreen(tr("renomear {nome} para").format(nome=atual), value=atual,
                                      selecionar=len(atual)), novo_nome)

    async def _lsp_renomear(self, ed, caminho, row, col, atual, novo) -> None:
        edicoes = await self._lsp_pedir("renomear", ed, caminho, row, col, novo)
        if edicoes is None:
            return
        if not edicoes:
            self.notify(tr("o servidor não encontrou nada para renomear"), severity="warning")
            return
        fora = [p for p in edicoes if not Path(p).resolve().is_relative_to(self.root)]
        if fora:
            self.notify(tr("a renomeação alteraria arquivos fora do projeto ({arquivo}); nada foi alterado")
                        .format(arquivo=fora[0]), severity="error")
            return
        from codar.studio.explorer import ConfirmScreen

        detalhe = "\n".join(f"{self._rel(p)}: {len(e)} alteração(ões)" for p, e in sorted(edicoes.items()))
        total = sum(len(e) for e in edicoes.values())
        if not await self.push_screen_wait(ConfirmScreen(
                tr("Renomear {atual} para {novo}? {total} alteração(ões) em {n} arquivo(s)").format(
                    atual=atual, novo=novo, total=total, n=len(edicoes)), detalhe)):
            return
        from codar.studio.saving import write_buffer

        for alvo, lista in edicoes.items():
            abertos = self._editores_de(Path(alvo).resolve())
            if abertos:
                substituir_texto(abertos[0], lsp.aplicar(abertos[0].text, lista))
                continue
            try:
                write_buffer(alvo, lsp.aplicar(Path(alvo).read_text(encoding="utf-8"), lista))
            except (OSError, ValueError, UnicodeDecodeError) as exc:
                self.notify(tr("não consegui alterar {arquivo}: {erro}").format(arquivo=self._rel(alvo), erro=exc),
                            severity="error")
        self.feed(f"LSP · {atual} → {novo} · {total} alteração(ões)", "green")
        self.notify(tr("Renomeado. Arquivos abertos ficam com alterações não salvas (Ctrl+S)."), timeout=6)

    async def action_lsp_formatar(self) -> None:
        if not (alvo := self._lsp_alvo()):
            return
        ed, caminho, _, _ = alvo
        antes = ed.text
        edicoes = await self._lsp_pedir("formatar", ed, caminho, ed.indent_width, ed.indent_type != "tabs")
        if edicoes is None:
            return
        if not edicoes:
            self.notify(tr("nada a formatar (ou o servidor não formata esta linguagem)"))
            return
        if ed.text != antes:
            self.notify(tr("o texto mudou enquanto o servidor formatava; tente de novo"), severity="warning")
            return
        substituir_texto(ed, lsp.aplicar(antes, edicoes))
        self.feed(f"LSP · {caminho.name} formatado", "green")

    def lsp_completar(self, ed: CodeEditor) -> bool:
        """F10 / Ctrl+Espaço: com servidor ativo, as sugestões dele vêm antes das do índice local."""
        if self._lsp is None or not ed.path or not self._lsp.aberto(Path(ed.path)):
            return False
        self.run_worker(self._lsp_completar(ed), group="lsp-completar", exclusive=True, exit_on_error=False)
        return True

    async def _lsp_completar(self, ed: CodeEditor) -> None:
        caminho = Path(ed.path)
        row, col = ed.cursor_location
        prefixo = re.search(r"[\w$]*$", ed.document.get_line(row)[:col])[0]
        itens = await self._lsp_pedir("completar", ed, caminho, row, col) or []
        locais = [i for i in ed.symbol_completions if i.name.startswith(prefixo)]
        vistos = set()
        escolhas: list[tuple[str, str]] = []  # (texto inserido, rótulo)
        for item in itens:
            texto = item.inserir if item.inserir.startswith(prefixo) or not prefixo else item.rotulo
            if texto in vistos or (prefixo and not texto.startswith(prefixo)):
                continue
            vistos.add(texto)
            escolhas.append((texto, " · ".join(x for x in (item.rotulo, item.tipo, item.detalhe) if x)))
        for item in locais:
            if item.name not in vistos:
                vistos.add(item.name)
                escolhas.append((item.name, item.signature + " · " + item.source))
        if not escolhas:
            self.notify(tr("nenhuma sugestão para este ponto"))
            return
        from codar.studio.review import ChoiceScreen

        original = (ed.text, ed.cursor_location)

        def escolhido(ident):
            if ident is None:
                return
            if (ed.text, ed.cursor_location) != original:
                self.notify(tr('O editor mudou durante a escolha; nenhum texto foi alterado.'), severity='warning')
                return
            ed.replace(escolhas[int(ident)][0], (row, col - len(prefixo)), (row, col))
            ed.focus()
        self.push_screen(ChoiceScreen(tr("COMPLETAR · servidor de linguagem e índice do projeto"),
                                      [(str(i), rotulo) for i, (_, rotulo) in enumerate(escolhas[:300])],
                                      searchable=True), escolhido)
