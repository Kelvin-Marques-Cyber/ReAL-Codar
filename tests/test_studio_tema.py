"""Tema do Studio: trocar o tema (Ctrl+P → theme) muda a interface inteira, não só os widgets padrão do Textual, e a
escolha vale para a próxima sessão."""

import asyncio
import json
from pathlib import Path

import pytest

textual = pytest.importorskip("textual")


def test_trocar_tema_muda_tudo_e_fica_salvo(tmp_path: Path, monkeypatch):
    from codar.studio.app import Studio
    from codar.studio.widgets import C, SENTRY, paleta

    monkeypatch.setenv("CODAR_HOME", str(tmp_path / "home"))
    monkeypatch.setenv("CODAR_NO_AUTOSTART", "1")
    (tmp_path / "a.py").write_text("x = 1\n", encoding="utf-8")

    async def cenario():
        app = Studio(tmp_path)
        async with app.run_test(size=(150, 42)) as pilot:
            await app.open_file(tmp_path / "a.py")
            await pilot.pause()
            assert app.theme == "sentry" and C["bg"] == SENTRY["bg"]
            assert app.get_css_variables()["codar-bg"] == SENTRY["bg"]

            app.theme = "nord"
            await pilot.pause(0.2)
            nord = paleta(app.get_theme("nord"))
            assert C["bg"] == nord["bg"] != SENTRY["bg"]
            assert app.get_css_variables()["codar-red"] == nord["red"]  # bordas e rótulos do studio.tcss
            assert app.current_editor().theme == "codar-nord"  # realce de sintaxe
            assert app.ansi_theme_dark.background_color.hex.lower() == nord["bg"].lower()  # terminal integrado

        estado = json.loads(next((tmp_path / "home").rglob("studio.json")).read_text(encoding="utf-8"))
        assert estado["tema"] == "nord"

        app = Studio(tmp_path)
        async with app.run_test(size=(150, 42)) as pilot:
            await pilot.pause()
            assert app.theme == "nord"
            app.theme = "sentry"
            await pilot.pause(0.2)
            assert C == SENTRY

    asyncio.run(cenario())
