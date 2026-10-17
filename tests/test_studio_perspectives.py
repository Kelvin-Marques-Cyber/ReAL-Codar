import asyncio
import pytest


def test_perspectivas_mantem_buffer_e_persistem_escolha(tmp_path, monkeypatch):
    pytest.importorskip('textual')
    from codar.studio.app import Studio
    from codar.studio import estado
    monkeypatch.setenv('CODAR_HOME',str(tmp_path/'home'))
    monkeypatch.setenv('CODAR_NO_AUTOSTART','1')
    file=tmp_path/'app.py';file.write_text('valor = 42\n')
    async def scenario():
        app=Studio(tmp_path,local=True)
        async with app.run_test(size=(150,42)) as pilot:
            await app.open_file(file)
            editor=app.current_editor()
            app.apply_perspective('essential')
            assert not app.query_one('#panel').display
            app.apply_perspective('learning')
            await pilot.pause(.1)
            assert app.query_one('#panel').active=='tab-estudo'
            assert editor.text=='valor = 42\n'
            assert estado.ler()['perspective']=='learning'
            await pilot.resize_terminal(80,24)
            await pilot.resize_terminal(150,42)
            assert not app.query_one('#right').display
            app.apply_perspective('development')
            assert app.query_one('#left').display and app.query_one('#right').display
    asyncio.run(scenario())


def test_editor_tem_largura_util_em_terminal_80_colunas(tmp_path, monkeypatch):
    pytest.importorskip('textual')
    from codar.studio.app import Studio
    monkeypatch.setenv('CODAR_HOME',str(tmp_path/'home'))
    monkeypatch.setenv('CODAR_NO_AUTOSTART','1')
    file=tmp_path/'app.py';file.write_text('valor = 42\n')
    async def scenario():
        app=Studio(tmp_path,local=True)
        async with app.run_test(size=(80,24)) as pilot:
            await app.open_file(file)
            await pilot.pause(.1)
            assert app.current_editor().region.width >= 70
            assert not app.query_one('#left').display and not app.query_one('#right').display
    asyncio.run(scenario())
