"""SDK Python do codar: cliente JSON-RPC síncrono (Unix socket, Named Pipe ou TCP local).

    from codar.client import Client
    with Client.connect() as c:
        r = c.translate("conectar ao redis", lang="python")
        print(r["code"])

Importa só a biblioteca padrão: é o caminho rápido usado pela CLI e pelos hooks de shell.
"""

from __future__ import annotations

import itertools
import json
import os
import socket
import threading
import time
from typing import Any, Callable

from codar import paths


class DaemonNotRunning(ConnectionError):
    pass


class RpcError(Exception):
    def __init__(self, code: int, message: str, data: Any = None):
        super().__init__(message)
        self.code, self.message, self.data = code, message, data


class _Transport:
    def __init__(self, ep: paths.Endpoint, timeout: float) -> None:
        self.ep = ep
        self.buf = b""
        self.sock: socket.socket | None = None
        self.pipe = None
        if ep.transport == "unix":
            if not hasattr(socket, "AF_UNIX"):
                raise DaemonNotRunning("Unix sockets indisponíveis neste sistema")
            s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            s.settimeout(timeout)
            try:
                s.connect(ep.address)
            except (FileNotFoundError, ConnectionRefusedError) as exc:
                s.close()
                raise DaemonNotRunning(str(exc)) from exc
            self.sock = s
        elif ep.transport == "tcp":
            host, _, port = ep.address.rpartition(":")
            try:
                self.sock = socket.create_connection((host, int(port)), timeout=timeout)
            except ConnectionRefusedError as exc:
                raise DaemonNotRunning(str(exc)) from exc
        else:  # Named Pipe (Windows)
            deadline = time.monotonic() + timeout
            while True:
                try:
                    self.pipe = open(ep.address, "r+b", buffering=0)  # noqa: SIM115
                    break
                except FileNotFoundError as exc:
                    raise DaemonNotRunning(str(exc)) from exc
                except OSError:  # ERROR_PIPE_BUSY: todas as instâncias ocupadas
                    if time.monotonic() > deadline:
                        raise
                    time.sleep(0.05)

    def settimeout(self, timeout: float | None) -> None:
        if self.sock:
            self.sock.settimeout(timeout)

    def send(self, data: bytes) -> None:
        if self.sock:
            self.sock.sendall(data)
        else:
            self.pipe.write(data)

    def readline(self) -> bytes:
        while b"\n" not in self.buf:
            chunk = self.sock.recv(65536) if self.sock else self.pipe.read(65536)
            if not chunk:
                raise ConnectionError("o daemon fechou a conexão")
            self.buf += chunk
        line, _, self.buf = self.buf.partition(b"\n")
        return line

    def close(self) -> None:
        try:
            if self.sock:
                self.sock.close()
            if self.pipe:
                self.pipe.close()
        except OSError:
            pass


class Client:
    def __init__(self, transport: _Transport) -> None:
        self.t = transport
        self._ids = itertools.count(1)
        # A conexão síncrona tem um único leitor. Dois leitores simultâneos
        # consumiam (e descartavam) a resposta um do outro, bloqueando ambos.
        self._calls = threading.Lock()
        # O vigia de cancelamento também escreve; cada frame deve ser atômico.
        self._writes = threading.Lock()

    @classmethod
    def connect(cls, autostart: bool = True, timeout: float = 600.0, endpoint: paths.Endpoint | None = None,
                start_timeout: float = 30.0) -> Client:
        autostart = autostart and os.environ.get("CODAR_NO_AUTOSTART") != "1"  # testes e CI: nunca sobe daemon sozinho
        ep = endpoint or paths.discover_endpoint()
        if ep is None and autostart:
            from codar.daemonctl import start_daemon

            start_daemon(wait=start_timeout)
            ep = paths.discover_endpoint()
        if ep is None:
            raise DaemonNotRunning("daemon não está em execução (rode `codar start`)")
        try:
            client = cls(_Transport(ep, timeout))
        except DaemonNotRunning:
            if not autostart or endpoint is not None:
                raise
            from codar.daemonctl import start_daemon

            start_daemon(wait=start_timeout)
            ep = paths.discover_endpoint()
            if ep is None:
                raise
            client = cls(_Transport(ep, timeout))
        if ep.transport == "tcp" and ep.token:
            try:
                client.call("auth", {"token": ep.token})
            except Exception:
                client.close()
                raise
        return client

    def __enter__(self) -> Client:
        return self

    def __exit__(self, *exc: Any) -> None:
        self.close()

    def close(self) -> None:
        self.t.close()

    def call(self, method: str, params: dict | None = None,
             on_notify: Callable[[str, dict], None] | None = None,
             cancel: threading.Event | None = None) -> Any:
        with self._calls:
            return self._call(method, params, on_notify, cancel)

    def _send(self, msg: dict) -> None:
        data = (json.dumps(msg, ensure_ascii=False) + "\n").encode("utf-8")
        with self._writes:
            self.t.send(data)

    def _call(self, method: str, params: dict | None,
              on_notify: Callable[[str, dict], None] | None,
              cancel: threading.Event | None) -> Any:
        if cancel is not None and cancel.is_set():
            raise RpcError(-32800, 'requisição cancelada')
        rid = next(self._ids)
        msg = {"jsonrpc": "2.0", "id": rid, "method": method, "params": params or {}}
        self._send(msg)
        done = threading.Event()
        def watch_cancel():
            while not done.wait(.02):
                if cancel.is_set():
                    try:
                        self.notify('$/cancelRequest', {'id': rid})
                    except (OSError, ConnectionError):
                        pass
                    return
        watcher = threading.Thread(target=watch_cancel, daemon=True) if cancel is not None else None
        if watcher:
            watcher.start()
        try:
            while True:
                try:
                    reply = json.loads(self.t.readline())
                except (ValueError, UnicodeError) as exc:
                    raise ConnectionError("resposta JSON inválida do daemon") from exc
                if not isinstance(reply, dict):
                    raise ConnectionError("resposta JSON-RPC inválida do daemon")
                if cancel is not None and cancel.is_set():
                    raise RpcError(-32800, 'requisição cancelada')
                if "id" not in reply and "method" in reply:
                    progress = reply.get("params") or {}
                    if reply["method"] == "$/progress" and progress.get("id", rid) != rid:
                        continue  # fragmento atrasado de um pedido já cancelado
                    if on_notify:
                        on_notify(reply["method"], progress)
                    continue
                if reply.get("id") != rid:
                    continue
                if "error" in reply:
                    e = reply["error"]
                    raise RpcError(e.get("code", -32603), e.get("message", "erro"), e.get("data"))
                return reply.get("result")
        finally:
            done.set()
            if watcher:
                watcher.join(timeout=.1)

    def notify(self, method: str, params: dict | None = None) -> None:
        msg = {"jsonrpc": "2.0", "method": method, "params": params or {}}
        self._send(msg)

    # ------------------------------------------------------------------ atalhos
    def ping(self) -> dict:
        return self.call("ping")

    def translate(self, intent: str, lang: str | None = None, *, file: str | None = None, before: str = "",
                  after: str = "", selected: str = "", project_root: str | None = None,
                  indent: str = "", indent_unit: str | None = None, stages: tuple[int, ...] = (0, 1, 2),
                  audit: bool = True, hints: bool = False, mode: str = "auto",
                  on_delta: Callable[[str], None] | None = None,
                  cancel: threading.Event | None = None, locale: str | None = None) -> dict:
        from codar.i18n import get_locale

        params = {"intent": intent, "lang": lang, 'locale': locale or get_locale(),
                  "context": {"file": file, "before": before, "after": after, "selected": selected,
                              "root": project_root, "indent": indent, "indent_unit": indent_unit},
                  "options": {"stages": list(stages), "audit": audit, "hints": hints, "mode": mode,
                              "stream": on_delta is not None}}

        def notify(method: str, p: dict) -> None:
            if method == "$/progress" and on_delta:
                on_delta(p.get("delta", ""))

        return self.call("translate", params, on_notify=notify, cancel=cancel)

    def audit(self, code: str, lang: str, hints: bool = False) -> dict:
        return self.call("audit", {"code": code, "lang": lang, "hints": hints})

    def stats(self) -> dict:
        return self.call("stats")

    def advise(self, root: str = ".") -> dict:
        return self.call("advise", {"root": os.path.abspath(root)})
