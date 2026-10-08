"""Léxico mínimo multi-linguagem: mascara comentários/strings preservando posições e acha corpos de laço.

Mascarar evita falsos positivos (uma regra sobre `eval(` não dispara num comentário) sem
precisar de um parser completo por linguagem. Custo: uma passada O(n) por snippet.
"""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class Syntax:
    line: tuple[str, ...] = ()
    block: tuple[tuple[str, str], ...] = ()
    quotes: tuple[str, ...] = ('"', "'")
    triple: bool = False  # aspas triplas (Python)
    raw_quotes: tuple[str, ...] = ()  # sem escapes (crase do Go, aspas simples do bash)
    escape: str = "\\"
    hash_word_start: bool = False  # bash: '#' só é comentário no início de uma palavra


_C = Syntax(line=("//",), block=(("/*", "*/"),))
SYNTAX: dict[str, Syntax] = {
    "python": Syntax(line=("#",), triple=True),
    "javascript": Syntax(line=("//",), block=(("/*", "*/"),), quotes=('"', "'", "`")),
    "typescript": Syntax(line=("//",), block=(("/*", "*/"),), quotes=('"', "'", "`")),
    "go": Syntax(line=("//",), block=(("/*", "*/"),), quotes=('"', "'"), raw_quotes=("`",)),
    "rust": _C, "java": _C, "c": _C, "cpp": _C, "csharp": _C, "kotlin": _C, "swift": _C,
    "php": Syntax(line=("//", "#"), block=(("/*", "*/"),)),
    "ruby": Syntax(line=("#",)),
    "bash": Syntax(line=("#",), quotes=('"',), raw_quotes=("'",), hash_word_start=True),
    "powershell": Syntax(line=("#",), block=(("<#", "#>"),), quotes=('"',), raw_quotes=("'",), escape="`"),
    "lua": Syntax(line=("--",), block=(("--[[", "]]"),)),
    "sql": Syntax(line=("--",), block=(("/*", "*/"),), quotes=("'",)),
    "yaml": Syntax(line=("#",)),
    "dockerfile": Syntax(line=("#",)),
}


def _blank(s: str) -> str:
    return "".join("\n" if c == "\n" else " " for c in s)


def mask(code: str, lang: str, strings: bool = False) -> str:
    """Remove comentários (e o conteúdo de strings, se strings=True), mantendo comprimento e quebras de linha."""
    syn = SYNTAX.get(lang)
    if syn is None:
        return code
    out: list[str] = []
    i, n = 0, len(code)
    while i < n:
        matched = False
        for start, end in syn.block:
            if code.startswith(start, i):
                j = code.find(end, i + len(start))
                j = n if j < 0 else j + len(end)
                out.append(_blank(code[i:j]))
                i, matched = j, True
                break
        if matched:
            continue
        for tok in syn.line:
            if code.startswith(tok, i) and (not syn.hash_word_start or i == 0 or code[i - 1] in " \t\n;(|&"):
                if syn.hash_word_start and code.startswith("#!", i) and (i == 0 or code[i - 1] == "\n"):
                    break
                j = code.find("\n", i)
                j = n if j < 0 else j
                out.append(" " * (j - i))
                i, matched = j, True
                break
        if matched:
            continue
        ch = code[i]
        if syn.triple and code.startswith(('"""', "'''"), i):
            q = code[i:i + 3]
            j = code.find(q, i + 3)
            j = n if j < 0 else j + 3
            out.append(q + (_blank(code[i + 3:j - 3]) if strings else code[i + 3:j - 3]) + (q if j <= n else ""))
            i = j
            continue
        if ch in syn.quotes or ch in syn.raw_quotes:
            raw = ch in syn.raw_quotes
            j = i + 1
            while j < n:
                c = code[j]
                if not raw and c == syn.escape:
                    j += 2
                    continue
                if c == ch:
                    if lang == "powershell" and raw and j + 1 < n and code[j + 1] == ch:
                        j += 2
                        continue
                    break
                if c == "\n" and ch not in ("`",) and lang not in ("bash", "powershell"):
                    break
                j += 1
            body = code[i + 1:min(j, n)]
            out.append(ch + (_blank(body) if strings else body) + (ch if j < n and code[j] == ch else ""))
            i = j + 1 if j < n and code[j] == ch else j
            continue
        out.append(ch)
        i += 1
    return "".join(out)


_LOOP_HEAD = re.compile(r"\b(for|foreach|while|until|loop|do)\b|\.(forEach|map|each|times|ForEach)\b|"
                        r"ForEach-Object|\|\s*%\s*\{")
_LUA_OPEN = re.compile(r"\b(function|if|do|repeat)\b")
_LUA_CLOSE = re.compile(r"\b(end|until)\b")


def loop_lines(code: str, lang: str) -> set[int]:
    """Linhas (1-based) dentro de corpos de laço."""
    if lang == "python":
        return _py_loop_lines(code)
    masked = mask(code, lang, strings=True)
    lines = masked.split("\n")
    inside: set[int] = set()
    if lang == "bash":
        depth_stack: list[bool] = []
        for no, ln in enumerate(lines, 1):
            if any(depth_stack):
                inside.add(no)
            for tok in re.findall(r"\b(do|done)\b", ln):
                if tok == "do":
                    depth_stack.append(bool(re.search(r"\b(for|while|until)\b", ln)) or bool(depth_stack and depth_stack[-1]))
                elif depth_stack:
                    depth_stack.pop()
        return inside
    if lang in ("lua", "ruby"):
        stack: list[bool] = []
        for no, ln in enumerate(lines, 1):
            if any(stack):
                inside.add(no)
            is_loop = bool(re.search(r"\b(for|while|until|loop)\b|\.(each|times|map)\b", ln))
            opens = len(_LUA_OPEN.findall(ln)) if lang == "lua" else len(re.findall(r"\b(do|def|if|unless|case|begin|class|module|while|until)\b", ln)) - (1 if re.search(r"\b(while|until)\b.*\bdo\b", ln) else 0)
            for k in range(opens):
                stack.append(is_loop and k == opens - 1)
            for _ in _LUA_CLOSE.findall(ln):
                if stack:
                    stack.pop()
        return inside
    # linguagens com chaves
    depth = 0
    loop_depths: list[int] = []
    pending = False
    for no, ln in enumerate(lines, 1):
        if loop_depths:
            inside.add(no)
        if _LOOP_HEAD.search(ln):
            pending = True
        for ch in ln:
            if ch == "{":
                depth += 1
                if pending:
                    loop_depths.append(depth)
                    pending = False
            elif ch == "}":
                if loop_depths and loop_depths[-1] == depth:
                    loop_depths.pop()
                depth = max(0, depth - 1)
        if pending and ln.rstrip().endswith(";"):
            pending = False
    return inside


def _py_loop_lines(code: str) -> set[int]:
    import ast

    try:
        tree = ast.parse(code)
    except SyntaxError:
        return set()
    out: set[int] = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.For, ast.While, ast.AsyncFor)):
            for stmt in node.body:
                out.update(range(stmt.lineno, (getattr(stmt, "end_lineno", None) or stmt.lineno) + 1))
        elif isinstance(node, (ast.ListComp, ast.SetComp, ast.DictComp, ast.GeneratorExp)):
            out.update(range(node.lineno, (getattr(node, "end_lineno", None) or node.lineno) + 1))
    return out
