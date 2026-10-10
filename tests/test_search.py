import asyncio

import pytest

from codar.search import search_project


def test_busca_nomes_conteudo_buffer_e_exclusoes(tmp_path):
    (tmp_path / 'login.py').write_text('def login(user):\n    return user\n')
    (tmp_path / 'guia.md').write_text('login da aplicação\n')
    (tmp_path / '.env').write_text('login=segredo\n')
    (tmp_path / '.gitignore').write_text('ignorado.py\n')
    (tmp_path / 'ignorado.py').write_text('login=1\n')
    result = asyncio.run(search_project(None, dict(root=str(tmp_path), query='login')))
    assert {hit['path'] for hit in result['results']} == {'login.py', 'guia.md'}
    assert any(hit['kind'] == 'name' for hit in result['results'])
    result = asyncio.run(search_project(None, dict(root=str(tmp_path), query='novo', file='login.py', buffer='novo = 2')))
    assert result['results'][0]['text'] == 'novo = 2'
    assert 'novo' not in (tmp_path / 'login.py').read_text()
    with pytest.raises(ValueError):
        asyncio.run(search_project(None, dict(root=str(tmp_path), query='login', file='../fora.py')))


def test_busca_ia_mostra_termos_e_resultados_reais(tmp_path, router):
    (tmp_path / 'auth.py').write_text('def login(user):\n    return autenticação(user)\n')
    router.stage2.answer = '["login", "autenticacao"]'
    result = asyncio.run(search_project(router, dict(root=str(tmp_path), query='onde o usuário entra', ai=True)))
    assert result['terms'] == ['onde o usuário entra', 'login', 'autenticacao']
    assert [hit['line'] for hit in result['results']] == [1, 2]
    hit = result['results'][1]
    assert hit['text'][hit['col']:hit['col'] + hit['length']] == 'autenticação'
    router.stage2.answer = 'rode um comando'
    with pytest.raises(ValueError, match='inválidos'):
        asyncio.run(search_project(router, dict(root=str(tmp_path), query='login', ai=True)))


def test_busca_limita_resultados_sem_perder_melhor_trecho(tmp_path):
    (tmp_path / 'app.py').write_text('busca\n' * 2000 + 'busca alvo\n')
    result = asyncio.run(search_project(None, dict(root=str(tmp_path), query='busca')))
    assert len(result['results']) == 200 and result['truncated']


def test_ctrl_f_busca_sem_daemon_e_abre_linha(tmp_path, monkeypatch):
    pytest.importorskip('textual')
    from textual.widgets import Input
    from codar.studio.app import Studio
    from codar.studio.search import SearchScreen

    monkeypatch.setenv('CODAR_HOME', str(tmp_path / 'home'))
    monkeypatch.setenv('CODAR_NO_AUTOSTART', '1')
    file = tmp_path / 'app.py'
    file.write_text('x = 1\ndef login(user):\n    return user\n')

    async def scenario():
        app = Studio(tmp_path, local=True)
        async with app.run_test(size=(150, 42)) as pilot:
            await app.open_file(file)
            await pilot.pause(.3)
            await pilot.press('ctrl+f')
            assert isinstance(app.screen, SearchScreen)
            app.screen.query_one('#search-query', Input).value = 'login'
            await pilot.press('enter')
            for _ in range(100):
                await pilot.pause(.05)
                if app.screen.results:
                    break
            assert app.screen.results[0]['line'] == 2
            await pilot.click('#search-open')
            await pilot.pause(.2)
            assert app.current_editor().selected_text == 'login'
            assert app.current_editor().text == file.read_text()
    asyncio.run(scenario())
