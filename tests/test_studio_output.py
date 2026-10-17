"""Código recebido deve chegar ao editor sem perder alterações concorrentes."""

import asyncio

import pytest

from codar.studio.edits import EditTarget


def test_alvo_acompanha_linhas_inseridas_e_alteradas_fora_do_trecho():
    original = '# cabeçalho\nx é igual a 10\nprint(x)\n'
    target = EditTarget.capture(original, 'line', (1, 0), ((1, 0), (1, 0)), row=1)
    current = '# cabeçalho atualizado\n# observação\nx é igual a 10\nprint(x + 1)\n'
    rebased = target.rebase(current)
    assert rebased is not None
    assert rebased.apply('x = 10', [], 'python', '')[0] == '# cabeçalho atualizado\n# observação\nx = 10\nprint(x + 1)\n'


@pytest.mark.parametrize('changed', ['x é igual a 20\n', 'x é igual a 10 e mais 2\n'])
def test_alvo_modificado_nao_e_sobrescrito(changed):
    original = 'x é igual a 10\n'
    target = EditTarget.capture(original, 'line', (0, 0), ((0, 0), (0, 0)), row=0)
    assert target.rebase(changed) is None


def test_alvo_repetido_nao_e_redirecionado_para_outra_ocorrencia():
    original = 'x é igual a 10\nx é igual a 10\n'
    target = EditTarget.capture(original, 'line', (0, 0), ((0, 0), (0, 0)), row=0)
    assert target.rebase('x é igual a 20\nx é igual a 10\n') is None


def result(body='x = 10', lang='python'):
    return dict(code=body, body=body, imports=[], lang=lang, stage='0', source='teste',
                timings={}, findings=[], notes=[], complete=True)


def setup_app(tmp_path, monkeypatch):
    pytest.importorskip('textual')
    from codar.studio.app import Studio
    monkeypatch.setenv('CODAR_HOME', str(tmp_path / 'home'))
    monkeypatch.setenv('CODAR_NO_AUTOSTART', '1')
    monkeypatch.setenv('CODAR_SHELL_ENV', '0')
    folder = tmp_path / 'project'
    folder.mkdir()
    return Studio(folder, local=True)


def test_studio_aplica_linha_apos_edicao_em_outro_trecho(tmp_path, monkeypatch):
    app = setup_app(tmp_path, monkeypatch)
    file = app.root / 'app.py'
    original = '# antes\nx é igual a 10\nprint(x)\n'
    file.write_text(original)
    async def scenario():
        async with app.run_test(size=(150, 42)):
            await app.open_file(file)
            editor = app.current_editor()
            target = EditTarget.capture(editor.text, 'line', (1, 0), ((1, 0), (1, 0)), row=1)
            editor.insert('# nota\n', (0, 0))
            app._apply(result(), target, editor.id, '')
            assert editor.text == '# nota\n# antes\nx = 10\nprint(x)\n'
            editor.action_undo()
            assert editor.text == '# nota\n' + original
            assert file.read_text() == original
    asyncio.run(scenario())


def test_studio_edita_arquivo_fora_da_pasta_inicial_com_historico(tmp_path, monkeypatch):
    from codar.workspace import EditStore
    app = setup_app(tmp_path, monkeypatch)
    external = tmp_path / 'outside'
    external.mkdir()
    file = external / 'app.py'
    original = 'x é igual a 10\n'
    file.write_text(original)
    async def scenario():
        async with app.run_test(size=(150, 42)):
            await app.open_file(file)
            editor = app.current_editor()
            target = EditTarget.capture(editor.text, 'line', (0, 0), ((0, 0), (0, 0)), row=0)
            app._apply(result(), target, editor.id, '')
            assert editor.text == 'x = 10\n'
            records = EditStore(external).list()
            assert records and EditStore(external).get(records[0]['id'])['changes'][0]['before'] == original
            assert file.read_text() == original
            editor.action_undo()
            assert editor.text == original
    asyncio.run(scenario())


@pytest.mark.parametrize('lang,code', [('javascript', 'const x = 10;'), ('html', '<h1>Olá</h1>')])
def test_saida_explica_bloqueio_e_recupera_codigo_em_nova_aba(tmp_path, monkeypatch, lang, code):
    from textual.widgets import Static
    app = setup_app(tmp_path, monkeypatch)
    file = app.root / 'app.py'
    file.write_text('x é igual a 10\n')
    async def scenario():
        async with app.run_test(size=(80, 24)):
            await app.open_file(file)
            editor = app.current_editor()
            target = EditTarget.capture(editor.text, 'line', (0, 0), ((0, 0), (0, 0)), row=0)
            editor.replace('x = 99\n', (0, 0), editor.document.end)
            app._apply(result(code, lang), target, editor.id, '')
            status = app.query_one('#output-status', Static).content
            assert 'trecho mudou' in str(status).lower() and 'token' not in str(status).lower()
            assert not app.query_one('#output-open').disabled
            app.action_copy_result()
            assert app.clipboard == code
            await app.action_open_result()
            recovered = app.current_editor()
            assert recovered is not editor and recovered.text == code + '\n'
            assert recovered.path is None and recovered.dirty and recovered.lang_id == lang
            assert app.current_lang() == lang
            assert editor.text == 'x = 99\n' and file.read_text() == 'x é igual a 10\n'
    asyncio.run(scenario())


def test_consulta_nao_e_aberta_como_codigo_e_exclusao_nao_e_contornada(tmp_path, monkeypatch):
    app = setup_app(tmp_path, monkeypatch)
    (app.root / 'codar.toml').write_text('[project]\nexclude = ["app.py"]\n')
    file = app.root / 'app.py'
    original = 'x é igual a 10\n'
    file.write_text(original)
    async def scenario():
        async with app.run_test(size=(150, 42)):
            await app.open_file(file)
            editor = app.current_editor()
            target = EditTarget.capture(editor.text, 'line', (0, 0), ((0, 0), (0, 0)), row=0)
            app._apply(result(), target, editor.id, '')
            assert editor.text == original and not app.query_one('#output-open').disabled
            query = {**result('Explicação'), 'action': 'query', 'complete': False, 'body': ''}
            app._apply(query, target, editor.id, '')
            assert app.query_one('#output-open').disabled
            await app.action_open_result()
            assert app.current_editor() is editor and editor.text == original
    asyncio.run(scenario())
