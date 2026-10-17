"""Frames adversariais, concorrência e cancelamento no protocolo usado pelos clientes."""

import asyncio
import json
import threading
import time

import pytest

from codar.client import Client
from codar.daemon.server import Conn, Daemon


def test_sync_client_serializes_readers_without_losing_replies():
    class Transport:
        def __init__(self):
            self.sent = []
            self.active = 0
            self.overlap = False

        def send(self, data):
            self.sent.append(json.loads(data))

        def readline(self):
            self.active += 1
            self.overlap |= self.active > 1
            # Dá à segunda thread tempo para tentar consumir a mesma conexão.
            time.sleep(.03)
            request = self.sent[-1]
            self.active -= 1
            return json.dumps({"id": request["id"], "result": request["params"]["value"]}).encode()

    transport = Transport()
    client = Client(transport)
    results = []
    threads = [threading.Thread(target=lambda n=n: results.append(client.call("echo", {"value": n})))
               for n in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(2)
        assert not thread.is_alive()
    assert sorted(results) == [0, 1]
    assert not transport.overlap


def test_client_ignores_late_stream_from_previous_request():
    replies = iter([
        b'{"method":"$/progress","params":{"id":99,"delta":"antigo"}}',
        b'{"method":"$/progress","params":{"id":1,"delta":"novo"}}',
        b'{"id":1,"result":{"code":"x = 1"}}',
    ])

    class Transport:
        def send(self, data):
            pass

        def readline(self):
            return next(replies)

    deltas = []
    result = Client(Transport()).translate("x", on_delta=deltas.append)
    assert deltas == ["novo"]
    assert result["code"] == "x = 1"


@pytest.mark.parametrize("frame", [b"[]", b"null", b"invalid-json"])
def test_client_reports_malformed_daemon_frame(frame):
    class Transport:
        def send(self, data):
            pass

        def readline(self):
            return frame

    with pytest.raises(ConnectionError, match="inválid"):
        Client(Transport()).call("ping")


class Writer:
    def __init__(self):
        self.frames = []

    def write(self, data):
        self.frames.append(json.loads(data))

    async def drain(self):
        pass


def bare_daemon():
    daemon = Daemon.__new__(Daemon)
    daemon.dcfg = {"max_inflight_per_conn": 8}
    daemon.methods = {}
    daemon.requests = 0
    return daemon


@pytest.mark.parametrize("message,expected", [
    ({"jsonrpc": "2.0", "method": "ping", "id": []}, -32600),
    ({"jsonrpc": "2.0", "method": "ping", "id": {}}, -32600),
    ({"jsonrpc": "2.0", "method": "ping", "id": True}, -32600),
    ({"jsonrpc": "2.0", "method": "ping", "id": float("nan")}, -32600),
    ({"method": "ping", "id": 1}, -32600),
    ({"jsonrpc": "2.0", "method": "ping", "id": 1, "params": []}, -32602),
])
def test_bad_frames_do_not_break_connection_dispatch(message, expected):
    async def scenario():
        writer = Writer()
        conn = Conn(writer, True)
        bare_daemon()._dispatch(conn, message)
        await asyncio.sleep(0)
        assert writer.frames[-1]["error"]["code"] == expected
        assert not conn.closed and not conn.tasks

    asyncio.run(scenario())


def test_cancelled_handler_cannot_return_success_and_duplicate_ids_are_rejected():
    async def scenario():
        daemon = bare_daemon()
        started, release = asyncio.Event(), asyncio.Event()

        async def ignores_cancel(conn, params, rid):
            started.set()
            await release.wait()
            return {"code": "must never be applied"}

        daemon.methods["translate"] = ignores_cancel
        writer = Writer()
        conn = Conn(writer, True)
        msg = {"jsonrpc": "2.0", "method": "translate", "id": 7}
        daemon._dispatch(conn, msg)
        await started.wait()
        daemon._dispatch(conn, msg)
        # Cancelamentos malformados também não derrubam a conexão.
        daemon._dispatch(conn, {"jsonrpc": "2.0", "method": "$/cancelRequest", "params": {"id": []}})
        daemon._dispatch(conn, {"jsonrpc": "2.0", "method": "$/cancelRequest", "params": {"id": 7}})
        release.set()
        await asyncio.gather(*(task for task, _ in conn.tasks.values()))
        await asyncio.sleep(0)
        assert [frame["error"]["code"] for frame in writer.frames] == [-32600, -32800]
        assert not conn.tasks

    asyncio.run(scenario())
