"""Telas modais do Studio: aceitar sugestão do consultor e pedir um texto."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Label, Static


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
                    yield Static(f"[b #47FFA9]{o['label']}[/]" + (f"\n[#6b551f]{o['reason']}[/]" if o.get("reason") else "") +
                                 "\n" + "\n".join(f"[#39d6c8]  {st}[/]" for st in o["steps"]), classes="advice-plan")
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

    def __init__(self, title: str, placeholder: str = "", value: str = "") -> None:
        super().__init__()
        self.title_text, self.placeholder, self.value = title, placeholder, value

    def compose(self) -> ComposeResult:
        with Vertical(id="prompt-card"):
            yield Label(self.title_text, id="prompt-title")
            yield Input(value=self.value, placeholder=self.placeholder, id="prompt-input")

    def on_mount(self) -> None:
        self.query_one(Input).focus()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        self.dismiss(event.value.strip() or None)

    def action_dismiss_none(self) -> None:
        self.dismiss(None)


# Atalhos do Studio, agrupados como aparecem na ajuda (F1). Mantenha em sincronia com Studio.BINDINGS.
SHORTCUTS: list[tuple[str, list[tuple[str, str]]]] = [
    ("TRADUZIR", [("Ctrl+Enter  ou  Ctrl+G", "traduz a linha do cursor (ou a seleção)"),
                  ("espaço + Enter", "no fim de uma frase, traduz em vez de quebrar a linha"),
                  ("Ctrl+L", "vai para a barra de intenção"),
                  ("Enter na barra", "gera o código e insere no editor")]),
    ("ESCREVER", [("Tab  ou  →", "aceita a sugestão (o texto apagado à direita)"),
                  ("Tab em .html/.css/.jsx", "expande abreviações: ul>li*3, a:blank, df+jcc"),
                  ("Ctrl+Z  /  Ctrl+Y", "desfaz / refaz")]),
    ("ARQUIVOS", [("Ctrl+S", "salva"), ("Ctrl+N", "novo arquivo"), ("Ctrl+W", "fecha a aba"),
                  ("Ctrl+B", "mostra/esconde o explorer"), ("F9", "mostra/esconde o painel")]),
    ("PROJETO", [("F5", "executa o arquivo"), ("F6", "audita o arquivo"), ("F8", "consultor de projeto"),
                 ("Ctrl+O", "abre no VS Code"), ("Ctrl+P", "paleta de comandos"), ("Ctrl+Q", "sai")]),
]
EXAMPLES: list[tuple[str, str]] = [
    ("x é igual a 10", "atribuição"), ("se total maior que 100 imprimir 'caro'", "condição"),
    ("para cada nome em nomes imprimir nome", "laço"), ("imprimir o tamanho de pedidos", "expressão"),
    ("criar uma calculadora", "padrão completo do banco"), ("validar cnpj", "padrão brasileiro"),
    ("ul>li.item$*3", "HTML (Tab num .html)"), ("df+jcc+aic", "CSS (Tab num .css)"),
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
                    yield Static(f"[b #FF4747]{group}[/]", classes="help-group")
                    yield Static("\n".join(f"  [b #47FFA9]{k:<24}[/] [#f0b32a]{v}[/]" for k, v in items),
                                 classes="help-items")
                yield Static("[b #FF4747]EXPERIMENTE[/]", classes="help-group")
                yield Static("\n".join(f"  [#54ff8a]{e:<40}[/] [#6b551f]{what}[/]" for e, what in EXAMPLES),
                             classes="help-items")

    def action_close(self) -> None:
        self.dismiss(None)
