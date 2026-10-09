"""Terminal integrado: ambiente do seu shell, cd que persiste, histórico, sugestões dos scripts do projeto e vários
terminais ao mesmo tempo (um servidor rodando num, comandos no outro)."""

import asyncio
import json
import os
import shutil
from pathlib import Path

import pytest

textual = pytest.importorskip("textual")
pytestmark = pytest.mark.skipif(os.name != "posix", reason="pseudoterminal só em sistemas POSIX")


def _texto(sessao) -> str:
    return "\n".join(linha.text for linha in sessao.log.lines)


async def _esperar(pilot, condicao, limite=150):
    for _ in range(limite):
        await pilot.pause(0.1)
        if condicao():
            return True
    return False


async def _digitar(pilot, texto: str) -> None:
    for ch in texto:
        await pilot.press({" ": "space"}.get(ch, ch))
    await pilot.press("enter")


@pytest.mark.skipif(not shutil.which("bash"), reason="precisa do bash")
def test_ambiente_do_shell_le_o_bashrc_e_ignora_o_que_ele_imprime(tmp_path, monkeypatch):
    from codar.studio.terminal import ambiente_do_shell

    (tmp_path / ".bashrc").write_text('echo "BANNER DO FASTFETCH"\nexport CODAR_TESTE=do_bashrc\n'
                                      'export PATH="$HOME/.bun/bin:$PATH"\n', encoding="utf-8")
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("SHELL", shutil.which("bash"))
    ambiente = ambiente_do_shell()
    assert ambiente["CODAR_TESTE"] == "do_bashrc"
    assert ambiente["PATH"].startswith(f"{tmp_path}/.bun/bin:")
    assert not any("BANNER" in v for v in ambiente.values())


def test_comandos_do_projeto_sugere_os_scripts_com_o_gerenciador_certo(tmp_path):
    from codar.studio.terminal import comandos_do_projeto

    (tmp_path / "package.json").write_text(json.dumps({"scripts": {"lint": "x", "dev": "vite", "build": "vite build"}}))
    (tmp_path / "bun.lock").write_text("")
    cmds = comandos_do_projeto(tmp_path)
    assert cmds[:4] == ["bun install", "bun run dev", "bun run build", "bun run lint"]  # sem node_modules: instalar primeiro


def test_cd_historico_e_varios_terminais(tmp_path, monkeypatch):
    from textual.widgets import Input

    from codar.studio.app import Studio

    monkeypatch.setenv("CODAR_HOME", str(tmp_path / "home"))
    monkeypatch.setenv("CODAR_NO_AUTOSTART", "1")
    projeto = tmp_path / "projeto"
    (projeto / "src").mkdir(parents=True)
    servidor = "import time\nprint('Local: http://localhost:5173/', flush=True)\ntime.sleep(30)\n"
    (projeto / "servidor.py").write_text(servidor, encoding="utf-8")

    async def cenario():
        app = Studio(projeto)
        async with app.run_test(size=(150, 42)) as pilot:
            await pilot.press("ctrl+t")
            terminal = app.terminal
            campo = app.query_one("#term-input", Input)

            await _digitar(pilot, "cd src")
            await _digitar(pilot, "pwd")
            assert await _esperar(pilot, lambda: str(projeto / "src") in _texto(terminal.sessao))
            await _digitar(pilot, "cd ..")

            await pilot.press("up")  # histórico
            assert campo.value == "cd .."
            await pilot.press("up")
            assert campo.value == "pwd"
            campo.value = ""

            await _digitar(pilot, "python3 servidor.py")
            primeiro = terminal.sessao
            assert await _esperar(pilot, lambda: primeiro.url == "http://localhost:5173/")  # servidor detectado
            assert primeiro.rodando()

            await pilot.press("ctrl+t")  # já no terminal: abre outro, o servidor continua
            assert terminal.sessao is not primeiro and len(terminal.sessoes) == 2
            await _digitar(pilot, "echo segundo")
            assert await _esperar(pilot, lambda: "segundo" in _texto(terminal.sessao) and "[exit 0" in _texto(terminal.sessao))
            assert primeiro.rodando()

            await pilot.press("ctrl+pageup")  # volta para o terminal do servidor
            assert terminal.sessao is primeiro
            await pilot.press("ctrl+c")
            assert await _esperar(pilot, lambda: not primeiro.rodando())

            await pilot.press("ctrl+pagedown")
            await _digitar(pilot, "exit")  # fecha o terminal 2
            assert len(terminal.sessoes) == 1 and terminal.sessao is primeiro

    asyncio.run(cenario())
