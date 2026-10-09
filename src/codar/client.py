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
            client.call("auth", {"token": ep.token})
        return client

    def __enter__(self) -> Client:
        return self

    def __exit__(self, *exc: Any) -> None:
        self.close()

    def close(self) -> None:
        self.t.close()

    def call(self, method: str, params: dict | None = None,
             on_notify: Callable[[str, dict], None] | None = None) -> Any:
        rid = next(self._ids)
        msg = {"jsonrpc": "2.0", "id": rid, "method": method, "params": params or {}}
        self.t.send((json.dumps(msg, ensure_ascii=False) + "\n").encode("utf-8"))
        while True:
            reply = json.loads(self.t.readline())
            if "id" not in reply and "method" in reply:
                if on_notify:
                    on_notify(reply["method"], reply.get("params") or {})
                continue
            if reply.get("id") != rid:
                continue
            if "error" in reply:
                e = reply["error"]
                raise RpcError(e.get("code", -32603), e.get("message", "erro"), e.get("data"))
            return reply.get("result")

    def notify(self, method: str, params: dict | None = None) -> None:
        msg = {"jsonrpc": "2.0", "method": method, "params": params or {}}
        self.t.send((json.dumps(msg) + "\n").encode("utf-8"))

    # ------------------------------------------------------------------ atalhos
    def ping(self) -> dict:
        return self.call("ping")

    def translate(self, intent: str, lang: str | None = None, *, file: str | None = None, before: str = "",
                  indent: str = "", indent_unit: str | None = None, stages: tuple[int, ...] = (0, 1, 2),
                  audit: bool = True, hints: bool = False, mode: str = "auto",
                  on_delta: Callable[[str], None] | None = None) -> dict:
        params = {"intent": intent, "lang": lang,
                  "context": {"file": file, "before": before, "indent": indent, "indent_unit": indent_unit},
                  "options": {"stages": list(stages), "audit": audit, "hints": hints, "mode": mode,
                              "stream": on_delta is not None}}

        def notify(method: str, p: dict) -> None:
            if method == "$/progress" and on_delta:
                on_delta(p.get("delta", ""))

        return self.call("translate", params, on_notify=notify)

    def audit(self, code: str, lang: str, hints: bool = False) -> dict:
        return self.call("audit", {"code": code, "lang": lang, "hints": hints})

    def stats(self) -> dict:
        return self.call("stats")

    def advise(self, root: str = ".") -> dict:
        return self.call("advise", {"root": os.path.abspath(root)})
