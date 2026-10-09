"""Terminal integrado do Studio.

Os comandos rodam com o ambiente do seu shell (o PATH que o .bashrc/.zshrc monta: bun, nvm, pyenv, cargo…), `cd`
vale para os próximos comandos, ↑/↓ percorrem o histórico e os scripts do projeto aparecem como sugestão
(`bun run dev`). Vários terminais rodam ao mesmo tempo: com o `bun run dev` ocupando um, Ctrl+T abre outro.
Programas que leem do teclado (input()) recebem o que se digita, e Ctrl+C interrompe. Para o que precisa de um
terminal completo (menus com setas, vim, aliases), F12 abre o seu shell de verdade e `exit` volta ao Studio.
"""

from __future__ import annotations

import codecs
import json
import os
import re
import select
import shlex
import shutil
import signal
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path

from rich.text import Text
from textual import on, work
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.suggester import Suggester
from textual.widgets import Input, RichLog

from codar.studio import estado
from codar.studio.widgets import Botao, C

TERM_IDLE = "$ comando (Enter executa · ↑ histórico · → completa · Ctrl+T outro terminal · F12 seu shell)"
TERM_RUNNING = "entrada do programa (Enter envia · Ctrl+C interrompe · Ctrl+T abre outro terminal)"
_URL = re.compile(r"https?://(?:localhost|127\.0\.0\.1|0\.0\.0\.0|\[::1?\]|[\w.-]+):(\d{2,5})\b[^\s'\"]*")
_CD = re.compile(r"^cd(?:\s+(.*))?$")
_ANSI = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]")
SAIDA_GUARDADA = 400  # linhas por terminal (para explicar erros)
HISTORICO = 300
# sem paginador: `git log` e `man` não ficam parados esperando uma tecla que o painel não manda
SEM_PAGINADOR = {"PAGER": "cat", "GIT_PAGER": "cat", "MANPAGER": "cat", "SYSTEMD_PAGER": "", "BAT_PAGER": "cat"}


def ambiente_do_shell(timeout: float = 8.0) -> dict[str, str]:
    """As variáveis do seu shell interativo: roda o shell uma vez e lê o `env`. O que o .bashrc imprimir (fastfetch,
    avisos) é descartado. Sem terminal de controle (start_new_session), o shell não mexe na tela do Studio."""
    base = dict(os.environ)
    shell = os.environ.get("SHELL", "")
    if os.name != "posix" or Path(shell).name not in ("bash", "zsh", "fish", "ksh", "mksh"):
        return base
    marca = "__CODAR_AMBIENTE__"
    try:
        r = subprocess.run([shell, "-i", "-c", f"printf '%s' {marca}; env -0"], capture_output=True, timeout=timeout,
                           stdin=subprocess.DEVNULL, env={**base, "CODAR_STUDIO": "1"}, start_new_session=True)
    except (OSError, subprocess.TimeoutExpired):
        return base
    i = r.stdout.rfind(marca.encode())
    if i < 0:
        return base
    ambiente = {}
    for par in r.stdout[i + len(marca):].split(b"\0"):
        chave, igual, valor = par.partition(b"=")
        if igual and chave:
            ambiente[chave.decode(errors="replace")] = valor.decode(errors="replace")
    for chave in ("PS1", "PROMPT_COMMAND", "SHLVL", "_", "OLDPWD", "PWD", "COLUMNS", "LINES"):
        ambiente.pop(chave, None)
    return ambiente if "PATH" in ambiente else base


def gerenciador_js(raiz: Path, caminho: str) -> str:
    """bun, pnpm, yarn ou npm: pelo lockfile do projeto; sem lockfile, o bun se estiver instalado."""
    for trava, pm in (("bun.lock", "bun"), ("bun.lockb", "bun"), ("pnpm-lock.yaml", "pnpm"), ("yarn.lock", "yarn"),
                      ("package-lock.json", "npm")):
        if (raiz / trava).exists():
            return pm
    return "bun" if shutil.which("bun", path=caminho) else "npm"


def comandos_do_projeto(raiz: Path, caminho: str = "") -> list[str]:
    """Comandos que fazem sentido aqui: scripts do package.json, alvos do Makefile, testes."""
    out: list[str] = []
    pacote = raiz / "package.json"
    if pacote.is_file():
        pm = gerenciador_js(raiz, caminho or os.environ.get("PATH", ""))
        try:
            scripts = json.loads(pacote.read_text(encoding="utf-8")).get("scripts", {}) or {}
        except (OSError, ValueError):
            scripts = {}
        ordem = {"dev": 0, "start": 1, "build": 2, "test": 3}
        prioridade = sorted(scripts, key=lambda s: (ordem.get(s, 9), s))
        out += [f"{pm} run {s}" for s in prioridade]
        if not (raiz / "node_modules").exists():
            out.insert(0, f"{pm} install")
    makefile = raiz / "Makefile"
    if makefile.is_file():
        try:
            alvos = re.findall(r"^([A-Za-z][\w-]*):", makefile.read_text(encoding="utf-8", errors="ignore"), re.M)
        except OSError:
            alvos = []
        out += [f"make {a}" for a in dict.fromkeys(alvos)]
    if (raiz / "pyproject.toml").exists() or (raiz / "tests").is_dir():
        out.append("python -m pytest")
    if (raiz / "requirements.txt").exists():
        out.append("pip install -r requirements.txt")
    if (raiz / "main.py").exists():
        out.append("python main.py")
    if (raiz / ".git").exists():
        out += ["git status", "git add .", 'git commit -m ""', "git log --oneline -10"]
    return out


@dataclass
class Sessao:
    """Um terminal: o processo, a pasta atual (cd), a saída recente e o servidor que ele subiu."""

    numero: int
    log: RichLog
    cwd: Path
    proc: subprocess.Popen | None = None
    fd: int | None = None  # lado mestre do pseudoterminal
    esperando: str = ""  # pergunta de um programa esperando entrada (texto sem quebra de linha)
    comando: str = ""
    codigo: int | None = None  # código de saída do último comando
    saida: list[str] = field(default_factory=list)
    url: str | None = None

    def rodando(self) -> bool:
        return self.proc is not None and self.proc.poll() is None

    def titulo(self) -> str:
        nome = self.comando.split(" ", 3)
        curto = " ".join(nome[:3])[:18] if self.comando else "terminal"
        estado_ = ("●", C["mint"]) if self.rodando() else ("○", C["dim"]) if self.codigo is None else \
            ("✓", C["green"]) if self.codigo == 0 else ("✗", C["error"])
        return f"[{C['text']}]{self.numero} {curto}[/] [{estado_[1]}]{estado_[0]}[/]"


class TerminalInput(Input):
    """Campo do terminal: ↑/↓ histórico, Tab/→ aceita a sugestão, e com um programa rodando Ctrl+C interrompe (em
    vez de copiar)."""

    BINDINGS = [Binding("ctrl+c", "interromper", "Interromper", show=False, priority=True),
                Binding("up", "historico(-1)", "Anterior", show=False),
                Binding("down", "historico(1)", "Próximo", show=False),
                Binding("tab", "completar", "Completar", show=False)]

    @property
    def painel(self) -> TerminalPainel:
        return next(a for a in self.ancestors if isinstance(a, TerminalPainel))

    def action_interromper(self) -> None:
        if self.painel.sessao.rodando():
            self.painel.interromper()
        else:
            self.action_copy()

    def action_historico(self, passo: int) -> None:
        painel = self.painel
        if painel.sessao.rodando() or not painel.historico:
            return
        pos = len(painel.historico) if painel.pos_historico is None else painel.pos_historico
        pos = max(0, min(len(painel.historico), pos + passo))
        painel.pos_historico = pos
        self.value = painel.historico[pos] if pos < len(painel.historico) else ""
        self.cursor_position = len(self.value)

    def action_completar(self) -> None:
        if self._suggestion and self._suggestion != self.value:
            self.value = self._suggestion
            self.cursor_position = len(self.value)
        else:
            self.screen.focus_next()


class SugestoesTerminal(Suggester):
    """Completa com o histórico (o mais recente primeiro) e com os comandos do projeto."""

    def __init__(self, painel: TerminalPainel) -> None:
        super().__init__(use_cache=False, case_sensitive=True)
        self.painel = painel

    async def get_suggestion(self, valor: str) -> str | None:
        if not valor.strip() or self.painel.sessao.rodando():
            return None
        candidatos = [*reversed(self.painel.historico),
                      *comandos_do_projeto(self.painel.sessao.cwd, self.painel.ambiente.get("PATH", ""))]
        return next((c for c in candidatos if c.startswith(valor) and c != valor), None)


class TerminalPainel(Vertical):
    """Painel TERMINAL: barra de terminais, a saída do terminal ativo e o campo de comando."""

    def __init__(self, raiz: Path, **kwargs) -> None:
        super().__init__(**kwargs)
        self.raiz = raiz
        self.sessoes: list[Sessao] = []
        self.sessao: Sessao = None  # type: ignore[assignment]  # criada no on_mount
        self.ambiente: dict[str, str] = dict(os.environ)
        self.historico: list[str] = list(estado.ler().get("historico_terminal", []))[-HISTORICO:]
        self.pos_historico: int | None = None

    def compose(self):
        yield Horizontal(id="sessoes")
        yield Vertical(id="term-logs")
        yield TerminalInput(placeholder=TERM_IDLE, id="term-input", suggester=SugestoesTerminal(self))

    async def on_mount(self) -> None:
        await self.nova_sessao(focar=False)
        if os.environ.get("CODAR_SHELL_ENV", "1") != "0":
            self.carregar_ambiente()

    @work(thread=True, exclusive=True, group="ambiente")
    def carregar_ambiente(self) -> None:
        ambiente = ambiente_do_shell()
        self.app.call_from_thread(setattr, self, "ambiente", ambiente)

    # ------------------------------------------------------------------ terminais
    async def nova_sessao(self, focar: bool = True) -> Sessao:
        numero = max((s.numero for s in self.sessoes), default=0) + 1
        log = RichLog(id="term-log" if numero == 1 else f"term-log-{numero}", markup=False, wrap=False, max_lines=3000,
                      classes="term-log")
        await self.query_one("#term-logs").mount(log)
        sessao = Sessao(numero, log, cwd=self.sessao.cwd if self.sessao else self.raiz)
        self.sessoes.append(sessao)
        self.ativar(sessao)
        if numero > 1:
            log.write(Text(f"terminal {numero} · em {self._rel(sessao.cwd)} · Ctrl+PgUp/PgDn troca de terminal",
                           style=C["dim"]))
        if focar:
            self.query_one(TerminalInput).focus()
        return sessao

    def ativar(self, sessao: Sessao) -> None:
        self.sessao = sessao
        for s in self.sessoes:
            s.log.display = s is sessao
        self.atualizar_barra()
        self.mostrar_espera(sessao.esperando)

    def trocar(self, passo: int) -> None:
        if len(self.sessoes) > 1:
            i = self.sessoes.index(self.sessao)
            self.ativar(self.sessoes[(i + passo) % len(self.sessoes)])

    def ativar_numero(self, numero: int) -> None:
        sessao = next((s for s in self.sessoes if s.numero == numero), None)
        if sessao is not None:
            self.ativar(sessao)
            self.query_one(TerminalInput).focus()

    async def fechar_sessao(self, sessao: Sessao) -> None:
        if len(self.sessoes) == 1:
            sessao.log.clear()
            return
        self.parar(sessao)
        self.sessoes.remove(sessao)
        await sessao.log.remove()
        if self.sessao is sessao:
            self.ativar(self.sessoes[-1])
        else:
            self.atualizar_barra()

    def atualizar_barra(self) -> None:
        barra = self.query_one("#sessoes", Horizontal)
        barra.remove_children()
        botoes = []
        for s in self.sessoes:
            marca = f"[b {C['orange']}]▸[/]" if s is self.sessao else " "
            botoes.append(Botao(f"{marca}{s.titulo()}", acao=f"terminal({s.numero})"))
        botoes.append(Botao(f"[b {C['mint']}]+ terminal[/]", acao="novo_terminal"))
        barra.mount_all(botoes)

    def escrever(self, texto: Text | str, sessao: Sessao | None = None) -> None:
        (sessao or self.sessao).log.write(texto if isinstance(texto, Text) else Text(texto, style=C["text"]))

    def _rel(self, pasta: Path) -> str:
        try:
            rel = pasta.resolve().relative_to(self.raiz.resolve()).as_posix()
        except ValueError:
            return str(pasta)
        return "." if rel == "." else rel

    # ------------------------------------------------------------------ entrada
    @on(Input.Submitted, "#term-input")
    async def _enviado(self, event: Input.Submitted) -> None:
        event.stop()
        texto = event.value
        event.input.value = ""
        self.pos_historico = None
        if self.sessao.rodando():  # com um programa rodando, a linha vai para a entrada dele (input(), read…)
            self.enviar(texto)
            return
        cmd = texto.strip()
        if not cmd:
            return
        self._lembrar(cmd)
        if cmd in ("clear", "cls"):
            self.sessao.log.clear()
        elif cmd == "exit":
            await self.fechar_sessao(self.sessao)
        elif m := _CD.match(cmd):
            self._cd(m.group(1))
        else:
            self.executar(cmd)

    def _lembrar(self, cmd: str) -> None:
        if cmd in self.historico:
            self.historico.remove(cmd)
        self.historico.append(cmd)
        del self.historico[:-HISTORICO]
        estado.salvar(historico_terminal=self.historico)

    def _cd(self, destino: str | None) -> None:
        try:
            alvo_txt = shlex.split(destino)[0] if destino and destino.strip() else "~"
        except ValueError:
            alvo_txt = destino.strip()
        alvo = (self.sessao.cwd / os.path.expanduser(alvo_txt)).resolve()
        self.escrever(Text(f"{self._rel(self.sessao.cwd)} $ cd {alvo_txt}", style=f"bold {C['mint']}"))
        if not alvo.is_dir():
            self.escrever(Text(f"cd: {alvo_txt}: pasta não existe", style=C["error"]))
            return
        self.sessao.cwd = alvo
        self.escrever(Text(f"agora em {self._rel(alvo)}", style=C["dim"]))

    def enviar(self, texto: str) -> None:
        sessao = self.sessao
        if sessao.fd is not None:  # pseudoterminal: o próprio terminal ecoa o que foi digitado
            os.write(sessao.fd, (texto + "\n").encode())
        elif sessao.proc is not None and sessao.proc.stdin is not None:  # Windows: pipe, eco manual
            sessao.proc.stdin.write((texto + "\n").encode())
            sessao.proc.stdin.flush()
            sessao.log.write(Text(sessao.esperando + texto, style=C["text"]))
        self.aguardando(sessao, "")

    def interromper(self, sessao: Sessao | None = None) -> None:
        """Ctrl+C: SIGINT para o programa (KeyboardInterrupt no Python)."""
        sessao = sessao or self.sessao
        if not sessao.rodando():
            return
        if os.name == "posix":
            os.killpg(sessao.proc.pid, signal.SIGINT)
        else:
            sessao.proc.terminate()

    def parar(self, sessao: Sessao | None = None) -> None:
        sessao = sessao or self.sessao
        if sessao.rodando():
            if os.name == "posix":
                os.killpg(sessao.proc.pid, signal.SIGTERM)  # o sh e o programa que ele iniciou
            else:
                sessao.proc.terminate()

    def parar_tudo(self) -> None:
        for s in self.sessoes:
            self.parar(s)

    def aguardando(self, sessao: Sessao, pergunta: str) -> None:
        """O programa imprimiu uma pergunta sem quebra de linha e está esperando: mostra a pergunta no campo."""
        sessao.esperando = pergunta
        if sessao is self.sessao:
            self.mostrar_espera(pergunta)
            if pergunta:
                self.query_one(TerminalInput).focus()
        hook = getattr(self.app, "terminal_mudou", None)
        if hook:
            hook()

    def mostrar_espera(self, pergunta: str) -> None:
        campo = self.query_one(TerminalInput)
        if pergunta:
            campo.placeholder = f"{pergunta.strip() or '>'}   ← o programa espera: digite e tecle Enter"
        elif self.sessao.rodando():
            campo.placeholder = TERM_RUNNING
        else:
            onde = self._rel(self.sessao.cwd)
            campo.placeholder = TERM_IDLE if onde == "." else f"{onde} {TERM_IDLE}"

    # ------------------------------------------------------------------ execução
    def executar(self, cmd: str, visivel: str | None = None, cwd: Path | None = None) -> None:
        """Roda no terminal ativo; se ele está ocupado (ex.: bun run dev), abre outro terminal para o comando."""
        if self.sessao.rodando():
            self.app.call_later(self._executar_em_novo, cmd, visivel, cwd)
            return
        self._iniciar(self.sessao, cmd, visivel, cwd)

    async def _executar_em_novo(self, cmd: str, visivel: str | None, cwd: Path | None = None) -> None:
        sessao = await self.nova_sessao(focar=False)
        self._iniciar(sessao, cmd, visivel, cwd)

    def _iniciar(self, sessao: Sessao, cmd: str, visivel: str | None, cwd: Path | None = None) -> None:
        if cwd is not None:
            sessao.cwd = cwd.resolve()
        onde = self._rel(sessao.cwd)
        sessao.comando, sessao.codigo, sessao.url = visivel or cmd, None, None
        sessao.saida.clear()
        sessao.log.write(Text(f"{'' if onde == '.' else onde + ' '}$ {visivel or cmd}", style=f"bold {C['mint']}"))
        self.atualizar_barra()
        self._trabalhador(sessao, cmd)

    @work(thread=True, group="terminal")
    def _trabalhador(self, sessao: Sessao, cmd: str) -> None:
        """Roda o comando num pseudoterminal: o programa se comporta como num terminal de verdade (input() mostra a
        pergunta na hora, a saída não fica presa em buffer, Ctrl+C e getpass funcionam). No Windows, pipes."""
        chamar = self.app.call_from_thread
        t0 = time.monotonic()
        from codar.toolchains import environment

        env = {**environment(self.ambiente), **SEM_PAGINADOR, "PYTHONUNBUFFERED": "1", "TERM": "xterm-256color",
               "CODAR_STUDIO": "1"}
        mestre = None
        try:
            if os.name == "posix":
                import fcntl
                import pty
                import struct
                import termios

                mestre, escravo = pty.openpty()
                colunas = max(40, sessao.log.size.width - 2)
                fcntl.ioctl(escravo, termios.TIOCSWINSZ, struct.pack("HHHH", 24, colunas, 0, 0))
                # setsid -c: sessão nova com o pseudoterminal como terminal de controle (Ctrl+C, getpass)
                argv = ["setsid", "-c", "sh", "-c", cmd] if shutil.which("setsid") else ["sh", "-c", cmd]
                sessao.proc = subprocess.Popen(argv, cwd=sessao.cwd, stdin=escravo, stdout=escravo, stderr=escravo,
                                               env=env, close_fds=True, start_new_session=argv[0] != "setsid")
                os.close(escravo)
            else:
                sessao.proc = subprocess.Popen(cmd, shell=True, cwd=sessao.cwd, stdin=subprocess.PIPE,
                                               stdout=subprocess.PIPE, stderr=subprocess.STDOUT, env=env, bufsize=0)
        except OSError as exc:
            if mestre is not None:
                os.close(mestre)
            chamar(sessao.log.write, Text(str(exc), style=C["error"]))
            return
        sessao.fd = mestre
        chamar(self.aguardando, sessao, "")
        chamar(self.atualizar_barra)
        decodificador = codecs.getincrementaldecoder("utf-8")(errors="replace")
        pendente = ""  # texto depois da última quebra de linha (a pergunta de um input(), por exemplo)
        avisado = ""
        ociosos = 0
        while True:
            pedaco = self._ler(sessao, 0.15)
            if pedaco is None:  # nada chegou: se sobrou texto sem quebra de linha, o programa está esperando
                if pendente and pendente != avisado and sessao.rodando():
                    avisado = pendente
                    chamar(self.aguardando, sessao, _ANSI.sub("", pendente))
                if not sessao.rodando():  # terminou, mas um filho em segundo plano segura o terminal
                    ociosos += 1
                    if ociosos > 6:
                        break
                continue
            if not pedaco:
                break
            texto = pendente + decodificador.decode(pedaco).replace("\r\n", "\n")
            *linhas, pendente = texto.split("\n")
            for linha in linhas:  # "\r" sozinho (barras de progresso): fica o que foi escrito por último
                linha = linha.rsplit("\r", 1)[-1]
                self._guardar(sessao, linha)
                chamar(sessao.log.write, Text.from_ansi(linha, style=C["text"]))
            if linhas and avisado:
                avisado = ""
                chamar(self.aguardando, sessao, "")
        codigo = sessao.proc.wait()
        if pendente.strip():
            self._guardar(sessao, pendente)
            chamar(sessao.log.write, Text.from_ansi(pendente, style=C["text"]))
        if mestre is not None:
            os.close(mestre)
        sessao.fd = None
        sessao.codigo = codigo
        chamar(self.aguardando, sessao, "")
        chamar(self.atualizar_barra)
        estilo = C["mint"] if codigo == 0 else C["error"]
        chamar(sessao.log.write, Text(f"[exit {codigo} · {time.monotonic() - t0:.2f}s]", style=f"bold {estilo}"))
        hook = getattr(self.app, "programa_terminou", None)
        if hook:
            chamar(hook, sessao, codigo)

    def _guardar(self, sessao: Sessao, linha: str) -> None:
        limpa = _ANSI.sub("", linha)
        sessao.saida.append(limpa)
        del sessao.saida[:-SAIDA_GUARDADA]
        m = _URL.search(limpa)
        if m and sessao.url is None:
            sessao.url = m.group(0).rstrip(".,;)")
            hook = getattr(self.app, "servidor_detectado", None)
            if hook:
                self.app.call_from_thread(hook, sessao, sessao.url)

    @staticmethod
    def _ler(sessao: Sessao, timeout: float) -> bytes | None:
        """Bytes disponíveis da saída do programa; None se nada chegou no prazo; b"" no fim."""
        if sessao.fd is not None:
            pronto, _, _ = select.select([sessao.fd], [], [], timeout)
            if not pronto:
                return None
            try:
                return os.read(sessao.fd, 4096)
            except OSError:  # EIO: o programa terminou e fechou o terminal
                return b""
        assert sessao.proc is not None and sessao.proc.stdout is not None
        return sessao.proc.stdout.read1(4096) if hasattr(sessao.proc.stdout, "read1") else sessao.proc.stdout.read(1)
