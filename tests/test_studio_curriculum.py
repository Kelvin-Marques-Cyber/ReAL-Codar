"""Percursos do modo estudo devem ser navegáveis sem exigir arquivo aberto."""

import asyncio

import pytest


def _studio(tmp_path, monkeypatch):
    pytest.importorskip("textual")
    from codar.studio.app import Studio

    monkeypatch.setenv("CODAR_HOME", str(tmp_path / "home"))
    monkeypatch.setenv("CODAR_NO_AUTOSTART", "1")
    monkeypatch.setenv("CODAR_SHELL_ENV", "0")
    root = tmp_path / "aulas"
    root.mkdir()
    return Studio(root, lang="html", local=True)


def test_estudo_retomar_marca_e_avanca_sem_abrir_arquivo(tmp_path, monkeypatch):
    from codar.estudo.curriculo import percurso
    from codar.estudo.progresso import ler

    app = _studio(tmp_path, monkeypatch)

    async def scenario():
        async with app.run_test(size=(150, 42)):
            assert app.current_editor() is None
            first = percurso("html", app.root)["next"]
            assert first is not None
            app.action_estudo_continuar()
            assert app.estudo
            assert app._estudo_conceito is not None
            assert app._estudo_conceito.id == first
            assert str(app.query_one("#estudo-corpo").content).strip()
            app.action_estudo_praticado()
            assert first in ler(app.root, "html")
            app.action_estudo_continuar()
            assert app._estudo_conceito.id != first

    asyncio.run(scenario())


def test_estudo_catalogo_mostra_percurso_por_nivel(tmp_path, monkeypatch):
    from codar.estudo.curriculo import percurso
    from codar.studio.screens import ChoiceScreen

    app = _studio(tmp_path, monkeypatch)

    async def scenario():
        async with app.run_test(size=(150, 42)):
            path = percurso("html", app.root)
            app.action_estudo_catalogo()
            assert isinstance(app.screen, ChoiceScreen)
            assert path["total"] >= 10
            assert path["lessons"][0]["id"]
            assert path["lessons"][0]["level"] == "iniciante"

    asyncio.run(scenario())
