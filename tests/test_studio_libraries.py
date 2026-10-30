import asyncio

import pytest

from codar.estudo import progresso


def test_bibliotecas_filtra_consulta_trilha_e_preserva_editor(tmp_path, monkeypatch):
    pytest.importorskip('textual')
    from textual.widgets import Button, Input, RichLog
    from codar.studio.app import Studio
    from codar.studio.libraries import LibrariesScreen, LibraryStudyScreen

    monkeypatch.setenv('CODAR_HOME', str(tmp_path / 'home'))
    monkeypatch.setenv('CODAR_NO_AUTOSTART', '1')
    file = tmp_path / 'app.py'
    file.write_text('import util\nprint("inalterado")\n')
    (tmp_path / 'util.py').write_text('def somar(a, b): return a+b\n')
    (tmp_path / 'requirements.txt').write_text('faltante==1\n')

    async def wait(pilot, condition):
        for _ in range(100):
            await pilot.pause(.04)
            if condition():
                return
        assert condition()

    async def scenario():
        app = Studio(tmp_path, local=True)
        async with app.run_test(size=(150, 42)) as pilot:
            await app.open_file(file)
            editor = app.current_editor()
            before = editor.text
            await pilot.press('ctrl+shift+l')
            await wait(pilot, lambda: isinstance(app.screen, LibrariesScreen) and len(app.screen.rows) == 2)
            screen = app.screen
            field = screen.query_one('#libraries-query', Input)
            field.value = 'util'
            await pilot.pause(.15)
            assert len(screen.filtered) == 1
            screen.query_one('#libraries-api', Button).press()
            await wait(pilot, lambda: 'somar' in str(screen.query_one('#libraries-details', RichLog).lines))
            assert editor.text == before
            screen.query_one('#libraries-study', Button).press()
            # a tela é empilhada antes de montar os filhos: espera o botão existir, não só a tela
            await wait(pilot, lambda: isinstance(app.screen, LibraryStudyScreen) and app.screen.query('#lesson-mark'))
            lesson = app.screen
            lesson.query_one('#lesson-mark', Button).press()
            await pilot.pause(.1)
            assert any(k.startswith('library.util.') for k in progresso.ler(tmp_path, 'python'))
            for _ in range(3):
                lesson.query_one('#lesson-next', Button).press()
                await pilot.pause(.03)
            lesson.query_one('#lesson-hint', Button).press()
            await pilot.pause(.1)
            assert lesson.hints == 1
            assert editor.text == before
            await pilot.press('escape', 'escape')
            assert not isinstance(app.screen, LibrariesScreen)
            assert editor.text == before and file.read_text() == before
            assert any('Bibliotecas' in title for title, _, _ in app.palette())
    asyncio.run(scenario())


def test_tela_bibliotecas_cabe_em_terminal_80_colunas(tmp_path, monkeypatch):
    pytest.importorskip('textual')
    from textual.widgets import Button
    from codar.studio.app import Studio
    from codar.studio.libraries import LibrariesScreen

    monkeypatch.setenv('CODAR_HOME', str(tmp_path / 'home'))
    monkeypatch.setenv('CODAR_NO_AUTOSTART', '1')

    async def scenario():
        app = Studio(tmp_path, local=True)
        async with app.run_test(size=(80, 24)) as pilot:
            app.action_libraries()
            await pilot.pause(.5)
            screen = app.screen
            assert isinstance(screen, LibrariesScreen)
            for button in screen.query(Button):
                assert button.region.right <= 80 and button.region.bottom <= 24
            assert screen.query_one('#libraries-details').region.width >= 25
    asyncio.run(scenario())
