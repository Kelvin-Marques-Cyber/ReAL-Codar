"""Telas modais do Studio: aceitar sugestão do consultor e pedir um texto."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Label, Static

from codar.studio.widgets import C
from codar.vocab import EXAMPLES


class AdviceScreen(ModalScreen[str | None]):
    """Cartão de sugestão: motivo, opções (botões) e o plano de cada uma. Retorna o id da opção ou None."""

    BINDINGS = [("escape", "dismiss_none", "Fechar")]

    def __init__(self, suggestion: dict) -> None:
        super().__init__()
        self.s = suggestion

    def compose(self) -> ComposeResult:
        s = self.s
        with Vertical(id="advice-card"):
            yield Label(f"▶ {s['title']}", id="advice-title")
            yield Static(s["reason"], id="advice-reason")
            with VerticalScroll(id="advice-options"):
                for o in s["options"]:
                    yield Static(f"[b {C['mint']}]{o['label']}[/]" +
                                 (f"\n[{C['dim']}]{o['reason']}[/]" if o.get("reason") else "") +
                                 "\n" + "\n".join(f"[{C['cyan']}]  {st}[/]" for st in o["steps"]), classes="advice-plan")
            with Horizontal(id="advice-buttons"):
                for o in s["options"]:
                    yield Button(f"✓ {o['label']}", id=f"opt-{o['id']}", classes="accept")
                yield Button("✗ Ignorar", id="opt-__none__", classes="reject")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        oid = (event.button.id or "").removeprefix("opt-")
        self.dismiss(None if oid == "__none__" else oid)

    def action_dismiss_none(self) -> None:
        self.dismiss(None)


class PromptScreen(ModalScreen[str | None]):
    BINDINGS = [("escape", "dismiss_none", "Cancelar")]

    def __init__(self, title: str, placeholder: str = "", value: str = "", selecionar: int | None = None) -> None:
        super().__init__()
        self.title_text, self.placeholder, self.value = title, placeholder, value
        self.selecionar = selecionar  # renomear: já seleciona o nome sem a extensão

    def compose(self) -> ComposeResult:
        with Vertical(id="prompt-card"):
            yield Label(self.title_text, id="prompt-title")
            yield Input(value=self.value, placeholder=self.placeholder, id="prompt-input")

    def on_mount(self) -> None:
        campo = self.query_one(Input)
        campo.focus()
        if self.selecionar:
            from textual.widgets.input import Selection

            self.call_after_refresh(setattr, campo, "selection", Selection(0, self.selecionar))

    def on_input_submitted(self, event: Input.Submitted) -> None:
        self.dismiss(event.value.strip() or None)

    def action_dismiss_none(self) -> None:
        self.dismiss(None)


# Atalhos do Studio, agrupados como aparecem na ajuda (F1). Mantenha em sincronia com Studio.BINDINGS.
SHORTCUTS: list[tuple[str, list[tuple[str, str]]]] = [
    ("NAVEGAR", [("Ctrl+E", "vai para o explorer (arquivos)"), ("Ctrl+T", "vai para o terminal"),
                 ("Ctrl+L", "vai para a barra de intenção"), ("Esc", "volta para o editor, de qualquer lugar"),
                 ("Ctrl+O", "abre um arquivo pelo nome"), ("Ctrl+P", "paleta: comandos e arquivos"),
                 ("Ctrl+PgDn  /  Ctrl+PgUp", "próxima aba / aba anterior")]),
    ("TRADUZIR", [("espaço + Enter", "no fim de uma frase, traduz em vez de quebrar a linha"),
                  ("Ctrl+G  ou  Ctrl+Enter", "traduz a linha; com várias linhas selecionadas, traduz o bloco"),
                  ("Enter na barra", "gera o código e insere no editor")]),
    ("ESCREVER", [("Tab  ou  →", "aceita a sugestão (o texto apagado à direita)"),
                  ("Tab em .html/.css/.jsx", "expande abreviações: ul>li*3, a:blank, df+jcc"),
                  ("( [ { \" '", "fecham sozinhos; com texto selecionado, envolvem a seleção"),
                  ("Enter", "mantém a indentação; depois de : ou { entra um nível"),
                  ("Tab  /  Shift+Tab", "com várias linhas selecionadas: indenta / desindenta"),
                  ("Ctrl+/", "comenta ou descomenta as linhas"),
                  ("Alt+↑  /  Alt+↓", "move a linha para cima / para baixo"),
                  ("Alt+Shift+↓", "duplica a linha"), ("Ctrl+A", "seleciona tudo"),
                  ("Ctrl+Z  /  Ctrl+Y", "desfaz / refaz")]),
    ("EXPLORER", [("↑ ↓  →  ←", "anda; → abre, ← fecha a pasta"), ("Enter", "abre o arquivo"),
                  ("n  /  p", "novo arquivo / nova pasta"), ("r  ou  F2", "renomeia"), ("d", "duplica"),
                  ("c  /  x  /  v", "copia / recorta / cola na pasta selecionada"),
                  ("Del", "apaga (vai para .codar/lixeira)"), ("m  ou  botão direito", "menu com todas as ações"),
                  ("arrastar arquivo", "solte no terminal com o explorer em foco: copia para o projeto")]),
    ("ARQUIVOS", [("Ctrl+S", "salva"), ("Ctrl+N", "novo arquivo"), ("Ctrl+W", "fecha a aba"),
                  ("Ctrl+B", "mostra/esconde o explorer"), ("F9", "mostra/esconde o painel")]),
    ("PROJETO", [("F5", "executa o arquivo"), ("F6", "audita o arquivo"), ("F8", "consultor de projeto"),
                 ("Ctrl+Q", "sai")]),
]


class HelpScreen(ModalScreen[None]):
    """F1: todos os atalhos e exemplos de frases que funcionam."""

    BINDINGS = [("escape", "close", "Fechar"), ("f1", "close", "Fechar"), ("q", "close", "Fechar")]

    def compose(self) -> ComposeResult:
        with Vertical(id="help-card") as card:
            card.border_title = "AJUDA · CODAR STUDIO"
            card.border_subtitle = "Esc fecha"
            with VerticalScroll(id="help-body"):
                for group, items in SHORTCUTS:
                    yield Static(f"[b {C['red']}]{group}[/]", classes="help-group")
                    yield Static("\n".join(f"  [b {C['mint']}]{k:<24}[/] [{C['text']}]{v}[/]" for k, v in items),
                                 classes="help-items")
                yield Static(f"[b {C['red']}]EXPERIMENTE[/]", classes="help-group")
                yield Static("\n".join(f"  [{C['green']}]{e:<40}[/] [{C['dim']}]{what}[/]" for e, what in EXAMPLES),
                             classes="help-items")

    def action_close(self) -> None:
        self.dismiss(None)
