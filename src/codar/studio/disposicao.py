"""Disposição da tela do Studio: o layout se adapta ao tamanho da janela e cada área pode ser ajustada à mão.

- Alças entre as colunas (⋮): arrastar muda a largura; clicar recolhe ou expande a coluna ao lado.
- Título de um bloco (EXPLORER, FEED, PAINEL, TELEMETRIA...): clicar recolhe ou expande. O título do PAINEL também se
  arrasta, para mudar a altura.
- Alt+M maximiza o editor (de novo: volta como estava); Ctrl+B mostra ou oculta o explorer; F9 recolhe o painel.
- Sem ajuste manual, a janela decide: em janelas baixas os blocos decorativos (radar, logotipo) saem antes do explorer,
  a coluna da direita só aparece quando sobra largura para o editor e o painel não passa da metade da altura.

As escolhas ficam salvas entre sessões; "Layout: restaurar o padrão", na paleta, volta tudo ao automático.
"""

from __future__ import annotations

from rich.text import Text
from textual import events
from textual.binding import Binding
from textual.dom import DOMNode
from textual.message import Message
from textual.widget import Widget
from textual.widgets import TabbedContent

from codar.i18n import tr
from codar.studio import estado
from codar.studio.widgets import ASCII, Botao

ATALHOS = [Binding("alt+m", "maximizar_editor", tr("Maximizar o editor"), show=False, priority=True)]

LARGURA_PARA_ESQUERDA = 84  # colunas da janela a partir das quais o explorer aparece sozinho
LARGURA_PARA_DIREITA = 150  # ... e a coluna da direita (HUD), sem tirar do editor a largura de que ele precisa
LARGURA_ESQUERDA_LARGA = 110  # abaixo disso, o explorer padrão fica mais estreito (26 em vez de 32)
EDITOR_MINIMO = 40  # colunas que o editor sempre mantém, mesmo com as laterais abertas à mão
PAINEL_MINIMO = 3  # linhas do painel ao arrastar (borda, abas e uma linha de conteúdo)
# Classes que o Textual põe na tela conforme a altura: os blocos decorativos somem primeiro (studio.tcss).
VERTICAL = [(0, "-altura-minima"), (28, "-altura-baixa"), (36, "-altura-media"), (50, "-altura-alta")]

# Blocos que recolhem pelo título, com o título que mostram.
BLOCOS = {"explorer": "EXPLORER", "radar": "PIPELINE ORBIT", "feed": "SOURCE / EVENT FEED", "panel": "PAINEL",
          "last-card": "LAST TRANSLATION", "telemetry": "TELEMETRIA", "history": "HISTÓRICO"}
# Rótulos da barra de ferramentas: completo e compacto (quando a coluna central fica estreita).
FERRAMENTAS = {"translate-button": ("▶ TRADUZIR F3", "▶ F3"), "search-button": ("⌕ BUSCAR", "⌕"),
               "libraries-button": ("BIBLIOTECAS", "LIBS"), "structure-button": ("ESTRUTURA", "ESTRUT.")}
FERRAMENTAS_LARGURA = 74  # colunas que a barra completa ocupa


def _seta(aberto: bool) -> str:
    if ASCII:
        return "v" if aberto else ">"
    return "▾" if aberto else "▸"


class Alca(Widget):
    """Alça vertical entre duas colunas: arrastar muda a largura da coluna; clicar recolhe ou expande."""

    DEFAULT_CSS = """
    Alca { width: 1; height: 1fr; background: $codar-bg; color: $codar-line; }
    Alca:hover, Alca.-arrastando { background: $codar-grid; color: $codar-orange; }
    """

    class Movida(Message):
        """A alça foi arrastada `deslocamento` colunas desde o começo do arrasto (fim: o botão foi solto)."""

        def __init__(self, alca: Alca, deslocamento: int, fim: bool) -> None:
            super().__init__()
            self.alca, self.deslocamento, self.fim = alca, deslocamento, fim

    class Clicada(Message):
        def __init__(self, alca: Alca) -> None:
            super().__init__()
            self.alca = alca

    def __init__(self, lado: str, **kwargs) -> None:
        super().__init__(**kwargs)
        self.lado = lado  # a coluna que ela controla: "esquerda" ou "direita"
        self.aberta = True
        self._inicio: int | None = None
        self._moveu = False
        self.tooltip = tr("Arraste para mudar a largura · clique para recolher ou expandir")

    def render(self) -> Text:
        altura = max(1, self.size.height)
        if self.aberta:
            marca = ":" if ASCII else "⋮"
        elif ASCII:
            marca = ">" if self.lado == "esquerda" else "<"
        else:  # coluna recolhida: a seta aponta para onde ela abre
            marca = "›" if self.lado == "esquerda" else "‹"
        meio = altura // 2
        return Text("\n".join(marca if abs(i - meio) <= 1 else " " for i in range(altura)))

    def marcar(self, aberta: bool) -> None:
        if aberta != self.aberta:
            self.aberta = aberta
            self.refresh()

    def on_mouse_down(self, event: events.MouseDown) -> None:
        # Sem stop: o Studio também vê o botão descer aqui (e esquece um título pressionado antes).
        if event.button != 1:
            return
        self._inicio, self._moveu = event.screen_x, False
        self.capture_mouse()
        self.add_class("-arrastando")

    def on_mouse_move(self, event: events.MouseMove) -> None:
        if self._inicio is None:
            return
        event.stop()
        deslocamento = event.screen_x - self._inicio
        if deslocamento or self._moveu:
            self._moveu = True
            self.post_message(self.Movida(self, deslocamento, False))

    def on_mouse_up(self, event: events.MouseUp) -> None:
        if self._inicio is None:
            return
        event.stop()
        deslocamento = event.screen_x - self._inicio
        self._inicio = None
        self.release_mouse()
        self.remove_class("-arrastando")
        if self._moveu or deslocamento:
            self.post_message(self.Movida(self, deslocamento, True))
        else:
            self.post_message(self.Clicada(self))

    def on_click(self, event: events.Click) -> None:
        event.stop()  # o clique já virou Clicada (ou foi o fim de um arrasto)


class PainelInferior(TabbedContent):
    """O painel de baixo (PROBLEMAS, TERMINAL, SAÍDA...). Quem o mostra (F5, /btw, depurador) também o expande, se ele
    estava recolhido: a saída nunca aparece num painel reduzido ao título."""

    def _get_display(self) -> bool:
        return DOMNode.display.fget(self)

    def _set_display(self, valor: bool | str) -> None:
        DOMNode.display.fset(self, valor)
        if valor in (True, "block") and self.has_class("recolhido"):
            self.remove_class("recolhido")
            aplicar = getattr(self.app, "painel_expandido", None)
            if aplicar is not None:
                aplicar()

    display = property(_get_display, _set_display)


class DisposicaoMixin:
    """Parte do Studio que cuida do tamanho e da visibilidade de cada área."""

    def _disposicao_init(self) -> None:
        salvo = estado.ler().get("disposicao") or {}
        if not isinstance(salvo, dict):
            salvo = {}

        def inteiro(valor):
            return valor if isinstance(valor, int) and not isinstance(valor, bool) and valor > 0 else None

        self._larguras = {lado: inteiro(salvo.get(lado)) for lado in ("esquerda", "direita")}
        self._altura_painel = inteiro(salvo.get("painel"))
        visivel = salvo.get("visivel") if isinstance(salvo.get("visivel"), dict) else {}
        self._visivel = {lado: visivel.get(lado) if isinstance(visivel.get(lado), bool) else None
                         for lado in ("esquerda", "direita")}  # None: a largura da janela decide
        recolhidos = salvo.get("recolhidos") if isinstance(salvo.get("recolhidos"), list) else []
        self._recolhidos = {b for b in recolhidos if b in BLOCOS}
        self._largura_no_arrasto: int | None = None
        self._arrasto_painel: tuple[int, int, bool] | None = None  # (y inicial, altura inicial, moveu)
        self._ignorar_clique = False
        self._titulo_pressionado: str | None = None  # o clique só vale no título em que o botão desceu
        self._foco: tuple[dict, bool] | None = None  # como estava antes de maximizar o editor
        self._ferramentas_compactas: bool | None = None

    def disposicao_montar(self) -> None:
        for bloco in BLOCOS:
            self.query_one(f"#{bloco}").set_class(bloco in self._recolhidos, "recolhido")
        self.disposicao_titulos()
        self._aplicar_painel()
        self.resize_workspace()

    def disposicao_titulos(self) -> None:
        """Títulos com ▾ (aberto) ou ▸ (recolhido): mostram que o título é clicável."""
        for bloco, titulo in BLOCOS.items():
            self.query_one(f"#{bloco}").border_title = f"{_seta(bloco not in self._recolhidos)} {tr(titulo)}"

    def _salvar_disposicao(self) -> None:
        visivel = self._foco[0] if self._foco is not None else self._visivel  # o modo foco não é salvo
        estado.salvar(disposicao={"esquerda": self._larguras["esquerda"], "direita": self._larguras["direita"],
                                  "painel": self._altura_painel, "visivel": dict(visivel),
                                  "recolhidos": sorted(self._recolhidos)})

    # ------------------------------------------------------------------ colunas
    @staticmethod
    def _largura_padrao(lado: str, largura: int) -> int:
        if lado == "direita":
            return 38
        return 32 if largura >= LARGURA_ESQUERDA_LARGA else 26

    @staticmethod
    def _limitar_largura(lado: str, valor: int, largura: int) -> int:
        return max(16, min(valor, int(largura * (0.5 if lado == "esquerda" else 0.45))))

    def _largura_coluna(self, lado: str, largura: int) -> int:
        escolhida = self._larguras[lado]
        return self._limitar_largura(lado, escolhida, largura) if escolhida else self._largura_padrao(lado, largura)

    def resize_workspace(self, width: int | None = None) -> None:
        from textual.css.query import NoMatches

        try:
            colunas = {"esquerda": self.query_one("#left"), "direita": self.query_one("#right")}
            alcas = {"esquerda": self.query_one("#alca-esquerda", Alca), "direita": self.query_one("#alca-direita", Alca)}
        except NoMatches:
            return
        largura = self.size.width if width is None else width
        automatico = {"esquerda": self.perspective != "essential" and largura >= LARGURA_PARA_ESQUERDA,
                      "direita": self.perspective == "development" and largura >= LARGURA_PARA_DIREITA}
        mostrar = {lado: automatico[lado] if self._visivel[lado] is None else self._visivel[lado] for lado in colunas}
        tamanhos = {lado: self._largura_coluna(lado, largura) for lado in colunas}
        for lado in ("direita", "esquerda"):  # o editor nunca fica estreito demais: a direita cede primeiro
            ocupado = sum(tamanhos[outro] for outro in colunas if mostrar[outro]) + len(alcas)
            if mostrar[lado] and largura - ocupado < EDITOR_MINIMO:
                mostrar[lado] = False
        for lado, coluna in colunas.items():
            if coluna.display != mostrar[lado]:
                coluna.display = mostrar[lado]
            if coluna.styles.width is None or coluna.styles.width.value != tamanhos[lado]:
                coluna.styles.width = tamanhos[lado]
            alcas[lado].marcar(mostrar[lado])
        centro = largura - len(alcas) - sum(tamanhos[lado] for lado in colunas if mostrar[lado])
        self._ajustar_ferramentas(centro)

    def _ajustar_ferramentas(self, largura_centro: int) -> None:
        compacto = largura_centro < FERRAMENTAS_LARGURA
        if self._ferramentas_compactas == compacto:
            return
        self._ferramentas_compactas = compacto
        for identificador, (completo, curto) in FERRAMENTAS.items():
            for botao in self.query(f"#{identificador}"):
                if isinstance(botao, Botao):
                    botao.update(tr(curto if compacto else completo))

    def _definir_visivel(self, lado: str, visivel: bool) -> None:
        self._visivel[lado] = visivel
        if self._foco is not None:  # mexer numa coluna sai do modo foco sem desfazer a escolha
            self._foco = None
        self.resize_workspace()
        self._salvar_disposicao()
        if visivel and not self.query_one("#left" if lado == "esquerda" else "#right").display:
            self.notify(tr("A janela está estreita demais para esta coluna e o editor juntos; aumente a janela ou "
                           "estreite a outra coluna."), severity="warning")

    def action_toggle_left(self) -> None:
        self._definir_visivel("esquerda", not self.query_one("#left").display)

    def action_toggle_right(self) -> None:
        self._definir_visivel("direita", not self.query_one("#right").display)

    def mostrar_explorer(self) -> None:
        """Ctrl+E: abre a coluna e o bloco do explorer, se estavam fechados."""
        if not self.query_one("#left").display:
            self._definir_visivel("esquerda", True)
        if "explorer" in self._recolhidos:
            self.alternar_bloco("explorer")

    def on_alca_movida(self, event: Alca.Movida) -> None:
        lado = event.alca.lado
        coluna = self.query_one("#left" if lado == "esquerda" else "#right")
        if self._largura_no_arrasto is None:
            # arrastar a alça de uma coluna recolhida a abre já com a largura do arrasto
            self._largura_no_arrasto = coluna.outer_size.width if coluna.display else 0
        sinal = 1 if lado == "esquerda" else -1
        nova = self._largura_no_arrasto + sinal * event.deslocamento
        if nova < 12:  # arrastou até quase sumir: recolhe, como no VS Code
            self._visivel[lado] = False
        else:
            self._visivel[lado] = True
            self._larguras[lado] = self._limitar_largura(lado, nova, self.size.width)
        self.resize_workspace()
        if event.fim:
            self._largura_no_arrasto = None
            self._salvar_disposicao()

    def on_alca_clicada(self, event: Alca.Clicada) -> None:
        (self.action_toggle_left if event.alca.lado == "esquerda" else self.action_toggle_right)()

    # ------------------------------------------------------------------ blocos e painel
    def alternar_bloco(self, bloco: str) -> None:
        widget = self.query_one(f"#{bloco}")
        recolher = bloco not in self._recolhidos
        (self._recolhidos.add if recolher else self._recolhidos.discard)(bloco)
        if bloco == "panel":
            if recolher:
                widget.remove_class("maximizado")
            elif not widget.display:
                widget.display = True
        widget.set_class(recolher, "recolhido")
        if bloco == "panel":
            self._aplicar_painel()
        self.disposicao_titulos()
        if recolher and widget.has_focus_within:
            self.action_focus_editor()
        self._salvar_disposicao()

    def painel_expandido(self) -> None:
        """O painel foi mostrado por um comando (F5, /btw, depurador...) e saiu do estado recolhido."""
        self._recolhidos.discard("panel")
        self._aplicar_painel()
        self.disposicao_titulos()
        self._salvar_disposicao()

    def _aplicar_painel(self) -> None:
        painel = self.query_one("#panel")
        if painel.has_class("maximizado") or painel.has_class("recolhido") or not self._altura_painel:
            painel.styles.clear_rule("height")  # valem as regras do studio.tcss
            painel.styles.clear_rule("max_height")
        else:
            painel.styles.height = self._altura_painel
            painel.styles.max_height = "85%"

    def action_toggle_panel(self) -> None:
        """F9: recolhe o painel ao título (de novo: expande)."""
        painel = self.query_one("#panel")
        if not painel.display:
            painel.display = True
            if "panel" in self._recolhidos:
                self.alternar_bloco("panel")
            return
        self.alternar_bloco("panel")

    def action_maximize_panel(self) -> None:
        """Shift+F9: o painel ocupa quase toda a área central (como Maximizar painel do VS Code) e volta."""
        painel = self.query_one("#panel")
        painel.display = True
        if "panel" in self._recolhidos:
            self.alternar_bloco("panel")
        painel.toggle_class("maximizado")
        self._aplicar_painel()

    def action_maximizar_editor(self) -> None:
        """Alt+M: só o editor na tela (sem colunas e sem painel); de novo, tudo volta como estava."""
        painel = self.query_one("#panel")
        if self._foco is None:
            self._foco = (dict(self._visivel), painel.display)
            self._visivel.update(esquerda=False, direita=False)
            DOMNode.display.fset(painel, False)
        else:
            visivel, mostrado = self._foco
            self._foco = None
            self._visivel.update(visivel)
            DOMNode.display.fset(painel, mostrado)
        self.resize_workspace()

    def action_restaurar_disposicao(self) -> None:
        """Volta ao layout automático: larguras, altura do painel, colunas e blocos."""
        self._larguras = {"esquerda": None, "direita": None}
        self._altura_painel = None
        self._visivel = {"esquerda": None, "direita": None}
        self._foco = None
        self._recolhidos.clear()
        painel = self.query_one("#panel")
        painel.remove_class("maximizado")
        for bloco in BLOCOS:
            self.query_one(f"#{bloco}").remove_class("recolhido")
        if self.perspective != "essential":
            painel.display = True
        self.disposicao_titulos()
        self._aplicar_painel()
        self.resize_workspace()
        self._salvar_disposicao()
        self.notify(tr("Layout padrão restaurado"))

    # ------------------------------------------------------------------ mouse nos títulos
    def _no_titulo(self, event: events.MouseEvent, bloco: str) -> Widget | None:
        """O bloco, se o evento caiu na linha do título dele (a borda de cima). Pela posição na tela: nos eventos que
        vêm do terminal, MouseDown não traz o widget (só o Click que o Textual monta depois)."""
        if len(self.screen_stack) > 1:  # uma janela por cima (menu, confirmação): o clique é dela
            return None
        widget = self.query_one(f"#{bloco}")
        regiao = widget.region
        if not widget.display or not regiao.height:
            return None
        return widget if event.screen_y == regiao.y and regiao.x <= event.screen_x < regiao.right else None

    def on_mouse_down(self, event: events.MouseDown) -> None:
        self._ignorar_clique = False
        self._titulo_pressionado = None
        if event.button != 1:
            return
        self._titulo_pressionado = next((bloco for bloco in BLOCOS if self._no_titulo(event, bloco) is not None), None)
        if self._titulo_pressionado == "panel":
            painel = self.query_one("#panel")
            self._arrasto_painel = (event.screen_y, painel.outer_size.height, False)
            painel.capture_mouse()

    def on_mouse_move(self, event: events.MouseMove) -> None:
        if self._arrasto_painel is None:
            return
        y_inicial, altura_inicial, moveu = self._arrasto_painel
        if event.screen_y == y_inicial and not moveu:
            return
        self._arrasto_painel = (y_inicial, altura_inicial, True)
        painel = self.query_one("#panel")
        centro = self.query_one("#center").size.height
        # o editor guarda umas 5 linhas (as duas barras de cima, a borda e as abas ficam fora da conta)
        nova = max(PAINEL_MINIMO, min(altura_inicial + y_inicial - event.screen_y, centro - 9))
        if "panel" in self._recolhidos:  # arrastar o título de um painel recolhido o abre
            self._recolhidos.discard("panel")
            painel.remove_class("recolhido")
            self.disposicao_titulos()
        painel.remove_class("maximizado")
        self._altura_painel = nova
        self._aplicar_painel()

    def on_mouse_up(self, event: events.MouseUp) -> None:
        if self._arrasto_painel is None:
            return
        moveu = self._arrasto_painel[2]
        self._arrasto_painel = None
        self.query_one("#panel").release_mouse()
        if moveu:
            self._ignorar_clique = True  # o clique que o Textual gera depois do arrasto não recolhe o painel
            self._salvar_disposicao()

    def on_click(self, event: events.Click) -> None:
        # Só recolhe se o botão desceu e subiu no mesmo título: depois que uma alça abre uma coluna, o clique que o
        # Textual monta no mouse_up pode cair no título que acabou de aparecer sob o ponteiro.
        bloco, self._titulo_pressionado = self._titulo_pressionado, None
        if self._ignorar_clique:
            self._ignorar_clique = False
            return
        if event.button == 1 and bloco is not None and self._no_titulo(event, bloco) is not None:
            event.stop()
            self.alternar_bloco(bloco)

    def disposicao_comandos_paleta(self) -> list[tuple[str, str, object]]:
        return [
            ("Layout: mostrar/ocultar a coluna da direita", "HUD, última tradução, telemetria e histórico",
             self.action_toggle_right),
            ("Layout: maximizar o editor", "Alt+M · de novo, tudo volta como estava", self.action_maximizar_editor),
            ("Layout: restaurar o padrão", "larguras, altura do painel e blocos recolhidos voltam ao automático",
             self.action_restaurar_disposicao),
        ]
