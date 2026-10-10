import asyncio
import os
import stat

import pytest
from codar.studio.saving import write_buffer


def test_gravacao_atomica_preserva_permissoes_e_alteracao_externa(tmp_path):
    file = tmp_path / 'app.py'
    file.write_text('x = 1\n')
    file.chmod(0o700)
    baseline = file.read_bytes()
    assert write_buffer(file, 'x = 2\n', baseline) == b'x = 2\n'
    if os.name != 'nt':
        assert stat.S_IMODE(file.stat().st_mode) == 0o700
    file.write_text('alterado por outro editor\n')
    with pytest.raises(ValueError, match='fora do Studio'):
        write_buffer(file, 'x = 3\n', b'x = 2\n')
    assert file.read_text() == 'alterado por outro editor\n'
    assert {p.name for p in tmp_path.iterdir()} == {'app.py'}


def test_auto_save_optin_arquivo_correto_conflito_e_preferencia(tmp_path, monkeypatch):
    pytest.importorskip('textual')
    from codar import config
    from codar.studio.app import Studio

    monkeypatch.setenv('CODAR_HOME', str(tmp_path / 'home'))
    monkeypatch.setenv('CODAR_NO_AUTOSTART', '1')
    files = [tmp_path / 'a.py', tmp_path / 'b.py']
    for file in files:
        file.write_text('x = 1\n')

    async def scenario():
        app = Studio(tmp_path, local=True)
        assert not app.autosave
        app.autosave_delay = .3
        async with app.run_test(size=(150, 42)) as pilot:
            await app.open_file(files[0])
            a = app.current_editor()
            a.load_text('x = 2\n')
            await pilot.pause(.5)
            assert files[0].read_text() == 'x = 1\n'
            await pilot.click('#autosave-button')
            await app.open_file(files[1])
            await pilot.pause(.5)
            assert files[0].read_text() == 'x = 2\n'
            assert files[1].read_text() == 'x = 1\n'
            b = app.current_editor()
            files[1].write_text('x = 999\n')
            b.load_text('x = 3\n')
            await pilot.pause(.5)
            assert files[1].read_text() == 'x = 999\n'
            assert b.dirty and b.autosave_paused
            assert config.load()['studio']['autosave']
            app.action_toggle_autosave()
            assert not config.load()['studio']['autosave']
    asyncio.run(scenario())
