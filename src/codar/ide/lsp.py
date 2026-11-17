"""Cliente LSP (Language Server Protocol) e gerente dos servidores de um projeto.

O Studio abre, altera, salva e fecha documentos; o servidor responde com diagnósticos, completar, informações do
símbolo, definição, referências, renomeação e formatação. Posições ficam em (linha, coluna) a partir de 0, contadas
em caracteres do Python; a conversão para a codificação negociada (UTF-16 por padrão no LSP) acontece aqui.

Servidores são programas instalados pelo usuário (pylsp, pyright, typescript-language-server, gopls, rust-analyzer,
clangd...). Alguns executam código do projeto (scripts de build do Rust, por exemplo); por isso o Studio só os inicia
num projeto marcado como confiável.
"""

from __future__ import annotations

import asyncio
import collections
import itertools
import os
import re
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import unquote, urlparse

from codar.ide.quadros import ErroProtocolo, Processo

# Servidores conhecidos por linguagem, na ordem de preferência. [lsp.servers] na configuração substitui a lista.
SERVIDORES: dict[str, list[list[str]]] = {
    "python": [["pylsp"], ["pyright-langserver", "--stdio"], ["basedpyright-langserver", "--stdio"],
               ["jedi-language-server"]],
    "javascript": [["typescript-language-server", "--stdio"]],
    "typescript": [["typescript-language-server", "--stdio"]],
    "go": [["gopls"]],
    "rust": [["rust-analyzer"]],
    "c": [["clangd"]],
    "cpp": [["clangd"]],
    "csharp": [["csharp-ls"]],
    "java": [["jdtls"]],
    "bash": [["bash-language-server", "start"]],
    "lua": [["lua-language-server"]],
    "ruby": [["ruby-lsp"], ["solargraph", "stdio"]],
    "php": [["intelephense", "--stdio"], ["phpactor", "language-server"]],
    "kotlin": [["kotlin-language-server"]],
    "swift": [["sourcekit-lsp"]],
    "dart": [["dart", "language-server", "--protocol=lsp"]],
    "html": [["vscode-html-language-server", "--stdio"]],
    "css": [["vscode-css-language-server", "--stdio"]],
    "json": [["vscode-json-language-server", "--stdio"]],
    "yaml": [["yaml-language-server", "--stdio"]],
    "dockerfile": [["docker-langserver", "--stdio"]],
    "latex": [["texlab"]],
    "markdown": [["marksman", "server"]],
    "toml": [["taplo", "lsp", "stdio"]],
    "terraform": [["terraform-ls", "serve"]],
}
# Linguagens que dividem o mesmo processo de servidor.
_GRUPO = {"javascript": "typescript", "cpp": "c"}
_ID_LSP = {"bash": "shellscript"}
_SEVERIDADE = {1: "error", 2: "warning", 3: "info", 4: "hint"}
_TIPOS = {1: "texto", 2: "método", 3: "função", 4: "construtor", 5: "campo", 6: "variável", 7: "classe",
          8: "interface", 9: "módulo", 10: "propriedade", 11: "unidade", 12: "valor", 13: "enum", 14: "palavra-chave",
          15: "trecho", 16: "cor", 17: "arquivo", 18: "referência", 19: "pasta", 20: "membro de enum", 21: "constante",
          22: "struct", 23: "evento", 24: "operador", 25: "parâmetro de tipo"}


class ErroLSP(Exception):
    pass


# ------------------------------------------------------------------------------------------- posições e textos
@dataclass(frozen=True)
class Intervalo:
    linha: int
    coluna: int
    fim_linha: int
    fim_coluna: int


@dataclass(frozen=True)
class Local:
    caminho: Path
    intervalo: Intervalo


@dataclass(frozen=True)
class Diagnostico:
    intervalo: Intervalo
    severidade: str  # error, warning, info, hint
    mensagem: str
    fonte: str = ""
    codigo: str = ""


@dataclass(frozen=True)
class Edicao:
    intervalo: Intervalo
    texto: str


@dataclass(frozen=True)
class ItemCompletar:
    rotulo: str
    inserir: str
    detalhe: str = ""
    tipo: str = ""
    documentacao: str = ""


_QUEBRA = re.compile(r"\r\n|\r|\n")


def linhas(texto: str) -> list[str]:
    """Linhas como o LSP as conta: só \\n, \\r\\n e \\r quebram linha."""
    return _QUEBRA.split(texto)


def _inicios(texto: str) -> list[int]:
    return [0] + [m.end() for m in _QUEBRA.finditer(texto)]


def para_unidades(linha: str, coluna: int, codificacao: str) -> int:
    """Coluna em caracteres do Python -> coluna na codificação do servidor."""
    trecho = linha[:coluna]
    if codificacao == "utf-32":
        return len(trecho)
    if codificacao == "utf-8":
        return len(trecho.encode("utf-8", "surrogatepass"))
    return len(trecho.encode("utf-16-le", "surrogatepass")) // 2


def de_unidades(linha: str, unidades: int, codificacao: str) -> int:
    """Coluna na codificação do servidor -> caracteres do Python (limitada ao fim da linha)."""
    if codificacao == "utf-32":
        return max(0, min(unidades, len(linha)))
    contado = 0
    for i, ch in enumerate(linha):
        if contado >= unidades:
            return i
        if codificacao == "utf-8":
            contado += len(ch.encode("utf-8", "surrogatepass"))
        else:
            contado += 2 if ord(ch) > 0xFFFF else 1
    return len(linha)


def aplicar(texto: str, edicoes: list[Edicao]) -> str:
    """Aplica edições (em caracteres do Python) de trás para frente, como o LSP exige: as posições se referem ao
    texto original."""
    inicios = _inicios(texto)
    tamanhos = [len(linha) for linha in linhas(texto)]

    def deslocamento(linha: int, coluna: int) -> int:
        if linha >= len(inicios):
            return len(texto)
        return inicios[linha] + min(max(coluna, 0), tamanhos[linha])

    # Inserções no mesmo ponto saem na ordem da lista: a última é aplicada primeiro.
    trechos = sorted(((deslocamento(e.intervalo.linha, e.intervalo.coluna),
                       deslocamento(e.intervalo.fim_linha, e.intervalo.fim_coluna), i, e.texto)
                      for i, e in enumerate(edicoes)), reverse=True)
    for inicio, fim, _, novo in trechos:
        texto = texto[:inicio] + novo + texto[max(inicio, fim):]
    return texto


def uri_de(caminho: str | Path) -> str:
    return Path(caminho).resolve().as_uri()


def caminho_de(uri: str) -> Path | None:
    partes = urlparse(uri)
    if partes.scheme != "file":
        return None
    caminho = unquote(partes.path)
    if os.name == "nt" and re.match(r"^/[A-Za-z]:", caminho):
        caminho = caminho[1:]
    return Path(caminho)


def texto_simples(conteudo) -> str:
    """Hover e documentação chegam como texto, MarkupContent, MarkedString ou listas deles."""
    if conteudo is None:
        return ""
    if isinstance(conteudo, str):
        return conteudo.strip()
    if isinstance(conteudo, list):
        return "\n\n".join(t for t in (texto_simples(c) for c in conteudo) if t)
    if isinstance(conteudo, dict):
        valor = str(conteudo.get("value", ""))
        if conteudo.get("kind") == "markdown":
            valor = re.sub(r"^```\w*\s*$", "", valor, flags=re.M)  # cercas de código viram texto
        return valor.strip()
    return str(conteudo)


# ---------------------------------------------------------------------------------------------- cliente
class ClienteLSP:
    """Conversa com um servidor de linguagem por stdin/stdout."""

    def __init__(self, comando: list[str], raiz: str | Path, env: dict[str, str] | None = None, *,
                 ao_diagnosticar=None, configuracao: dict | None = None, tempo: float = 15.0) -> None:
        self.comando = list(comando)
        self.nome = Path(comando[0]).name
        self.raiz = Path(raiz).resolve()
        self.processo = Processo(self.comando, str(self.raiz), env)
        self.ao_diagnosticar = ao_diagnosticar
        self.configuracao = configuracao or {}
        self.tempo = tempo
        self.capacidades: dict = {}
        self.codificacao = "utf-16"
        self.mensagens: collections.deque[str] = collections.deque(maxlen=50)
        self._ids = itertools.count(1)
        self._pendentes: dict[int, asyncio.Future] = {}
        self._docs: dict[Path, list] = {}  # caminho -> [versão, texto]
        self._leitura: asyncio.Task | None = None
        self.encerrado = False

    # -------------------------------------------------------------- ciclo de vida
    async def iniciar(self) -> None:
        try:
            await self.processo.iniciar()
        except OSError as exc:
            raise ErroLSP(f"{self.nome} não pôde ser iniciado: {exc}") from exc
        self._leitura = asyncio.create_task(self._ler())
        from codar import __version__

        params = {
            "processId": os.getpid(),
            "clientInfo": {"name": "codar", "version": __version__},
            "rootUri": uri_de(self.raiz), "rootPath": str(self.raiz),
            "workspaceFolders": [{"uri": uri_de(self.raiz), "name": self.raiz.name}],
            "initializationOptions": self.configuracao.get("initializationOptions", {}),
            "capabilities": {
                "general": {"positionEncodings": ["utf-32", "utf-16"]},
                "textDocument": {
                    "synchronization": {"didSave": True, "willSave": False, "dynamicRegistration": False},
                    "publishDiagnostics": {"relatedInformation": False, "versionSupport": False},
                    "completion": {"completionItem": {"snippetSupport": False,
                                                      "documentationFormat": ["plaintext", "markdown"]}},
                    "hover": {"contentFormat": ["plaintext", "markdown"]},
                    "signatureHelp": {"signatureInformation": {"documentationFormat": ["plaintext", "markdown"]}},
                    "definition": {"linkSupport": True}, "references": {}, "rename": {"prepareSupport": False},
                    "formatting": {},
                },
                "workspace": {"workspaceFolders": True, "configuration": True, "applyEdit": False,
                              "workspaceEdit": {"documentChanges": True}},
                "window": {"workDoneProgress": False},
            },
        }
        try:
            resultado = await self.requisitar("initialize", params, tempo=max(self.tempo, 30))
        except (ErroLSP, ConnectionError, asyncio.TimeoutError) as exc:
            detalhe = self.processo.ultimas_linhas()
            await self.processo.encerrar(.5)
            raise ErroLSP(f"{self.nome} não respondeu ao initialize: {exc}" + (f"\n{detalhe}" if detalhe else "")) from exc
        self.capacidades = (resultado or {}).get("capabilities", {}) or {}
        self.codificacao = self.capacidades.get("positionEncoding") or "utf-16"
        await self.notificar("initialized", {})
        if self.configuracao.get("settings"):
            await self.notificar("workspace/didChangeConfiguration", {"settings": self.configuracao["settings"]})

    async def encerrar(self) -> None:
        if self.encerrado:
            return
        self.encerrado = True
        if self.processo.vivo:
            try:
                await self.requisitar("shutdown", None, tempo=3)
                await self.notificar("exit", None)
            except (ErroLSP, ConnectionError, asyncio.TimeoutError):
                pass
        await self.processo.encerrar()
        if self._leitura:
            self._leitura.cancel()

    @property
    def vivo(self) -> bool:
        return self.processo.vivo and not self.encerrado

    # -------------------------------------------------------------- mensagens
    async def requisitar(self, metodo: str, params, tempo: float | None = None):
        if not self.processo.vivo:
            raise ConnectionError(f"{self.nome} não está em execução")
        ident = next(self._ids)
        futuro = asyncio.get_running_loop().create_future()
        self._pendentes[ident] = futuro
        mensagem = {"jsonrpc": "2.0", "id": ident, "method": metodo}
        if params is not None:
            mensagem["params"] = params
        try:
            await self.processo.enviar(mensagem)
            return await asyncio.wait_for(futuro, tempo or self.tempo)
        except asyncio.TimeoutError:
            if self.processo.vivo:
                await self.notificar("$/cancelRequest", {"id": ident})
            raise
        finally:
            self._pendentes.pop(ident, None)

    async def notificar(self, metodo: str, params) -> None:
        mensagem = {"jsonrpc": "2.0", "method": metodo}
        if params is not None:
            mensagem["params"] = params
        await self.processo.enviar(mensagem)

    async def _ler(self) -> None:
        try:
            while (mensagem := await self.processo.receber()) is not None:
                if "method" in mensagem:
                    if "id" in mensagem:
                        await self._responder(mensagem)
                    else:
                        self._notificacao(mensagem)
                elif "id" in mensagem:
                    futuro = self._pendentes.get(mensagem["id"])
                    if futuro and not futuro.done():
                        if "error" in mensagem:
                            erro = mensagem["error"] or {}
                            futuro.set_exception(ErroLSP(f"{erro.get('message', 'erro')} ({erro.get('code')})"))
                        else:
                            futuro.set_result(mensagem.get("result"))
        except (ErroProtocolo, ConnectionError) as exc:
            self.mensagens.append(f"protocolo: {exc}")
        finally:
            for futuro in self._pendentes.values():
                if not futuro.done():
                    futuro.set_exception(ConnectionError(f"{self.nome} terminou"))

    async def _responder(self, pedido: dict) -> None:
        metodo, params = pedido["method"], pedido.get("params") or {}
        resultado, erro = None, None
        if metodo == "workspace/configuration":
            resultado = [self._secao(item.get("section")) for item in params.get("items", [])]
        elif metodo == "workspace/workspaceFolders":
            resultado = [{"uri": uri_de(self.raiz), "name": self.raiz.name}]
        elif metodo == "workspace/applyEdit":
            resultado = {"applied": False, "failureReason": "o Studio aplica edições só a pedido do usuário"}
        elif metodo in ("client/registerCapability", "client/unregisterCapability", "window/workDoneProgress/create",
                        "window/showMessageRequest", "window/showDocument"):
            resultado = None
        else:
            erro = {"code": -32601, "message": f"método não suportado: {metodo}"}
        resposta = {"jsonrpc": "2.0", "id": pedido["id"]}
        resposta.update({"error": erro} if erro else {"result": resultado})
        try:
            await self.processo.enviar(resposta)
        except ConnectionError:
            pass

    def _secao(self, secao):
        dados = self.configuracao.get("settings", {})
        if not secao:
            return dados or None
        for parte in secao.split("."):
            if not isinstance(dados, dict) or parte not in dados:
                return None
            dados = dados[parte]
        return dados

    def _notificacao(self, mensagem: dict) -> None:
        metodo, params = mensagem["method"], mensagem.get("params") or {}
        if metodo == "textDocument/publishDiagnostics":
            caminho = caminho_de(params.get("uri", ""))
            if caminho is None or self.ao_diagnosticar is None:
                return
            texto = self._texto(caminho)
            diags = [Diagnostico(self._intervalo(texto, d.get("range", {})), _SEVERIDADE.get(d.get("severity"), "error"),
                                 str(d.get("message", "")).strip(), str(d.get("source") or ""),
                                 str(d.get("code") if d.get("code") is not None else ""))
                     for d in params.get("diagnostics", [])[:500]]
            self.ao_diagnosticar(caminho, diags)
        elif metodo in ("window/showMessage", "window/logMessage"):
            self.mensagens.append(str(params.get("message", ""))[:500])

    # -------------------------------------------------------------- conversões
    def _texto(self, caminho: Path) -> str:
        if caminho in self._docs:
            return self._docs[caminho][1]
        try:
            return caminho.read_text(encoding="utf-8", errors="replace")
        except OSError:
            return ""

    def _posicao(self, texto: str, linha: int, coluna: int) -> dict:
        todas = linhas(texto)
        atual = todas[linha] if 0 <= linha < len(todas) else ""
        return {"line": linha, "character": para_unidades(atual, coluna, self.codificacao)}

    def _intervalo(self, texto: str, r: dict) -> Intervalo:
        todas = linhas(texto)

        def ponto(p: dict) -> tuple[int, int]:
            linha = int(p.get("line", 0))
            atual = todas[linha] if 0 <= linha < len(todas) else ""
            return linha, de_unidades(atual, int(p.get("character", 0)), self.codificacao)

        inicio, fim = ponto(r.get("start", {})), ponto(r.get("end", r.get("start", {})))
        return Intervalo(inicio[0], inicio[1], fim[0], fim[1])

    def _locais(self, resultado) -> list[Local]:
        if not resultado:
            return []
        itens = resultado if isinstance(resultado, list) else [resultado]
        locais = []
        for item in itens[:200]:
            uri = item.get("uri") or item.get("targetUri")
            intervalo = item.get("range") or item.get("targetSelectionRange") or item.get("targetRange") or {}
            caminho = caminho_de(uri or "")
            if caminho is not None:
                locais.append(Local(caminho, self._intervalo(self._texto(caminho), intervalo)))
        return locais

    def _edicoes(self, texto: str, itens) -> list[Edicao]:
        return [Edicao(self._intervalo(texto, e.get("range", {})), str(e.get("newText", ""))) for e in itens or []]

    def _doc(self, caminho: Path, linha: int, coluna: int) -> dict:
        caminho = Path(caminho).resolve()
        return {"textDocument": {"uri": uri_de(caminho)}, "position": self._posicao(self._texto(caminho), linha, coluna)}

    def suporta(self, capacidade: str) -> bool:
        # No LSP, um objeto de opções vazio ({}) também anuncia o recurso; só ausência, null e false o negam.
        return self.capacidades.get(capacidade) not in (None, False)

    # -------------------------------------------------------------- documentos
    async def abrir(self, caminho: Path, lang_id: str, texto: str) -> None:
        caminho = Path(caminho).resolve()
        self._docs[caminho] = [1, texto]
        await self.notificar("textDocument/didOpen", {"textDocument": {
            "uri": uri_de(caminho), "languageId": lang_id, "version": 1, "text": texto}})

    async def alterar(self, caminho: Path, texto: str) -> None:
        caminho = Path(caminho).resolve()
        doc = self._docs.get(caminho)
        if doc is None or doc[1] == texto:
            return
        doc[0] += 1
        doc[1] = texto
        await self.notificar("textDocument/didChange", {"textDocument": {"uri": uri_de(caminho), "version": doc[0]},
                                                         "contentChanges": [{"text": texto}]})

    async def salvar(self, caminho: Path, texto: str) -> None:
        caminho = Path(caminho).resolve()
        if caminho not in self._docs:
            return
        await self.alterar(caminho, texto)
        sync = self.capacidades.get("textDocumentSync")
        incluir = isinstance(sync, dict) and isinstance(sync.get("save"), dict) and sync["save"].get("includeText")
        params = {"textDocument": {"uri": uri_de(caminho)}}
        if incluir:
            params["text"] = texto
        await self.notificar("textDocument/didSave", params)

    async def fechar(self, caminho: Path) -> None:
        caminho = Path(caminho).resolve()
        if self._docs.pop(caminho, None) is not None:
            await self.notificar("textDocument/didClose", {"textDocument": {"uri": uri_de(caminho)}})

    # -------------------------------------------------------------- recursos
    async def completar(self, caminho: Path, linha: int, coluna: int, limite: int = 200) -> list[ItemCompletar]:
        if not self.suporta("completionProvider"):
            return []
        resultado = await self.requisitar("textDocument/completion", self._doc(caminho, linha, coluna))
        itens = resultado.get("items", []) if isinstance(resultado, dict) else resultado or []
        saida = []
        for item in itens[:limite]:
            edicao = item.get("textEdit") or {}
            inserir = edicao.get("newText") or item.get("insertText") or item.get("label", "")
            saida.append(ItemCompletar(str(item.get("label", "")), str(inserir), str(item.get("detail") or ""),
                                       _TIPOS.get(item.get("kind"), ""), texto_simples(item.get("documentation"))))
        return saida

    async def informacoes(self, caminho: Path, linha: int, coluna: int) -> str:
        if not self.suporta("hoverProvider"):
            return ""
        resultado = await self.requisitar("textDocument/hover", self._doc(caminho, linha, coluna))
        return texto_simples((resultado or {}).get("contents"))

    async def assinatura(self, caminho: Path, linha: int, coluna: int) -> str:
        if not self.suporta("signatureHelpProvider"):
            return ""
        resultado = await self.requisitar("textDocument/signatureHelp", self._doc(caminho, linha, coluna)) or {}
        assinaturas = resultado.get("signatures") or []
        if not assinaturas:
            return ""
        ativa = assinaturas[min(int(resultado.get("activeSignature") or 0), len(assinaturas) - 1)]
        return str(ativa.get("label", ""))

    async def definicao(self, caminho: Path, linha: int, coluna: int) -> list[Local]:
        if not self.suporta("definitionProvider"):
            return []
        return self._locais(await self.requisitar("textDocument/definition", self._doc(caminho, linha, coluna)))

    async def referencias(self, caminho: Path, linha: int, coluna: int) -> list[Local]:
        if not self.suporta("referencesProvider"):
            return []
        params = self._doc(caminho, linha, coluna) | {"context": {"includeDeclaration": True}}
        return self._locais(await self.requisitar("textDocument/references", params))

    async def renomear(self, caminho: Path, linha: int, coluna: int, novo: str) -> dict[Path, list[Edicao]]:
        if not self.suporta("renameProvider"):
            return {}
        params = self._doc(caminho, linha, coluna) | {"newName": novo}
        edicao = await self.requisitar("textDocument/rename", params) or {}
        por_arquivo: dict[Path, list[Edicao]] = {}
        for uri, itens in (edicao.get("changes") or {}).items():
            if (alvo := caminho_de(uri)) is not None:
                por_arquivo.setdefault(alvo, []).extend(self._edicoes(self._texto(alvo), itens))
        for mudanca in edicao.get("documentChanges") or []:
            if "kind" in mudanca:  # criar, renomear ou apagar arquivos: o Studio não aplica operações de arquivo
                raise ErroLSP(f"a renomeação pede uma operação de arquivo ({mudanca['kind']}) que o Studio não aplica")
            alvo = caminho_de((mudanca.get("textDocument") or {}).get("uri", ""))
            if alvo is not None:
                por_arquivo.setdefault(alvo, []).extend(self._edicoes(self._texto(alvo), mudanca.get("edits")))
        return por_arquivo

    async def formatar(self, caminho: Path, recuo: int = 4, espacos: bool = True) -> list[Edicao]:
        if not self.suporta("documentFormattingProvider"):
            return []
        caminho = Path(caminho).resolve()
        params = {"textDocument": {"uri": uri_de(caminho)}, "options": {"tabSize": recuo, "insertSpaces": espacos}}
        return self._edicoes(self._texto(caminho), await self.requisitar("textDocument/formatting", params))


# ---------------------------------------------------------------------------------------------- gerente
def grupo(lang: str) -> str:
    return _GRUPO.get(lang, lang)


def id_lsp(lang: str, caminho: str | Path) -> str:
    sufixo = Path(caminho).suffix.lower()
    if sufixo == ".tsx":
        return "typescriptreact"
    if sufixo == ".jsx":
        return "javascriptreact"
    return _ID_LSP.get(lang, lang)


@dataclass
class _Estado:
    cliente: ClienteLSP | None = None
    tarefa: asyncio.Task | None = None
    motivo: str = ""
    linguagens: set[str] = field(default_factory=set)


def _normalizar(valor) -> list[list[str]]:
    """[lsp.servers] aceita um comando (["pyright-langserver", "--stdio"]) ou uma lista de comandos."""
    if isinstance(valor, str):
        return [[valor]]
    if valor and all(isinstance(c, (list, tuple)) for c in valor):
        return [[str(p) for p in c] for c in valor if c]
    return [[str(p) for p in valor]]


class GerenteLSP:
    """Um servidor por grupo de linguagens, iniciado na primeira vez que um arquivo daquela linguagem é aberto."""

    def __init__(self, raiz: str | Path, *, env: dict[str, str] | None = None, servidores: dict | None = None,
                 ao_diagnosticar=None, configuracao: dict | None = None) -> None:
        self.raiz = Path(raiz).resolve()
        self.env = dict(env if env is not None else os.environ)
        self.servidores = {k: _normalizar(v) for k, v in (servidores or {}).items() if v}
        self.ao_diagnosticar = ao_diagnosticar
        self.configuracao = configuracao or {}
        self._estados: dict[str, _Estado] = {}
        self._docs: dict[Path, str] = {}  # caminho -> grupo

    def candidatos(self, lang: str) -> list[list[str]]:
        return self.servidores.get(lang) or SERVIDORES.get(lang, [])

    def comando(self, lang: str) -> list[str] | None:
        """O primeiro servidor da linguagem encontrado no PATH."""
        for candidato in self.candidatos(lang):
            achado = shutil.which(candidato[0], path=self.env.get("PATH"))
            if achado:
                return [achado, *candidato[1:]]
        return None

    def disponivel(self, lang: str) -> bool:
        return self.comando(lang) is not None

    def estado(self) -> dict[str, str]:
        """Grupo -> nome do servidor em execução ou motivo de estar indisponível."""
        return {g: (e.cliente.nome if e.cliente and e.cliente.vivo else e.motivo or "iniciando")
                for g, e in self._estados.items()}

    async def cliente(self, lang: str) -> ClienteLSP | None:
        chave = grupo(lang)
        estado = self._estados.setdefault(chave, _Estado())
        estado.linguagens.add(lang)
        if estado.cliente and estado.cliente.vivo:
            return estado.cliente
        if estado.motivo and not estado.tarefa:
            return None
        if estado.tarefa is None:
            estado.tarefa = asyncio.create_task(self._iniciar(lang, estado))
        try:
            return await asyncio.shield(estado.tarefa)
        finally:
            if estado.tarefa and estado.tarefa.done():
                estado.tarefa = None

    async def _iniciar(self, lang: str, estado: _Estado) -> ClienteLSP | None:
        motivos = []
        for candidato in self.candidatos(lang):
            executavel = shutil.which(candidato[0], path=self.env.get("PATH"))
            if not executavel:
                continue
            cliente = ClienteLSP([executavel, *candidato[1:]], self.raiz, self.env, ao_diagnosticar=self.ao_diagnosticar,
                                 configuracao=self.configuracao.get(candidato[0], {}))
            try:
                await cliente.iniciar()
            except ErroLSP as exc:
                motivos.append(str(exc))
                continue
            estado.cliente, estado.motivo = cliente, ""
            return cliente
        estado.motivo = "; ".join(motivos) or (
            "nenhum servidor instalado (" + ", ".join(c[0] for c in self.candidatos(lang)) + ")"
            if self.candidatos(lang) else "sem servidor conhecido para a linguagem")
        return None

    def _do_documento(self, caminho: Path) -> ClienteLSP | None:
        chave = self._docs.get(Path(caminho).resolve())
        estado = self._estados.get(chave) if chave else None
        return estado.cliente if estado and estado.cliente and estado.cliente.vivo else None

    async def abrir(self, caminho: Path, lang: str, texto: str) -> ClienteLSP | None:
        caminho = Path(caminho).resolve()
        cliente = await self.cliente(lang)
        if cliente is None:
            return None
        self._docs[caminho] = grupo(lang)
        await cliente.abrir(caminho, id_lsp(lang, caminho), texto)
        return cliente

    async def alterar(self, caminho: Path, texto: str) -> None:
        if cliente := self._do_documento(caminho):
            await cliente.alterar(caminho, texto)

    async def salvar(self, caminho: Path, texto: str) -> None:
        if cliente := self._do_documento(caminho):
            await cliente.salvar(caminho, texto)

    async def fechar(self, caminho: Path) -> None:
        if cliente := self._do_documento(caminho):
            await cliente.fechar(caminho)
        self._docs.pop(Path(caminho).resolve(), None)

    def aberto(self, caminho: Path) -> bool:
        return self._do_documento(caminho) is not None

    async def _chamar(self, nome: str, caminho: Path, *args):
        cliente = self._do_documento(caminho)
        if cliente is None:
            raise ErroLSP("nenhum servidor de linguagem acompanha este arquivo")
        return await getattr(cliente, nome)(Path(caminho).resolve(), *args)

    async def completar(self, caminho, linha, coluna):
        return await self._chamar("completar", caminho, linha, coluna)

    async def informacoes(self, caminho, linha, coluna):
        return await self._chamar("informacoes", caminho, linha, coluna)

    async def assinatura(self, caminho, linha, coluna):
        return await self._chamar("assinatura", caminho, linha, coluna)

    async def definicao(self, caminho, linha, coluna):
        return await self._chamar("definicao", caminho, linha, coluna)

    async def referencias(self, caminho, linha, coluna):
        return await self._chamar("referencias", caminho, linha, coluna)

    async def renomear(self, caminho, linha, coluna, novo):
        return await self._chamar("renomear", caminho, linha, coluna, novo)

    async def formatar(self, caminho, recuo=4, espacos=True):
        return await self._chamar("formatar", caminho, recuo, espacos)

    async def encerrar(self) -> None:
        clientes = [e.cliente for e in self._estados.values() if e.cliente]
        await asyncio.gather(*(c.encerrar() for c in clientes), return_exceptions=True)
        self._estados.clear()
        self._docs.clear()


def configuracao_padrao(python: str | None) -> dict:
    """Ambiente do projeto para os servidores Python: imports resolvidos no .venv do projeto."""
    if not python:
        return {}
    return {
        "pylsp": {"settings": {"pylsp": {"plugins": {"jedi": {"environment": python}}}}},
        "pyright-langserver": {"settings": {"python": {"pythonPath": python}}},
        "basedpyright-langserver": {"settings": {"python": {"pythonPath": python}}},
        "jedi-language-server": {"initializationOptions": {"workspace": {"environmentPath": python}}},
    }
