"""Ao atualizar o pacote, o Studio não deve continuar conectado ao daemon antigo."""

import pytest

from codar import ENGINE_REVISION
from codar.studio.backend import StudioBackend


class FakeClient:
    def __init__(self, revision):
        self.revision = revision
        self.closed = False

    def ping(self):
        return {"engine_revision": self.revision}

    def close(self):
        self.closed = True


def test_studio_reinicia_motor_antigo_automaticamente(monkeypatch):
    from codar.client import Client
    from codar import daemonctl

    first, second, upgraded = FakeClient(None), FakeClient(None), FakeClient(ENGINE_REVISION)
    clients = iter([first, second, upgraded])
    calls = []
    monkeypatch.setattr(Client, "connect", lambda **kw: next(clients))
    monkeypatch.setattr(daemonctl, "stop_daemon", lambda: calls.append("stop") or True)
    monkeypatch.setattr(daemonctl, "start_daemon", lambda: calls.append("start"))

    client = StudioBackend()._client()
    assert client is upgraded
    assert first.closed and second.closed
    assert calls == ["stop", "start"]


def test_studio_nao_reinicia_motor_compativel(monkeypatch):
    from codar.client import Client

    active = FakeClient(ENGINE_REVISION)
    monkeypatch.setattr(Client, "connect", lambda **kw: active)
    assert StudioBackend()._client() is active


def test_motor_antigo_nao_pode_ser_utilizado_se_parada_falhar(monkeypatch):
    from codar.client import Client
    from codar import daemonctl

    first, second = FakeClient(None), FakeClient(None)
    clients = iter([first, second])
    monkeypatch.setattr(Client, "connect", lambda **kw: next(clients))
    monkeypatch.setattr(daemonctl, "stop_daemon", lambda: False)
    with pytest.raises(RuntimeError, match="codar restart"):
        StudioBackend()._client()
    assert first.closed and second.closed
