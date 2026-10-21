import asyncio
import json
import re

import pytest

from codar.cli.main import main
from codar.i18n import LOCALES, normalize_locale, resources, tr
from codar.engine.locale_intents import normalize


def test_recursos_tem_chaves_e_placeholders_equivalentes():
    base = resources('pt-BR')['ui']
    for locale in LOCALES:
        values = resources(locale)['ui']
        assert set(base) <= set(values)
        for key in base:
            assert set(re.findall(r'{(\w+)}', key)) == set(re.findall(r'{(\w+)}', values[key]))
    assert tr('Marcar praticado', 'en') == 'Mark practiced'
    assert tr('Cancelar', 'es') == 'Cancelar'
    assert normalize_locale('pt_PT') == 'pt-PT'
    with pytest.raises(ValueError): normalize_locale('../../arquivo')


@pytest.mark.parametrize('lang', ['python','javascript','typescript','go','rust','dart','powershell'])
@pytest.mark.parametrize('pt,en,es', [
    ('x é igual a 10','x equals 10','x es igual a 10'),
    ("imprimir 'más y si'", "print 'más y si'", "imprime 'más y si'"),
    ('imprimir a soma de x e y','print the sum of x and y','imprime la suma de x y y'),
    ("se total maior que 10 imprimir 'si'", "if total greater than 10 print 'si'", "si total mayor que 10 imprime 'si'"),
])
def test_intencoes_equivalentes_usam_mesmo_compilador(translate, lang, pt, en, es):
    before = 'x = 2\ny = 3\ntotal = 11\n'
    results = [translate(value, lang, before=before, stages=(0,), locale=locale)
               for value, locale in [(pt,'pt-BR'),(en,'en'),(es,'es'),(pt,'pt-PT')]]
    assert all(result.stage == '0' for result in results)
    assert len({result.code for result in results}) == 1


def test_es_preserva_identificadores_e_texto_literal():
    assert normalize("valorTotal es igual a 'si mayor que y'", 'es') == "valorTotal é igual a 'si mayor que y'"
    assert normalize('imprime la suma de x y y', 'es', {'x','y'}) == 'imprimir x + y'
    assert normalize('import libreria', 'es') == 'import libreria'


def test_locale_cli_independente_da_linguagem(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv('CODAR_HOME', str(tmp_path / 'home'))
    monkeypatch.setenv('CODAR_BACKEND', 'none')
    assert main(['run','x es igual a 10','--locale','es','--lang','javascript','--local','--stages','0','--json']) == 0
    result = json.loads(capsys.readouterr().out)
    assert result['lang'] == 'javascript' and result['code'] == 'const x = 10;'


def test_studio_english_traduz_controles_sem_mudar_arquivo(tmp_path, monkeypatch):
    pytest.importorskip('textual')
    from codar.studio.app import Studio
    from textual.widgets import Button, Input
    monkeypatch.setenv('CODAR_HOME', str(tmp_path / 'home'))
    monkeypatch.setenv('CODAR_LOCALE', 'en')
    monkeypatch.setenv('CODAR_NO_AUTOSTART', '1')
    file = tmp_path / 'app.py'
    file.write_text('nome = "não traduzir"\n')
    async def scenario():
        app = Studio(tmp_path, local=True)
        async with app.run_test(size=(150,42)) as pilot:
            await app.open_file(file)
            app.action_libraries()
            await pilot.pause(.4)
            assert app.screen.query_one('#libraries-study',Button).label.plain == 'Open learning path'
            assert app.screen.query_one('#libraries-query',Input).placeholder.startswith('Search name')
            assert app.current_editor().text == file.read_text()
            assert any(title == 'Codar: Project libraries' for title,_,_ in app.palette())
    asyncio.run(scenario())


def test_es_preserva_indentacao_em_blocos(translate):
    pt = 'se total maior que 10\n    imprimir total'
    es = 'si total mayor que 10\n    imprime total'
    a = translate(pt, stages=(0,), before='total = 11\n')
    b = translate(es, stages=(0,), before='total = 11\n', locale='es')
    assert a.code == b.code
    assert normalize('    imprime total', 'es') == '    imprimir total'


@pytest.mark.parametrize('kind,pt,en,es,pt_pt', [
    ('query', 'o que é uma lista', 'what is a list', 'qué es una lista', 'o que é uma lista'),
    ('query', 'consulte a API de requests', 'look up the requests API', 'consulta la API de requests',
     'consulte a API de requests'),
    ('install', 'instale requests', 'install requests', 'instala requests', 'instale requests'),
    ('study', 'quero aprender listas', 'I want to learn lists', 'quiero aprender listas', 'quero aprender listas'),
    ('study', 'aprender python', 'learn python', 'aprende python', 'aprender python'),
    ('execute', 'execute meu arquivo', 'run my file', 'ejecuta mi archivo', 'corre o meu ficheiro'),
    ('execute', 'rode os testes', 'run the tests', 'corre las pruebas', 'corra os testes'),
    ('generate', 'execute 3 vezes', 'run 3 times', 'ejecuta 3 veces', 'execute 3 vezes'),
    ('generate', 'teste se x é maior que 10', 'test if x > 10', 'prueba si x es mayor que 10',
     'verifique se x é maior que 10'),
])
def test_classe_da_intencao_equivalente_nos_quatro_idiomas(kind, pt, en, es, pt_pt):
    from codar.engine.actions import classify

    for text, locale in [(pt, 'pt-BR'), (en, 'en'), (es, 'es'), (pt_pt, 'pt-PT')]:
        assert classify(text, 'python', locale) == kind, (text, locale)


@pytest.mark.parametrize('lang', ['python', 'javascript', 'go'])
@pytest.mark.parametrize('pt,en,es', [
    ('repita 3 vezes', 'run 3 times', 'ejecuta 3 veces'),
    ('teste se x é maior que 10', 'check if x > 10', 'comprueba si x es mayor que 10'),
])
def test_construcao_com_verbo_de_acao_equivalente_nos_idiomas(translate, lang, pt, en, es):
    results = [translate(value, lang, before='x = 2\n', stages=(0,), locale=locale)
               for value, locale in [(pt, 'pt-BR'), (en, 'en'), (es, 'es'), (pt, 'pt-PT')]]
    assert all(result.stage == '0' and result.action == 'generate' for result in results)
    assert len({result.code for result in results}) == 1
