"""Terminal do Studio: programas que leem do teclado (input()) recebem o que se digita, e Ctrl+C interrompe."""

import asyncio
import os
from pathlib import Path

import pytest

textual = pytest.importorskip("textual")
pytestmark = pytest.mark.skipif(os.name != "posix", reason="pseudoterminal só em sistemas POSIX")


def _log(app):
    from textual.widgets import RichLog

    return "\n".join(linha.text for linha in app.query_one("#term-log", RichLog).lines)


async def _esperar(pilot, condicao, limite=150):
    for _ in range(limite):
        await pilot.pause(0.1)
        if condicao():
            return True
    return False


def test_input_e_ctrl_c(tmp_path: Path, monkeypatch):
    from textual.widgets import Input

    from codar.studio.app import Studio

    monkeypatch.setenv("CODAR_HOME", str(tmp_path / "home"))  # sem daemon: o Studio só precisa do terminal aqui
    monkeypatch.setenv("CODAR_NO_AUTOSTART", "1")  # e não deixa um daemon órfão rodando depois do teste
    (tmp_path / "perguntas.py").write_text('nome = input("Nome: ")\nprint(f"Olá, {nome}!")\n', encoding="utf-8")
    (tmp_path / "eterno.py").write_text(
        "import time\nprint('rodando')\ntry:\n    while True:\n        time.sleep(0.1)\n"
        "except KeyboardInterrupt:\n    print('interrompido')\n", encoding="utf-8")

    async def cenario():
        app = Studio(tmp_path)
        async with app.run_test(size=(150, 42)) as pilot:
            await app.open_file(tmp_path / "perguntas.py")
            await pilot.press("f5")
            campo = app.query_one("#term-input", Input)
            assert await _esperar(pilot, lambda: "Nome:" in campo.placeholder)
            assert app.focused is campo
            for tecla in "Ana":
                await pilot.press(tecla)
            await pilot.press("enter")
            assert await _esperar(pilot, lambda: "[exit 0" in _log(app))
            assert "Nome: Ana" in _log(app) and "Olá, Ana!" in _log(app)
            assert "$ python perguntas.py" in _log(app)

            await app.open_file(tmp_path / "eterno.py")
            await pilot.press("f5")
            assert await _esperar(pilot, lambda: "rodando" in _log(app))
            campo.focus()
            await pilot.press("ctrl+c")
            assert await _esperar(pilot, lambda: "interrompido" in _log(app))

    asyncio.run(cenario())
