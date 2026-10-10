"""Pedidos de dependências têm escopo de importação, não de implementação.

O catálogo é local e pequeno; fora dele, a IA só pode sugerir declarações
de importação. Código executável nunca faz parte dessa resposta.
"""

from __future__ import annotations

import ast
import re

from codar.textutil import fold


_PREFIX = re.compile(
    r"^(?:(?:por favor|please|eu quero|quero|preciso|gostaria de|i want to|i need to)\s*[, :]?\s*)?"
    r"(?:(?:so|somente|apenas|just|only)\s+)?"
    r"(?:importar|importe|importa|import|importacao|incluir|inclua|include|require|requerer|"
    r"(?:usar|use|adicionar|adicione|add)\s+(?:(?:uma?|a|o|the|an?)\s+)?"
    r"(?:biblioteca|lib|modulo|pacote|library|module|package))\b"
)
_LIBRARY = re.compile(r"\b(?:biblioteca|lib|modulo|pacote|library|module|package|header|cabecalho)\b")
_ALSO = re.compile(
    r"\b(?:e|and|depois|then)\s+(?:(?:tambem|also)\s+)?"
    r"(?:crie|criar|gere|gerar|implemente|implementar|escreva|escrever|leia|ler|liste|listar|"
    r"baixe|baixar|execute|executar|imprima|imprimir|create|build|generate|implement|write|read|"
    r"list|download|run|print)\b"
)


def is_import_request(intent: str, lang: str | None = None) -> bool:
    """Reconhece a ação pedida, sem confundir a finalidade da biblioteca com código novo."""
    if is_native_import(intent, lang):
        return True
    if "\n" in intent.strip():
        return False
    text = fold(intent.strip())
    match = _PREFIX.match(text)
    if not match:
        return False
    # "importar um CSV para o banco" é importação de dados, não de um módulo.
    rest = text[match.end():].strip()
    if not rest:
        return False
    if not _LIBRARY.search(text) and not re.search(r'\b[\w./-]+\.py\b|\b(?:funcao|funcoes|function|functions)\b', rest) and re.match(
            r"(?:(?:um|uma|o|a|the)\s+)?(?:dados|data|arquivo|file|csv|planilha|spreadsheet)\b", rest):
        return False
    # "para ler vídeos e listar playlists" descreve a biblioteca. Já
    # "importe X e crie uma função" pede explicitamente uma implementação.
    action = re.split(r"\b(?:para|pra|to|for|que)\b", text, maxsplit=1)[0]
    return not _ALSO.search(action)


def is_native_import(intent: str, lang: str | None) -> bool:
    """Código já escrito preserva #include, ponto e vírgula, nomes e aliases."""
    if lang == "python":
        try:
            nodes = ast.parse(intent).body
            if nodes and all(isinstance(n, (ast.Import, ast.ImportFrom)) for n in nodes):
                return True
        except SyntaxError:
            pass
    elif lang in _RULES and re.fullmatch(_RULES[lang], re.sub(r"\s+", " ", intent.strip()),
                                        re.I if lang in ("powershell", "html") else 0):
        return True
    elif lang == "go" and re.fullmatch(r"import\s*\([\s\S]*\)", intent.strip()):
        return bool(import_prefix(intent, lang))
    return False


# APIs conferidas nas fontes oficiais. Nunca executa pip/npm/pub nem downloads.
YOUTUBE_IMPORTS = {
    "python": ("from yt_dlp import YoutubeDL", "yt-dlp", "https://github.com/yt-dlp/yt-dlp#embedding-yt-dlp"),
    "javascript": ("import { Innertube } from 'youtubei.js';", "youtubei.js", "https://ytjs.dev/guide/getting-started"),
    "typescript": ("import { Innertube } from 'youtubei.js';", "youtubei.js", "https://ytjs.dev/guide/getting-started"),
    "dart": ("import 'package:youtube_explode_dart/youtube_explode_dart.dart';", "youtube_explode_dart",
             "https://pub.dev/packages/youtube_explode_dart"),
    "csharp": ("using YoutubeExplode;", "YoutubeExplode", "https://github.com/Tyrrrz/YoutubeExplode"),
}


def catalog_import(intent: str, lang: str) -> tuple[str, str, str] | None:
    """YouTube é uma finalidade; yt_dlp/pytube/etc. escritos explicitamente são nomes de módulos."""
    if re.search(r"\byou\s*tube\b", fold(intent)):
        return YOUTUBE_IMPORTS.get(lang)
    return None


_ID = r"[A-Za-z_]\w*"
_PATH = r"[\w./:@+\\-]+"
_STR = r'''(?:"[^"\n]*"|'[^'\n]*')'''
_BINDINGS = rf"(?:\*\s+as\s+{_ID}|{_ID}(?:\s*,\s*\{{[\w\s,]*\}})?|\{{[\w\s,]*\}})"
_JS = rf"(?:import\s+(?:(?:type\s+)?{_BINDINGS}\s+from\s+)?{_STR}|(?:const|let|var)\s+{_BINDINGS}\s*=\s*require\(\s*{_STR}\s*\))\s*;?"
_RULES = {
    "javascript": _JS,
    "typescript": _JS,
    "go": rf"import\s+(?:(?:{_ID}|\.)\s+)?\"[^\"\n]+\"",
    "rust": r"(?:use\s+[\w\s:{},*]+|extern\s+crate\s+\w+(?:\s+as\s+\w+)?)\s*;",
    "java": r"import\s+(?:static\s+)?[\w.*]+\s*;",
    "kotlin": rf"import\s+[\w.*]+(?:\s+as\s+{_ID})?\s*;?",
    "csharp": r"(?:global\s+)?using\s+(?:static\s+)?(?:\w+\s*=\s*)?[\w.:]+\s*;",
    "c": rf"#\s*include\s*(?:<[^>\n]+>|{_STR})",
    "cpp": rf"(?:#\s*include\s*(?:<[^>\n]+>|{_STR})|(?:export\s+)?import\s+[\w.:]+\s*;)",
    "php": rf"(?:use\s+(?:function\s+|const\s+)?[\w\\]+(?:\s+as\s+{_ID})?\s*;|require(?:_once)?\s*\(?\s*{_STR}\s*\)?\s*;)",
    "ruby": rf"require(?:_relative)?\s*(?:\(\s*{_STR}\s*\)|\s+{_STR})\s*;?",
    "lua": rf"local\s+{_ID}\s*=\s*require\s*(?:\(\s*{_STR}\s*\)|{_STR})\s*;?",
    "powershell": rf"(?:Import-Module\s+(?:-Name\s+)?(?:{_STR}|{_PATH})|using\s+(?:module|namespace|assembly)\s+(?:{_STR}|{_PATH}))\s*;?",
    "swift": r"import\s+(?:(?:class|struct|enum|protocol|func|var|typealias)\s+)?[\w.]+\s*;?",
    "dart": rf"import\s+{_STR}(?:\s+deferred)?(?:\s+as\s+{_ID})?(?:\s+(?:show|hide)\s+[\w\s,]+)*\s*;",
    "julia": r"(?:using|import)\s+[\w.,:\s]+",
    "r": rf"(?:library|require)\(\s*(?:{_ID}|{_STR})\s*\)\s*;?",
    "bash": rf"(?:source|\.)\s+(?:{_STR}|{_PATH})",
    "html": rf"<script\s+src\s*=\s*{_STR}\s*>\s*</script>|<link\s+rel\s*=\s*['\"]stylesheet['\"]\s+href\s*=\s*{_STR}\s*/?>",
    "css": rf"@import\s+(?:{_STR}|url\(\s*{_STR}\s*\))\s*;",
}
IMPORT_LANGS = frozenset(_RULES) | {"python"}


def _balanced(text: str) -> bool:
    """Delimitadores de imports multilinha, ignorando delimitadores dentro de strings."""
    quote = ""
    escaped = False
    depth = 0
    for char in text:
        if escaped:
            escaped = False
        elif quote:
            if char == "\\":
                escaped = True
            elif char == quote:
                quote = ""
        elif char in "\"'":
            quote = char
        elif char in "([{":
            depth += 1
        elif char in ")]}":
            depth -= 1
    return not quote and depth == 0


def import_prefix(code: str, lang: str) -> list[str]:
    """Aceita apenas declarações completas do topo, descartando toda implementação extra.

    Valida a declaração inteira: `using X; Executar();` e `require('x')()
    não são imports puros. Nenhum código é executado nesta verificação.
    """
    if lang not in IMPORT_LANGS or len(code) > 16000:
        return []
    lines = code.strip().splitlines()
    statements: list[str] = []
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        i += 1
        if not line or line.startswith(("//", "--", "/*", "<!--")) or (
                line.startswith("#") and not re.match(r"#\s*include\b", line)):
            continue
        if lang == "php" and line == "<?php":
            continue
        if lang == "go" and not statements and re.fullmatch(r"package\s+\w+", line):
            continue
        chunk = line
        while not _balanced(chunk) and i < len(lines) and len(chunk) < 4096:
            chunk += "\n" + lines[i].strip()
            i += 1
        if not _balanced(chunk):
            break
        if lang == "python":
            try:
                nodes = ast.parse(chunk).body
            except SyntaxError:
                break
            if not nodes or not all(isinstance(n, (ast.Import, ast.ImportFrom)) for n in nodes):
                break
            found = [ast.unparse(n) for n in nodes]
        elif lang == "go" and re.fullmatch(r"import\s*\([\s\S]*\)", chunk):
            found = ["import " + item.strip() for item in chunk[chunk.index("(") + 1:-1].splitlines() if item.strip()]
            if not found or any(not re.fullmatch(_RULES[lang], item) for item in found):
                break
        else:
            # Une os imports multilinha; os padrões não aceitam chamadas ou
            # comandos concatenados após uma declaração.
            chunk = re.sub(r"\s+", " ", chunk) if "\n" in chunk else chunk
            if not re.fullmatch(_RULES[lang], chunk, re.I if lang in ("powershell", "html") else 0):
                break
            if lang in ("bash", "powershell") and any(x in chunk for x in ("$", "`")):
                break
            found = [chunk]
        statements.extend(x for x in found if x not in statements)
        if len(statements) > 6:
            return []
    return statements
