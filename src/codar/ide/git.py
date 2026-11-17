"""Git para o Studio: estado, diferenças por trecho, preparar e descartar trechos, commit, branches, histórico,
marcas de linhas alteradas e resolução de conflitos.

Usa o git instalado, sempre com lista de argumentos (sem shell), saída em formato de máquina, sem pedir senha no
terminal e sem travas opcionais (um `git status` do Studio não disputa o índice com o git do usuário). Operações de
rede (pull, push, fetch) não ficam aqui: o Studio as roda no terminal, onde a autenticação e o progresso aparecem.
"""

from __future__ import annotations

import difflib
import os
import re
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path


class ErroGit(Exception):
    pass


@dataclass(frozen=True)
class Mudanca:
    caminho: str  # relativo à raiz do repositório, com /
    indice: str  # X do status: M A D R C U ? ou .
    trabalho: str  # Y do status
    origem: str = ""  # nome anterior, numa renomeação

    @property
    def conflito(self) -> bool:
        return "U" in (self.indice, self.trabalho) or self.indice + self.trabalho in ("AA", "DD")

    @property
    def nova(self) -> bool:
        return self.indice == "?"

    @property
    def preparada(self) -> bool:
        return not self.conflito and self.indice not in ".?"

    @property
    def alterada(self) -> bool:
        return not self.conflito and not self.nova and self.trabalho != "."


@dataclass
class Estado:
    branch: str | None = None  # None: HEAD destacado
    commit: str | None = None  # None: repositório sem commits
    upstream: str | None = None
    a_frente: int = 0
    atras: int = 0
    mudancas: list[Mudanca] = field(default_factory=list)
    em_merge: bool = False

    @property
    def conflitos(self) -> list[Mudanca]:
        return [m for m in self.mudancas if m.conflito]


@dataclass(frozen=True)
class Trecho:
    cabecalho: str  # @@ -a,b +c,d @@ contexto
    linhas: tuple[str, ...]
    inicio_novo: int  # primeira linha (a partir de 0) do lado novo

    @property
    def texto(self) -> str:
        return "\n".join((self.cabecalho, *self.linhas)) + "\n"


@dataclass(frozen=True)
class Diferenca:
    caminho: str
    cabecalho: tuple[str, ...]  # de "diff --git" até "+++"
    trechos: tuple[Trecho, ...]
    binario: bool = False

    def patch(self, indices: list[int]) -> str:
        escolhidos = [self.trechos[i] for i in sorted(set(indices))]
        return "\n".join(self.cabecalho) + "\n" + "".join(t.texto for t in escolhidos)


@dataclass(frozen=True)
class Commit:
    hash: str
    autor: str
    data: str
    assunto: str


@dataclass(frozen=True)
class Branch:
    nome: str
    atual: bool
    remoto: bool
    upstream: str = ""


@dataclass(frozen=True)
class Conflito:
    inicio: int  # linha do <<<<<<< (a partir de 0)
    fim: int  # linha do >>>>>>>
    nosso: tuple[str, ...]
    deles: tuple[str, ...]
    rotulo_nosso: str = ""
    rotulo_deles: str = ""


_TRECHO = re.compile(r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@")


def analisar_diff(caminho: str, texto: str) -> Diferenca | None:
    """O diff de um arquivo em cabeçalho e trechos; None quando não há diferença."""
    linhas = texto.split("\n")
    if linhas and linhas[-1] == "":
        linhas.pop()
    if not linhas:
        return None
    cabecalho, trechos, atual = [], [], None
    for linha in linhas:
        achado = _TRECHO.match(linha)
        if achado:
            if atual:
                trechos.append(Trecho(atual[0], tuple(atual[1]), atual[2]))
            novo = int(achado[3])
            atual = (linha, [], max(0, novo - 1) if (achado[4] or "1") != "0" else novo)
        elif atual is not None:
            atual[1].append(linha)
        else:
            cabecalho.append(linha)
    if atual:
        trechos.append(Trecho(atual[0], tuple(atual[1]), atual[2]))
    binario = not trechos and any(l.startswith(("Binary files", "GIT binary patch")) for l in cabecalho)
    return Diferenca(caminho, tuple(cabecalho), tuple(trechos), binario)


def marcas_de_linha(original: str | None, atual: str) -> dict[int, str]:
    """Linhas do texto atual em relação ao original (o que está no índice): novo, alterado ou apagado (linhas
    apagadas logo antes desta). Sem original, o arquivo inteiro é novo."""
    b = atual.replace("\r\n", "\n").split("\n")
    if original is None:
        return {i: "novo" for i, linha in enumerate(b) if not (i == len(b) - 1 and linha == "")}
    a = original.replace("\r\n", "\n").split("\n")
    marcas: dict[int, str] = {}
    for tag, _, _, j1, j2 in difflib.SequenceMatcher(None, a, b, autojunk=False).get_opcodes():
        if tag == "insert":
            marcas.update({j: "novo" for j in range(j1, j2)})
        elif tag == "replace":
            marcas.update({j: "alterado" for j in range(j1, j2)})
        elif tag == "delete":
            marcas.setdefault(min(j1, max(0, len(b) - 1)), "apagado")
    if b and b[-1] == "" and marcas.get(len(b) - 1) in ("novo", "alterado"):
        del marcas[len(b) - 1]  # a linha vazia depois do último \n não existe no editor como conteúdo
    return marcas


def conflitos_no_texto(texto: str) -> list[Conflito]:
    linhas = texto.split("\n")
    blocos, i = [], 0
    while i < len(linhas):
        if not linhas[i].startswith("<<<<<<<"):
            i += 1
            continue
        inicio, nosso, base, deles, parte = i, [], [], [], "nosso"
        rotulo_nosso = linhas[i][7:].strip()
        i += 1
        while i < len(linhas):
            linha = linhas[i]
            if linha.startswith("|||||||") and parte == "nosso":
                parte = "base"
            elif linha.startswith("=======") and parte in ("nosso", "base"):
                parte = "deles"
            elif linha.startswith(">>>>>>>") and parte == "deles":
                blocos.append(Conflito(inicio, i, tuple(nosso), tuple(deles), rotulo_nosso, linha[7:].strip()))
                break
            else:
                {"nosso": nosso, "base": base, "deles": deles}[parte].append(linha)
            i += 1
        i += 1
    return blocos


def resolver_conflito(texto: str, indice: int, escolha: str) -> str:
    """escolha: nosso (a versão atual), deles (a que está entrando) ou ambos (atual e depois a outra)."""
    bloco = conflitos_no_texto(texto)[indice]
    linhas = texto.split("\n")
    novo = {"nosso": list(bloco.nosso), "deles": list(bloco.deles), "ambos": [*bloco.nosso, *bloco.deles]}[escolha]
    return "\n".join(linhas[:bloco.inicio] + novo + linhas[bloco.fim + 1:])


class Repositorio:
    """Um repositório git, a partir da sua raiz."""

    def __init__(self, raiz: Path, git: str) -> None:
        self.raiz = Path(raiz).resolve()
        self.git = git

    @classmethod
    def abrir(cls, pasta: str | Path) -> Repositorio | None:
        git = shutil.which("git")
        if git is None:
            return None
        try:
            saida = subprocess.run([git, "rev-parse", "--show-toplevel"], cwd=pasta, capture_output=True, text=True,
                                   timeout=10, env=_ambiente(), stdin=subprocess.DEVNULL)
        except (OSError, subprocess.SubprocessError):
            return None
        if saida.returncode or not saida.stdout.strip():
            return None
        return cls(Path(saida.stdout.strip()), git)

    @classmethod
    def iniciar(cls, pasta: str | Path) -> Repositorio:
        """git init na pasta (a branch inicial segue a configuração do usuário)."""
        git = shutil.which("git")
        if git is None:
            raise ErroGit("git não encontrado: instale o git")
        saida = subprocess.run([git, "init", "-q"], cwd=pasta, capture_output=True, text=True, timeout=30,
                               env=_ambiente(), stdin=subprocess.DEVNULL)
        if saida.returncode:
            raise ErroGit(saida.stderr.strip() or "git init falhou")
        repo = cls.abrir(pasta)
        if repo is None:
            raise ErroGit("o repositório foi criado, mas o git não o reconhece nesta pasta")
        return repo

    def _git(self, *args: str, entrada: str | None = None, aceitar: tuple[int, ...] = (0,), tempo: float = 60) -> str:
        # Em bytes: o modo texto do subprocess troca \r\n por \n, o que estragaria diffs de arquivos com CRLF.
        # surrogateescape preserva bytes que não são UTF-8 na ida e na volta.
        dados = ({"input": entrada.encode("utf-8", "surrogateescape")} if entrada is not None
                 else {"stdin": subprocess.DEVNULL})  # nunca lê do terminal do Studio
        try:
            saida = subprocess.run([self.git, "-c", "core.quotepath=false", "-c", "color.ui=false", *args],
                                   cwd=self.raiz, capture_output=True, timeout=tempo, env=_ambiente(), **dados)
        except subprocess.TimeoutExpired as exc:
            raise ErroGit(f"git {args[0]} demorou demais") from exc
        except OSError as exc:
            raise ErroGit(str(exc)) from exc
        texto = saida.stdout.decode("utf-8", "surrogateescape")
        if saida.returncode not in aceitar:
            erro = (saida.stderr.decode("utf-8", "replace") or texto).strip().splitlines()
            raise ErroGit("\n".join(erro[-6:]) or f"git {args[0]} falhou ({saida.returncode})")
        return texto

    def pasta_git(self) -> Path:
        """A pasta .git de verdade (num worktree ou submódulo, .git é um arquivo que aponta para ela)."""
        return Path(self._git("rev-parse", "--absolute-git-dir").strip())

    def relativo(self, caminho: str | Path) -> str:
        return Path(caminho).resolve().relative_to(self.raiz).as_posix()

    def absoluto(self, relativo: str) -> Path:
        alvo = (self.raiz / relativo).resolve()
        if not alvo.is_relative_to(self.raiz):
            raise ErroGit(f"{relativo} fica fora do repositório")
        return alvo

    # -------------------------------------------------------------- leitura
    def estado(self) -> Estado:
        saida = self._git("status", "--porcelain=v2", "--branch", "-z", "--untracked-files=all")
        estado = Estado(em_merge=bool(self._git("rev-parse", "-q", "--verify", "MERGE_HEAD", aceitar=(0, 1)).strip()))
        campos = saida.split("\0")
        i = 0
        while i < len(campos):
            registro = campos[i]
            i += 1
            if not registro:
                continue
            if registro.startswith("# "):
                chave, _, valor = registro[2:].partition(" ")
                if chave == "branch.oid":
                    estado.commit = None if valor == "(initial)" else valor
                elif chave == "branch.head":
                    estado.branch = None if valor == "(detached)" else valor
                elif chave == "branch.upstream":
                    estado.upstream = valor
                elif chave == "branch.ab":
                    frente, atras = valor.split()
                    estado.a_frente, estado.atras = int(frente), abs(int(atras))
            elif registro[0] == "1":
                partes = registro.split(" ", 8)
                estado.mudancas.append(Mudanca(partes[8], partes[1][0], partes[1][1]))
            elif registro[0] == "2":
                partes = registro.split(" ", 9)
                estado.mudancas.append(Mudanca(partes[9], partes[1][0], partes[1][1], campos[i]))
                i += 1  # o nome anterior vem no campo seguinte
            elif registro[0] == "u":
                partes = registro.split(" ", 10)
                estado.mudancas.append(Mudanca(partes[10], partes[1][0], partes[1][1]))
            elif registro[0] == "?":
                estado.mudancas.append(Mudanca(registro[2:], "?", "?"))
        return estado

    def diferenca(self, caminho: str, preparada: bool = False, nova: bool | None = None) -> Diferenca | None:
        """O diff do arquivo: índice → trabalho, ou HEAD → índice (preparada). nova: o arquivo não é rastreado
        (None descobre pelo status)."""
        fixos = ("--no-color", "--no-ext-diff", "--src-prefix=a/", "--dst-prefix=b/", "-U3")
        if nova is None and not preparada:
            nova = caminho in {m.caminho for m in self.estado().mudancas if m.nova}
        if nova and not preparada:
            texto = self._git("diff", "--no-index", *fixos, "--", os.devnull, caminho, aceitar=(0, 1))
        else:
            texto = self._git("diff", *(("--cached",) if preparada else ()), *fixos, "--", caminho)
        return analisar_diff(caminho, texto)

    def original(self, caminho: str) -> str | None:
        """O conteúdo no índice (base das marcas de alteração); None se o arquivo não está no índice."""
        try:
            return self._git("show", f":{caminho}")
        except ErroGit:
            return None

    def historico(self, limite: int = 100, caminho: str | None = None) -> list[Commit]:
        if not self.tem_commits():
            return []
        args = ["log", f"-n{limite}", "--date=short", "--format=%h%x00%an%x00%ad%x00%s"]
        if caminho:
            args += ["--follow", "--", caminho]
        return [Commit(*linha.split("\0", 3)) for linha in self._git(*args).splitlines() if linha.count("\0") >= 3]

    def detalhes(self, commit: str) -> str:
        if not re.fullmatch(r"[0-9a-fA-F]{4,64}", commit):
            raise ErroGit("identificador de commit inválido")
        return self._git("show", "--stat", "--patch", "--no-color", "--no-ext-diff", commit)

    def branches(self) -> list[Branch]:
        saida = self._git("for-each-ref", "--format=%(refname)%00%(HEAD)%00%(upstream:short)", "refs/heads",
                          "refs/remotes")
        lista = []
        for linha in saida.splitlines():
            ref, atual, upstream = (linha.split("\0") + ["", ""])[:3]
            if ref.endswith("/HEAD"):
                continue
            remoto = ref.startswith("refs/remotes/")
            nome = ref[len("refs/remotes/"):] if remoto else ref[len("refs/heads/"):]
            lista.append(Branch(nome, atual == "*", remoto, upstream))
        return lista

    def remotos(self) -> list[str]:
        return self._git("remote").split()

    def tem_commits(self) -> bool:
        return bool(self._git("rev-parse", "-q", "--verify", "HEAD", aceitar=(0, 1)).strip())

    # -------------------------------------------------------------- escrita
    def preparar(self, caminhos: list[str]) -> None:
        self._git("add", "--", *caminhos)

    def preparar_tudo(self) -> None:
        self._git("add", "--all")

    def despreparar(self, caminhos: list[str]) -> None:
        if self.tem_commits():
            self._git("restore", "--staged", "--", *caminhos)
        else:
            self._git("rm", "--cached", "-q", "-r", "--", *caminhos)

    def descartar(self, caminhos: list[str]) -> None:
        """Volta os arquivos ao conteúdo do índice. Arquivos novos (não rastreados) não são apagados aqui."""
        self._git("restore", "--worktree", "--", *caminhos)

    def mover_nao_rastreado(self, caminho: str, destino: Path) -> None:
        """Tira um arquivo novo (não rastreado) da árvore de trabalho, movendo-o para destino (a lixeira do Studio, de
        onde dá para recuperar). Arquivo rastreado nunca sai por aqui: use descartar."""
        alvo = self.absoluto(caminho)
        if caminho not in {m.caminho for m in self.estado().mudancas if m.nova}:
            raise ErroGit(f"{caminho} é rastreado pelo git; use descartar")
        try:
            Path(destino).parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(alvo), str(destino))
        except OSError as exc:
            raise ErroGit(f"não consegui mover {caminho}: {exc.strerror or exc}") from exc

    def _aplicar(self, patch: str, *opcoes: str) -> None:
        self._git("apply", "--whitespace=nowarn", *opcoes, "-", entrada=patch)

    def preparar_trechos(self, diferenca: Diferenca, indices: list[int]) -> None:
        self._aplicar(diferenca.patch(indices), "--cached")

    def despreparar_trechos(self, diferenca_preparada: Diferenca, indices: list[int]) -> None:
        self._aplicar(diferenca_preparada.patch(indices), "--cached", "--reverse")

    def descartar_trechos(self, diferenca: Diferenca, indices: list[int]) -> None:
        self._aplicar(diferenca.patch(indices), "--reverse")

    def commit(self, mensagem: str, emendar: bool = False) -> str:
        if not mensagem.strip() and not emendar:
            raise ErroGit("escreva a mensagem do commit")
        estado = self.estado()
        if not emendar and not estado.em_merge and not any(m.preparada for m in estado.mudancas):
            raise ErroGit("nada preparado para o commit")  # num merge, o commit fecha o merge mesmo sem diferença
        if emendar and not mensagem.strip():
            self._git("commit", "--amend", "--no-edit", tempo=300)  # só junta o que foi preparado ao último commit
        else:
            args = ["commit", "-F", "-"] + (["--amend"] if emendar else [])
            self._git(*args, entrada=mensagem, tempo=300)  # hooks de pre-commit podem demorar
        return self._git("rev-parse", "--short", "HEAD").strip()

    def criar_branch(self, nome: str, trocar: bool = True) -> None:
        if self._git("check-ref-format", "--branch", nome, aceitar=(0, 1, 128)).strip() != nome:
            raise ErroGit(f"nome de branch inválido: {nome}")
        self._git(*(("switch", "-c", nome) if trocar else ("branch", nome)))

    def trocar_branch(self, nome: str) -> None:
        if nome.startswith("-"):
            raise ErroGit("nome de branch inválido")
        self._git("switch", nome)

    def abortar_merge(self) -> None:
        self._git("merge", "--abort")


def _ambiente() -> dict[str, str]:
    env = dict(os.environ)
    env.update({"GIT_TERMINAL_PROMPT": "0", "GIT_OPTIONAL_LOCKS": "0", "LC_ALL": "C", "GIT_PAGER": "cat",
                "GIT_EDITOR": "true"})
    return env
