"""Disposição do Studio: o layout se adapta à janela, e alças e títulos ajustam cada área à mão (e ficam salvos)."""

import asyncio

import pytest

pytest.importorskip("textual")


@pytest.fixture
def projeto(tmp_path, monkeypatch):
    monkeypatch.setenv("CODAR_HOME", str(tmp_path / "home"))
    monkeypatch.setenv("CODAR_NO_AUTOSTART", "1")
    raiz = tmp_path / "projeto"
    for nome in ["app.py", "README.md", "src/modulo.py", "tests/test_app.py", "codar-0.6.0-py3-none-any.whl"]:
        (raiz / nome).parent.mkdir(parents=True, exist_ok=True)
        (raiz / nome).write_text("x = 1\n", encoding="utf-8")
    return raiz


def _linhas_explorer(app):
    explorer = app.query_one("#explorer")
    return explorer.scrollable_content_region.height if explorer.display and app.query_one("#left").display else 0


def _visivel(app, seletor):
    widget = app.query_one(seletor)
    return bool(widget.display and widget.region.height)


@pytest.mark.parametrize("largura,altura,explorer_min,editor_min,direita", [
    (136, 35, 14, 95, False),  # a janela do relato: o explorer tinha 1 linha útil e o editor 66 colunas
    (120, 30, 12, 80, False),
    (100, 30, 12, 66, False),
    (160, 46, 20, 80, True),
    (80, 24, 0, 70, False),
])
def test_layout_se_adapta_ao_tamanho_da_janela(projeto, largura, altura, explorer_min, editor_min, direita):
    from codar.studio.app import Studio

    async def cenario():
        app = Studio(projeto, local=True)
        async with app.run_test(size=(largura, altura)) as pilot:
            await app.open_file(projeto / "app.py")
            await pilot.pause(.2)
            assert _linhas_explorer(app) >= explorer_min
            editor = app.query_one("#editors").region
            assert editor.width >= editor_min and editor.height >= 8  # o painel não come o editor
            assert _visivel(app, "#right") is direita
            assert _visivel(app, "#radar") is (altura >= 50)  # decorativo: sai primeiro em janelas baixas
            assert app.query_one("#explorer").styles.overflow_x == "hidden"
    asyncio.run(cenario())


def test_janela_baixa_esconde_feed_e_janela_alta_mostra_radar(projeto):
    from codar.studio.app import Studio

    async def cenario():
        app = Studio(projeto, local=True)
        async with app.run_test(size=(140, 26)) as pilot:
            await pilot.pause(.1)
            assert not _visivel(app, "#feed") and _linhas_explorer(app) >= 17
            await pilot.resize_terminal(200, 55)
            await pilot.pause(.1)
            assert _visivel(app, "#radar") and _visivel(app, "#feed") and _visivel(app, "#right")
            assert _linhas_explorer(app) >= 20
    asyncio.run(cenario())


def test_alca_arrasta_a_largura_e_clique_recolhe_e_expande(projeto):
    from codar.studio import estado
    from codar.studio.app import Studio

    async def cenario():
        app = Studio(projeto, local=True)
        async with app.run_test(size=(136, 35)) as pilot:
            await pilot.pause(.1)
            esquerda = app.query_one("#left")
            assert esquerda.outer_size.width == 32
            x, y = app.query_one("#alca-esquerda").region.x, 10  # coordenadas da tela: o botão solta onde o mouse está
            await pilot.mouse_down(None, offset=(x, y))
            await pilot.hover(None, offset=(x + 8, y))
            await pilot.mouse_up(None, offset=(x + 8, y))
            await pilot.pause(.1)
            assert esquerda.outer_size.width == 40
            assert estado.ler()["disposicao"]["esquerda"] == 40
            await pilot.click("#alca-esquerda", offset=(0, 10))  # clique sem arrastar: recolhe
            await pilot.pause(.1)
            assert not esquerda.display and not app.query_one("#alca-esquerda").aberta
            await pilot.click("#alca-esquerda", offset=(0, 10))  # de novo: volta com a largura escolhida
            await pilot.pause(.1)
            assert esquerda.display and esquerda.outer_size.width == 40
            # a coluna da direita, escondida nesta largura, abre pela alça da borda; o clique que chega depois na
            # mesma posição não recolhe o bloco que apareceu sob o ponteiro
            for altura in range(5, 30, 4):
                await pilot.click("#alca-direita", offset=(0, altura))
                await pilot.pause(.1)
                assert _visivel(app, "#right") and app.query_one("#center").region.width >= 40
                assert app._recolhidos == set(), altura
                await pilot.click("#alca-direita", offset=(0, altura))
                await pilot.pause(.1)
                assert not _visivel(app, "#right")
            await pilot.click("#alca-direita", offset=(0, 10))
            await pilot.pause(.1)

        segundo = Studio(projeto, local=True)  # a escolha sobrevive a reabrir o Studio
        async with segundo.run_test(size=(136, 35)) as pilot:
            await pilot.pause(.1)
            assert segundo.query_one("#left").outer_size.width == 40 and _visivel(segundo, "#right")
            segundo.action_restaurar_disposicao()
            await pilot.pause(.1)
            assert segundo.query_one("#left").outer_size.width == 32 and not _visivel(segundo, "#right")
            assert estado.ler()["disposicao"]["esquerda"] is None
    asyncio.run(cenario())


def test_titulo_recolhe_e_expande_blocos_e_o_painel(projeto):
    from codar.studio.app import Studio

    async def cenario():
        app = Studio(projeto, local=True)
        async with app.run_test(size=(136, 35)) as pilot:
            await app.open_file(projeto / "app.py")
            await pilot.pause(.1)
            feed = app.query_one("#feed")
            altura_feed = feed.outer_size.height
            await pilot.click("#explorer", offset=(6, 0))  # a linha do título (borda de cima)
            await pilot.pause(.1)
            explorer = app.query_one("#explorer")
            assert explorer.has_class("recolhido") and explorer.outer_size.height == 1
            assert explorer.border_title.startswith(("▸", ">")) and feed.outer_size.height > altura_feed
            await pilot.click("#explorer", offset=(6, 0))
            await pilot.pause(.1)
            assert not explorer.has_class("recolhido") and _linhas_explorer(app) >= 14

            painel = app.query_one("#panel")
            await pilot.click("#panel", offset=(6, 0))
            await pilot.pause(.1)
            assert painel.has_class("recolhido") and painel.outer_size.height == 1
            assert app.query_one("#editors").region.height >= 25  # o editor ganha o espaço
            painel.display = True  # o que um F5 ou o /btw faz: mostrar o painel o expande
            await pilot.pause(.1)
            assert not painel.has_class("recolhido") and painel.outer_size.height == 14
            await pilot.press("f9")  # F9 recolhe ao título e expande de novo
            await pilot.pause(.1)
            assert painel.has_class("recolhido")
            await pilot.press("f9")
            await pilot.pause(.1)
            assert not painel.has_class("recolhido") and painel.outer_size.height == 14
    asyncio.run(cenario())


def test_arrastar_o_titulo_do_painel_muda_a_altura(projeto):
    from codar.studio import estado
    from codar.studio.app import Studio

    async def cenario():
        app = Studio(projeto, local=True)
        async with app.run_test(size=(136, 40)) as pilot:
            await pilot.pause(.1)
            painel = app.query_one("#panel")
            assert painel.outer_size.height == 14
            x, y = painel.region.x + 10, painel.region.y  # a linha do título, em coordenadas da tela
            await pilot.mouse_down(None, offset=(x, y))
            await pilot.hover(None, offset=(x, y - 6))  # sobe 6 linhas
            await pilot.mouse_up(None, offset=(x, y - 6))
            await pilot.pause(.1)
            assert painel.outer_size.height == 20 and not painel.has_class("recolhido")
            assert estado.ler()["disposicao"]["painel"] == 20
            await pilot.press("shift+f9")  # maximizar continua funcionando com a altura escolhida
            await pilot.pause(.1)
            assert painel.outer_size.height > 25
            await pilot.press("shift+f9")
            await pilot.pause(.1)
            assert painel.outer_size.height == 20
    asyncio.run(cenario())


def test_alt_m_maximiza_o_editor_e_volta(projeto):
    from codar.studio.app import Studio

    async def cenario():
        app = Studio(projeto, local=True)
        async with app.run_test(size=(170, 46)) as pilot:
            await app.open_file(projeto / "app.py")
            await pilot.pause(.1)
            antes = app.query_one("#editors").region
            assert _visivel(app, "#left") and _visivel(app, "#right") and _visivel(app, "#panel")
            await pilot.press("alt+m")
            await pilot.pause(.1)
            depois = app.query_one("#editors").region
            assert not _visivel(app, "#left") and not _visivel(app, "#right") and not _visivel(app, "#panel")
            assert depois.width >= 160 and depois.height > antes.height + 10
            await pilot.press("alt+m")
            await pilot.pause(.1)
            assert _visivel(app, "#left") and _visivel(app, "#right") and _visivel(app, "#panel")
            assert app.query_one("#editors").region == antes
    asyncio.run(cenario())


def test_ferramentas_compactas_em_coluna_estreita(projeto):
    from codar.studio.app import Studio

    async def cenario():
        app = Studio(projeto, local=True)
        async with app.run_test(size=(96, 30)) as pilot:
            await pilot.pause(.1)
            botao = app.query_one("#translate-button")
            barra = app.query_one("#tools-bar")
            assert str(botao.content) == "▶ F3"
            assert sum(b.outer_size.width + 1 for b in barra.children) <= barra.size.width + 1  # nada cortado
            await pilot.resize_terminal(140, 35)
            await pilot.pause(.1)
            assert str(botao.content) == "▶ TRADUZIR F3"
    asyncio.run(cenario())
