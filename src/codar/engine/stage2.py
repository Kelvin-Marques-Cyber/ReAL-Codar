"""Estágio 2 — SLM local (llama.cpp), acionado só quando os Estágios 0/1 não resolvem.

Dois papéis:
  * compositor: escolhe ferramentas (padrões verificados) do banco e preenche seus argumentos.
    A saída é JSON restrito por gramática (GBNF gerada de um JSON Schema com enum dos ids
    candidatos), então até um modelo de 0.5B não consegue inventar ferramentas.
  * gerador: escreve código novo ancorado no padrão mais próximo (RAG) + diretrizes (skills).

Todas as chamadas ao modelo rodam numa única thread dedicada: um contexto llama.cpp não é
thread-safe e o daemon nunca deve ter duas cópias de KV cache.
"""

from __future__ import annotations

import ctypes
import gc
import http.client
import json
import logging
import os
import shutil
import socket
import subprocess
import sys
import threading
import time
from collections import deque
from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from codar.engine.models import STOP, ModelCard, guess_fmt, resolve_model

log = logging.getLogger("codar.stage2")


class ModelUnavailable(RuntimeError):
    pass


class Cancelled(RuntimeError):
    pass


@dataclass
class GenResult:
    text: str
    tokens: int
    prompt_tokens: int
    ms: float
    finish: str  # stop | length | cancel


def physical_cores() -> int:
    try:
        cores = set()
        phys = core = None
        with open("/proc/cpuinfo", encoding="utf-8") as fh:
            for line in fh:
                if line.startswith("physical id"):
                    phys = line.split(":")[1].strip()
                elif line.startswith("core id"):
                    core = line.split(":")[1].strip()
                elif not line.strip() and core is not None:
                    cores.add((phys, core))
                    phys = core = None
        if cores:
            return len(cores)
    except OSError:
        pass
    return max(1, (os.cpu_count() or 2) // 2)


def malloc_trim() -> None:
    """Devolve ao SO a memória livre do heap (glibc). No-op em outras libc/SO."""
    if sys.platform.startswith("linux"):
        try:
            ctypes.CDLL("libc.so.6").malloc_trim(0)
        except (OSError, AttributeError):
            pass


def compact_ram_cache(capacity_bytes: int):
    """LlamaRAMCache que mede o tamanho REAL de cada estado.

    O original contabiliza só o estado C (~6 MB), mas cada LlamaState carrega também uma cópia dos logits
    (n_batch x n_vocab x 4 bytes = 78 MB no Qwen com n_batch 128): com "64 MB" ele chegava a +840 MB de RSS.
    Para reaproveitar prefixo os logits não importam (o último token do prompt é sempre reavaliado), então
    guardamos só uma linha — load_state a propaga por broadcasting.
    """
    from llama_cpp import LlamaRAMCache

    class CompactRAMCache(LlamaRAMCache):
        @property
        def cache_size(self) -> int:
            return sum(st.llama_state_size + st.scores.nbytes + st.input_ids.nbytes for st in self.cache_state.values())

        def __setitem__(self, key, value) -> None:
            if getattr(value, "scores", None) is not None and len(value.scores) > 1:
                value.scores = value.scores[-1:].copy()
            super().__setitem__(key, value)

    return CompactRAMCache(capacity_bytes=capacity_bytes)


# =============================================================================== backends

class Backend:
    name = "none"
    loaded = False
    child_pid: int | None = None

    def load(self) -> None:
        raise ModelUnavailable("nenhum backend de modelo configurado")

    def unload(self) -> None:
        pass

    def reset(self) -> None:
        pass

    def tokens(self, text: str) -> int:
        return max(1, len(text) // 3)

    def complete(self, prompt: str, *, max_tokens: int, temperature: float, stop: list[str],
                 schema: dict | None = None, on_token: Callable[[str], None] | None = None,
                 cancel: threading.Event | None = None) -> GenResult:
        raise ModelUnavailable("nenhum backend de modelo configurado")


class LlamaCppBackend(Backend):
    """llama.cpp in-process via llama-cpp-python (bindings C/ctypes)."""

    name = "llama_cpp"

    def __init__(self, path: Path, mcfg: dict) -> None:
        self.path = path
        self.mcfg = mcfg
        self.llm = None

    def load(self) -> None:
        if self.loaded:
            return
        try:
            from llama_cpp import Llama
        except ImportError as exc:
            from codar.extras import hint

            raise ModelUnavailable(f"llama-cpp-python não instalado (rode: {hint('llm')})") from exc
        if not self.path.is_file():
            raise ModelUnavailable(f"modelo não encontrado: {self.path} (rode `codar model pull`)")
        m = self.mcfg
        n_batch = int(m.get("n_batch", 128))
        kwargs: dict[str, Any] = dict(
            model_path=str(self.path), n_ctx=int(m.get("n_ctx", 1024)), n_batch=n_batch,
            n_ubatch=int(m.get("n_ubatch") or n_batch), n_threads=int(m.get("n_threads") or min(4, physical_cores())),
            n_threads_batch=int(m.get("n_threads_batch") or min(8, os.cpu_count() or 2)), n_gpu_layers=0,
            use_mmap=bool(m.get("use_mmap", False)), use_mlock=bool(m.get("use_mlock", False)), seed=int(m.get("seed", 42)), verbose=False,
        )
        if int(m.get("prompt_lookup", 0)) > 0:
            from llama_cpp.llama_speculative import LlamaPromptLookupDecoding

            kwargs["draft_model"] = LlamaPromptLookupDecoding(num_pred_tokens=int(m["prompt_lookup"]))
        if m.get("flash_attn"):
            kwargs["flash_attn"] = True
        t0 = time.perf_counter()
        self.llm = Llama(**kwargs)
        self._set_cache()
        self.loaded = True
        log.info("modelo carregado em %.1fs: %s", time.perf_counter() - t0, self.path.name)

    def _set_cache(self) -> None:
        """Cache de estados KV por prefixo de tokens, limitado em memória (restaura o prefixo mais longo já visto)."""
        mb = int(self.mcfg.get("prompt_cache_mb", 64))
        if self.llm is not None and mb > 0:
            self.llm.set_cache(compact_ram_cache(mb << 20))

    def warm(self, prompt: str) -> None:
        """Pre-warming: toca todas as páginas dos pesos e deixa o prefixo do prompt no KV cache."""
        if self.llm is not None:
            self.llm(prompt, max_tokens=1, temperature=0.0)

    def unload(self) -> None:
        if self.llm is not None:
            try:
                self.llm.close()
            except Exception:  # pragma: no cover - close() é best-effort
                pass
            self.llm = None
        self.loaded = False
        gc.collect()
        malloc_trim()

    def reset(self) -> None:
        if self.llm is not None:
            self.llm.reset()
            self._set_cache()  # pressão de memória: descarta os estados guardados

    def tokens(self, text: str) -> int:
        if self.llm is None:
            return super().tokens(text)
        return len(self.llm.tokenize(text.encode("utf-8"), add_bos=False, special=True))

    def complete(self, prompt, *, max_tokens, temperature, stop, schema=None, on_token=None, cancel=None):
        if self.llm is None:
            raise ModelUnavailable("modelo não carregado")
        grammar = None
        if schema is not None:
            from llama_cpp import LlamaGrammar

            grammar = LlamaGrammar.from_json_schema(json.dumps(schema), verbose=False)
        m = self.mcfg
        t0 = time.perf_counter()
        parts: list[str] = []
        finish = "stop"
        stream = self.llm(prompt, max_tokens=max_tokens, temperature=temperature, top_p=float(m.get("top_p", 0.9)),
                          top_k=int(m.get("top_k", 40)), repeat_penalty=float(m.get("repeat_penalty", 1.08)),
                          stop=stop, grammar=grammar, stream=True)
        n = 0
        try:
            for chunk in stream:
                choice = chunk["choices"][0]
                delta = choice.get("text") or ""
                if delta:
                    n += 1
                    parts.append(delta)
                    if on_token:
                        on_token(delta)
                if choice.get("finish_reason"):
                    finish = choice["finish_reason"]
                if cancel is not None and cancel.is_set():
                    finish = "cancel"
                    break
        finally:
            close = getattr(stream, "close", None)
            if close:
                close()
        return GenResult("".join(parts), n, self.tokens(prompt), (time.perf_counter() - t0) * 1000, finish)


class LlamaServerBackend(Backend):
    """llama.cpp como processo filho isolado (`llama-server`). Vazamentos no runtime nativo
    nunca se acumulam no daemon: o supervisor recicla o processo."""

    name = "llama_server"

    def __init__(self, path: Path, mcfg: dict) -> None:
        self.path = path
        self.mcfg = mcfg
        self.proc: subprocess.Popen | None = None
        self.port = 0

    def load(self) -> None:
        if self.loaded:
            return
        binary = shutil.which(self.mcfg.get("server_bin") or "llama-server")
        if not binary:
            raise ModelUnavailable("llama-server não encontrado no PATH (veja [model] server_bin)")
        if not self.path.is_file():
            raise ModelUnavailable(f"modelo não encontrado: {self.path}")
        with socket.socket() as s:
            s.bind(("127.0.0.1", 0))
            self.port = s.getsockname()[1]
        m = self.mcfg
        n_batch = int(m.get("n_batch", 128))
        cmd = [binary, "-m", str(self.path), "-c", str(m.get("n_ctx", 1024)), "-b", str(n_batch),
               "-ub", str(m.get("n_ubatch") or n_batch), "-t", str(m.get("n_threads") or min(4, physical_cores())),
               "-tb", str(m.get("n_threads_batch") or min(8, os.cpu_count() or 2)), "--host", "127.0.0.1",
               "--port", str(self.port), "-np", "1"]
        if m.get("use_mlock"):
            cmd.append("--mlock")
        if not m.get("use_mmap", False):
            cmd.append("--no-mmap")
        self.proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                     stdin=subprocess.DEVNULL)
        self.child_pid = self.proc.pid
        deadline = time.monotonic() + 180
        while time.monotonic() < deadline:
            if self.proc.poll() is not None:
                raise ModelUnavailable(f"llama-server saiu com código {self.proc.returncode}")
            try:
                status, _ = self._request("GET", "/health", None, timeout=2)
                if status == 200:
                    self.loaded = True
                    return
            except OSError:
                pass
            time.sleep(0.25)
        self.unload()
        raise ModelUnavailable("llama-server não ficou pronto em 180s")

    def _request(self, method: str, path: str, body: dict | None, timeout: float = 600):
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=timeout)
        try:
            conn.request(method, path, body=json.dumps(body) if body is not None else None,
                         headers={"Content-Type": "application/json"})
            resp = conn.getresponse()
            return resp.status, resp.read()
        finally:
            conn.close()

    def unload(self) -> None:
        if self.proc is not None:
            self.proc.terminate()
            try:
                self.proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.proc.kill()
                self.proc.wait(timeout=5)
        self.proc = None
        self.child_pid = None
        self.loaded = False

    def tokens(self, text: str) -> int:
        try:
            status, data = self._request("POST", "/tokenize", {"content": text}, timeout=10)
            if status == 200:
                return len(json.loads(data)["tokens"])
        except (OSError, ValueError, KeyError):
            pass
        return super().tokens(text)

    def complete(self, prompt, *, max_tokens, temperature, stop, schema=None, on_token=None, cancel=None):
        m = self.mcfg
        body: dict[str, Any] = {"prompt": prompt, "n_predict": max_tokens, "temperature": temperature,
                                "top_p": float(m.get("top_p", 0.9)), "top_k": int(m.get("top_k", 40)),
                                "repeat_penalty": float(m.get("repeat_penalty", 1.08)), "stop": stop,
                                "cache_prompt": True, "stream": True}
        if schema is not None:
            body["json_schema"] = schema
        t0 = time.perf_counter()
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=600)
        parts: list[str] = []
        finish, n, prompt_tokens = "stop", 0, 0
        try:
            conn.request("POST", "/completion", body=json.dumps(body), headers={"Content-Type": "application/json"})
            resp = conn.getresponse()
            for raw in resp:
                if cancel is not None and cancel.is_set():
                    finish = "cancel"
                    break
                line = raw.decode("utf-8", "replace").strip()
                if not line.startswith("data:"):
                    continue
                event = json.loads(line[5:])
                delta = event.get("content", "")
                if delta:
                    n += 1
                    parts.append(delta)
                    if on_token:
                        on_token(delta)
                if event.get("stop"):
                    finish = "length" if event.get("stop_type") == "limit" else "stop"
                    prompt_tokens = int(event.get("tokens_evaluated", 0))
                    break
        finally:
            conn.close()
        return GenResult("".join(parts), n, prompt_tokens, (time.perf_counter() - t0) * 1000, finish)


def make_backend(mcfg: dict) -> tuple[Backend, ModelCard | None, Path | None, str]:
    card, path = resolve_model(mcfg)
    fmt = card.fmt if card else (guess_fmt(path) if path else "chatml")
    kind = mcfg.get("backend", "auto")
    if kind == "none" or path is None:
        return Backend(), card, path, fmt
    if kind == "llama_server":
        return LlamaServerBackend(path, mcfg), card, path, fmt
    if kind == "auto":
        try:
            import llama_cpp  # noqa: F401
        except ImportError:
            if shutil.which(mcfg.get("server_bin") or "llama-server"):
                return LlamaServerBackend(path, mcfg), card, path, fmt
            return Backend(), card, path, fmt
    return LlamaCppBackend(path, mcfg), card, path, fmt


# =============================================================================== orquestrador

class Stage2:
    def __init__(self, cfg: dict) -> None:
        self.mcfg = dict(cfg["model"])
        self.backend, self.card, self.path, self.fmt = make_backend(self.mcfg)
        self.pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix="codar-slm")
        self.last_used = time.monotonic()
        self.load_error: str | None = None
        self.generations = 0
        self.pending = 0
        self._state_lock = threading.Lock()
        self.warm_langs: list[str] = [self.mcfg.get("warm_lang") or "python"]
        self._warm_queue: deque[str] = deque()

    # ------------------------------------------------------------------ ciclo de vida
    @property
    def name(self) -> str:
        return self.card.key if self.card else (self.path.name if self.path else "nenhum")

    def configured(self) -> bool:
        return self.path is not None and type(self.backend) is not Backend

    def submit(self, fn: Callable[..., Any], *args: Any, **kwargs: Any) -> Future:
        self.last_used = time.monotonic()  # trabalho na fila conta como uso (o watchdog não descarrega)
        self.pending += 1
        fut = self.pool.submit(fn, *args, **kwargs)
        fut.add_done_callback(self._done)
        return fut

    def _done(self, _fut: Future) -> None:
        self.pending -= 1
        self.last_used = time.monotonic()

    def ensure_loaded(self) -> None:
        """Roda na thread do modelo."""
        self.last_used = time.monotonic()
        if self.backend.loaded:
            return
        if not self.configured():
            raise ModelUnavailable(self.load_error or "modelo não configurado (rode `codar model pull`)")
        try:
            self.backend.load()
            if isinstance(self.backend, LlamaCppBackend):
                # a primeira linguagem aquece já; as outras vão para o fim da fila, sem atrasar pedidos
                first, *rest = self.warm_langs or ["python"]
                self._warm(first)
                self._warm_queue = deque(rest)
                if rest:
                    self.submit(self._warm_next)
            self.load_error = None
        except ModelUnavailable as exc:
            self.load_error = str(exc)
            raise
        finally:
            gc.collect()

    def _warm(self, lang_id: str) -> None:
        """Gera 1 token com o prompt literal da linguagem: o prefixo (sistema + exemplos) fica no cache KV e o
        primeiro pedido real nessa linguagem não paga ~12 s de processamento do prompt."""
        from codar import langs
        from codar.engine.models import build_literal_prompt
        from codar.engine.router import literal_examples

        lang = langs.try_resolve(lang_id)
        if lang is not None and self.backend.loaded:
            self.backend.warm(build_literal_prompt(self.fmt, lang.name, lang.fence, "x é igual a 10",
                                                   list(literal_examples(lang.id))))

    def _warm_next(self) -> None:
        """Roda na thread do modelo. Se há pedido do usuário na fila, cede a vez e volta para o fim dela."""
        if not self._warm_queue or not self.backend.loaded:
            return
        if self.pending > 1:
            self.submit(self._warm_next)
            return
        self._warm(self._warm_queue.popleft())
        if self._warm_queue:
            self.submit(self._warm_next)

    def preload(self) -> Future:
        return self.submit(self.ensure_loaded)

    def unload(self) -> Future:
        return self.submit(self.backend.unload)

    def shrink(self) -> Future:
        """Pressão de memória moderada: descarta KV/estado e devolve heap ao SO, mantendo os pesos."""
        def _do() -> None:
            self.backend.reset()
            gc.collect()
            malloc_trim()
        return self.submit(_do)

    def idle_seconds(self) -> float:
        return time.monotonic() - self.last_used

    def info(self) -> dict:
        return {"name": self.name, "backend": self.backend.name, "loaded": self.backend.loaded,
                "path": str(self.path) if self.path else None, "format": self.fmt, "error": self.load_error,
                "generations": self.generations, "idle_s": round(self.idle_seconds(), 1),
                "child_pid": self.backend.child_pid}

    def shutdown(self) -> None:
        try:
            self.pool.submit(self.backend.unload).result(timeout=30)
        except Exception:  # pragma: no cover
            pass
        self.pool.shutdown(wait=False, cancel_futures=True)

    # ------------------------------------------------------------------ chamadas (thread do modelo)
    def _budget(self, prompt: str, wanted: int) -> int:
        n_ctx = int(self.mcfg.get("n_ctx", 1024))
        return max(0, min(wanted, n_ctx - self.backend.tokens(prompt) - 8))

    def generate(self, prompt_builder: Callable[[int], str], *, on_token=None, cancel=None,
                 max_tokens: int | None = None, stop: list[str] | None = None,
                 required_output: str | None = None) -> GenResult:
        """prompt_builder(nível) devolve prompts progressivamente menores (0 = completo) até caber no n_ctx."""
        self.ensure_loaded()
        self.last_used = time.monotonic()
        wanted = min(int(self.mcfg.get("max_tokens", 384)), max_tokens or 10**9)
        minimum = 32
        if required_output is not None:
            minimum = max(64, self.backend.tokens(required_output) + 32)
            if minimum > wanted:
                raise ModelUnavailable(f"substituição precisa de cerca de {minimum} tokens de saída; model.max_tokens="
                                       f"{wanted}. Selecione uma função menor ou use `codar edit` para dividir por funções")
        prompt, budget = "", 0
        for level in range(4):
            prompt = prompt_builder(level)
            budget = self._budget(prompt, wanted)
            if budget >= max(minimum, min(160, wanted)):
                break
        if budget < minimum:
            raise ModelUnavailable(f"prompt deixa {budget} tokens de saída, mas são necessários {minimum}; "
                                   "selecione um trecho menor ou aumente [model] n_ctx. O original foi preservado")
        res = self.backend.complete(prompt, max_tokens=budget, temperature=float(self.mcfg.get("temperature", 0.15)),
                                    stop=stop or STOP, on_token=on_token, cancel=cancel)
        self.generations += 1
        self.last_used = time.monotonic()
        if res.finish == "cancel":
            raise Cancelled("geração cancelada")
        return res

    def plan(self, prompt: str, schema: dict, cancel=None) -> tuple[dict, GenResult]:
        self.ensure_loaded()
        self.last_used = time.monotonic()
        res = self.backend.complete(prompt, max_tokens=160, temperature=0.0, stop=["<|im_end|>", "<|endoftext|>"],
                                    schema=schema, cancel=cancel)
        self.last_used = time.monotonic()
        try:
            return json.loads(res.text), res
        except ValueError:
            return {"steps": []}, res


def plan_prompt(fmt: str, intent: str, lang_name: str, tools: list[dict]) -> str:
    lines = []
    for i, t in enumerate(tools, 1):
        params = ", ".join(t["params"]) or "nenhum"
        lines.append(f"{i}. {t['id']} — {t['title']} (params: {params})")
    user = (f"Task: {intent}\nLanguage: {lang_name}\nAvailable patterns:\n" + "\n".join(lines) +
            "\n\nPick the patterns that implement the task, in execution order, and fill params ONLY with values "
            'written in the task. If no pattern fits the task, answer {"steps": []}.')
    prompt = ("<|im_start|>system\nYou route programming tasks to reusable, verified code patterns. "
              "Answer with JSON only.<|im_end|>\n"
              f"<|im_start|>user\n{user}<|im_end|>\n<|im_start|>assistant\n")
    if fmt == "chatml-nothink":
        prompt += "<think>\n\n</think>\n\n"
    return prompt


def plan_schema(tools: list[dict]) -> dict:
    params = sorted({p for t in tools for p in t["params"]})
    args: dict[str, Any] = {"type": "object", "additionalProperties": False,
                            "properties": {p: {"type": "string", "maxLength": 80} for p in params}}
    return {
        "type": "object", "additionalProperties": False, "required": ["steps"],
        "properties": {"steps": {"type": "array", "maxItems": 3, "items": {
            "type": "object", "additionalProperties": False, "required": ["pattern"],
            "properties": {"pattern": {"type": "string", "enum": [t["id"] for t in tools]}, "args": args}}}},
    }
