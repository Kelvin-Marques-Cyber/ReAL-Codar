"""Daemon codar: servidor JSON-RPC 2.0 (NDJSON) sobre Unix socket, Named Pipe ou TCP local.

Uma linha = uma mensagem JSON. Simples para qualquer cliente (VS Code, Neovim, PowerShell,
socat, nc), sem cabeçalhos Content-Length. Cada requisição vira uma task; respostas podem
chegar fora de ordem (casadas pelo id), o que permite cancelar e fazer streaming.
"""

from __future__ import annotations

import argparse
import asyncio
import gc
import json
import logging
import logging.handlers
import os
import secrets
import signal
import sys
import threading
import time
from pathlib import Path
from typing import Any, Awaitable, Callable

from codar import __version__, config, langs, paths
from codar.daemon.memguard import MemGuard, apply_job_limit
from codar.engine.gguf import GGUFError, estimate, read_gguf
from codar.engine.router import Request, Router, TranslateError
from codar.engine.stage1 import PatternStore
from codar.engine.stage2 import Cancelled, ModelUnavailable, Stage2, malloc_trim
from codar.plugin_loader import Pattern, discover

log = logging.getLogger("codar.daemon")

PARSE_ERROR, INVALID_REQUEST, METHOD_NOT_FOUND, INVALID_PARAMS, INTERNAL = -32700, -32600, -32601, -32602, -32603
UNAUTHORIZED, BUSY, MODEL_UNAVAILABLE, NOT_RESOLVED, CANCELLED = -32001, -32002, -32003, -32004, -32800


class RpcError(Exception):
    def __init__(self, code: int, message: str, data: Any = None):
        super().__init__(message)
        self.code, self.message, self.data = code, message, data


class Conn:
    _ids = 0

    def __init__(self, writer: asyncio.StreamWriter, authed: bool) -> None:
        Conn._ids += 1
        self.id = Conn._ids
        self.writer = writer
        self.authed = authed
        self.lock = asyncio.Lock()
        self.tasks: dict[Any, tuple[asyncio.Task, threading.Event]] = {}
        self.closed = False

    def _encode(self, obj: dict) -> bytes:
        return (json.dumps(obj, ensure_ascii=False, separators=(",", ":")) + "\n").encode("utf-8")

    async def send(self, obj: dict) -> None:
        if self.closed:
            return
        async with self.lock:
            try:
                self.writer.write(self._encode(obj))
                await self.writer.drain()
            except (ConnectionError, RuntimeError):
                self.closed = True

    def notify_nowait(self, method: str, params: dict) -> None:
        """Chamado no event loop (via call_soon_threadsafe) para notificações de streaming."""
        if not self.closed:
            try:
                self.writer.write(self._encode({"jsonrpc": "2.0", "method": method, "params": params}))
            except (ConnectionError, RuntimeError):
                self.closed = True



def _load_usage() -> dict[str, int]:
    """Quantas traduções você pediu em cada linguagem (alimenta warm_langs = ["auto"])."""
    try:
        data = json.loads(paths.usage_file().read_text(encoding="utf-8"))
        return {str(k): int(v) for k, v in data.items()}
    except (OSError, ValueError, AttributeError, TypeError):
        return {}

class Daemon:
    def __init__(self, cfg: dict) -> None:
        self.cfg = cfg
        self.started = time.time()
        self.requests = 0
        self.conns: set[Conn] = set()
        self.dcfg = cfg["daemon"]
        self.limit = int(self.dcfg.get("max_request_kb", 256)) * 1024
        self.memguard = MemGuard(cfg["memory"])
        self.bundle = discover(cfg)
        paths.data_dir().mkdir(parents=True, exist_ok=True)
        self.store = PatternStore(paths.db_path())
        self.store.sync(self.bundle.patterns, self.bundle.fingerprint)
        self.stage2 = Stage2(cfg)
        self.usage = _load_usage()
        self._usage_saved = time.monotonic()
        self._usage_dirty = False
        self.stage2.warm_langs = self._warm_langs()
        self.router = Router(cfg, self.store, self.bundle, self.stage2, needle=self._needle())
        self.endpoint: paths.Endpoint | None = None
        self.stop_event = asyncio.Event()
        self._servers: list[Any] = []
        self._last_soft = 0.0
        self.methods: dict[str, Callable[[Conn, dict, Any], Awaitable[Any]]] = {
            "ping": self.m_ping, "auth": self.m_auth, "translate": self.m_translate, "audit": self.m_audit,
            "stats": self.m_stats, "history": self.m_history, "shutdown": self.m_shutdown, "reload": self.m_reload,
            "patterns.search": self.m_pat_search, "patterns.list": self.m_pat_list, "patterns.get": self.m_pat_get,
            "patterns.add": self.m_pat_add, "patterns.remove": self.m_pat_remove, "model.load": self.m_model_load,
            "model.unload": self.m_model_unload, "model.info": self.m_model_info, "cache.clear": self.m_cache_clear,
            "rules.list": self.m_rules, "skills.list": self.m_skills, "langs.list": self.m_langs,
            "advise": self.m_advise, "plugins.list": self.m_plugins,
        }

    def _needle(self):
        if not self.cfg.get("needle", {}).get("enabled"):
            return None
        try:
            from codar.engine.needle_adapter import NeedleRouter

            return NeedleRouter(float(self.cfg["needle"].get("min_confidence", 0.6)))
        except Exception as exc:  # opcional; nunca impede o daemon de subir
            log.warning("needle indisponível: %s", exc)
            return None

    # ------------------------------------------------------------------ servidor
    async def serve(self) -> None:
        ep_spec = self.dcfg.get("endpoint") or ""
        ep = paths.parse_endpoint(ep_spec) if ep_spec else paths.default_endpoint()
        paths.ensure_private_dir(paths.runtime_dir())
        if ep.transport == "unix":
            sock = Path(ep.address)
            paths.ensure_private_dir(sock.parent)
            if sock.exists():
                sock.unlink()
            old_umask = os.umask(0o177)
            try:
                server = await asyncio.start_unix_server(self._client(authed=True), path=str(sock), limit=self.limit)
            finally:
                os.umask(old_umask)
            self._servers.append(server)
            self.endpoint = ep
        elif ep.transport == "pipe":
            loop = asyncio.get_running_loop()
            start_pipe = getattr(loop, "start_serving_pipe", None)
            if start_pipe is None:
                raise RuntimeError("Named Pipes exigem o ProactorEventLoop do Windows")

            def factory():
                return asyncio.StreamReaderProtocol(asyncio.StreamReader(limit=self.limit), self._client(authed=True))

            self._servers.extend(await start_pipe(factory, ep.address))
            self.endpoint = ep
        else:
            host, _, port = ep.address.rpartition(":")
            if host not in ("127.0.0.1", "localhost", "::1"):
                raise RuntimeError("o daemon só escuta em loopback")
            server = await asyncio.start_server(self._client(authed=False), host=host, port=int(port or 0),
                                                limit=self.limit)
            real_port = server.sockets[0].getsockname()[1]
            self.endpoint = paths.Endpoint("tcp", f"{host}:{real_port}", secrets.token_urlsafe(24))
            self._servers.append(server)
        ep_file = paths.endpoint_file()
        tmp = ep_file.with_suffix(".tmp")
        tmp.write_text(self.endpoint.to_json(os.getpid(), __version__), encoding="utf-8")
        if not paths.IS_WIN:
            tmp.chmod(0o600)
        tmp.replace(ep_file)
        paths.pid_file().write_text(str(os.getpid()), encoding="utf-8")
        log.info("ouvindo em %s (pid %d)", self.endpoint.uri(), os.getpid())

    def _client(self, authed: bool):
        async def handler(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
            if len(self.conns) >= int(self.dcfg.get("max_connections", 64)):
                writer.close()
                return
            conn = Conn(writer, authed)
            self.conns.add(conn)
            try:
                await self._loop(conn, reader)
            finally:
                conn.closed = True
                for task, ev in list(conn.tasks.values()):
                    ev.set()
                    task.cancel()
                self.conns.discard(conn)
                try:
                    writer.close()
                except Exception:
                    pass
        return handler

    async def _loop(self, conn: Conn, reader: asyncio.StreamReader) -> None:
        while not conn.closed:
            try:
                line = await reader.readline()
            except (asyncio.LimitOverrunError, ValueError):
                await conn.send(_err(None, INVALID_REQUEST, f"mensagem maior que {self.limit // 1024} KB"))
                return
            except (ConnectionError, asyncio.IncompleteReadError):
                return
            if not line:
                return
            if not line.strip():
                continue
            try:
                msg = json.loads(line)
            except ValueError:
                await conn.send(_err(None, PARSE_ERROR, "JSON inválido"))
                continue
            for item in msg if isinstance(msg, list) else [msg]:
                self._dispatch(conn, item)

    def _dispatch(self, conn: Conn, msg: Any) -> None:
        if not isinstance(msg, dict) or not isinstance(msg.get("method"), str):
            asyncio.ensure_future(conn.send(_err(msg.get("id") if isinstance(msg, dict) else None, INVALID_REQUEST,
                                                 "requisição JSON-RPC inválida")))
            return
        method, rid = msg["method"], msg.get("id")
        if method == "$/cancelRequest":
            entry = conn.tasks.get((msg.get("params") or {}).get("id"))
            if entry:
                entry[1].set()
            return
        if len(conn.tasks) >= int(self.dcfg.get("max_inflight_per_conn", 8)):
            asyncio.ensure_future(conn.send(_err(rid, BUSY, "muitas requisições simultâneas nesta conexão")))
            return
        cancel = threading.Event()
        task = asyncio.ensure_future(self._run(conn, method, msg.get("params") or {}, rid, cancel))
        key = rid if rid is not None else object()
        conn.tasks[key] = (task, cancel)
        task.add_done_callback(lambda _t, k=key: conn.tasks.pop(k, None))

    async def _run(self, conn: Conn, method: str, params: dict, rid: Any, cancel: threading.Event) -> None:
        self.requests += 1
        try:
            if not conn.authed and method not in ("auth", "ping"):
                raise RpcError(UNAUTHORIZED, "autentique-se com o método 'auth' (token em endpoint.json)")
            handler = self.methods.get(method)
            if handler is None:
                raise RpcError(METHOD_NOT_FOUND, f"método desconhecido: {method}")
            if not isinstance(params, dict):
                raise RpcError(INVALID_PARAMS, "params deve ser um objeto")
            params["_cancel"] = cancel
            result = await handler(conn, params, rid)
            if rid is not None:
                await conn.send({"jsonrpc": "2.0", "id": rid, "result": result})
        except RpcError as exc:
            if rid is not None:
                await conn.send(_err(rid, exc.code, exc.message, exc.data))
        except TranslateError as exc:
            if rid is not None:
                await conn.send(_err(rid, NOT_RESOLVED, str(exc), {"candidates": exc.candidates}))
        except ModelUnavailable as exc:
            if rid is not None:
                await conn.send(_err(rid, MODEL_UNAVAILABLE, str(exc)))
        except (Cancelled, asyncio.CancelledError):
            if rid is not None and not conn.closed:
                await conn.send(_err(rid, CANCELLED, "requisição cancelada"))
        except Exception as exc:  # nunca derruba a conexão
            log.exception("erro em %s", method)
            if rid is not None:
                await conn.send(_err(rid, INTERNAL, f"{type(exc).__name__}: {exc}"))

    # ------------------------------------------------------------------ métodos
    async def m_ping(self, conn, p, rid):
        return {"pong": True, "version": __version__, "pid": os.getpid()}

    async def m_auth(self, conn, p, rid):
        if self.endpoint and secrets.compare_digest(str(p.get("token", "")), self.endpoint.token):
            conn.authed = True
            return {"ok": True}
        raise RpcError(UNAUTHORIZED, "token inválido")

    async def m_translate(self, conn, p, rid):
        if not str(p.get("intent", "")).strip():
            raise RpcError(INVALID_PARAMS, "intent vazio")
        try:
            req = Request.from_params(p, self.cfg.get("router", {}).get("default_lang"))
        except (TypeError, ValueError) as exc:
            raise RpcError(INVALID_PARAMS, str(exc)) from exc
        on_token = None
        if (p.get("options") or {}).get("stream"):
            loop = asyncio.get_running_loop()

            def on_token(delta: str) -> None:
                loop.call_soon_threadsafe(conn.notify_nowait, "$/progress", {"id": rid, "delta": delta})
        try:
            res = await self.router.translate(req, on_token=on_token, cancel=p["_cancel"])
        except langs.UnknownLanguage as exc:
            raise RpcError(INVALID_PARAMS, str(exc)) from exc
        out = res.as_dict()
        if out.get("lang"):
            self.usage[out["lang"]] = self.usage.get(out["lang"], 0) + 1
            self._usage_dirty = True
        return out

    async def m_audit(self, conn, p, rid):
        code = str(p.get("code", ""))
        lang = langs.try_resolve(p.get("lang")) or langs.from_path(p.get("file"))
        if lang is None:
            raise RpcError(INVALID_PARAMS, "informe lang ou file")
        return self.router.audit(code, lang.id, bool(p.get("hints")))

    async def m_stats(self, conn, p, rid):
        return {"version": __version__, "pid": os.getpid(), "uptime_s": round(time.time() - self.started),
                "endpoint": self.endpoint.uri() if self.endpoint else None, "requests": self.requests,
                "connections": len(self.conns), "memory": self.memguard.as_dict(), "model": self.stage2.info(),
                "patterns": self.store.stats(), "plugins": len(self.bundle.plugins), "rules": len(self.router.auditor.rules),
                "skills": len(self.bundle.skills), "stages": self.router.metrics.snapshot(),
                "cache": len(self.router._cache), "python": sys.version.split()[0]}

    async def m_history(self, conn, p, rid):
        return list(self.router.metrics.history)[: int(p.get("limit", 50))]

    async def m_shutdown(self, conn, p, rid):
        asyncio.get_running_loop().call_later(0.05, self.stop_event.set)
        return {"ok": True}

    async def m_reload(self, conn, p, rid):
        self.bundle = discover(self.cfg)
        changed = self.store.sync(self.bundle.patterns, self.bundle.fingerprint, force=bool(p.get("force")))
        self.router = Router(self.cfg, self.store, self.bundle, self.stage2, needle=self.router.needle)
        return {"patterns_rebuilt": changed, "plugins": len(self.bundle.plugins), **self.store.stats()}

    async def m_pat_search(self, conn, p, rid):
        lang = langs.try_resolve(p.get("lang"))
        return [m.as_dict() for m in self.store.search(str(p.get("intent", "")), lang.id if lang else None,
                                                       int(p.get("limit", 10)))]

    async def m_pat_list(self, conn, p, rid):
        lang = langs.try_resolve(p.get("lang"))
        return self.store.list(lang.id if lang else None, p.get("query"), int(p.get("limit", 500)))

    async def m_pat_get(self, conn, p, rid):
        pat = self.store.get(str(p.get("id", "")))
        if pat is None:
            raise RpcError(INVALID_PARAMS, "padrão não encontrado")
        return {"id": pat.id, "title": pat.title, "kind": pat.kind, "keywords": pat.keywords, "slots": pat.slots,
                "tags": pat.tags, "source": pat.source, "code": pat.code, "path": pat.path}

    async def m_pat_add(self, conn, p, rid):
        try:
            lang = langs.resolve(p["lang"]).id
            pat = Pattern(id=str(p["id"]), title=str(p["title"]), code={lang: str(p["code"]).rstrip() + "\n"},
                          keywords=str(p.get("keywords", "")), slots=dict(p.get("slots") or {}),
                          tags=list(p.get("tags") or ["user"]))
        except (KeyError, langs.UnknownLanguage) as exc:
            raise RpcError(INVALID_PARAMS, f"campo obrigatório ausente/ inválido: {exc}") from exc
        self.store.add(pat)
        self.router.clear_cache()
        return {"ok": True, "id": pat.id}

    async def m_pat_remove(self, conn, p, rid):
        return {"removed": self.store.remove(str(p.get("id", "")))}

    async def m_model_load(self, conn, p, rid):
        self._preflight()
        await asyncio.wrap_future(self.stage2.preload())
        return self.stage2.info()

    async def m_model_unload(self, conn, p, rid):
        await asyncio.wrap_future(self.stage2.unload())
        return self.stage2.info()

    async def m_model_info(self, conn, p, rid):
        info = self.stage2.info()
        if self.stage2.path and self.stage2.path.is_file():
            try:
                g = read_gguf(self.stage2.path)
                m = self.cfg["model"]
                info["gguf"] = g.describe()
                info["estimate"] = estimate(g, int(m["n_ctx"]), int(m.get("n_ubatch") or m["n_batch"]), use_mmap=bool(m.get("use_mmap"))).as_dict()
            except (GGUFError, OSError) as exc:
                info["gguf_error"] = str(exc)
        return info

    async def m_cache_clear(self, conn, p, rid):
        return {"cleared": self.router.clear_cache()}

    async def m_rules(self, conn, p, rid):
        return self.router.auditor.describe()

    async def m_skills(self, conn, p, rid):
        return [{"id": s.id, "langs": s.langs, "triggers": s.triggers, "guidance": s.guidance, "source": s.source}
                for s in self.bundle.skills]

    async def m_langs(self, conn, p, rid):
        from codar.engine.emit import EMITTERS

        return [{"id": lg.id, "name": lg.name, "aliases": list(lg.aliases), "stage0": lg.id in EMITTERS}
                for lg in langs.LANGS.values()]

    async def m_plugins(self, conn, p, rid):
        return [{"name": pl.name, "version": pl.version, "description": pl.description, "builtin": pl.builtin,
                 "patterns": len(pl.patterns), "skills": len(pl.skills), "rules": len(pl.rules),
                 "advice": len(pl.advice), "errors": pl.errors} for pl in self.bundle.plugins]

    async def m_advise(self, conn, p, rid):
        from codar.advisor import scan_project

        root = Path(str(p.get("root") or ".")).expanduser()
        if not root.is_dir():
            raise RpcError(INVALID_PARAMS, f"diretório inexistente: {root}")
        return await asyncio.get_running_loop().run_in_executor(None, scan_project, root, self.bundle.advice)

    # ------------------------------------------------------------------ memória
    def _preflight(self) -> None:
        """Recusa carregar um modelo cuja estimativa de RSS estoura o teto duro."""
        path = self.stage2.path
        if not path or not path.is_file():
            return
        try:
            g = read_gguf(path)
        except (GGUFError, OSError):
            return
        m = self.cfg["model"]
        est = estimate(g, int(m["n_ctx"]), int(m.get("n_ubatch") or m["n_batch"]), use_mmap=bool(m.get("use_mmap")))
        current = self.memguard.sample([]).rss_mb
        if est.total_mb + current - est.runtime_mb > self.memguard.hard / 1048576:
            raise ModelUnavailable(f"o modelo exigiria ~{est.total_mb:.0f} MB e o teto é "
                                   f"{self.memguard.hard / 1048576:.0f} MB; escolha um modelo menor ou reduza n_ctx/n_batch")

    def _warm_langs(self) -> list[str]:
        """Linguagens a pré-aquecer: as da config, com "auto" virando as 3 mais usadas (ou python)."""
        out: list[str] = []
        for item in self.cfg["model"].get("warm_langs") or ["auto"]:
            if str(item).lower() == "auto":
                ranked = sorted(self.usage, key=self.usage.get, reverse=True)[:3]
                candidates = ranked or ["python"]
            else:
                candidates = [str(item)]
            for c in candidates:
                lang = langs.try_resolve(c)
                if lang and lang.id not in out:
                    out.append(lang.id)
        return out or ["python"]

    def save_usage(self, force: bool = False) -> None:
        if not self._usage_dirty or (not force and time.monotonic() - self._usage_saved < 60):
            return
        try:
            tmp = paths.usage_file().with_suffix(".tmp")
            tmp.write_text(json.dumps(self.usage, ensure_ascii=False), encoding="utf-8")
            tmp.replace(paths.usage_file())
            self._usage_dirty, self._usage_saved = False, time.monotonic()
        except OSError as exc:
            log.debug("não salvei o uso por linguagem: %s", exc)

    async def watchdog(self) -> None:
        mcfg = self.cfg["memory"]
        interval = float(mcfg.get("check_interval_s", 2.0))
        idle_limit = float(mcfg.get("idle_unload_s", 900))
        while not self.stop_event.is_set():
            await asyncio.sleep(interval)
            self.save_usage()
            st = self.memguard.sample([self.stage2.backend.child_pid])
            now = time.monotonic()
            if st.level == "hard" and self.stage2.backend.loaded:
                st.hard_events += 1
                log.warning("RSS %.0f MB acima do teto duro: descarregando o modelo", st.rss_mb + st.child_mb)
                self.router.clear_cache()
                await asyncio.wrap_future(self.stage2.unload())
            elif st.level == "soft" and now - self._last_soft > 30:
                st.soft_events += 1
                self._last_soft = now
                log.info("RSS %.0f MB acima do limite suave: liberando caches", st.rss_mb + st.child_mb)
                self.router.clear_cache()
                await asyncio.wrap_future(self.stage2.shrink())
            if idle_limit > 0 and self.stage2.backend.loaded and not self.stage2.pending \
                    and self.stage2.idle_seconds() > idle_limit:
                log.info("modelo ocioso há %.0fs: descarregando", self.stage2.idle_seconds())
                await asyncio.wrap_future(self.stage2.unload())

    async def preload(self) -> None:
        try:
            self._preflight()
            await asyncio.wrap_future(self.stage2.preload())
        except ModelUnavailable as exc:
            self.stage2.load_error = str(exc)
            log.warning("estágio 2 indisponível: %s", exc)
        finally:
            gc.collect()
            malloc_trim()
            gc.freeze()  # objetos de inicialização saem da varredura do GC

    async def run(self) -> None:
        await self.serve()
        loop = asyncio.get_running_loop()
        for sig in (signal.SIGINT, signal.SIGTERM):
            try:
                loop.add_signal_handler(sig, self.stop_event.set)
            except (NotImplementedError, RuntimeError):
                pass
        tasks = [asyncio.ensure_future(self.watchdog())]
        if self.cfg["model"].get("preload", True) and self.stage2.configured():
            tasks.append(asyncio.ensure_future(self.preload()))
        else:
            gc.collect()
            gc.freeze()
        await self.stop_event.wait()
        log.info("encerrando")
        for t in tasks:
            t.cancel()
        for srv in self._servers:
            srv.close()
        for conn in list(self.conns):
            conn.closed = True
            conn.writer.close()
        self.stage2.shutdown()
        self.store.close()
        self.cleanup()

    def cleanup(self) -> None:
        self.save_usage(force=True)
        for f in (paths.endpoint_file(), paths.pid_file()):
            try:
                f.unlink()
            except OSError:
                pass
        if self.endpoint and self.endpoint.transport == "unix":
            try:
                Path(self.endpoint.address).unlink()
            except OSError:
                pass


def _err(rid: Any, code: int, message: str, data: Any = None) -> dict:
    err: dict[str, Any] = {"code": code, "message": message}
    if data is not None:
        err["data"] = data
    return {"jsonrpc": "2.0", "id": rid, "error": err}


def setup_logging(level: str, foreground: bool) -> None:
    paths.log_dir().mkdir(parents=True, exist_ok=True)
    handlers: list[logging.Handler] = [logging.handlers.RotatingFileHandler(
        paths.log_dir() / "daemon.log", maxBytes=1_000_000, backupCount=2, encoding="utf-8")]
    if foreground:
        handlers.append(logging.StreamHandler(sys.stderr))
    logging.basicConfig(level=getattr(logging, level.upper(), logging.INFO), handlers=handlers,
                        format="%(asctime)s %(levelname)s %(name)s: %(message)s")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="codar-daemon")
    ap.add_argument("--foreground", action="store_true")
    ap.add_argument("--endpoint")
    args = ap.parse_args(argv)
    cfg = config.load()
    if args.endpoint:
        cfg["daemon"]["endpoint"] = args.endpoint
    setup_logging(cfg["daemon"].get("log_level", "info"), args.foreground)
    if sys.platform == "win32" and cfg["memory"].get("enforce", "auto") in ("auto", "job"):
        limit = int(cfg["memory"]["budget_mb"]) * 1048576
        if apply_job_limit(limit):
            os.environ["CODAR_JOB_LIMIT"] = str(limit)
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())  # Named Pipes
    from codar.client import Client, DaemonNotRunning

    try:
        with Client.connect(autostart=False, timeout=1.0) as c:
            c.call("ping")
        print("codar: o daemon já está em execução", file=sys.stderr)
        return 1
    except (DaemonNotRunning, OSError):
        pass
    daemon = Daemon(cfg)
    try:
        asyncio.run(daemon.run())
    except KeyboardInterrupt:
        pass
    finally:
        daemon.cleanup()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
