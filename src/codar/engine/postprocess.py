"""Pós-processamento determinístico: limpeza da saída do SLM, imports, reindentação."""

from __future__ import annotations

import ast
import re
import textwrap

from codar.textutil import fold

_FENCE = re.compile(r"^\s*```[\w+#-]*\s*$")


def clean_generation(text: str, lang: str) -> str:
    lines = text.replace("\r\n", "\n").split("\n")
    while lines and (not lines[0].strip() or _FENCE.match(lines[0])):
        lines.pop(0)
    if lines and lines[0].strip().lower() in (lang, "python", "py", "go", "rust", "bash", "powershell"):
        lines.pop(0)
    out: list[str] = []
    repeat = 0
    for ln in lines:
        if _FENCE.match(ln):
            break
        if out and ln.strip() and ln == out[-1]:
            repeat += 1
            if repeat >= 3:
                continue
        else:
            repeat = 0
        out.append(ln.rstrip())
    code = textwrap.dedent("\n".join(out)).strip("\n")
    if lang == "python":
        code = repair_python(code)
    return code


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
    while i < len(lines):
        ln = lines[i]
        if not ln.strip():
            i += 1
            continue
        if lang == "go" and ln.strip() == "import (":
            j = i + 1
            while j < len(lines) and lines[j].strip() != ")":
                if lines[j].strip():
                    imports.append(f"import {lines[j].strip()}")
                j += 1
            i = j + 1
            continue
        if rx.match(ln) and not ln.startswith((" ", "\t")):
            imports.append(ln.rstrip())
            i += 1
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
