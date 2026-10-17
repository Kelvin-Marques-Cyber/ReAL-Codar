import asyncio
import json
import threading

import pytest

from codar.client import Client, RpcError
from codar.engine.local import LocalClient
from codar import config


def test_cliente_envia_cancelamento_do_id_exato():
    cancel = threading.Event()
    received = threading.Event()
    class Transport:
        def __init__(self): self.messages = []
        def send(self, data):
            value = json.loads(data)
            self.messages.append(value)
            if value.get('method') == '$/cancelRequest': received.set()
        def readline(self):
            cancel.set()
            assert received.wait(2)
            return b'{"jsonrpc":"2.0","id":1,"error":{"code":-32800,"message":"cancelado"}}\n'
    transport = Transport()
    with pytest.raises(RpcError) as exc:
        Client(transport).call('translate', {'intent': 'crie'}, cancel=cancel)
    assert exc.value.code == -32800
    assert transport.messages[-1]['params'] == {'id': 1}


def test_pedido_ja_cancelado_nao_consulta_motor(tmp_path, monkeypatch):
    monkeypatch.setenv('CODAR_HOME', str(tmp_path / 'home'))
    cancel = threading.Event()
    cancel.set()
    with LocalClient(config.load(), with_model=False, db=':memory:') as client:
        with pytest.raises(RpcError) as exc:
            client.translate('x é igual a 10', cancel=cancel)
        assert exc.value.code == -32800
        assert not client.router.metrics.count


def test_cancelar_no_studio_descarta_resposta_tardia_sem_perder_codigo(tmp_path, monkeypatch):
    pytest.importorskip('textual')
    from codar.studio.app import Studio
    started, release = threading.Event(), threading.Event()
    observed = []
    def slow(intent, lang, **kwargs):
        observed.append(kwargs['cancel'])
        started.set()
        release.wait(3)
        return {'code':'x = 10','body':'x = 10','imports':[], 'lang':'python','stage':'0',
                'source':'teste','timings':{},'findings':[]}
    monkeypatch.setenv('CODAR_HOME', str(tmp_path / 'home'))
    monkeypatch.setenv('CODAR_NO_AUTOSTART', '1')
    file = tmp_path / 'app.py'
    file.write_text('x é igual a 10\n')
    async def scenario():
        app = Studio(tmp_path, local=True)
        monkeypatch.setattr(app.backend, 'translate', slow)
        async with app.run_test(size=(150,42)) as pilot:
            await app.open_file(file)
            editor = app.current_editor()
            app.request('x é igual a 10', 'line', editor, 0)
            for _ in range(50):
                await pilot.pause(.02)
                if started.is_set(): break
            assert started.is_set()
            editor.insert('# meu texto novo\n', (0,0))
            before = editor.text
            await pilot.press('f2')
            assert observed[0].is_set()
            release.set()
            await pilot.pause(.3)
            assert editor.text == before and app.last is None
            assert file.read_text() == 'x é igual a 10\n'
    asyncio.run(scenario())
