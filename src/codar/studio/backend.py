"""Acesso ao motor a partir do Studio: daemon (padrão) ou in-process (--local). Chamado em threads de worker."""

from __future__ import annotations

import threading
from pathlib import Path
from typing import Any, Callable


class StudioBackend:
    def __init__(self, local: bool = False) -> None:
        self.local = local
        self._local = None
        self._lock = threading.Lock()

    def _client(self):
        if self.local:
            with self._lock:
                if self._local is None:
                    from codar.engine.local import LocalClient

                    self._local = LocalClient()
            return _NoClose(self._local)
        from codar.client import Client

        return Client.connect()

    def translate(self, intent: str, lang: str | None, *, file: str | None, before: str, indent: str,
                  indent_unit: str | None, stages: tuple[int, ...], hints: bool,
                  after: str = "", selected: str = "", mode: str = "auto",
                  on_delta: Callable[[str], None] | None = None) -> dict:
        with self._client() as c:
            return c.translate(intent, lang, file=file, before=before, indent=indent, indent_unit=indent_unit,
                               after=after, selected=selected, mode=mode, stages=stages, hints=hints, on_delta=on_delta)

    def audit(self, code: str, lang: str) -> dict:
        with self._client() as c:
            return c.audit(code, lang)

    def stats(self) -> dict:
        with self._client() as c:
            return c.stats()

    def call(self, method: str, params: dict | None = None) -> Any:
        with self._client() as c:
            return c.call(method, params or {})

    def advise(self, root: Path) -> dict:
        with self._client() as c:
            return c.call("advise", {"root": str(root)})

    def close(self) -> None:
        if self._local is not None:
            self._local.close()


class _NoClose:
    def __init__(self, inner) -> None:
        self.inner = inner

    def __enter__(self):
        return self.inner

    def __exit__(self, *exc) -> None:
        return None
