"""Cliente DAP (Debug Adapter Protocol): inicia o adaptador, envia breakpoints e controla a execução.

Adaptadores conhecidos: debugpy para Python e o modo DAP do GDB 14 ou mais novo para C, C++ e Rust (o arquivo é
compilado com informações de depuração antes). O programa só roda quando o usuário pede a depuração. Linhas ficam a
partir de 0, como no editor; a conversão para o DAP (a partir de 1) acontece aqui.
"""

from __future__ import annotations

import asyncio
import collections
import itertools
import os
import re
import shutil
import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

from codar.ide.quadros import ErroProtocolo, Processo


class ErroDAP(Exception):
    pass


@dataclass(frozen=True)
class Quadro:
    id: int
    nome: str
    caminho: Path | None
    linha: int  # a partir de 0
    coluna: int


@dataclass(frozen=True)
class Escopo:
    nome: str
    referencia: int
    caro: bool = False


@dataclass(frozen=True)
class Variavel:
    nome: str
    valor: str
    tipo: str = ""
    referencia: int = 0  # > 0: tem filhos (objetos, listas, structs)


class SessaoDAP:
    """Uma depuração: um adaptador, um programa."""

    def __init__(self, adaptador: list[str], cwd: str | Path, env: dict[str, str] | None = None, *,
                 ao_evento=None, tempo: float = 20.0) -> None:
        self.adaptador = list(adaptador)
        self.processo = Processo(self.adaptador, str(cwd), env)
        self.ao_evento = ao_evento  # (evento, corpo): stopped, continued, output, exited, terminated, breakpoint
        self.tempo = tempo
        self.capacidades: dict = {}
        self.parado_em: int | None = None  # thread parada
        self.motivo_parada = ""
        self.codigo_saida: int | None = None
        self.terminou = False
        self.saida: collections.deque[tuple[str, str]] = collections.deque(maxlen=5000)
        self.avisos: list[str] = []
        self._seq = itertools.count(1)
        self._pendentes: dict[int, asyncio.Future] = {}
        self._pronto = asyncio.Event()
        self._leitura: asyncio.Task | None = None
        self._configurando = True  # antes do launch, a saída é do próprio depurador, não do programa

    # -------------------------------------------------------------- ciclo de vida
    async def iniciar(self, adapter_id: str, lancamento: dict, breakpoints: dict[Path, list[int]] | None = None,
                      configurar_antes: bool = False) -> None:
        """configurar_antes: o adaptador anuncia "initialized" logo após o initialize e inicia o programa já no
        launch (GDB 15); os breakpoints vão antes do launch, ou um programa rápido terminaria sem parar neles."""
        try:
            await self.processo.iniciar()
        except OSError as exc:
            raise ErroDAP(f"{Path(self.adaptador[0]).name} não pôde ser iniciado: {exc}") from exc
        self._leitura = asyncio.create_task(self._ler())
        try:
            self.capacidades = await self.pedir("initialize", {
                "clientID": "codar", "clientName": "CODAR Studio", "adapterID": adapter_id, "locale": "pt-BR",
                "pathFormat": "path", "linesStartAt1": True, "columnsStartAt1": True, "supportsVariableType": True,
                "supportsRunInTerminalRequest": False}, tempo=30)
        except (ErroDAP, ConnectionError, asyncio.TimeoutError) as exc:
            await self.processo.encerrar(.5)
            raise ErroDAP(f"o adaptador não respondeu: {exc}\n{self.processo.ultimas_linhas()}".strip()) from exc
        if configurar_antes:
            try:
                await asyncio.wait_for(self._pronto.wait(), 15)
            except asyncio.TimeoutError:
                await self.encerrar()
                raise ErroDAP("o depurador não ficou pronto para receber breakpoints") from None
            for caminho, linhas in (breakpoints or {}).items():
                await self.definir_breakpoints(caminho, linhas)
            try:
                await self.pedir("launch", lancamento, tempo=60)
            except (ErroDAP, ConnectionError, asyncio.TimeoutError) as exc:
                await self.encerrar()
                raise ErroDAP(f"o programa não iniciou: {exc}") from exc
            self._configurando = False
            await self._configuracao_feita()
            return
        # O debugpy só responde ao launch depois do configurationDone e anuncia "initialized" depois de recebê-lo.
        launch = asyncio.create_task(self.pedir("launch", lancamento, tempo=60))
        pronto = asyncio.create_task(self._pronto.wait())
        await asyncio.wait({launch, pronto}, timeout=30, return_when=asyncio.FIRST_COMPLETED)
        if launch.done() and launch.exception() is not None:
            pronto.cancel()
            await self.encerrar()
            raise ErroDAP(f"o programa não iniciou: {launch.exception()}")
        if not self._pronto.is_set():
            pronto.cancel()
            launch.cancel()
            await self.encerrar()
            raise ErroDAP("o adaptador não ficou pronto para receber breakpoints")
        for caminho, linhas in (breakpoints or {}).items():
            await self.definir_breakpoints(caminho, linhas)
        self._configurando = False
        await self._configuracao_feita()
        try:
            await launch
        except (ErroDAP, ConnectionError, asyncio.TimeoutError) as exc:
            await self.encerrar()
            raise ErroDAP(f"o programa não iniciou: {exc}") from exc

    async def _configuracao_feita(self) -> None:
        if self.capacidades.get("supportsConfigurationDoneRequest"):
            try:
                await self.pedir("configurationDone", {})
            except ErroDAP as exc:  # adaptador que já iniciou o programa responde "notStopped"; segue mesmo assim
                self.avisos.append(f"configurationDone: {exc}")

    async def encerrar(self) -> None:
        if self.processo.vivo:
            try:
                if self.capacidades.get("supportsTerminateRequest") and not self.terminou:
                    await self.pedir("terminate", {}, tempo=3)
            except (ErroDAP, ConnectionError, asyncio.TimeoutError):
                pass
            try:
                await self.pedir("disconnect", {"terminateDebuggee": True}, tempo=3)
            except (ErroDAP, ConnectionError, asyncio.TimeoutError):
                pass
        await self.processo.encerrar()
        if self._leitura:
            self._leitura.cancel()
        self.terminou = True
        self.parado_em = None

    # -------------------------------------------------------------- mensagens
    async def pedir(self, comando: str, argumentos: dict | None = None, tempo: float | None = None) -> dict:
        if not self.processo.vivo:
            raise ConnectionError("o depurador terminou")
        seq = next(self._seq)
        futuro = asyncio.get_running_loop().create_future()
        self._pendentes[seq] = futuro
        try:
            await self.processo.enviar({"seq": seq, "type": "request", "command": comando, "arguments": argumentos or {}})
            resposta = await asyncio.wait_for(futuro, tempo or self.tempo)
        finally:
            self._pendentes.pop(seq, None)
        if not resposta.get("success"):
            corpo = resposta.get("body") or {}
            erro = (corpo.get("error") or {}).get("format") if isinstance(corpo, dict) else None
            raise ErroDAP(erro or resposta.get("message") or f"{comando} falhou")
        return resposta.get("body") or {}

    async def _ler(self) -> None:
        try:
            while (mensagem := await self.processo.receber()) is not None:
                tipo = mensagem.get("type")
                if tipo == "response":
                    futuro = self._pendentes.get(mensagem.get("request_seq"))
                    if futuro and not futuro.done():
                        futuro.set_result(mensagem)
                elif tipo == "event":
                    self._evento(mensagem.get("event", ""), mensagem.get("body") or {})
                elif tipo == "request":  # runInTerminal e afins: o Studio usa o console interno
                    await self.processo.enviar({"seq": next(self._seq), "type": "response",
                                                "request_seq": mensagem.get("seq"), "command": mensagem.get("command"),
                                                "success": False, "message": "não suportado pelo CODAR"})
        except (ErroProtocolo, ConnectionError):
            pass
        finally:
            for futuro in self._pendentes.values():
                if not futuro.done():
                    futuro.set_exception(ConnectionError("o depurador terminou"))
            if not self.terminou:
                self.terminou = True
                self.parado_em = None
                self._avisar("terminated", {})

    def _evento(self, nome: str, corpo: dict) -> None:
        if nome == "initialized":
            self._pronto.set()
            return
        if nome == "output":
            if corpo.get("category") == "telemetry":
                return
            if self._configurando:  # "No source file named…" do GDB enquanto o programa ainda não carregou
                self.avisos.append(str(corpo.get("output", "")).strip())
                return
            self.saida.append((corpo.get("category") or "console", str(corpo.get("output", ""))))
        elif nome == "stopped":
            self.parado_em = corpo.get("threadId")
            self.motivo_parada = str(corpo.get("reason") or "")
        elif nome == "continued":
            self.parado_em = None
        elif nome == "exited":
            self.codigo_saida = corpo.get("exitCode")
        elif nome == "terminated":
            if self.terminou:
                return
            self.terminou = True
            self.parado_em = None
        self._avisar(nome, corpo)

    def _avisar(self, nome: str, corpo: dict) -> None:
        if self.ao_evento is not None:
            self.ao_evento(nome, corpo)

    # -------------------------------------------------------------- comandos
    async def definir_breakpoints(self, caminho: Path, linhas: list[int]) -> list[tuple[int, bool]]:
        corpo = await self.pedir("setBreakpoints", {"source": {"path": str(Path(caminho).resolve())},
                                                    "breakpoints": [{"line": n + 1} for n in sorted(set(linhas))]})
        return [(int(b.get("line", 1)) - 1, bool(b.get("verified"))) for b in corpo.get("breakpoints", [])]

    async def _thread(self) -> int:
        if self.parado_em is not None:
            return self.parado_em
        threads = (await self.pedir("threads")).get("threads") or []
        if not threads:
            raise ErroDAP("nenhuma thread em execução")
        return threads[0]["id"]

    async def continuar(self) -> None:
        await self.pedir("continue", {"threadId": await self._thread()})
        self.parado_em = None

    async def proximo(self) -> None:
        await self.pedir("next", {"threadId": await self._thread()})

    async def entrar(self) -> None:
        await self.pedir("stepIn", {"threadId": await self._thread()})

    async def sair(self) -> None:
        await self.pedir("stepOut", {"threadId": await self._thread()})

    async def pausar(self) -> None:
        await self.pedir("pause", {"threadId": await self._thread()})

    async def pilha(self, limite: int = 50) -> list[Quadro]:
        corpo = await self.pedir("stackTrace", {"threadId": await self._thread(), "startFrame": 0, "levels": limite})
        quadros = []
        for q in corpo.get("stackFrames", []):
            caminho = (q.get("source") or {}).get("path")
            quadros.append(Quadro(int(q["id"]), str(q.get("name", "?")), Path(caminho) if caminho else None,
                                  max(0, int(q.get("line") or 1) - 1), max(0, int(q.get("column") or 1) - 1)))
        return quadros

    async def escopos(self, quadro: int) -> list[Escopo]:
        corpo = await self.pedir("scopes", {"frameId": quadro})
        return [Escopo(str(e.get("name", "")), int(e.get("variablesReference") or 0), bool(e.get("expensive")))
                for e in corpo.get("scopes", [])]

    async def variaveis(self, referencia: int, limite: int = 300) -> list[Variavel]:
        corpo = await self.pedir("variables", {"variablesReference": referencia})
        return [Variavel(str(v.get("name", "")), str(v.get("value", "")), str(v.get("type") or ""),
                         int(v.get("variablesReference") or 0)) for v in corpo.get("variables", [])[:limite]]

    async def avaliar(self, expressao: str, quadro: int | None = None) -> str:
        argumentos = {"expression": expressao, "context": "repl"}
        if quadro is not None:
            argumentos["frameId"] = quadro
        corpo = await self.pedir("evaluate", argumentos)
        return str(corpo.get("result", ""))


# ------------------------------------------------------------------------------------------------ planos
@dataclass
class Plano:
    """Como depurar um arquivo: compilar (se preciso), qual adaptador e os argumentos do launch."""
    adapter_id: str
    adaptador: list[str]
    lancamento: dict
    compilar: list[str] | None = None
    falta: str = ""  # por que não dá para depurar (ferramenta ausente)
    configurar_antes: bool = False  # breakpoints antes do launch (GDB)
    instalar: list[str] = field(default_factory=list)  # comando sugerido para preparar o ambiente


_COMPILADORES = {"c": (("cc", "gcc", "clang"), ["-g", "-O0", "-Wall"]),
                 "cpp": (("c++", "g++", "clang++"), ["-g", "-O0", "-Wall"]),
                 "rust": (("rustc",), ["-g", "-C", "opt-level=0"])}


def versao_gdb(path: str | None = None) -> int | None:
    gdb = shutil.which("gdb", path=path)
    if not gdb:
        return None
    try:
        saida = subprocess.run([gdb, "--version"], capture_output=True, text=True, timeout=10).stdout
    except (OSError, subprocess.SubprocessError):
        return None
    achado = re.search(r"\b(\d+)\.\d+", saida.splitlines()[0] if saida else "")
    return int(achado[1]) if achado else None


def plano(lang: str, arquivo: Path, raiz: Path, *, python: str, env: dict[str, str] | None = None,
          pasta_build: Path | None = None) -> Plano | None:
    """None: a linguagem não tem depurador integrado."""
    caminho = (env or {}).get("PATH")
    arquivo, raiz = Path(arquivo).resolve(), Path(raiz).resolve()
    if lang == "python":
        from codar.advisor.pacotes import modulos_ausentes

        p = Plano("python", [python, "-m", "debugpy.adapter"], {
            "type": "python", "request": "launch", "name": "codar", "program": str(arquivo), "cwd": str(raiz),
            "console": "internalConsole", "justMyCode": True, "python": [python], "redirectOutput": True})
        if modulos_ausentes(python, ["debugpy"]):
            p.falta = "o debugpy não está instalado no Python do projeto"
            p.instalar = [python, "-m", "pip", "install", "debugpy"]
        return p
    if lang in _COMPILADORES:
        nomes, opcoes = _COMPILADORES[lang]
        compilador = next((shutil.which(n, path=caminho) for n in nomes if shutil.which(n, path=caminho)), None)
        pasta = Path(pasta_build or tempfile.mkdtemp(prefix="codar-depurar-"))
        programa = pasta / (arquivo.stem + ".exe" if os.name == "nt" else arquivo.stem)
        p = Plano("gdb", ["gdb", "--interpreter=dap", "-q"], {"program": str(programa), "cwd": str(raiz), "args": []},
                  compilar=[compilador or nomes[0], *opcoes, str(arquivo), "-o", str(programa)], configurar_antes=True)
        versao = versao_gdb(caminho)
        if compilador is None:
            p.falta = f"compilador ausente ({', '.join(nomes)})"
        elif versao is None:
            p.falta = "GDB ausente (instale o gdb 14 ou mais novo)"
        elif versao < 14:
            p.falta = f"GDB {versao} não tem o modo DAP; instale o gdb 14 ou mais novo"
        return p
    return None
