"""Explorer do Studio pelo teclado: criar arquivo e pasta, renomear, duplicar, copiar e colar, apagar para a lixeira e
copiar arquivos arrastados do gerenciador de arquivos (o terminal cola o caminho)."""

import asyncio
from pathlib import Path

import pytest

textual = pytest.importorskip("textual")


def _studio(tmp_path: Path, monkeypatch):
    from codar.studio.app import Studio

    monkeypatch.setenv("CODAR_HOME", str(tmp_path / "home"))
    monkeypatch.setenv("CODAR_NO_AUTOSTART", "1")
    projeto = tmp_path / "projeto"
    (projeto / "src").mkdir(parents=True)
    (projeto / "main.py").write_text("print('oi')\n", encoding="utf-8")
    return Studio(projeto), projeto


async def _digitar(pilot, texto: str) -> None:
    for ch in texto:
        await pilot.press({" ": "space"}.get(ch, ch))


async def _ir_para(pilot, explorer, nome: str) -> None:
    """Põe o cursor do explorer no item `nome` (usa as setas, como a pessoa faria)."""
    await pilot.press("ctrl+e")
    await pilot.press("home")
    for _ in range(30):
        if explorer.selecionado() is not None and explorer.selecionado().name == nome:
            return
        await pilot.press("down")
    raise AssertionError(f"{nome} não apareceu no explorer")


def test_operacoes_de_arquivo_pelo_teclado(tmp_path, monkeypatch):
    from codar.studio.explorer import Explorer, LIXEIRA

    app, projeto = _studio(tmp_path, monkeypatch)

    async def cenario():
        async with app.run_test(size=(150, 42)) as pilot:
            explorer = app.query_one(Explorer)
            await pilot.press("ctrl+e")
            await pilot.pause(0.3)

            await pilot.press("p")  # nova pasta (na raiz: o cursor está no projeto)
            await _digitar(pilot, "modelos")
            await pilot.press("enter")
            await pilot.pause(0.3)
            assert (projeto / "modelos").is_dir()

            await _ir_para(pilot, explorer, "modelos")
            await pilot.press("n")  # novo arquivo dentro da pasta selecionada, já aberto no editor
            await _digitar(pilot, "conta.py")
            await pilot.press("enter")
            await pilot.pause(0.3)
            assert (projeto / "modelos" / "conta.py").is_file()
            assert app.current_editor().path == str(projeto / "modelos" / "conta.py")

            await _ir_para(pilot, explorer, "conta.py")
            await pilot.press("r")  # o nome vem preenchido com "conta" selecionado: digitar troca só o nome
            await _digitar(pilot, "banco")
            await pilot.press("enter")
            await pilot.pause(0.3)
            assert (projeto / "modelos" / "banco.py").is_file() and not (projeto / "modelos" / "conta.py").exists()
            assert app.current_editor().path == str(projeto / "modelos" / "banco.py")  # a aba acompanha

            await _ir_para(pilot, explorer, "main.py")
            await pilot.press("d")
            await pilot.pause(0.3)
            assert (projeto / "main_copia.py").is_file()

            await _ir_para(pilot, explorer, "main.py")
            await pilot.press("c")
            await _ir_para(pilot, explorer, "src")
            await pilot.press("v")
            await pilot.pause(0.3)
            assert (projeto / "src" / "main.py").read_text(encoding="utf-8") == "print('oi')\n"

            await _ir_para(pilot, explorer, "main_copia.py")
            await pilot.press("delete")
            await pilot.press("enter")  # confirma
            await pilot.pause(0.3)
            assert not (projeto / "main_copia.py").exists()
            assert list((projeto / LIXEIRA).rglob("main_copia.py"))  # dá para recuperar

            await pilot.press("escape")
            assert app.focused is app.current_editor()

    asyncio.run(cenario())


def test_arrastar_arquivo_para_o_terminal_copia_para_o_projeto(tmp_path, monkeypatch):
    from textual import events

    from codar.studio.explorer import Explorer, caminhos_colados

    app, projeto = _studio(tmp_path, monkeypatch)
    fora = tmp_path / "Downloads"
    fora.mkdir()
    (fora / "foto 1.png").write_bytes(b"png")
    assert caminhos_colados(f"'{fora / 'foto 1.png'}' ") == [fora / "foto 1.png"]  # GNOME Terminal: entre aspas
    assert caminhos_colados(f"file://{fora}/foto%201.png") == [fora / "foto 1.png"]  # URI
    assert caminhos_colados("isto não é caminho") == []

    async def cenario():
        async with app.run_test(size=(150, 42)) as pilot:
            explorer = app.query_one(Explorer)
            await _ir_para(pilot, explorer, "src")
            explorer.post_message(events.Paste(f"'{fora / 'foto 1.png'}'"))
            await pilot.pause(0.5)
            assert (projeto / "src" / "foto 1.png").read_bytes() == b"png"

    asyncio.run(cenario())
