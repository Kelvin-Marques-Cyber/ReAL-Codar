"""Mensagens JSON com cabeçalho Content-Length sobre stdin/stdout, o transporte do LSP e do DAP.

`Processo` inicia a ferramenta sem shell, lê stderr continuamente (um servidor que escreve muito em stderr não trava
esperando quem leia) e guarda as últimas linhas para explicar uma falha.
"""

from __future__ import annotations

import asyncio
import collections
import json
import os
import signal

MAXIMO = 64 * 1024 * 1024  # uma mensagem maior que isso é tratada como protocolo quebrado


class ErroProtocolo(Exception):
    pass


def quadro(mensagem: dict) -> bytes:
    corpo = json.dumps(mensagem, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    return b"Content-Length: %d\r\n\r\n" % len(corpo) + corpo


async def ler(leitor: asyncio.StreamReader) -> dict | None:
    """A próxima mensagem, ou None no fim do fluxo."""
    tamanho = None
    while True:
        linha = await leitor.readline()
        if not linha:
            return None
        if linha in (b"\r\n", b"\n"):
            if tamanho is None:
                continue  # linhas vazias entre mensagens
            break
        nome, _, valor = linha.decode("ascii", "replace").partition(":")
        if nome.strip().lower() == "content-length":
            try:
                tamanho = int(valor.strip())
            except ValueError as exc:
                raise ErroProtocolo(f"Content-Length inválido: {valor.strip()!r}") from exc
    if not 0 <= tamanho <= MAXIMO:
        raise ErroProtocolo(f"mensagem de {tamanho} bytes recusada")
    try:
        corpo = await leitor.readexactly(tamanho)
    except asyncio.IncompleteReadError:
        return None
    try:
        mensagem = json.loads(corpo)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ErroProtocolo(f"JSON inválido: {exc}") from exc
    if not isinstance(mensagem, dict):
        raise ErroProtocolo("a mensagem não é um objeto JSON")
    return mensagem


class Processo:
    """Ferramenta externa com stdin/stdout em quadros e stderr guardado."""

    def __init__(self, comando: list[str], cwd: str, env: dict[str, str] | None = None) -> None:
        self.comando = list(comando)
        self.cwd = cwd
        self.env = env
        self.stderr: collections.deque[str] = collections.deque(maxlen=200)
        self._proc: asyncio.subprocess.Process | None = None
        self._dreno: asyncio.Task | None = None
        self._escrita = asyncio.Lock()

    async def iniciar(self) -> None:
        extra = {"start_new_session": True} if os.name != "nt" else {}
        self._proc = await asyncio.create_subprocess_exec(
            *self.comando, cwd=self.cwd, env=self.env, stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE, limit=1024 * 1024, **extra)
        self._dreno = asyncio.create_task(self._drenar())

    async def _drenar(self) -> None:
        assert self._proc and self._proc.stderr
        while linha := await self._proc.stderr.readline():
            self.stderr.append(linha.decode("utf-8", "replace").rstrip())

    @property
    def vivo(self) -> bool:
        return self._proc is not None and self._proc.returncode is None

    @property
    def pid(self) -> int | None:
        return self._proc.pid if self._proc else None

    async def enviar(self, mensagem: dict) -> None:
        if not self.vivo or self._proc.stdin is None:
            raise ConnectionError("o processo terminou")
        async with self._escrita:
            self._proc.stdin.write(quadro(mensagem))
            await self._proc.stdin.drain()

    async def receber(self) -> dict | None:
        assert self._proc and self._proc.stdout
        return await ler(self._proc.stdout)

    def ultimas_linhas(self, n: int = 8) -> str:
        return "\n".join(list(self.stderr)[-n:])

    async def encerrar(self, espera: float = 2.0) -> None:
        """Fecha stdin, espera um pouco e então termina o grupo do processo."""
        proc = self._proc
        if proc is None:
            return
        if proc.returncode is None and proc.stdin and not proc.stdin.is_closing():
            proc.stdin.close()
        try:
            await asyncio.wait_for(proc.wait(), espera)
        except asyncio.TimeoutError:
            self._sinal(signal.SIGTERM)
            try:
                await asyncio.wait_for(proc.wait(), espera)
            except asyncio.TimeoutError:
                self._sinal(signal.SIGKILL if os.name != "nt" else signal.SIGTERM)
                await proc.wait()
        if self._dreno:  # o resto do stderr explica por que o processo terminou
            try:
                await asyncio.wait_for(self._dreno, 1)
            except (asyncio.TimeoutError, asyncio.CancelledError):
                self._dreno.cancel()

    def terminar_agora(self) -> None:
        """Sem esperar: fecha stdin e manda SIGTERM ao grupo (usado quando o Studio está saindo)."""
        proc = self._proc
        if proc is None or proc.returncode is not None:
            return
        if proc.stdin and not proc.stdin.is_closing():
            proc.stdin.close()
        self._sinal(signal.SIGTERM)

    def _sinal(self, sinal) -> None:
        proc = self._proc
        if proc is None or proc.returncode is not None:
            return
        try:
            if os.name != "nt":
                os.killpg(proc.pid, sinal)
            else:
                proc.terminate()
        except (ProcessLookupError, PermissionError):
            pass
