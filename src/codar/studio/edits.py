"""Alvos imutáveis: a resposta aplica-se ao documento e à seleção de quando o pedido foi feito."""

from __future__ import annotations

import re
import ast
from dataclasses import dataclass

from codar.textutil import fold


def wants_edit(intent: str) -> bool:
    """Sem seleção, apenas um pedido explícito de edição autoriza substituir o arquivo aberto."""
    return bool(re.match(r"^(?:por favor[, ]+)?(?:corri[gj]\w*|consert\w*|arrum\w*|refator\w*|reescrev\w*|"
                         r"substitu\w*|sobrescrev\w*|complet\w*|melhor\w*|otimiz\w*|ajust\w*|"
                         r"fix|rewrite|refactor|replace|overwrite|complete|improve|optimize)\b", fold(intent)))


def offset(text: str, location: tuple[int, int]) -> int:
    row, col = location
    return sum(len(ln) + 1 for ln in text.split("\n")[:row]) + col


@dataclass(frozen=True)
class EditTarget:
    text: str
    start: tuple[int, int]
    end: tuple[int, int]
    mode: str

    @classmethod
    def capture(cls, text, mode, cursor, selection, row=None, original=None):
        lines = text.split("\n")
        if mode == "edit":
            start, end = sorted(selection)
            if start == end:
                start, end = (0, 0), (len(lines) - 1, len(lines[-1]))
        elif mode in ("line", "block"):
            start, end = sorted(selection)
            if start == end:
                row = cursor[0] if row is None else row
                last = row + (original.count("\n") if original is not None else 0)
                start, end = (row, 0), (last, len(lines[last]))
        else:
            row = cursor[0]
            col = len(lines[row]) if lines[row].strip() else 0
            start, end = (row, col), (row, len(lines[row]))
        return cls(text, start, end, mode)

    @property
    def before(self):
        return self.text[:offset(self.text, self.start)][-6000:]

    @property
    def after(self):
        return self.text[offset(self.text, self.end):][:3000]

    @property
    def selected(self):
        return self.text[offset(self.text, self.start):offset(self.text, self.end)]

    def apply(self, body: str, imports: list[str], lang: str, indent: str) -> tuple[str, int, int]:
        """Calcula uma única substituição (corpo + imports), desfeita com um Ctrl+Z."""
        first, last = offset(self.text, self.start), offset(self.text, self.end)
        start_row = self.start[0]
        if self.mode == "insert" and not body.strip() and imports:
            # Importar pela barra de intenção não insere uma linha vazia no
            # meio do código, nem altera a posição de instruções existentes.
            text, added = hoist_imports(self.text, imports, lang)
            return text, start_row + added, start_row + added
        if self.mode == "insert":
            body = "\n".join(indent + ln if ln.strip() else ln for ln in body.split("\n"))
            if self.start[1]:
                body = "\n" + body
                start_row += 1
            elif last == len(self.text):
                body += "\n"
        elif self.mode in ("edit", "line", "block"):
            if self.start[1] and indent and body.startswith(indent):
                body = body[len(indent):]  # indentação da primeira linha já existe fora da seleção
            if self.selected.endswith("\n") and not body.endswith("\n"):
                body += "\n"
        text = self.text[:first] + body + self.text[last:]
        text, added = hoist_imports(text, imports, lang)
        count = body.strip("\n").count("\n")
        return text, start_row + added, start_row + added + count


def hoist_imports(text: str, imports: list[str], lang: str) -> tuple[str, int]:
    existing = {ln.strip() for ln in text.split("\n")}
    missing = []
    for imp in imports:
        if imp.strip() not in existing:
            missing.append(imp)
            existing.add(imp.strip())
    if not missing:
        return text, 0
    if lang == "powershell":
        directives = [imp for imp in missing if imp.lower().startswith(("using ", "#requires"))]
        modules = [imp for imp in missing if imp not in directives]
        text, first = _insert_imports(text, directives, 0) if directives else (text, 0)
        text, last = _insert_imports(text, modules, powershell_param_end(text)) if modules else (text, 0)
        return text, first + last
    lines = text.split("\n")
    at = 0
    if lang == "python":
        try:
            module = ast.parse(text)
            if module.body and isinstance(module.body[0], ast.Expr) and isinstance(module.body[0].value, ast.Constant) \
                    and isinstance(module.body[0].value.value, str):
                at = module.body[0].end_lineno or 0
        except SyntaxError:
            pass
    while at < len(lines) and (lines[at].startswith(("#!", "package ", "<?php")) or
                               (lang == "python" and lines[at].startswith("from __future__")) or
                               (lang == "dart" and lines[at].startswith(("library ", "//")))):
        at += 1
    return _insert_imports(text, missing, at)


def powershell_param_end(text: str) -> int:
    """Import-Module deve vir depois do param do script; using/#Requires vêm antes dos atributos."""
    masked = re.sub(r"'(?:(?:'')|[^'])*'|\"(?:`.|[^\"])*\"|#[^\n]*", lambda m: " " * len(m[0])
                    if "\n" not in m[0] else "\n".join(" " * len(s) for s in m[0].split("\n")), text)
    match = re.search(r"(?im)^\s*param\s*\(", masked)
    if not match:
        return 0
    prefix = re.sub(r"(?im)^\s*using[^\n]*", "", masked[:match.start()])
    prefix = re.sub(r"\[[\s\S]*?\]", "", prefix)
    if prefix.strip():
        return 0  # não move imports para o param de uma função
    depth = 1
    for i in range(match.end(), len(masked)):
        depth += (masked[i] == "(") - (masked[i] == ")")
        if depth == 0:
            return text.count("\n", 0, i + 1) + 1
    return 0


def _insert_imports(text: str, missing: list[str], at: int) -> tuple[str, int]:
    lines = text.split("\n")
    block = "\n".join(missing) + "\n"
    if at < len(lines) and lines[at].strip() and not lines[at].startswith(
            ("import", "from", "use", "#include", "using", "require")):
        block += "\n"
    lines.insert(at, block.rstrip("\n"))
    # Mantém a linha em branco gerada acima.
    if block.endswith("\n\n"):
        lines.insert(at + 1, "")
    return "\n".join(lines), block.count("\n")
