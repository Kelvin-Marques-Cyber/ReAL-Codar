"""Servidores de linguagem no Studio: confiança por projeto, diagnósticos na margem e em PROBLEMAS, definição,
referências, informações, renomear e formatar."""

import asyncio
import json
import os
import shutil
import sys
from pathlib import Path

import pytest

pytest.importorskip("textual")

FALSO = [sys.executable, str(Path(__file__).with_name("lsp_falso.py"))]


def _ambiente(tmp_path, monkeypatch, servidores: dict | None, confiar: bool):
    from codar import paths
    from codar.studio import estado

    monkeypatch.setenv("CODAR_HOME", str(tmp_path / "home"))
    monkeypatch.setenv("CODAR_NO_AUTOSTART", "1")
    monkeypatch.setenv("PATH", os.pathsep.join([str(Path(sys.executable).parent), os.environ.get("PATH", "")]))
    raiz = tmp_path / "projeto"
    raiz.mkdir()
    if servidores:
        paths.config_file().parent.mkdir(parents=True, exist_ok=True)
        linhas = "\n".join(f"{lang} = {json.dumps(cmd)}" for lang, cmd in servidores.items())
        paths.config_file().write_text(f"[lsp.servers]\n{linhas}\n", encoding="utf-8")
    if confiar:
        estado.salvar(lsp_confiaveis=[str(raiz.resolve())])
    return raiz


async def _esperar(pilot, condicao, vezes=150):
    for _ in range(vezes):
        await pilot.pause(.05)
        if condicao():
            return True
    return condicao()


def test_diagnosticos_e_acoes_com_servidor(tmp_path, monkeypatch):
    from textual.widgets import DataTable, Input

    from codar.studio.app import Studio
    from codar.studio.explorer import ConfirmScreen
    from codar.studio.review import ChoiceScreen
    from codar.studio.screens import PromptScreen, TerminalOutputScreen

    raiz = _ambiente(tmp_path, monkeypatch, {"python": FALSO}, confiar=True)
    arquivo = raiz / "m.py"
    arquivo.write_text("alvo = 1\nprint(alvo)  # erro\n", encoding="utf-8")

    async def cenario():
        app = Studio(raiz, local=True)
        async with app.run_test(size=(160, 44)) as pilot:
            await app.open_file(arquivo)
            ed = app.current_editor()
            assert await _esperar(pilot, lambda: ed.marcas_diagnostico.get(1) == "error")
            assert ed.mensagens_diagnostico[1] == "palavra proibida"
            tabela = app.query_one("#problems", DataTable)
            assert await _esperar(pilot, lambda: tabela.row_count == 1)
            assert "falso:F1" in str(tabela.get_row_at(0)[1])
            assert app.lsp_rotulo().startswith("LSP python") and "✗1" in app.lsp_rotulo()
            ed.focus()
            ed.move_cursor((1, 8))
            await pilot.pause(.1)
            assert app.context_hint().startswith("palavra proibida")

            await pilot.press("alt+d")  # definição: linha 0
            assert await _esperar(pilot, lambda: ed.cursor_location == (0, 0))

            await pilot.press("alt+u")  # referências
            assert await _esperar(pilot, lambda: isinstance(app.screen, ChoiceScreen))
            assert "2 em 1 arquivo" in app.screen.title_text
            await pilot.press("escape")

            await pilot.press("alt+h")  # informações
            assert await _esperar(pilot, lambda: isinstance(app.screen, TerminalOutputScreen))
            assert "alvo(x: int) -> int" in app.screen.text and "alvo: int" in app.screen.text
            await pilot.press("escape")

            await pilot.press("alt+f")  # formatar
            assert await _esperar(pilot, lambda: ed.text.startswith("# formatado\nalvo = 1"))
            await pilot.press("ctrl+z")  # uma única edição: um Ctrl+Z desfaz
            assert await _esperar(pilot, lambda: ed.text == "alvo = 1\nprint(alvo)  # erro\n")

            ed.move_cursor((0, 1))
            await pilot.press("alt+r")  # renomear
            assert await _esperar(pilot, lambda: isinstance(app.screen, PromptScreen))
            app.screen.query_one(Input).value = "novo"
            await pilot.press("enter")
            assert await _esperar(pilot, lambda: isinstance(app.screen, ConfirmScreen))
            assert "2 alteração(ões) em 1 arquivo" in app.screen.pergunta
            await pilot.press("enter")
            assert await _esperar(pilot, lambda: ed.text == "novo = 1\nprint(novo)  # erro\n")
            assert arquivo.read_text() == "alvo = 1\nprint(alvo)  # erro\n"  # aberto: alterado no editor, não no disco

            ed.text = "novo = 1\n"  # sem a palavra proibida, o diagnóstico some
            assert await _esperar(pilot, lambda: not ed.marcas_diagnostico)
            processo = app._lsp._do_documento(arquivo).processo
        assert not processo.vivo or await asyncio.sleep(.5) or not processo.vivo
    asyncio.run(cenario())


def test_projeto_nao_confiavel_so_sugere_e_alt_l_ativa(tmp_path, monkeypatch):
    from codar.studio.app import Studio
    from codar.studio.explorer import ConfirmScreen

    raiz = _ambiente(tmp_path, monkeypatch, {"python": FALSO}, confiar=False)
    arquivo = raiz / "m.py"
    arquivo.write_text("x = 1  # erro\n", encoding="utf-8")

    async def cenario():
        app = Studio(raiz, local=True)
        async with app.run_test(size=(160, 44)) as pilot:
            await app.open_file(arquivo)
            ed = app.current_editor()
            await pilot.pause(.5)
            assert not ed.marcas_diagnostico and app._lsp.estado() == {}  # nenhum servidor iniciado
            assert app.lsp_rotulo() == "LSP ALT+L"
            await pilot.press("alt+d")
            assert not isinstance(app.screen, ConfirmScreen)  # só avisa
            await pilot.press("alt+l")
            assert await _esperar(pilot, lambda: isinstance(app.screen, ConfirmScreen))
            assert "python: python" in app.screen.detalhe and "scripts de build" in app.screen.detalhe
            await pilot.press("enter")
            assert await _esperar(pilot, lambda: ed.marcas_diagnostico.get(0) == "error")
            from codar.studio import estado
            assert str(raiz.resolve()) in estado.ler()["lsp_confiaveis"]

            await pilot.press("alt+l")  # desativar
            assert await _esperar(pilot, lambda: isinstance(app.screen, ConfirmScreen))
            await pilot.press("enter")
            # nenhum servidor em execução; a barra de status só consulta o PATH para sugerir Alt+L
            assert await _esperar(pilot, lambda: not ed.marcas_diagnostico and not app._lsp.estado())
            assert app.lsp_rotulo() == "LSP ALT+L"
    asyncio.run(cenario())


@pytest.mark.slow
def test_pylsp_no_studio_vai_para_definicao_em_outro_arquivo(tmp_path, monkeypatch):
    if not shutil.which("pylsp", path=os.pathsep.join([str(Path(sys.executable).parent), os.environ.get("PATH", "")])):
        pytest.skip("pylsp ausente")
    from codar.studio.app import Studio

    raiz = _ambiente(tmp_path, monkeypatch, None, confiar=True)
    (raiz / "calc.py").write_text("def somar(a, b):\n    return a + b\n", encoding="utf-8")
    main = raiz / "main.py"
    main.write_text("from calc import somar\n\ntotal = somar(2, 3)\nprint(totl)\n", encoding="utf-8")

    async def cenario():
        app = Studio(raiz, local=True)
        async with app.run_test(size=(160, 44)) as pilot:
            await app.open_file(main)
            ed = app.current_editor()
            assert await _esperar(pilot, lambda: 3 in ed.marcas_diagnostico, vezes=300)  # totl não existe
            ed.focus()
            ed.move_cursor((2, 10))
            await pilot.press("alt+d")
            assert await _esperar(pilot, lambda: app.current_editor() is not ed, vezes=200)
            novo = app.current_editor()
            assert Path(novo.path).name == "calc.py" and novo.cursor_location[0] == 0
    asyncio.run(cenario())
