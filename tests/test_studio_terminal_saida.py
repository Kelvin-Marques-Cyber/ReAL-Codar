"""F5 mostra a saída do programa: em qualquer perspectiva, com espaço útil e com a pergunta de um input() visível."""

import asyncio
import html
import re

import pytest

pytest.importorskip("textual")

from codar.studio.app import Studio


def _tela(app) -> str:
    """Texto desenhado na tela (o SVG troca espaços por &#160;)."""
    return html.unescape("".join(re.findall(r">([^<>]+)</text>", app.export_screenshot()))).replace("\xa0", " ")


def _studio(tmp_path, monkeypatch):
    monkeypatch.setenv("CODAR_HOME", str(tmp_path / "home"))
    monkeypatch.setenv("CODAR_NO_AUTOSTART", "1")
    raiz = tmp_path / "projeto"
    raiz.mkdir()
    return Studio(raiz, local=True), raiz


async def _esperar(pilot, condicao, vezes=100):
    for _ in range(vezes):
        await pilot.pause(0.05)
        if condicao():
            return
    assert condicao()


@pytest.mark.parametrize("perspectiva", ["essential", "development", "learning"])
def test_f5_mostra_a_saida_em_qualquer_perspectiva(tmp_path, monkeypatch, perspectiva):
    app, raiz = _studio(tmp_path, monkeypatch)
    (raiz / "ola.py").write_text("for i in range(3):\n    print('linha', i)\n", encoding="utf-8")

    async def cenario():
        async with app.run_test(size=(100, 30)) as pilot:
            app.apply_perspective(perspectiva, save=False)
            await app.open_file(raiz / "ola.py")
            await pilot.pause(0.2)
            await app.action_run_file()
            await _esperar(pilot, lambda: app.terminal.sessao.codigo is not None)
            await pilot.pause(0.3)
            tela = _tela(app)
            assert "linha 2" in tela and "exit 0" in tela
            assert app.terminal.sessao.log.text().count("$ python ola.py") == 1  # o texto copiável não duplica
    asyncio.run(cenario())


def test_saida_do_terminal_tem_espaco_util_e_pode_ser_maximizada(tmp_path, monkeypatch):
    app, raiz = _studio(tmp_path, monkeypatch)

    async def cenario():
        async with app.run_test(size=(100, 30)) as pilot:
            app.query_one("#panel").active = "tab-terminal"
            await pilot.pause(0.3)
            log = app.terminal.sessao.log
            normal = log.size.height
            assert normal >= 6, normal
            app.action_maximize_panel()
            await pilot.pause(0.2)
            assert log.size.height > normal + 4 and app.query_one("#panel").has_class("maximizado")
            app.action_maximize_panel()
            await pilot.pause(0.2)
            assert log.size.height == normal
    asyncio.run(cenario())


def test_pergunta_de_input_aparece_antes_da_resposta_e_sem_repetir(tmp_path, monkeypatch):
    app, raiz = _studio(tmp_path, monkeypatch)
    (raiz / "pergunta.py").write_text("nome = input('Seu nome: ')\nprint('oi', nome)\n", encoding="utf-8")

    async def cenario():
        async with app.run_test(size=(100, 30)) as pilot:
            await app.open_file(raiz / "pergunta.py")
            await pilot.pause(0.2)
            await app.action_run_file()
            await _esperar(pilot, lambda: "Seu nome:" in _tela(app) and app.terminal.sessao.esperando)
            app.terminal.enviar("Ana")
            await _esperar(pilot, lambda: app.terminal.sessao.codigo is not None)
            await pilot.pause(0.3)
            texto = app.terminal.sessao.log.text()
            assert "oi Ana" in texto and texto.count("Seu nome:") == 1, texto
            assert "oi Ana" in _tela(app)
    asyncio.run(cenario())
