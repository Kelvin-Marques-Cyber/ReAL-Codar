"""/btw no Studio: a IA local explica o trecho selecionado, sem tocar no código.

Na barra de intenção, `/btw` explica a seleção (ou a linha do cursor) e `/btw por que usar um dicionário aqui?` faz uma
pergunta sobre ela. Alt+E faz o mesmo sem pergunta. A resposta vai para a aba SAÍDA, marcada como explicação não
testada; sem modelo (ou com o S2 desligado), a explicação vem do material do Estudo, linha a linha.
"""

from __future__ import annotations

import re
from pathlib import Path

from rich.text import Text
from textual import work
from textual.binding import Binding
from textual.widgets import RichLog, Static, TabbedContent

from codar.i18n import tr
from codar.studio.widgets import C

ATALHOS = [Binding("alt+e", "btw", tr("Explicar o trecho (/btw)"), show=False, priority=True)]
_PEDIDO = re.compile(r"^\s*/btw(?:\s+(?P<pergunta>.*))?$", re.I | re.S)


def pedido_btw(texto: str) -> str | None:
    """A pergunta de "/btw ..." ("" sem pergunta), ou None se o texto não é um /btw."""
    achado = _PEDIDO.match(texto)
    return None if achado is None else (achado["pergunta"] or "").strip()


class ExplicacaoMixin:
    """Parte do Studio que pede explicações à IA local."""

    def action_btw(self) -> None:
        self.btw("")

    def btw(self, pergunta: str) -> None:
        ed = self.current_editor()
        if ed is None:
            self.notify(tr("abra um arquivo e selecione o trecho que quer entender"), severity="warning")
            return
        if ed.selected_text.strip():
            trecho = ed.selected_text
            r0, r1 = ed.linhas_selecionadas()
        else:
            r0 = r1 = ed.cursor_location[0]
            trecho = ed.document.get_line(r0)
        if not trecho.strip():
            self.notify(tr("selecione o trecho (ou ponha o cursor numa linha com código) e use /btw de novo"),
                        severity="warning")
            return
        lang = ed.lang_id or self.current_lang()
        contexto = "\n".join(ed.document.get_line(n) for n in range(max(0, r0 - 60), r0))
        nome = Path(ed.path).name if ed.path else tr("sem nome")
        rotulo = f"/btw · {nome}:{r0 + 1}" + (f"-{r1 + 1}" if r1 > r0 else "") + (f" · {pergunta}" if pergunta else "")
        painel = self.query_one("#panel", TabbedContent)
        painel.display = True
        painel.active = "tab-output"
        self.query_one("#output-status", Static).update(Text(tr("/btw: explicando o trecho…"), style=C["cyan"]))
        self.query_one("#output", RichLog).write(Text(rotulo, style=f"bold {C['orange']}"))
        self._btw_worker(trecho, lang, pergunta, contexto, 2 in self.stages, rotulo)

    @work(thread=True, group="btw", exclusive=True, exit_on_error=False)
    def _btw_worker(self, trecho: str, lang: str, pergunta: str, contexto: str, usar_ia: bool, rotulo: str) -> None:
        try:
            resposta = self.backend.explain(trecho, lang, pergunta, contexto, usar_ia)
        except Exception as exc:  # daemon fora do ar, modelo quebrado: a explicação local ainda ajuda
            from codar.engine.explicar import sem_ia

            resposta = {"text": sem_ia(trecho, lang, str(exc).splitlines()[0][:120]), "origin": "estudo", "model": None}
        self.call_from_thread(self._btw_mostrar, resposta, rotulo)

    def _btw_mostrar(self, resposta: dict, rotulo: str) -> None:
        saida = self.query_one("#output", RichLog)
        saida.write(Text(resposta.get("text", "")))
        if resposta.get("origin") == "ia":
            origem = tr("IA local ({modelo}) · explicação, não testada").format(modelo=resposta.get("model") or "?")
        else:
            origem = tr("material do Estudo, sem IA")
        aviso = tr(" · trecho longo: só o começo foi analisado") if resposta.get("truncated") else ""
        saida.write(Text(f"— {origem}{aviso} · {tr('o código não foi alterado')}", style=C["dim"]))
        self.query_one("#output-status", Static).update(Text(rotulo + " · " + origem, style=C["dim"]))
        self.feed("BTW · " + origem, "cyan")
