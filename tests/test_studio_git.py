"""Git no Studio, de ponta a ponta com um repositório de verdade: painel, trechos, commit, branch, marcas e conflito."""

import asyncio
import shutil
import subprocess

import pytest

pytest.importorskip("textual")
pytestmark = pytest.mark.skipif(shutil.which("git") is None, reason="git não instalado")

LINHAS = [f"linha {n}" for n in range(1, 31)]


def ramo(nome):
    from codar.studio.widgets import ASCII

    return ("git:" if ASCII else "⎇ ") + nome  # terminais sem Unicode (TERM=linux) usam texto simples


@pytest.fixture
def projeto(tmp_path, monkeypatch):
    config = tmp_path / "gitconfig"
    config.write_text("")
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", str(config))
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")
    for variavel in ("GIT_AUTHOR_NAME", "GIT_COMMITTER_NAME"):
        monkeypatch.setenv(variavel, "Pessoa Teste")
    for variavel in ("GIT_AUTHOR_EMAIL", "GIT_COMMITTER_EMAIL"):
        monkeypatch.setenv(variavel, "pessoa@exemplo.invalid")
    monkeypatch.setenv("CODAR_HOME", str(tmp_path / "home"))
    monkeypatch.setenv("CODAR_NO_AUTOSTART", "1")
    raiz = tmp_path / "projeto"
    raiz.mkdir()
    sh(raiz, "init", "-q", "-b", "main")
    (raiz / "lista.txt").write_text("\n".join(LINHAS) + "\n", encoding="utf-8")
    (raiz / "app.py").write_text("def saudacao():\n    return 'oi'\n", encoding="utf-8")
    sh(raiz, "add", "-A")
    sh(raiz, "commit", "-q", "-m", "base")
    return raiz


def sh(pasta, *args, ok=(0,)):
    saida = subprocess.run(["git", *args], cwd=pasta, capture_output=True, text=True)
    assert saida.returncode in ok, saida.stderr
    return saida.stdout


async def esperar(pilot, condicao, vezes=200):
    for _ in range(vezes):
        if condicao():
            return True
        await pilot.pause(.05)
    return condicao()


async def destacar(app, pilot, identidade):
    from textual.widgets import OptionList

    lista = app.query_one("#git-changes", OptionList)
    assert await esperar(pilot, lambda: any(lista.get_option_at_index(i).id == identidade
                                            for i in range(lista.option_count)))
    lista.highlighted = next(i for i in range(lista.option_count) if lista.get_option_at_index(i).id == identidade)
    lista.focus()
    await pilot.pause()
    return lista


def test_painel_trechos_marcas_commit_e_branch(projeto):
    from textual.widgets import Input, TabbedContent

    from codar.studio.app import Studio
    from codar.studio.controle_versao import DiffScreen
    from codar.studio.explorer import ConfirmScreen, Explorer

    alterado = LINHAS.copy()
    alterado[1] = "linha 2 alterada"
    alterado[25] = "perto do fim alterada"
    (projeto / "lista.txt").write_text("\n".join(alterado) + "\n", encoding="utf-8")
    (projeto / "novo.py").write_text("print('novo')\n", encoding="utf-8")

    async def cenario():
        app = Studio(projeto, local=True)
        async with app.run_test(size=(170, 50)) as pilot:
            assert await esperar(pilot, lambda: app._git_estado is not None)
            assert app.git_rotulo() == ramo("main •2")
            explorer = app.query_one("#explorer", Explorer)
            assert explorer.git_arquivos[projeto / "novo.py"] == ("N", "green")
            assert explorer.git_arquivos[projeto / "lista.txt"] == ("M", "cyan")

            await app.open_file(projeto / "lista.txt")
            ed = app.current_editor()
            assert await esperar(pilot, lambda: ed.marcas_git == {1: "alterado", 25: "alterado"})
            ed.move_cursor((5, 0))
            ed.insert("inserida\n")
            assert await esperar(pilot, lambda: ed.marcas_git.get(5) == "novo")
            ed.replace("", (5, 0), (6, 0))  # volta ao texto do disco
            assert await esperar(pilot, lambda: 5 not in ed.marcas_git and not ed.dirty)

            await pilot.press("alt+g")
            assert app.query_one("#panel", TabbedContent).active == "tab-git"
            await destacar(app, pilot, "t:lista.txt")
            await pilot.press("enter")
            assert await esperar(pilot, lambda: isinstance(app.screen, DiffScreen))
            tela = app.screen
            assert len(tela.diff.trechos) == 2
            await pilot.press("s")  # prepara só o primeiro trecho
            assert await esperar(pilot, lambda: len(tela.diff.trechos) == 1)
            assert "linha 2 alterada" in sh(projeto, "diff", "--cached")
            await pilot.press("t")  # o lado preparado
            assert tela.preparada and len(tela.diff.trechos) == 1
            await pilot.press("u")
            assert await esperar(pilot, lambda: tela.diff is None or not tela.diff.trechos)
            assert sh(projeto, "diff", "--cached") == ""
            await pilot.press("t")
            await pilot.press("d")  # descarta o trecho destacado (o primeiro), com confirmação
            assert await esperar(pilot, lambda: isinstance(app.screen, ConfirmScreen))
            await pilot.press("s")
            assert await esperar(pilot, lambda: "linha 2\n" in (projeto / "lista.txt").read_text())
            assert "perto do fim alterada" in (projeto / "lista.txt").read_text()
            # a aba aberta (sem alterações não salvas) recarrega o disco
            assert await esperar(pilot, lambda: ed.text.split("\n")[1] == "linha 2")
            assert await esperar(pilot, lambda: ed.marcas_git == {25: "alterado"})
            await pilot.press("escape")
            assert await esperar(pilot, lambda: not isinstance(app.screen, DiffScreen))

            # Commit sem nada preparado: oferece preparar tudo (inclusive o arquivo novo).
            campo = app.query_one("#git-message", Input)
            campo.focus()
            campo.value = "Ajusta a lista"
            await pilot.press("enter")
            assert await esperar(pilot, lambda: isinstance(app.screen, ConfirmScreen))
            await pilot.press("s")
            assert await esperar(pilot, lambda: "Ajusta a lista" in sh(projeto, "log", "-1", "--format=%s"))
            assert await esperar(pilot, lambda: campo.value == "" and app.git_rotulo() == ramo("main"))
            assert sh(projeto, "status", "--porcelain") == ""
            assert await esperar(pilot, lambda: ed.marcas_git == {} and explorer.git_arquivos == {})

            # Branch nova pela lista de branches.
            app.action_git_branch()
            await pilot.pause()
            await pilot.press("enter")  # primeira opção: criar branch
            await pilot.pause()
            await pilot.press(*"tarefa/x", "enter")
            assert await esperar(pilot, lambda: sh(projeto, "branch", "--show-current").strip() == "tarefa/x")
            assert await esperar(pilot, lambda: app.git_rotulo() == ramo("tarefa/x"))
    asyncio.run(cenario())


def test_descartar_arquivo_novo_vai_para_a_lixeira(projeto):
    from codar.studio.app import Studio
    from codar.studio.explorer import ConfirmScreen

    (projeto / "rascunho.txt").write_text("rascunho\n", encoding="utf-8")
    antigo = projeto / ".codar" / "lixeira" / "20260101-000000" / "velho.txt"  # lixeira de uma versão anterior
    antigo.parent.mkdir(parents=True)
    antigo.write_text("velho\n", encoding="utf-8")

    async def cenario():
        app = Studio(projeto, local=True)
        async with app.run_test(size=(170, 50)) as pilot:
            assert await esperar(pilot, lambda: app._git_estado is not None)
            await destacar(app, pilot, "t:rascunho.txt")
            await pilot.press("d")
            assert await esperar(pilot, lambda: isinstance(app.screen, ConfirmScreen))
            await pilot.press("s")
            assert await esperar(pilot, lambda: not (projeto / "rascunho.txt").exists())
            assert [p.read_text() for p in (projeto / ".codar" / "lixeira").rglob("rascunho.txt")] == ["rascunho\n"]
            assert await esperar(pilot, lambda: app._git_estado is not None and app._git_estado.mudancas == [])
    asyncio.run(cenario())


def test_conflito_resolvido_no_studio_e_mudanca_externa_percebida(projeto):
    from codar.studio.app import Studio
    from codar.studio.controle_versao import ConflitoScreen
    from codar.studio.explorer import ConfirmScreen

    sh(projeto, "switch", "-q", "-c", "outra")
    (projeto / "app.py").write_text("def saudacao():\n    return 'olá'\n", encoding="utf-8")
    sh(projeto, "commit", "-q", "-am", "outra")
    sh(projeto, "switch", "-q", "main")
    (projeto / "app.py").write_text("def saudacao():\n    return 'bom dia'\n", encoding="utf-8")
    sh(projeto, "commit", "-q", "-am", "main")

    async def cenario():
        app = Studio(projeto, local=True)
        async with app.run_test(size=(170, 50)) as pilot:
            assert await esperar(pilot, lambda: app._git_estado is not None)
            await app.open_file(projeto / "app.py")
            ed = app.current_editor()
            sh(projeto, "merge", "outra", ok=(1,))  # por fora do Studio, como no terminal
            # o Studio percebe pelo índice: estado com conflito e a aba recarregada com as marcas
            assert await esperar(pilot, lambda: app._git_estado.em_merge and app.git_rotulo().endswith("!1"))
            assert await esperar(pilot, lambda: "<<<<<<< HEAD" in ed.text)
            await destacar(app, pilot, "c:app.py")
            await pilot.press("enter")
            assert await esperar(pilot, lambda: isinstance(app.screen, ConflitoScreen))
            await pilot.press("2")  # aceita o que entra
            assert await esperar(pilot, lambda: (projeto / "app.py").read_text() == "def saudacao():\n    return 'olá'\n")
            assert ed.text == "def saudacao():\n    return 'olá'\n" and not ed.dirty
            await pilot.press("escape")
            assert await esperar(pilot, lambda: isinstance(app.screen, ConfirmScreen))
            await pilot.press("s")  # marcar como resolvido
            assert await esperar(pilot, lambda: not app._git_estado.conflitos)
            app.query_one("#git-message").value = "Merge da outra"
            app.action_git_commit()
            assert await esperar(pilot, lambda: not app._git_estado.em_merge)
            assert sh(projeto, "log", "-1", "--format=%s").strip() == "Merge da outra"
    asyncio.run(cenario())


def test_pasta_sem_git_e_iniciar(tmp_path, monkeypatch):
    from textual.widgets import Static

    from codar.studio.app import Studio

    monkeypatch.setenv("CODAR_HOME", str(tmp_path / "home"))
    monkeypatch.setenv("CODAR_NO_AUTOSTART", "1")
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", str(tmp_path / "vazio"))
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")
    (tmp_path / "vazio").write_text("")
    raiz = tmp_path / "solto"
    raiz.mkdir()

    async def cenario():
        app = Studio(raiz, local=True)
        async with app.run_test(size=(170, 50)) as pilot:
            await pilot.pause(.2)
            assert app._repo is None and app.git_rotulo() == ""
            assert "não está num repositório git" in str(app.query_one("#git-status", Static).content)
            app.action_git_iniciar()
            await pilot.pause()
            await pilot.press("s")
            assert await esperar(pilot, lambda: app._repo is not None and app._git_estado is not None)
            assert (raiz / ".git").is_dir() and app.git_rotulo().startswith(ramo(""))  # main ou master, conforme o git
    asyncio.run(cenario())
