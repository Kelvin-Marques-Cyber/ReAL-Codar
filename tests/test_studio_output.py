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

def test_saida_vazia_mantem_tokens_para_copiar_e_selecionar(tmp_path, monkeypatch):
    from codar.studio.screens import TerminalOutputScreen

    app = setup_app(tmp_path, monkeypatch)
    path = app.root / 'main.py'
    path.write_text('print("original")\n')
    raw = 'dt lp\n.Y\noutube\nDL\n()\n'

    async def scenario():
        async with app.run_test(size=(150, 42)) as pilot:
            await app.open_file(path)
            editor = app.current_editor()
            target = EditTarget.capture(editor.text, 'insert', (0, 0), ((0, 0), (0, 0)))
            app._output_text = raw
            app._apply(result(''), target, editor.id, '')
            assert editor.text == 'print("original")\n'
            assert not app.query_one('#output-copy').disabled
            assert not app.query_one('#output-select').disabled
            assert app.query_one('#output-open').disabled
            app.action_copy_result()
            assert app.clipboard == raw
            await pilot.click('#output')
            await pilot.pause()
            assert isinstance(app.screen, TerminalOutputScreen)
            assert app.screen.query_one('#terminal-output-text').text == raw

    asyncio.run(scenario())


def test_importacao_pura_enviada_pelo_motor_e_inserida_no_editor(tmp_path, monkeypatch):
    app = setup_app(tmp_path, monkeypatch)
    path = app.root / 'main.py'
    path.write_text('print("original")\n')

    async def scenario():
        async with app.run_test(size=(150, 42)):
            await app.open_file(path)
            editor = app.current_editor()
            target = EditTarget.capture(editor.text, 'insert', (0, 0), ((0, 0), (0, 0)))
            code = 'from yt_dlp import YoutubeDL'
            res = {**result(code), 'body': '', 'imports': [code]}
            app._apply(res, target, editor.id, '')
            assert editor.text.startswith(code + '\n')
            assert 'print("original")' in editor.text
            assert 'Código aplicado' in str(app.query_one('#output-status').content)

    asyncio.run(scenario())


def test_saida_bruta_sem_streaming_fica_visivel_e_copiavel(tmp_path, monkeypatch):
    """Recebemos raw_output mesmo quando nenhum callback on_delta foi emitido."""
    from textual.widgets import Static
    app = setup_app(tmp_path, monkeypatch)
    path = app.root / 'main.py'
    path.write_text('print("preservado")\n')
    raw = 'Resposta parcial: import yt_dlp\n'

    async def scenario():
        async with app.run_test(size=(150, 42)):
            await app.open_file(path)
            editor = app.current_editor()
            target = EditTarget.capture(editor.text, 'insert', (0, 0), ((0, 0), (0, 0)))
            response = {**result(''), 'raw_output': raw, 'complete': False,
                        'diagnostics': {'generation_attempts': [{'reason': 'python_syntax'}]}}
            app._apply(response, target, editor.id, '')
            assert editor.text == 'print("preservado")\n'
            assert 'python_syntax' in str(app.query_one('#output-status', Static).content)
            assert not app.query_one('#output-copy').disabled
            app.action_copy_result()
            assert app.clipboard == raw
            assert path.read_text() == 'print("preservado")\n'

    asyncio.run(scenario())


def test_ausencia_de_saida_nao_oferece_copia_vazia(tmp_path, monkeypatch):
    from textual.widgets import Static
    app = setup_app(tmp_path, monkeypatch)
    path = app.root / 'main.py'
    path.write_text('pass\n')

    async def scenario():
        async with app.run_test(size=(150, 42)):
            await app.open_file(path)
            editor = app.current_editor()
            target = EditTarget.capture(editor.text, 'insert', (0, 0), ((0, 0), (0, 0)))
            app._apply({**result(''), 'complete': False, 'raw_output': ''}, target, editor.id, '')
            assert app.query_one('#output-copy').disabled
            assert app.query_one('#output-select').disabled
            assert 'Nenhum texto' in str(app.query_one('#output-status', Static).content)
            assert editor.text == 'pass\n'

    asyncio.run(scenario())


def test_resultado_validado_pode_ser_inserido_manualmente_sem_apagar_edicao(tmp_path, monkeypatch):
    """Se o alvo da resposta envelheceu, INSERIR usa o cursor ATUAL sem substituir o arquivo."""
    app = setup_app(tmp_path, monkeypatch)
    file = app.root / "main.py"
    file.write_text("x = 10\n")

    async def scenario():
        async with app.run_test(size=(150, 42)):
            await app.open_file(file)
            ed = app.current_editor()
            target = EditTarget.capture(ed.text, "line", (0, 0), ((0, 0), (0, 0)), row=0)
            ed.replace("x = 99\n", (0, 0), ed.document.end)
            app._apply(result("y = 42"), target, ed.id, "")
            assert ed.text == "x = 99\n"
            assert not app.query_one("#output-insert").disabled
            app.action_insert_result()
            assert "x = 99" in ed.text
            assert "y = 42" in ed.text
            assert file.read_text() == "x = 10\n"
            ed.action_undo()
            assert ed.text == "x = 99\n"

    asyncio.run(scenario())


def test_botao_inserir_nao_aceita_geracao_incompleta(tmp_path, monkeypatch):
    app = setup_app(tmp_path, monkeypatch)
    file = app.root / "main.py"
    file.write_text("x = 10\n")

    async def scenario():
        async with app.run_test(size=(150, 42)):
            await app.open_file(file)
            ed = app.current_editor()
            target = EditTarget.capture(ed.text, "insert", (0, 0), ((0, 0), (0, 0)))
            app._apply({**result("y = 42"), "complete": False}, target, ed.id, "")
            assert app.query_one("#output-insert").disabled
            app.action_insert_result()
            assert ed.text == "x = 10\n"

    asyncio.run(scenario())
