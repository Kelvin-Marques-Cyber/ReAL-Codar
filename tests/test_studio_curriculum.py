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
    from codar.studio.review import ChoiceScreen

    app = _studio(tmp_path, monkeypatch)

    async def scenario():
        async with app.run_test(size=(150, 42)) as pilot:
            path = percurso("html", app.root)
            app.action_estudo_catalogo()
            await pilot.pause()
            assert isinstance(app.screen, ChoiceScreen)
            # guia e os oito tópicos de HTML descritos em docs/ESTUDO.md, todos listados no catálogo
            assert path["total"] >= 9
            assert app.screen.query_one("#choices").option_count == path["total"]
            levels = [lesson["level"] for lesson in path["lessons"]]
            order = ["iniciante", "intermediario", "avancado"]
            assert levels[0] == "iniciante" and levels == sorted(levels, key=order.index)

    asyncio.run(scenario())
