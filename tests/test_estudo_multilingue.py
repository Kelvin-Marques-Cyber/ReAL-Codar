import asyncio
import subprocess
import sys

import pytest
from codar import estudo, langs
from codar.estudo.ampliado import GUIAS
from codar.estudo.progresso import ler, marcar


@pytest.mark.parametrize('lang', sorted(langs.LANGS))
def test_estudo_cobre_todo_tipo_de_arquivo_com_exemplo_nativo(lang):
    catalog = estudo.catalogo(lang)
    assert len(catalog) >= 2
    concept = estudo.POR_ID['guia_' + lang]
    code, actual = estudo.exemplo(concept, lang)
    assert code == GUIAS[lang][2] and actual == lang
    found = estudo.conceitos_da_linha(code.splitlines()[0], lang)
    assert found and estudo.exemplo(found[0], lang)[1] == lang
    assert all(estudo.exemplo(c, lang)[1] == lang for c in catalog)
    assert estudo.fontes(concept, lang)[0].startswith('https://')


def test_exemplos_python_novos_compilam_e_teste_revela_defeito():
    for concept in estudo.catalogo('python'):
        code, _ = estudo.exemplo(concept, 'python')
        compile(code, concept.id, 'exec')
    code = estudo.exemplo(estudo.POR_ID['testes_python'], 'python')[0]
    correct = subprocess.run([sys.executable, '-c', code], capture_output=True)
    broken = subprocess.run([sys.executable, '-c', code.replace('return x * 2', 'return x + 2')], capture_output=True)
    assert correct.returncode == 0 and broken.returncode != 0


def test_pratica_e_separada_por_projeto_e_linguagem(tmp_path, monkeypatch):
    monkeypatch.setenv('CODAR_HOME', str(tmp_path / 'home'))
    marcar(tmp_path / 'a', 'dart', 'future_dart')
    assert 'future_dart' in ler(tmp_path / 'a', 'dart')
    assert not ler(tmp_path / 'b', 'dart') and not ler(tmp_path / 'a', 'python')


def test_painel_nativo_ao_trocar_entre_todas_linguagens(tmp_path, monkeypatch):
    pytest.importorskip('textual')
    from textual.widgets import Static
    from codar.studio.app import Studio
    from tests.test_estudo import _texto

    monkeypatch.setenv('CODAR_HOME', str(tmp_path / 'home'))
    monkeypatch.setenv('CODAR_NO_AUTOSTART', '1')

    async def scenario():
        app = Studio(tmp_path, local=True)
        async with app.run_test(size=(150, 42)):
            app.estudo = True
            for lang, meta in langs.LANGS.items():
                name = 'Dockerfile' if lang == 'dockerfile' else 'exemplo' + meta.exts[0]
                file = tmp_path / name
                file.write_text(GUIAS[lang][2], encoding='utf-8')
                await app.open_file(file)
                app.atualizar_estudo()
                assert app._estudo_conceito and estudo.exemplo(app._estudo_conceito, lang)[1] == lang
                assert 'Fontes oficiais:' in _texto(app.query_one('#estudo-corpo', Static).content)
    asyncio.run(scenario())
