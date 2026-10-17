import asyncio

import pytest

from codar.studio.symbols import index


def test_indice_usa_funcoes_do_projeto_e_api_sem_executar(tmp_path, monkeypatch):
    monkeypatch.setenv('CODAR_HOME', str(tmp_path / 'home'))
    (tmp_path / 'calculos.py').write_text('def somar_valores(a,b): return a+b\n')
    (tmp_path / 'biblioteca.py').write_text('raise RuntimeError("nao executar")\nclass Cliente:\n    def consultar_dados(self, limite=10): pass\n')
    current = tmp_path / 'app.py'
    current.write_text('import biblioteca\n')
    symbols = {item.name:item for item in index(tmp_path, str(current), current.read_text(), 'python')}
    assert 'somar_valores' in symbols and 'consultar_dados' in symbols
    assert 'limite=10' in symbols['consultar_dados'].signature
    assert symbols['somar_valores'].kind == 'project'


def test_indice_respeita_exclusoes_e_links(tmp_path, monkeypatch):
    monkeypatch.setenv('CODAR_HOME', str(tmp_path / 'home'))
    (tmp_path / 'codar.toml').write_text('[project]\nexclude=["privado.py"]\n')
    (tmp_path / 'privado.py').write_text('def nao_mostrar(): pass\n')
    assert 'nao_mostrar' not in {item.name for item in index(tmp_path,None,'','python')}


def test_f10_mostra_assinatura_e_completa_com_undo(tmp_path, monkeypatch):
    pytest.importorskip('textual')
    from codar.studio.app import Studio
    from textual.widgets import OptionList
    monkeypatch.setenv('CODAR_HOME', str(tmp_path / 'home'))
    monkeypatch.setenv('CODAR_NO_AUTOSTART', '1')
    (tmp_path / 'calculos.py').write_text('def somar_valores(a,b): return a+b\n')
    file = tmp_path / 'app.py'
    file.write_text('som')
    async def scenario():
        app=Studio(tmp_path,local=True)
        async with app.run_test(size=(150,42)) as pilot:
            await app.open_file(file)
            ed=app.current_editor()
            ed.move_cursor((0,3))
            for _ in range(80):
                await pilot.pause(.03)
                if ed.symbol_completions: break
            assert ed.complete('som',0)=='somar_valores'
            await pilot.press('f10')
            choices=app.screen.query_one('#choices',OptionList)
            assert 'somar_valores(a, b)' in str(choices.get_option_at_index(0).prompt)
            await pilot.press('enter')
            await pilot.pause(.1)
            assert ed.text=='somar_valores'
            ed.action_undo()
            assert ed.text=='som' and file.read_text()=='som'
    asyncio.run(scenario())
