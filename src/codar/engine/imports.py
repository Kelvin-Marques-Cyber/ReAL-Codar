"""Pedidos de dependências têm escopo de importação, não de implementação.

Nomes explícitos são resolvidos offline, inclusive bibliotecas não catalogadas.
Quando falta o nome, a IA só pode sugerir declarações de importação.
"""

from __future__ import annotations

import ast
import keyword
import re

from codar.library_names import (C_HEADERS, CPP_HEADERS, CSHARP_NAMESPACES, DART_ENTRIES, GO_PACKAGES,
                                 JAVA_PACKAGES, JS_DEFAULTS, PYTHON_IMPORTS, python_distribution, python_module)
from codar.textutil import fold, fold_keep_len


_PREFIX = re.compile(
    r"^(?:(?:por favor|please|eu quero|quero|preciso|gostaria de|i want to|i need to)\s*[, :]?\s*)?"
    r"(?:(?:so|somente|apenas|just|only)\s+)?"
    r"(?:importar|importe|importa|import|importacao|incluir|inclua|include|require|requerer|"
    r"(?:usar|use|adicionar|adicione|add)\s+(?:(?:uma?|a|o|the|an?)\s+)?"
    r"(?:bibliotecas?|libs?|modulos?|pacotes?|libraries|library|modules?|packages?))\b"
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


_NAME = r"[A-Za-z_@./][\w./:@+\\-]*"
_NOISE = re.compile(r"^(?:(?:de|da|do|das|dos|a|o|as|os|um|uma|the|an|of|from|"
                    r"bibliotecas?|libs?|modulos?|pacotes?|libraries|library|modules?|packages?|"
                    r"header|cabecalho|chamada|chamado|called|named)\b\s*)+", re.I)
_NOT_NAMES = set("para pra que to for function functions funcao funcoes classe classes class metodo method "
                 "arquivo file minha minhas meu meus propria proprio leia ler read dados data playlists videos ".split())


def _named_requests(intent: str) -> list[tuple[str, str, str]]:
    """(módulo, símbolo opcional, alias opcional); aceita apenas nomes explícitos."""
    text = fold_keep_len(intent.strip())
    prefix = _PREFIX.match(text)
    if not prefix:
        return []
    rest = intent.strip()[prefix.end():].strip()
    # A finalidade fica fora da lista de nomes; não vira argumento ou comando.
    purpose = re.search(r"\s+(?:para|pra|to|for|que)\s+", fold_keep_len(rest))
    if purpose:
        rest = rest[:purpose.start()]
    symbol = re.fullmatch(rf"(?:(?:a|o|the)\s+)?(?:funcao|function|classe|class|simbolo|symbol)\s+"
                          rf"(?P<symbol>[A-Za-z_]\w*)\s+(?:de|da|do|from)\s+(?P<module>{_NAME})"
                          rf"(?:\s+(?:como|as)\s+(?P<alias>[A-Za-z_]\w*))?", fold_keep_len(rest))
    if symbol:
        return [(rest[symbol.start('module'):symbol.end('module')],
                 rest[symbol.start('symbol'):symbol.end('symbol')],
                 rest[symbol.start('alias'):symbol.end('alias')] if symbol['alias'] else '')]
    noise = _NOISE.match(fold_keep_len(rest))
    rest = rest[noise.end():] if noise else rest
    output = []
    for part in re.split(r"\s*,\s*|\s+(?:e|and)\s+", rest, flags=re.I):
        part = part.strip().strip('`')
        match = re.fullmatch(rf"(?P<name>{_NAME}|['\"]{_NAME}['\"])(?:\s+(?:como|as)\s+"
                             rf"(?P<alias>[A-Za-z_]\w*))?", part, re.I)
        if not match:
            return []
        name = match['name'].strip("'\"")
        if fold(name) in _NOT_NAMES or name.endswith('.py'):
            return []
        output.append((name, '', match['alias'] or ''))
    return output if 0 < len(output) <= 6 else []


def _named_import(name: str, symbol: str, alias: str, lang: str) -> tuple[str, str] | None:
    """Sintaxe do ecossistema sem adivinhar exports, headers ou arquivos de entrada."""
    if lang == 'python':
        module = python_module(name)
        if not symbol:
            module, default = PYTHON_IMPORTS.get(module, (module, ''))
            alias = alias or default
        if not all(part.isidentifier() and not keyword.iskeyword(part) for part in module.split('.')) or (
                alias and (not alias.isidentifier() or keyword.iskeyword(alias))):
            return None
        if symbol:
            code = f'from {module} import {symbol}' + (f' as {alias}' if alias else '')
        else:
            code = f'import {module}' + (f' as {alias}' if alias else '')
        return code, python_distribution(name)
    if lang in ('javascript', 'typescript'):
        if not re.fullmatch(r'(?:@[\w.-]+/)?[\w.-]+(?:/[\w./-]+)?|\.{1,2}/[\w./-]+', name) or '..' in name.split('/')[2:]:
            return None
        default = JS_DEFAULTS.get(name.lower())
        name = name.lower() if default else name
        binding = alias or default or re.sub(r'\W+', '_', name.split('/')[-1])
        if not re.fullmatch(r'[A-Za-z_$][\w$]*', binding) or binding in ('default', 'class', 'import', 'new', 'var', 'let', 'const', 'function'):
            return None
        if symbol:
            return f"import {{ {symbol}" + (f' as {alias}' if alias else '') + f" }} from '{name}';", name
        return (f"import {binding} from '{name}';" if default else f"import * as {binding} from '{name}';"), name
    if lang == 'dart':
        entry = DART_ENTRIES.get(name.lower(), name if re.fullmatch(r'[a-z][\w/]*/[\w/]+\.dart', name) else '')
        if not entry:
            return None
        return f"import 'package:{entry}'" + (f' as {alias}' if alias else '') + (f' show {symbol}' if symbol else '') + ';', entry.split('/')[0]
    if lang == 'go' and not symbol and not any(char in name for char in "'\"\\"):
        name = GO_PACKAGES.get(name.lower(), name)
        return 'import ' + (alias + ' ' if alias else '') + f'"{name}"', name
    if lang == 'rust' and re.fullmatch(r'[\w-]+(?:::[\w:]+)?', name):
        name = name.replace('-', '_')
        return 'use ' + name + ('::' + symbol if symbol else '') + (f' as {alias}' if alias else '') + ';', name
    if lang in ('java', 'kotlin') and re.fullmatch(r'[\w.]+', name):
        name = JAVA_PACKAGES.get(name.lower(), name)
        wildcard = not symbol and not name.split('.')[-1][0].isupper()
        if alias and (lang == 'java' or wildcard):
            return None
        return 'import ' + name + ('.' + symbol if symbol else '.*' if wildcard else '') + (
            ' as ' + alias if alias else '') + (';' if lang == 'java' else ''), name
    if lang == 'csharp' and re.fullmatch(r'[\w.]+', name) and not symbol:
        name = CSHARP_NAMESPACES.get(name.lower(), name)
        return 'using ' + (alias + ' = ' if alias else '') + name + ';', name
    if lang in ('c', 'cpp'):
        name = (CPP_HEADERS if lang == 'cpp' else C_HEADERS).get(name.lower(), name)
    if lang in ('c', 'cpp') and not symbol and not alias and re.fullmatch(r'[\w./-]+', name) and (
            name.endswith(('.h', '.hpp', '.hxx')) or lang == 'cpp' and name in (
                'vector', 'string', 'iostream', 'memory', 'map', 'set', 'algorithm', 'thread', 'filesystem', 'optional', 'tuple')):
        return f'#include <{name}>', name
    if lang == 'php' and re.fullmatch(r'[\w\\]+', name):
        return 'use ' + name + ('\\' + symbol if symbol else '') + (f' as {alias}' if alias else '') + ';', name
    if lang == 'ruby' and not symbol and not alias and re.fullmatch(r'[\w./-]+', name):
        return f'require "{name}"', name
    if lang == 'lua' and not symbol and re.fullmatch(r'[\w./-]+', name):
        binding = alias or re.sub(r'\W+', '_', name.split('/')[-1])
        return f'local {binding} = require("{name}")', name
    if lang == 'powershell' and not symbol and not alias and re.fullmatch(r'[\w./\\-]+', name):
        return f'Import-Module -Name "{name}"', name
    if lang == 'swift' and not alias and not symbol and re.fullmatch(r'[\w.]+', name):
        return 'import ' + name, name
    if lang == 'r' and not symbol and not alias and re.fullmatch(r'[\w.]+', name):
        return f'library("{name}")', name
    if lang == 'julia' and not alias and re.fullmatch(r'[\w.]+', name):
        return 'using ' + name + (': ' + symbol if symbol else ''), name
    if lang == 'bash' and not symbol and not alias and re.fullmatch(r'[\w./-]+', name) and name.endswith('.sh'):
        return f'source "{name}"', name
    return None


def catalog_import(intent: str, lang: str) -> tuple[str, str, str] | None:
    named = _named_requests(intent)
    # O nome informado tem prioridade sobre palavras da finalidade, como
    # "importar requests para consultar o YouTube".
    if named and not any(fold(name) in ('youtube', 'you-tube') for name, _, _ in named):
        found = [_named_import(*request, lang) for request in named]
        if all(found) and all(import_prefix(item[0], lang) for item in found):
            return '\n'.join(item[0] for item in found), ', '.join(item[1] for item in found), 'nomes informados pelo usuário'
        return None
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
