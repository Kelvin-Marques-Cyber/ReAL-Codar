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
    assert not explained.complete  # também protege clientes antigos que verificam código incompleto
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


def test_cli_consulta_tem_sucesso_sem_ser_marcada_como_codigo_incompleto(tmp_path, monkeypatch, capsys):
    from codar.cli.main import main
    monkeypatch.setenv('CODAR_HOME', str(tmp_path / 'home'))
    monkeypatch.setenv('CODAR_BACKEND', 'none')
    assert main(['run', 'explique uma função', '--local', '--root', str(tmp_path)]) == 0
    output = capsys.readouterr()
    assert 'função' in output.out and 'resposta incompleta' not in output.err


@pytest.mark.parametrize('intent', [
    'execute 3 vezes', 'execute isso 5 vezes', 'rode o loop 3 vezes', 'run the loop 3 times',
    'executar a função soma com 2 e 3', 'run the function soma with 2 and 3',
    'teste se x é maior que 10', 'testar se a lista está vazia', 'test if x > 10', 'test whether x > 10',
    'teste unitário para a função somar', 'testes unitários para somar',
])
def test_construcao_de_codigo_com_verbo_de_acao_gera_codigo(intent):
    # "execute 3 vezes" é um laço e "teste se" um if: nenhum deles pede para rodar o arquivo.
    assert classify(intent, 'python') == 'generate'


@pytest.mark.parametrize('intent', [
    'execute meu arquivo', 'executar o programa', 'rode os testes', 'rodar testes', 'run tests', 'run main.py',
    'teste meu código', 'test this file', 'ejecuta el archivo', 'execute', 'rode pytest',
])
def test_pedido_de_execucao_continua_informativo(intent):
    assert classify(intent, 'python') == 'execute'


@pytest.mark.parametrize('intent,expected', [
    ('execute 3 vezes', 'for _ in range(3):'),
    ('rode o loop 3 vezes', 'for _ in range(3):'),
    ('executar a função soma com 2 e 3', 'soma(2, 3)'),
    ('run the function soma with 2 and 3', 'soma(2, 3)'),
    ('teste se x é maior que 10', 'if x > 10:'),
    ('verifique se x é maior que 10', 'if x > 10:'),
])
def test_construcao_com_verbo_de_acao_chega_ao_compilador(translate, intent, expected):
    result = translate(intent, before='x = 1\n', stages=(0,))
    assert result.action == 'generate' and result.stage == '0'
    assert expected in result.code
