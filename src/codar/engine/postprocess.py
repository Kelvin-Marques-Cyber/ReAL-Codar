"""Pós-processamento determinístico: limpeza da saída do SLM, imports, reindentação."""

from __future__ import annotations

import ast
import re
import textwrap

from codar.textutil import fold

_FENCE = re.compile(r"^[ \t]*(?P<mark>`{3,}|~{3,})(?P<label>[\w+#.-]*)[ \t]*$")


def clean_generation(text: str, lang: str, *, repair: bool = False) -> str:
    """Extrai codigo puro OU um bloco Markdown inteiro sem descartar seu conteudo.

    Respostas pequenas podem começar com ```python (nao devem ser
    interrompidas pelo marcador). Se houver prosa antes do bloco, a prosa
    nao entra no editor. Se nao houver bloco, mantem o texto para validar.
    """
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    # Só remove metadados na borda: <think> pode ser conteúdo de uma string.
    text = re.sub(r"\A\s*<think>.*?</think>\s*", "", text, flags=re.S)
    text = re.sub(r"(?:<\|im_end\|>|<\|endoftext\|>)\s*\Z", "", text)
    lines = text.split("\n")
    first = next((i for i, line in enumerate(lines) if _FENCE.fullmatch(line)), None)
    if first is not None:
        prefix = "\n".join(lines[:first])
        # Uma cerca dentro de uma string/expressão é código, não Markdown.
        prefix_is_code = bool(re.search(r"[=(){};]|^\s*(?:def|class|import|from|const|let|var)\b", prefix, re.M))
        if not prefix_is_code:
            from codar import langs

            blocks: list[str] = []
            i = first
            while i < len(lines):
                opener = _FENCE.fullmatch(lines[i])
                if not opener:
                    i += 1
                    continue
                mark, label = opener['mark'], opener['label']
                j = i + 1
                while j < len(lines) and not re.fullmatch(r"[ \t]*" + re.escape(mark[0]) +
                                                         "{" + str(len(mark)) + r",}[ \t]*", lines[j]):
                    j += 1
                resolved = langs.try_resolve(label)
                if not label or (resolved and resolved.id == lang):
                    blocks.append(textwrap.dedent("\n".join(lines[i + 1:j])).strip("\n"))
                i = j + 1
            # Uma resposta cercada em outra linguagem nunca vira código da linguagem alvo.
            text = "\n\n".join(blocks)
    # Não poda repetições, imports, linhas em branco ou o fim de uma função.
    # Qualquer reparo que descarte código exige opt-in explícito fora do pipeline.
    code = textwrap.dedent(text).strip("\n")
    if repair and lang == "python":
        code = repair_python(code)
    return code


def strip_context_echo(code: str, before: str = "", after: str = "") -> str:
    """Remove sobreposições contíguas com as bordas do contexto, nunca linhas soltas em qualquer lugar.

    Uma instrução repetida pode ser intencional: só remove duas ou mais linhas não vazias.
    Não se aplica a edições, cuja resposta precisa preservar a seleção inteira.
    """
    lines = code.split("\n")
    left, right = before.rstrip("\n").split("\n"), after.lstrip("\n").split("\n")
    for size in range(min(len(left), len(lines)), 1, -1):
        if sum(bool(ln.strip()) for ln in lines[:size]) >= 2 and lines[:size] == left[-size:]:
            lines = lines[size:]
            break
    for size in range(min(len(right), len(lines)), 1, -1):
        if sum(bool(ln.strip()) for ln in lines[-size:]) >= 2 and lines[-size:] == right[:size]:
            lines = lines[:-size]
            break
    return "\n".join(lines).strip("\n")


def repair_python(code: str) -> str:
    """Se a geração foi truncada no meio de uma instrução, recua até o último ponto sintaticamente válido."""
    try:
        ast.parse(code)
        return code
    except SyntaxError:
        pass
    lines = code.split("\n")
    for cut in range(len(lines) - 1, max(0, len(lines) - 25), -1):
        candidate = "\n".join(lines[:cut]).rstrip()
        if not candidate:
            break
        try:
            ast.parse(candidate)
            return candidate
        except SyntaxError:
            continue
    return code


def python_ok(code: str) -> bool:
    try:
        ast.parse(code)
        return True
    except SyntaxError:
        return False


_IMPORT_RX = {
    "python": re.compile(r"^(?:import\s+\w|from\s+[\w.]+\s+import\s)"),
    "javascript": re.compile(r"^(?:import\s.+from\s|import\s+['\"]|const\s+\w+\s*=\s*require\()"),
    "typescript": re.compile(r"^(?:import\s.+from\s|import\s+['\"]|import\s+type\s)"),
    "go": re.compile(r"^import\s"),
    "rust": re.compile(r"^(?:use\s+[\w:{}, *]+;|extern\s+crate\s)"),
    "java": re.compile(r"^import\s+[\w.*]+;"),
    "kotlin": re.compile(r"^import\s+[\w.*]+"),
    "c": re.compile(r"^#\s*include\s"),
    "cpp": re.compile(r"^#\s*include\s"),
    "csharp": re.compile(r"^using\s+[\w.]+;"),
    "php": re.compile(r"^(?:use\s+[\w\\]+;|require(?:_once)?\s)"),
    "ruby": re.compile(r"^require(?:_relative)?\s"),
    "lua": re.compile(r"^local\s+\w+\s*=\s*require\s*\(?"),
    "powershell": re.compile(r"^(?:Import-Module\s|using\s+(?:module|namespace)\s|#Requires\s)", re.I),
    "swift": re.compile(r"^import\s+\w+"),
    "dart": re.compile(r"^import\s+['\"]"),
    "julia": re.compile(r"^(?:using|import)\s+\w"),
    "r": re.compile(r"^(?:library|require)\("),
    "bash": re.compile(r"^(?:source|\.)\s+\S"),
}


def split_imports(code: str, lang: str) -> tuple[list[str], str]:
    """Separa imports do topo do snippet do corpo (editores içam os imports para o topo do arquivo)."""
    rx = _IMPORT_RX.get(lang)
    if not rx:
        return [], code
    lines = code.split("\n")
    imports: list[str] = []
    i = 0
    if lang == "go" and lines and lines[0].startswith("package "):
        return [], code
    if lang == "python":
        try:
            tree = ast.parse(code)
        except SyntaxError:
            return [], code
        end = 0
        for node in tree.body:
            if not isinstance(node, (ast.Import, ast.ImportFrom)):
                break
            if any(line.strip() for line in lines[end:node.lineno - 1]):
                break  # comentários/documentação não desaparecem ao içar imports
            # Separar só metade de uma linha apagaria a instrução após `;`.
            last = node.end_lineno or node.lineno
            trailing = lines[last - 1][node.end_col_offset:]
            if trailing.strip() and not trailing.lstrip().startswith('#'):
                break
            imports.append("\n".join(lines[node.lineno - 1:last]))
            end = last
        return imports, "\n".join(lines[end:]).strip("\n")
    while i < len(lines):
        ln = lines[i]
        if not ln.strip():
            i += 1
            continue
        if lang == "go" and ln.strip() == "import (":
            j = i + 1
            while j < len(lines) and lines[j].strip() != ")":
                j += 1
            if j == len(lines):
                break  # um grupo aberto continua no corpo para validação, sem perder linhas
            from codar.engine.imports import import_prefix

            group = import_prefix('\n'.join(lines[i:j + 1]), lang)
            if not group:
                break
            imports.extend(group)
            i = j + 1
            continue
        if (rx.match(ln) or lang in ('javascript', 'typescript') and re.match(r'^import\b', ln)) and not ln.startswith((" ", "\t")):
            from codar.engine.imports import import_prefix, is_native_import

            # O recognizer comum aceita declarações multilinha e aliases, e
            # impede içar código que compartilha a linha com uma importação.
            j = i + 1
            while j <= len(lines):
                chunk = "\n".join(lines[i:j])
                if is_native_import(chunk, lang):
                    imports.extend(import_prefix(chunk, lang))
                    i = j
                    break
                j += 1
            else:
                break
            continue
        break
    body = "\n".join(lines[i:]).strip("\n")
    return imports, body


def join_imports(imports: list[str], body: str, lang: str) -> str:
    if not imports:
        return body
    if lang == "go" and len(imports) > 1:
        specs = sorted({imp[len("import "):].strip() for imp in imports}, key=lambda x: x.strip('"'))
        head = "import (\n" + "\n".join(f"\t{s}" for s in specs) + "\n)"
    else:
        head = "\n".join(imports)
    return f"{head}\n\n{body}" if body else head


def detect_indent_unit(code: str) -> str:
    widths = []
    for ln in code.split("\n"):
        if ln.startswith("\t"):
            return "\t"
        stripped = len(ln) - len(ln.lstrip(" "))
        if stripped and ln.strip():
            widths.append(stripped)
    if not widths:
        return "    "
    unit = min(widths)
    return " " * (unit if unit in (2, 3, 4, 8) else 4)


def reindent(code: str, unit: str | None = None, base: str = "", src_unit: str | None = None) -> str:
    """Converte a indentação para a unidade do editor e aplica a indentação base da linha original."""
    src = src_unit or detect_indent_unit(code)
    out = []
    for ln in code.split("\n"):
        if not ln.strip():
            out.append("")
            continue
        depth = 0
        rest = ln
        while True:
            if src == "\t" and rest.startswith("\t"):
                rest = rest[1:]
            elif src != "\t" and rest.startswith(src):
                rest = rest[len(src):]
            else:
                break
            depth += 1
        out.append(base + (unit if unit is not None else src) * depth + rest)
    return "\n".join(out)


def prune_imports(code: str, lang: str) -> str:
    """Remove imports que o código gerado não usa (e sempre `import *`). Só Python: análise pela AST, sem custo de IA."""
    if lang != "python":
        return code
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return code
    # Um trecho contendo somente importações é uma resposta completa: as dependências
    # podem ser usadas no arquivo aberto, mesmo que não haja referências no snippet.
    if tree.body and all(isinstance(node, (ast.Import, ast.ImportFrom)) for node in tree.body):
        return code
    used = {n.id for n in ast.walk(tree) if isinstance(n, ast.Name)}
    used |= {n.value.id for n in ast.walk(tree) if isinstance(n, ast.Attribute) and isinstance(n.value, ast.Name)}
    drop: set[int] = set()
    for node in tree.body:
        if isinstance(node, ast.ImportFrom):
            names = [a.asname or a.name for a in node.names]
            if "*" in names or not any(n in used for n in names):
                drop.update(range(node.lineno, (node.end_lineno or node.lineno) + 1))
        elif isinstance(node, ast.Import):
            names = [(a.asname or a.name).split(".")[0] for a in node.names]
            if not any(n in used for n in names):
                drop.update(range(node.lineno, (node.end_lineno or node.lineno) + 1))
    if not drop:
        return code
    return "\n".join(ln for i, ln in enumerate(code.split("\n"), 1) if i not in drop).strip("\n")



# Valor literal "de exemplo": só constantes (nunca chamadas sem argumento como input() nem expressões com nomes).
_ATOM = r"""(?:-?\d+(?:\.\d+)?[fFLdDmM]?|"(?:[^"\\]|\\.)*"|'(?:[^'\\]|\\.)*'|true|false|True|False|None|null|nil|undefined|\$true|\$false|\$null)"""
_ITEM = rf"""(?:(?:{_ATOM}|[A-Za-z_]\w*)\s*(?::|=>|=)\s*)?{_ATOM}"""
_SEQ0 = rf"""\s*(?:{_ITEM}\s*[,;]?\s*)*"""
_SEQ1 = rf"""\s*{_ITEM}\s*[,;]?\s*(?:{_ITEM}\s*[,;]?\s*)*"""
_LITERAL = (rf"""(?:{_ATOM}(?:\.\w+\(\))?|\[{_SEQ0}\]|\{{{_SEQ0}\}}|@\({_SEQ0}\)|\({_SEQ0}\)|vec!\[{_SEQ0}\]"""
            rf"""|(?:\[\]|map\[\w+\])[\w.*]+\{{{_SEQ0}\}}|new\s+[\w.<>]+(?:\[\])?\s*(?:\(\))?\s*\{{{_SEQ0}\}}"""
            rf"""|[\w.:]+(?:<[\w,\s]*>)?\({_SEQ1}\))""")
_SAMPLE_LINE = re.compile(  # declaração/atribuição simples (sem `.`, `+=`, `==`) de um valor constante
    r"^\s*(?P<lhs>[\w$\s:<>\[\],*&]+?)(?<![-+*/%&|^!<>.:\s])\s*(?::=|=)\s*"
    rf"(?:{_LITERAL}|{_ATOM}(?:\s*,\s*{_ATOM})+)\s*;?\s*$")
_ASSIGN_VERBS = re.compile(r"\b(?:zerar|zere|resetar|reset|inicializar|inicialize|init|definir|defina|define|atribuir|"
                           r"atribua|criar|crie|declarar|declare|limpar|limpe|esvaziar|esvazie|igual|vale|valendo|"
                           r"recebe|receber|set|let)\b|=")


def prune_sample_data(code: str, intent: str) -> str:
    """Modo literal: remove linhas iniciais que inventam dados de exemplo para variáveis citadas na frase
    (`const itens = [1, 2, 3];` antes de `itens.reverse();`). Mantém se a frase pede uma atribuição."""
    folded = fold(intent)
    if _ASSIGN_VERBS.search(folded):
        return code
    mentioned = set(re.findall(r"[a-z_][a-z0-9_]*", folded))
    lines = code.split("\n")
    while len(lines) > 1:
        m = _SAMPLE_LINE.match(lines[0])
        if not m or not {fold(w) for w in re.findall(r"[A-Za-z_]\w*", m.group("lhs"))} & mentioned:
            break
        lines.pop(0)
    return "\n".join(lines)
