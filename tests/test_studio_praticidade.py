"""Regressões dos fluxos relatados: Tab, cópia, Ctrl+Enter e contexto de arquivo."""

import asyncio
import shlex

import pytest

from codar.studio.completion import complete_command
from codar.studio.references import AmbiguousReference, referenced_files


def test_completa_caminhos_com_espacos_cd_e_cursor_no_meio(tmp_path):
    (tmp_path / "minha pasta").mkdir()
    (tmp_path / "minha pasta" / "app.py").write_text("x = 1\n")
    (tmp_path / "dados.txt").write_text("ok")
    choices = complete_command('cd "min', 7, tmp_path, {})
    assert shlex.split(choices[0][0]) == ["cd", "minha pasta/"]
    assert choices[0][1] == len(choices[0][0])
    choices = complete_command("python ap --help", 9, tmp_path / "minha pasta", {})
    assert choices == [("python app.py --help", 13)]
    assert complete_command("cd dados", 8, tmp_path, {}) == []


def test_completa_path_e_historico_sem_executar_comando(tmp_path):
    executable = tmp_path / "meu-comando"
    executable.write_text("#!/bin/sh\ntouch NAO_EXECUTAR\n")
    executable.chmod(0o755)
    assert ("meu-comando ", 12) in complete_command("meu-", 4, tmp_path, {"PATH": str(tmp_path)})
    assert not (tmp_path / "NAO_EXECUTAR").exists()
    assert complete_command("git st", 6, tmp_path, {}, ["git status"])[0] == ("git status", 10)


def test_referencias_respeitam_nome_exato_ambiguidade_e_exclusoes(tmp_path):
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "arquivo.py").write_text("x = 1\n")
    assert referenced_files(tmp_path, "crie uma interface diante do arquivo.py em minha pasta") == ["src/arquivo.py"]
    (tmp_path / "arquivo.py").write_text("x = 2\n")
    assert referenced_files(tmp_path, "melhore src/arquivo.py") == ["src/arquivo.py"]
    (tmp_path / "arquivo.py").unlink()
    (tmp_path / "outro").mkdir()
    (tmp_path / "outro" / "arquivo.py").write_text("x = 3\n")
    with pytest.raises(AmbiguousReference):
        referenced_files(tmp_path, "adapte arquivo.py")
    with pytest.raises(ValueError):
        referenced_files(tmp_path, "edite ../fora.py")
    (tmp_path / "codar.toml").write_text('[project]\nexclude=["src/*"]\n')
    with pytest.raises(ValueError):
        referenced_files(tmp_path, "edite src/arquivo.py")


async def wait(pilot, condition):
    for _ in range(80):
        await pilot.pause(0.05)
        if condition():
            return
    assert condition()


def test_tab_copia_historico_e_atalhos_no_terminal(tmp_path, monkeypatch):
    pytest.importorskip("textual")
    from textual.widgets import Input, TextArea
    from codar.studio.app import Studio
    from codar.studio.screens import TerminalOutputScreen

    monkeypatch.setenv("CODAR_HOME", str(tmp_path / "home"))
    monkeypatch.setenv("CODAR_NO_AUTOSTART", "1")
    monkeypatch.setenv("CODAR_SHELL_ENV", "0")
    (tmp_path / "alpha.py").write_text("x = 1\n")
    (tmp_path / "alpine.py").write_text("x = 2\n")

    async def scenario():
        app = Studio(tmp_path)
        async with app.run_test(size=(150, 42)) as pilot:
            await pilot.press("ctrl+t")
            field = app.query_one("#term-input", Input)
            field.value = "python al"
            field.cursor_position = len(field.value)
            await pilot.press("tab")
            assert field.value == "python alpha.py " and app.focused is field
            await pilot.press("tab")
            assert field.value == "python alpine.py "
            await pilot.press("shift+tab")
            assert field.value == "python alpha.py "
            field.value = "nao-encontrado-xyz"
            field.cursor_position = len(field.value)
            await pilot.press("tab")
            assert app.focused is field and field.value == "nao-encontrado-xyz"
            field.value = "meu rascunho"
            app.terminal.historico = ["echo anterior"]
            await pilot.press("up", "down")
            assert field.value == "meu rascunho"
            field.value = "echo palavra"
            field.cursor_position = len(field.value)
            await pilot.press("ctrl+w")
            assert field.value == "echo "
            log = app.terminal.sessao.log
            long = "Olá · " + "x" * 400
            log.write(long)
            await pilot.press("ctrl+shift+c")
            assert app.clipboard == long
            await pilot.press("ctrl+shift+a")
            assert isinstance(app.screen, TerminalOutputScreen)
            area = app.screen.query_one(TextArea)
            assert area.text == long and area.read_only
            app.copy_to_clipboard("clipboard anterior")
            await pilot.press("ctrl+a", "ctrl+c")
            assert area.selected_text == long
            assert app.clipboard == long
            await pilot.press("escape")
            field.focus()
            await pilot.press("ctrl+l")
            assert log.text() == "" and app.focused is field
            field.value = "echo terminal-ok"
            await pilot.press("ctrl+enter")
            await wait(pilot, lambda: "[exit 0" in log.text())
            assert "terminal-ok" in log.text()
    asyncio.run(scenario())


@pytest.mark.parametrize("selection", [((0, 0), (1, 0)), ((1, 0), (0, 0)), ((0, 0), (0, 14))])
def test_selecao_de_uma_linha_preserva_a_linha_seguinte(tmp_path, monkeypatch, selection):
    pytest.importorskip("textual")
    from textual.widgets.text_area import Selection
    from codar.studio.app import Studio

    monkeypatch.setenv("CODAR_HOME", str(tmp_path / "home"))
    monkeypatch.setenv("CODAR_NO_AUTOSTART", "1")
    monkeypatch.setenv("CODAR_SHELL_ENV", "0")
    original = 'x é igual a 10\nprint("linha seguinte")\n'
    file = tmp_path / "app.py"
    file.write_text(original)

    async def scenario():
        app = Studio(tmp_path, local=True)
        async with app.run_test(size=(150, 42)) as pilot:
            await app.open_file(file)
            await pilot.pause(.3)
            editor = app.current_editor()
            editor.selection = Selection(*selection)
            await pilot.press("ctrl+enter")
            await wait(pilot, lambda: "x = 10" in editor.text)
            assert editor.text == 'x = 10\nprint("linha seguinte")\n'
            editor.action_undo()
            assert editor.text == original
    asyncio.run(scenario())


def test_alvo_capturado_nao_muda_quando_cursor_vai_para_outra_linha():
    from codar.studio.edits import EditTarget

    original = '    x é igual a 10\n    print("vizinha")\n'
    # Inclui a quebra de linha, exclui a linha seguinte e conserva o recuo externo.
    target = EditTarget.capture(original, "block", (1, 0), ((0, 4), (1, 0)))
    result, _, _ = target.apply("    x = 10", [], "python", "    ")
    assert result == '    x = 10\n    print("vizinha")\n'
    line = EditTarget.capture(original, "line", (0, 0), ((0, 0), (0, 0)), row=0)
    assert line.apply("    x = 10", [], "python", "    ")[0] == result


@pytest.mark.parametrize("key", ["ctrl+enter", "ctrl+j", "ctrl+g"])
def test_ctrl_enter_na_intencao_usa_arquivo_citado_e_substitui(tmp_path, monkeypatch, key):
    pytest.importorskip("textual")
    from textual.widgets import Input
    from codar.studio.app import Studio
    from codar.studio.review import ReviewScreen

    monkeypatch.setenv("CODAR_HOME", str(tmp_path / "home"))
    monkeypatch.setenv("CODAR_NO_AUTOSTART", "1")
    monkeypatch.setenv("CODAR_SHELL_ENV", "0")
    original = "def calcular(a, b):\n    return a + b\n"
    file = tmp_path / "arquivo.py"
    file.write_text(original)
    requests = []

    class Backend:
        def stats(self):
            raise RuntimeError("sem daemon")

        def close(self):
            pass

        def translate(self, intent, lang, **kw):
            requests.append(dict(intent=intent, lang=lang, **kw))
            text = original + '\n# Interface\nimport tkinter as tk\n'
            return dict(stage="2:edit", source="teste", timings={}, body=text, code=text, lang="python",
                        imports=[], findings=[], notes=[], complete=True)

    async def scenario():
        app = Studio(tmp_path)
        app.backend = Backend()
        async with app.run_test(size=(150, 42)) as pilot:
            field = app.query_one("#intent", Input)
            field.focus()
            field.value = "crie uma interface gráfica diante do arquivo.py em minha pasta"
            await pilot.press(key)
            await wait(pilot, lambda: isinstance(app.screen, ReviewScreen))
            request = requests[0]
            assert request["mode"] == "edit" and request["selected"] == original
            assert request["file"] == str(file) and request["project_root"] == str(tmp_path)
            editor = app.current_editor()
            assert editor.text == original
            await pilot.click("#review-apply")
            await wait(pilot, lambda: "Interface" in editor.text)
            assert editor.text.count("def calcular") == 1
            assert file.read_text() == original
            editor.action_undo()
            assert editor.text == original
    asyncio.run(scenario())
