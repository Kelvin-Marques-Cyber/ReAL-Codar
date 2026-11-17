"""Servidor LSP mínimo para os testes: posições em UTF-16, pedidos ao cliente e muita saída em stderr.

Responde a completar, informações, definição, referências, renomear e formatar sobre a palavra `alvo`, e publica um
diagnóstico na primeira linha que contém `erro`.
"""

import json
import re
import sys

entrada, saida = sys.stdin.buffer, sys.stdout.buffer
documentos: dict[str, str] = {}
configuracao_recebida = None


def enviar(mensagem):
    corpo = json.dumps(mensagem).encode()
    saida.write(b"Content-Length: %d\r\n\r\n" % len(corpo) + corpo)
    saida.flush()


def receber():
    tamanho = None
    while True:
        linha = entrada.readline()
        if not linha:
            return None
        if linha in (b"\r\n", b"\n"):
            break
        nome, _, valor = linha.decode().partition(":")
        if nome.lower() == "content-length":
            tamanho = int(valor)
    return json.loads(entrada.read(tamanho))


def utf16(texto_linha, coluna):
    return len(texto_linha[:coluna].encode("utf-16-le")) // 2


def onde(uri, palavra):
    for n, linha in enumerate(documentos.get(uri, "").split("\n")):
        i = linha.find(palavra)
        if i >= 0:
            return {"start": {"line": n, "character": utf16(linha, i)},
                    "end": {"line": n, "character": utf16(linha, i + len(palavra))}}
    return None


def diagnosticar(uri):
    diags = []
    if (r := onde(uri, "erro")) is not None:
        diags.append({"range": r, "severity": 1, "source": "falso", "code": "F1", "message": "palavra proibida"})
    enviar({"jsonrpc": "2.0", "method": "textDocument/publishDiagnostics", "params": {"uri": uri, "diagnostics": diags}})


pedido_configuracao = 1000
while (msg := receber()) is not None:
    sys.stderr.write("log " * 2000 + "\n")  # stderr volumoso não pode travar o cliente
    sys.stderr.flush()
    metodo, params = msg.get("method"), msg.get("params") or {}
    if "id" in msg and metodo is None:  # resposta a um pedido nosso
        if msg["id"] == pedido_configuracao:
            configuracao_recebida = msg.get("result")
        continue
    if metodo == "initialize":
        enviar({"jsonrpc": "2.0", "id": msg["id"], "result": {"capabilities": {
            "textDocumentSync": {"openClose": True, "change": 1, "save": {"includeText": True}},
            "completionProvider": {}, "hoverProvider": True, "definitionProvider": True, "referencesProvider": True,
            "renameProvider": True, "documentFormattingProvider": True, "signatureHelpProvider": {}}}})
    elif metodo == "initialized":
        enviar({"jsonrpc": "2.0", "id": pedido_configuracao, "method": "workspace/configuration",
                "params": {"items": [{"section": "falso.nivel"}]}})
    elif metodo == "textDocument/didOpen":
        documentos[params["textDocument"]["uri"]] = params["textDocument"]["text"]
        diagnosticar(params["textDocument"]["uri"])
    elif metodo == "textDocument/didChange":
        documentos[params["textDocument"]["uri"]] = params["contentChanges"][-1]["text"]
        diagnosticar(params["textDocument"]["uri"])
    elif metodo == "textDocument/didSave":
        enviar({"jsonrpc": "2.0", "method": "window/logMessage",
                "params": {"type": 3, "message": "salvo com texto" if "text" in params else "salvo"}})
    elif metodo == "textDocument/completion":
        enviar({"jsonrpc": "2.0", "id": msg["id"], "result": {"isIncomplete": False, "items": [
            {"label": "alvo_completo", "kind": 3, "detail": "() -> None", "documentation": {"kind": "markdown", "value": "Faz **algo**."}}]}})
    elif metodo == "textDocument/hover":
        enviar({"jsonrpc": "2.0", "id": msg["id"], "result": {"contents": {"kind": "markdown",
                                                                           "value": "```python\nalvo: int\n```"}}})
    elif metodo == "textDocument/signatureHelp":
        enviar({"jsonrpc": "2.0", "id": msg["id"], "result": {"signatures": [{"label": "alvo(x: int) -> int"}]}})
    elif metodo in ("textDocument/definition", "textDocument/references"):
        uri = params["textDocument"]["uri"]
        r = onde(uri, "alvo")
        if metodo == "textDocument/definition":
            resultado = [{"targetUri": uri, "targetRange": r, "targetSelectionRange": r}]
        else:
            resultado = [{"uri": uri, "range": r}, {"uri": uri, "range": r}]
        enviar({"jsonrpc": "2.0", "id": msg["id"], "result": resultado})
    elif metodo == "textDocument/rename":
        uri = params["textDocument"]["uri"]
        texto = documentos[uri]
        edits = []
        for n, linha in enumerate(texto.split("\n")):
            for m in re.finditer(r"\balvo\b", linha):
                edits.append({"range": {"start": {"line": n, "character": utf16(linha, m.start())},
                                        "end": {"line": n, "character": utf16(linha, m.end())}},
                              "newText": params["newName"]})
        enviar({"jsonrpc": "2.0", "id": msg["id"], "result": {"documentChanges": [
            {"textDocument": {"uri": uri, "version": None}, "edits": edits}]}})
    elif metodo == "textDocument/formatting":
        enviar({"jsonrpc": "2.0", "id": msg["id"], "result": [
            {"range": {"start": {"line": 0, "character": 0}, "end": {"line": 0, "character": 0}},
             "newText": "# formatado\n"}]})
    elif metodo == "shutdown":
        enviar({"jsonrpc": "2.0", "id": msg["id"], "result": None})
    elif metodo == "exit":
        sys.stderr.write(f"configuracao={json.dumps(configuracao_recebida)}\n")
        break
    elif "id" in msg:
        enviar({"jsonrpc": "2.0", "id": msg["id"], "error": {"code": -32601, "message": "não suportado"}})
