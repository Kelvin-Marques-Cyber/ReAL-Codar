"""Depurador no Studio: breakpoints na margem, deslocamento ao editar, debugpy e GDB de ponta a ponta."""

import asyncio
import shutil
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

pytest.importorskip("textual")

PROGRAMA = textwrap.dedent("""\
    def dobro(x):
        y = x * 2
        return y

    nome = "Ana"
    r = dobro(21)
    print("depois", r)
    """)


def _studio(tmp_path, monkeypatch):
    monkeypatch.setenv("CODAR_HOME", str(tmp_path / "home"))
    monkeypatch.setenv("CODAR_NO_AUTOSTART", "1")
    raiz = tmp_path / "projeto"
    raiz.mkdir()
    return raiz


async def _esperar(pilot, condicao, vezes=200):
    for _ in range(vezes):
        await pilot.pause(.05)
        if condicao():
            return True
    return condicao()


def test_breakpoints_alt_b_clique_persistencia_e_deslocamento(tmp_path, monkeypatch):
    from codar.studio.app import Studio
    from codar.studio.widgets import CodeEditor

    raiz = _studio(tmp_path, monkeypatch)
    arquivo = raiz / "alvo.py"
    arquivo.write_text(PROGRAMA, encoding="utf-8")

    async def cenario():
        app = Studio(raiz, local=True)
        async with app.run_test(size=(160, 44)) as pilot:
            await app.open_file(arquivo)
            ed = app.current_editor()
            ed.focus()
            ed.move_cursor((1, 0))
            await pilot.press("alt+b")
            assert ed.breakpoints == {1}
            await pilot.click(CodeEditor, offset=(ed.gutter.left + 1, ed.gutter.top + 5))  # margem da linha 6
            assert await _esperar(pilot, lambda: ed.breakpoints == {1, 5})
            assert ed.cursor_location == (1, 0)  # o clique na margem não move o cursor

            ed.insert("# comentário\n", (0, 0))  # uma linha a mais acima: tudo desce
            assert ed.breakpoints == {2, 6}
            ed.move_cursor((2, 0))
            ed.insert("\n")  # Enter no início da linha do breakpoint: ele acompanha o código
            assert ed.breakpoints == {3, 7}
            ed.delete((0, 0), (2, 0))  # duas linhas a menos
            assert ed.breakpoints == {1, 5}
            ed.replace(ed.text.replace("nome", "nome_completo"), (0, 0), ed.document.end)  # formatar o arquivo todo
            assert ed.breakpoints == {1, 5}

            await pilot.press("ctrl+s")
            await pilot.press("ctrl+w")
            await app.open_file(arquivo)  # reaberto: os breakpoints continuam lá
            assert app.current_editor().breakpoints == {1, 5}
        from codar.studio import estado
        assert estado.ler()["breakpoints"][str(raiz.resolve())] == {"alvo.py": [1, 5]}
    asyncio.run(cenario())


def test_linguagem_sem_depurador_e_debugpy_ausente(tmp_path, monkeypatch):
    from codar.studio.app import Studio
    from codar.studio.explorer import ConfirmScreen

    raiz = _studio(tmp_path, monkeypatch)
    (raiz / "pagina.html").write_text("<p>oi</p>\n", encoding="utf-8")
    sem_debugpy = shutil.which("python3", path="/usr/bin")
    if sem_debugpy is None or subprocess.run([sem_debugpy, "-c", "import debugpy"], capture_output=True).returncode == 0:
        pytest.skip("é preciso um Python sem debugpy")
    subprocess.run([sem_debugpy, "-m", "venv", "--without-pip", str(raiz / ".venv")], check=True)
    (raiz / "alvo.py").write_text(PROGRAMA, encoding="utf-8")

    async def cenario():
        app = Studio(raiz, local=True)
        async with app.run_test(size=(160, 44)) as pilot:
            avisos = []
            app.notify = lambda mensagem, **_: avisos.append(mensagem)
            await app.open_file(raiz / "pagina.html")
            await pilot.press("ctrl+f5")
            assert await _esperar(pilot, lambda: any("Python, C, C++ e Rust" in a for a in avisos))
            await app.open_file(raiz / "alvo.py")
            await pilot.press("ctrl+f5")
            assert await _esperar(pilot, lambda: isinstance(app.screen, ConfirmScreen))
            assert "pip install debugpy" in app.screen.detalhe and ".venv" in app.screen.detalhe
            await pilot.press("escape")  # recusar não executa nada
            assert not app.dap_ativo()
    asyncio.run(cenario())


@pytest.mark.slow
def test_depurar_python_no_studio(tmp_path, monkeypatch):
    if subprocess.run([sys.executable, "-c", "import debugpy"], capture_output=True).returncode:
        pytest.skip("debugpy ausente")
    from textual.widgets import Input, OptionList, RichLog, Static, Tree

    from codar.studio.app import Studio

    raiz = _studio(tmp_path, monkeypatch)  # sem .venv no projeto, o Studio usa o próprio Python, que tem debugpy
    arquivo = raiz / "alvo.py"
    arquivo.write_text(PROGRAMA, encoding="utf-8")

    async def cenario():
        app = Studio(raiz, local=True)
        async with app.run_test(size=(160, 50)) as pilot:
            await app.open_file(arquivo)
            ed = app.current_editor()
            ed.breakpoints = {1}
            await pilot.press("ctrl+f5")
            status = app.query_one("#debug-status", Static)
            assert await _esperar(pilot, lambda: ed.linha_depuracao == 1, vezes=400), str(status.content)
            assert "PARADO" in str(status.content) and "breakpoint" in str(status.content)
            pilha = app.query_one("#debug-stack", OptionList)
            assert pilha.option_count == 2 and "dobro" in str(pilha.get_option_at_index(0).prompt)
            arvore = app.query_one("#debug-vars", Tree)
            assert await _esperar(pilot, lambda: any("x = 21" in str(n.label) for n in arvore.root.children[0].children))

            campo = app.query_one("#debug-eval", Input)
            campo.focus()
            campo.value = "x * 10"
            await pilot.press("enter")
            console = app.query_one("#debug-console", RichLog)
            assert await _esperar(pilot, lambda: any("210" in "".join(s.text for s in l) for l in console.lines))

            ed.focus()
            await pilot.press("f10")  # passa por cima: linha 3 (return y)
            assert await _esperar(pilot, lambda: ed.linha_depuracao == 2)
            await pilot.press("f5")  # continua até o fim
            assert await _esperar(pilot, lambda: not app.dap_ativo(), vezes=400)
            assert ed.linha_depuracao is None
            texto = "\n".join("".join(s.text for s in l) for l in console.lines)
            assert "depois 42" in texto and "terminou" in str(status.content)
    asyncio.run(cenario())


@pytest.mark.slow
def test_depurar_c_no_studio_com_gdb(tmp_path, monkeypatch):
    from codar.ide import dap

    if (dap.versao_gdb() or 0) < 14 or not shutil.which("cc"):
        pytest.skip("gdb 14+ ou compilador C ausente")
    from textual.widgets import OptionList

    from codar.studio.app import Studio

    raiz = _studio(tmp_path, monkeypatch)
    arquivo = raiz / "alvo.c"
    arquivo.write_text("#include <stdio.h>\nint dobro(int x) {\n    int y = x * 2;\n    return y;\n}\n"
                       "int main(void) {\n    int r = dobro(21);\n    printf(\"depois %d\\n\", r);\n    return 0;\n}\n")

    async def cenario():
        app = Studio(raiz, local=True)
        async with app.run_test(size=(160, 50)) as pilot:
            await app.open_file(arquivo)
            ed = app.current_editor()
            ed.breakpoints = {2}
            await pilot.press("ctrl+f5")
            assert await _esperar(pilot, lambda: ed.linha_depuracao == 2, vezes=400)
            pilha = app.query_one("#debug-stack", OptionList)
            assert "dobro" in str(pilha.get_option_at_index(0).prompt)
            await pilot.press("shift+f11")  # sai de dobro: volta para main
            assert await _esperar(pilot, lambda: ed.linha_depuracao == 6)
            await pilot.press("shift+f5")  # para
            assert await _esperar(pilot, lambda: not app.dap_ativo() and ed.linha_depuracao is None)
    asyncio.run(cenario())
