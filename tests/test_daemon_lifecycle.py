"""Fallback do serviço e ida/volta real Studio→SDK→daemon→roteador."""

import asyncio
import json

import pytest

from codar import ENGINE_REVISION, config, paths
from codar.client import Client, RpcError
from codar.daemon.server import Daemon


def test_cgroup_fallback_reopens_child_log(tmp_path, monkeypatch):
    from codar import daemonctl

    monkeypatch.setenv("CODAR_HOME", str(tmp_path / "home"))
    commands = []

    def command(cfg):
        return (["systemd-run"], "cgroup") if cfg["memory"]["enforce"] != "soft" else (["python"], "watchdog")

    def popen(cmd, **kwargs):
        assert not kwargs["stdout"].closed
        commands.append(cmd)

        class Process:
            pid = 42

            def poll(self):
                return 1 if cmd == ["systemd-run"] else None

        return Process()

    class Probe:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def call(self, method):
            return {"pid": 42}

    monkeypatch.setattr(daemonctl, "daemon_command", command)
    monkeypatch.setattr(daemonctl.subprocess, "Popen", popen)
    monkeypatch.setattr(paths, "discover_endpoint", lambda: paths.Endpoint("tcp", "127.0.0.1:1"))
    monkeypatch.setattr(Client, "connect", lambda **kwargs: Probe())
    assert daemonctl.start_daemon() == (42, "watchdog")
    assert commands == [["systemd-run"], ["python"]]


def test_real_tcp_daemon_stages_auth_and_bad_frames(tmp_path, monkeypatch):
    monkeypatch.setenv("CODAR_HOME", str(tmp_path / "home"))
    cfg = config.load()
    cfg["model"].update(backend="none", preload=False)
    cfg["daemon"]["endpoint"] = "tcp://127.0.0.1:0"

    async def scenario():
        daemon = Daemon(cfg)
        await daemon.serve()
        try:
            def client_flow():
                with Client.connect(endpoint=daemon.endpoint, autostart=False, timeout=10) as client:
                    assert client.ping()["engine_revision"] == ENGINE_REVISION
                    s0 = client.translate("x é igual a 10", "python", stages=(0,))
                    assert s0["body"] == "x = 10" and s0["stage"] == "0"
                    s1 = client.translate("criar uma calculadora", "python", stages=(1,))
                    compile(s1["code"], "<calculadora>", "exec")
                    assert s1["stage"] == "1"
                    with pytest.raises(RpcError) as error:
                        client.call("translate", {"intent": ""})
                    assert error.value.code == -32602
                    assert client.ping()["pong"]  # erro anterior não quebrou a conexão

            await asyncio.to_thread(client_flow)
            host, port = daemon.endpoint.address.rsplit(":", 1)
            reader, writer = await asyncio.open_connection(host, int(port))
            try:
                writer.write(b'{"jsonrpc":"2.0","method":"translate","id":1,"params":{"intent":"x"}}\n')
                await writer.drain()
                assert json.loads(await reader.readline())["error"]["code"] == -32001
                writer.write(b'{"jsonrpc":"2.0","method":"ping","id":[]}\n')
                writer.write(b'{"jsonrpc":"2.0","method":"ping","id":2}\n')
                await writer.drain()
                frames = [json.loads(await reader.readline()), json.loads(await reader.readline())]
                assert any(frame.get("error", {}).get("code") == -32600 for frame in frames)
                assert any(frame.get("result", {}).get("pong") for frame in frames)
            finally:
                writer.close()
                await writer.wait_closed()
        finally:
            for conn in list(daemon.conns):
                conn.writer.close()
            for server in daemon._servers:
                server.close()
                await server.wait_closed()
            daemon.stage2.shutdown()
            daemon.store.close()
            daemon.cleanup()

    asyncio.run(scenario())
