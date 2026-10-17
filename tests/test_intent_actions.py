import asyncio

import pytest

from codar.engine.actions import classify


@pytest.mark.parametrize('intent,kind', [
    ('explique esta função', 'query'), ('how does this function work?', 'query'),
    ('consulte a API de requests', 'query'), ('instale requests', 'install'),
    ('estudar biblioteca requests', 'study'), ('execute meu arquivo', 'execute'),
    ('crie uma função que explique os resultados', 'generate'),
    ('importe requests', 'import'), ('import requests', 'import'),
])
def test_classe_da_intencao_separa_informacao_e_codigo(intent, kind):
    assert classify(intent, 'python') == kind


def test_consulta_e_instalacao_nao_chamam_ia_nem_alteram_codigo(translate, router, tmp_path):
    original = 'def somar(a, b):\n    return a+b\n'
    explained = translate('explique a função', selected=original, mode='edit', project_root=str(tmp_path))
    assert explained.action == 'query' and explained.body == '' and explained.imports == []
    assert 'função' in explained.code.lower()
    planned = translate('instale requests', before=original, mode='edit', project_root=str(tmp_path))
    assert planned.action == 'install' and 'pip install requests' in planned.code
    assert not (tmp_path / '.venv').exists()
    assert not router.stage2.prompts


def test_consulta_api_reflete_fonte_real(translate, tmp_path):
    (tmp_path / 'util.py').write_text('def somar(a, b): return a+b\n')
    result = translate('consulte API de util', project_root=str(tmp_path))
    assert result.action == 'query' and 'def somar(a, b)' in result.code
    assert str(tmp_path / 'util.py') in result.code


def test_consulta_no_studio_preserva_selecao_e_arquivo(tmp_path, monkeypatch):
    pytest.importorskip('textual')
    from codar.studio.app import Studio
    from textual.widgets.text_area import Selection
    monkeypatch.setenv('CODAR_HOME', str(tmp_path / 'home'))
    monkeypatch.setenv('CODAR_NO_AUTOSTART', '1')
    file = tmp_path / 'app.py'
    original = 'def somar(a,b):\n    return a+b\n'
    file.write_text(original)
    async def scenario():
        app = Studio(tmp_path, local=True)
        async with app.run_test(size=(150,42)) as pilot:
            await app.open_file(file)
            editor = app.current_editor()
            editor.selection = Selection((0,0),(1,14))
            await app.submit_intent('explique esta função')
            for _ in range(100):
                await pilot.pause(.03)
                if app.last: break
            assert app.last and app.last['action'] == 'query'
            assert editor.text == original and file.read_text() == original
            assert app.query_one('#panel').active == 'tab-output'
    asyncio.run(scenario())
