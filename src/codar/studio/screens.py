"""Telas modais do Studio: aceitar sugestão do consultor e pedir um texto."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Label, Static, TextArea

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


class CopyableOutput(TextArea):
    BINDINGS = [Binding("ctrl+a", "select_all", "Selecionar tudo", show=False, priority=True),
                Binding("ctrl+c", "copy_native", "Copiar", show=False, priority=True)]

    def action_copy_native(self):
        from codar.studio.clipboard import copy_text

        if self.selected_text:
            copy_text(self.app, self.selected_text)


class TerminalOutputScreen(ModalScreen[None]):
    """Cópia por seleção, teclado ou botão, mantendo a saída original sem cortes de largura."""

    DEFAULT_CSS = """
    TerminalOutputScreen { align: center middle; background: $codar-bg 75%; }
    #terminal-output-card { width: 120; max-width: 95%; height: 90%; border: round $codar-orange; padding: 1 2; }
    #terminal-output-text { height: 1fr; margin: 1 0; }
    #terminal-output-buttons { height: 3; }
    #terminal-output-buttons Button { margin-right: 2; }
    """
    BINDINGS = [("escape", "close", "Fechar"), ("ctrl+shift+c", "copy_selection", "Copiar")]

    def __init__(self, text: str, title: str):
        super().__init__()
        self.text, self.title_text = text, title

    def compose(self):
        with Vertical(id="terminal-output-card"):
            yield Label(f"SAÍDA · {self.title_text}")
            yield Static("Selecione com o mouse ou Shift + setas. Ctrl+A seleciona tudo; Ctrl+C copia. Esc volta.")
            yield CopyableOutput(self.text, read_only=True, soft_wrap=False, id="terminal-output-text")
            with Horizontal(id="terminal-output-buttons"):
                yield Button("Copiar seleção", id="terminal-copy-selection")
                yield Button("Copiar tudo", id="terminal-copy-all", variant="success")
                yield Button("Fechar", id="terminal-output-close")

    def on_mount(self):
        self.query_one(TextArea).focus()

    def action_copy_selection(self):
        from codar.studio.clipboard import copy_text

        ed = self.query_one(TextArea)
        text = ed.selected_text
        if not text:
            self.notify("Selecione um trecho ou use Copiar tudo.")
            return
        copy_text(self.app, text)
        self.notify("Seleção copiada.")

    def on_button_pressed(self, event: Button.Pressed):
        if event.button.id == "terminal-copy-selection":
            self.action_copy_selection()
        elif event.button.id == "terminal-copy-all":
            from codar.studio.clipboard import copy_text

            copy_text(self.app, self.text)
            self.notify("Saída copiada.")
        else:
            self.dismiss(None)

    def action_close(self):
        self.dismiss(None)


def qr_texto(conteudo: str):
    """QR code para a tela: preto sobre branco explícito (o leitor do celular não depende do tema do terminal)."""
    from rich.style import Style
    from rich.text import Text

    from codar.qr import QR

    m = QR(conteudo).linhas(borda=2)
    if len(m) % 2:
        m.append([False] * len(m[0]))
    texto = Text(no_wrap=True)
    for y in range(0, len(m), 2):
        for a, b in zip(m[y], m[y + 1]):
            texto.append("▀", Style(color="#000000" if a else "#ffffff", bgcolor="#000000" if b else "#ffffff"))
        if y + 2 < len(m):
            texto.append("\n")
    return texto


class CelularScreen(ModalScreen[str | None]):
    """F4: o endereço na rede local e o QR code para abrir no celular (no mesmo Wi-Fi)."""

    BINDINGS = [("escape,f4", "fechar", "Fechar"), ("p", "parar", "Parar o servidor")]

    def __init__(self, titulo: str, url_rede: str | None, url_local: str, aviso: str | None = None) -> None:
        super().__init__()
        self.titulo, self.url_rede, self.url_local, self.aviso = titulo, url_rede, url_local, aviso

    def compose(self) -> ComposeResult:
        with Vertical(id="celular-card") as card:
            card.border_title = "VER NO CELULAR"
            card.border_subtitle = "Esc fecha (o servidor continua) · p para"
            yield Static(f"[b {C['mint']}]{self.titulo}[/]", id="celular-titulo")
            if self.url_rede:
                yield Static(qr_texto(self.url_rede), id="celular-qr")
                yield Static(f"[{C['dim']}]no celular (mesmo Wi-Fi), aponte a câmera ou abra:[/]\n"
                             f"[b {C['mint']}]{self.url_rede}[/]")
            yield Static(f"[{C['dim']}]neste computador:[/] [{C['cyan']}]{self.url_local}[/]")
            if self.aviso:
                yield Static(f"[{C['orange']}]{self.aviso}[/]")

    def action_fechar(self) -> None:
        self.dismiss(None)

    def action_parar(self) -> None:
        self.dismiss("parar")


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
                 ("Ctrl+F / Ctrl+Shift+F", "busca no arquivo / projeto; IA local opcional sugere palavras-chave"),
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
    ("ESTUDAR", [("F7", "modo estudo: explica o conceito da linha (ou do comentário) com exemplo e exercício"),
                 ("Ctrl+Shift+F7", "catálogo com tópicos da linguagem, fontes oficiais e prática registrada"),
                 ("F7 depois de um erro", "abre o conceito do erro que acabou de acontecer"),
                 ("trilha POO", "mostra o que da orientação a objetos você já usa e o próximo passo"),
                 ("Shift+F7", "cria o arquivo que o estudo sugeriu (ex.: main.py comentado)")]),
    ("ARQUIVOS", [("Ctrl+S", "salva"), ("Ctrl+N", "novo arquivo"), ("Ctrl+W", "fecha a aba"),
                  ("Botão AUTO ON/OFF", "salvamento automático opcional após a digitação; evita sobrescrever alterações externas"),
                  ("Botão SDKs", "instala versões Python, escolhe a do projeto e cria ambientes separados"),
                  ("Ctrl+B", "mostra/esconde o explorer"), ("F9", "mostra/esconde o painel")]),
    ("TERMINAL", [("Tab / Shift+Tab", "completa/percorre caminhos, comandos, histórico e scripts"),
                  ("↑ / ↓", "histórico; ↓ no final restaura seu rascunho"),
                  ("Ctrl+Enter", "envia o comando ou a entrada do programa"),
                  ("Ctrl+Shift+C", "copia toda a saída do terminal ativo"),
                  ("Ctrl+Shift+A", "abre saída selecionável: mouse, Shift+setas, Ctrl+A e Ctrl+C"),
                  ("Ctrl+L / Ctrl+W", "limpa a saída / apaga a palavra anterior no comando"),
                  ("Ctrl+C / Ctrl+D", "interrompe / envia EOF; Ctrl+D ocioso fecha a sessão vazia"),
                  ("Ctrl+Shift+W", "fecha o terminal ocioso (interrompa antes se ocupado)"),
                  ("F12", "abre seu shell completo na pasta atual; exit volta ao Studio")]),
    ("PROJETO", [("F5", "executa o arquivo (.html: abre a prévia)"),
                 ("F4", "ver no celular: prévia na rede com QR code (ou repassa o servidor do terminal)"),
                 ("F6", "audita o arquivo"), ("F8", "consultor de projeto"),
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
