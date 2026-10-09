"""Motor in-process com a mesma interface do SDK (codar.client.Client), para uso sem daemon (--local, CI, testes)."""

from __future__ import annotations

import asyncio
from typing import Any, Callable

from codar import config, langs, paths
from codar.client import RpcError
from codar.engine.router import Request, Router, TranslateError
from codar.engine.stage1 import PatternStore
from codar.engine.stage2 import ModelUnavailable, Stage2
from codar.plugin_loader import discover


class LocalClient:
    def __init__(self, cfg: dict | None = None, with_model: bool = True, db: str | None = None) -> None:
        self.cfg = cfg or config.load()
        self.bundle = discover(self.cfg)
        self.store = PatternStore(db or paths.db_path())
        self.store.sync(self.bundle.patterns, self.bundle.fingerprint)
        self.stage2 = Stage2(self.cfg) if with_model else None
        self.router = Router(self.cfg, self.store, self.bundle, self.stage2)

    def __enter__(self) -> LocalClient:
        return self

    def __exit__(self, *exc: Any) -> None:
        self.close()

    def close(self) -> None:
        if self.stage2:
            self.stage2.shutdown()
        self.store.close()

    def translate(self, intent: str, lang: str | None = None, *, file: str | None = None, before: str = "",
                  after: str = "", selected: str = "",
                  indent: str = "", indent_unit: str | None = None, stages: tuple[int, ...] = (0, 1, 2),
                  audit: bool = True, hints: bool = False, mode: str = "auto",
                  on_delta: Callable[[str], None] | None = None) -> dict:
        req = Request(intent=intent, lang=lang, lang_explicit=bool(lang), file=file, before=before, indent=indent,
                      after=after, selected=selected,
                      indent_unit=indent_unit, stages=tuple(stages), audit=audit, hints=hints, mode=mode)
        try:
            return asyncio.run(self.router.translate(req, on_token=on_delta)).as_dict()
        except TranslateError as exc:
            raise RpcError(-32004, str(exc), {"candidates": exc.candidates}) from exc
        except ModelUnavailable as exc:
            raise RpcError(-32003, str(exc)) from exc
        except langs.UnknownLanguage as exc:
            raise RpcError(-32602, str(exc)) from exc

    def audit(self, code: str, lang: str, hints: bool = False) -> dict:
        return self.router.audit(code, langs.resolve(lang).id, hints)

    def call(self, method: str, params: dict | None = None, on_notify=None) -> Any:
        p = params or {}
        if method == "patterns.search":
            lang = langs.try_resolve(p.get("lang"))
            return [m.as_dict() for m in self.store.search(p.get("intent", ""), lang.id if lang else None,
                                                           int(p.get("limit", 10)))]
        if method == "patterns.list":
            lang = langs.try_resolve(p.get("lang"))
            return self.store.list(lang.id if lang else None, p.get("query"), int(p.get("limit", 500)))
        if method == "history":
            return list(self.router.metrics.history)[: int(p.get("limit", 50))]
        if method == "patterns.get":
            pat = self.store.get(str(p.get("id", "")))
            if pat is None:
                raise RpcError(-32602, "padrão não encontrado")
            return {"id": pat.id, "title": pat.title, "kind": pat.kind, "keywords": pat.keywords, "slots": pat.slots,
                    "tags": pat.tags, "source": pat.source, "code": pat.code, "path": pat.path}
        if method == "patterns.add":
            from codar.plugin_loader import Pattern

            lang = langs.resolve(p["lang"]).id
            self.store.add(Pattern(id=str(p["id"]), title=str(p["title"]), code={lang: str(p["code"]).rstrip() + "\n"},
                                   keywords=str(p.get("keywords", "")), tags=["user"]))
            self.router.clear_cache()
            return {"ok": True, "id": p["id"]}
        if method in ("model.load", "model.unload", "model.info"):
            if self.stage2 is None:
                raise RpcError(-32003, "modo local sem modelo")
            if method == "model.load":
                self.stage2.preload().result()
            elif method == "model.unload":
                self.stage2.unload().result()
            return self.stage2.info()
        if method == "cache.clear":
            return {"cleared": self.router.clear_cache()}
        if method == "advise":
            from pathlib import Path

            from codar.advisor import scan_project

            return scan_project(Path(p.get("root", ".")), self.bundle.advice)
        raise RpcError(-32601, f"método {method} não disponível no modo local")

    def stats(self) -> dict:
        from codar.daemon.memguard import MemGuard

        guard = MemGuard(self.cfg["memory"])
        guard.sample([self.stage2.backend.child_pid] if self.stage2 else [])
        return {"version": "local", "pid": None, "memory": guard.as_dict(), "patterns": self.store.stats(),
                "stages": self.router.metrics.snapshot(), "rules": len(self.router.auditor.rules),
                "skills": len(self.bundle.skills), "plugins": len(self.bundle.plugins),
                "model": self.stage2.info() if self.stage2 else None}
