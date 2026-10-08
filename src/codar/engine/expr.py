"""Expressões em linguagem natural (PT/EN) -> AST -> código por linguagem.

"x maior ou igual a 10 e nome diferente de 'Ana'"  ->  ("bin","&&",("bin",">=",x,10),("bin","!=",nome,"Ana"))
"""

from __future__ import annotations

import re
from typing import Any

from codar.textutil import fold

Ast = tuple

_SCAN = re.compile(
    r"""(?P<str>"(?:[^"\\]|\\.)*"|'(?:[^'\\]|\\.)*'|`[^`]*`)
      |(?P<num>\d+(?:\.\d+)?)
      |(?P<op>===|!==|==|!=|<>|<=|>=|&&|\|\||//|\*\*|[-+*/%<>!=])
      |(?P<word>[^\W\d]\w*)
      |(?P<punct>[()\[\],.])
      |(?P<ws>\s+)
      |(?P<other>.)""",
    re.X,
)

# Frases (palavras já normalizadas) -> operador.  Ordem: mais longas primeiro.
_PHRASES: list[tuple[tuple[str, ...], str]] = sorted(
    [
        (("maior", "ou", "igual", "a"), ">="), (("maior", "ou", "igual", "que"), ">="),
        (("greater", "than", "or", "equal", "to"), ">="), (("at", "least"), ">="),
        (("menor", "ou", "igual", "a"), "<="), (("menor", "ou", "igual", "que"), "<="),
        (("less", "than", "or", "equal", "to"), "<="), (("at", "most"), "<="),
        (("maior", "do", "que"), ">"), (("maior", "que"), ">"), (("greater", "than"), ">"),
        (("acima", "de"), ">"), (("more", "than"), ">"), (("bigger", "than"), ">"),
        (("menor", "do", "que"), "<"), (("menor", "que"), "<"), (("less", "than"), "<"),
        (("abaixo", "de"), "<"), (("smaller", "than"), "<"), (("fewer", "than"), "<"),
        (("diferente", "de"), "!="), (("not", "equal", "to"), "!="), (("nao", "igual", "a"), "!="),
        (("igual", "a"), "=="), (("equal", "to"), "=="), (("equals",), "=="), (("igual",), "=="),
        (("dividido", "por"), "/"), (("divided", "by"), "/"),
        (("multiplicado", "por"), "*"), (("multiplied", "by"), "*"), (("vezes",), "*"), (("times",), "*"),
        (("mais",), "+"), (("plus",), "+"), (("menos",), "-"), (("minus",), "-"),
        (("mod",), "%"), (("modulo",), "%"),
        (("e",), "&&"), (("and",), "&&"), (("ou",), "||"), (("or",), "||"),
        (("nao",), "!"), (("not",), "!"),
    ],
    key=lambda p: -len(p[0]),
)
_COPULA = {"é", "for", "is", "está", "estiver", "seja", "are", "be", "fosse", "esta"}
_TRUE = {"verdadeiro", "true", "verdade", "sim"}
_FALSE = {"falso", "false"}
_NULL = {"nulo", "null", "none", "nil", "nada", "nenhum"}
_SUFFIX = {  # predicados pós-fixos: "x é par" -> x % 2 == 0
    "par": [("op", "%"), ("num", "2"), ("op", "=="), ("num", "0")],
    "even": [("op", "%"), ("num", "2"), ("op", "=="), ("num", "0")],
    "impar": [("op", "%"), ("num", "2"), ("op", "!="), ("num", "0")],
    "odd": [("op", "%"), ("num", "2"), ("op", "!="), ("num", "0")],
    "positivo": [("op", ">"), ("num", "0")], "positive": [("op", ">"), ("num", "0")],
    "negativo": [("op", "<"), ("num", "0")], "negative": [("op", "<"), ("num", "0")],
}


class ExprError(ValueError):
    pass


def _lex(text: str) -> list[tuple[str, str, str]]:
    """[(tipo, valor original, valor normalizado)]."""
    out = []
    for m in _SCAN.finditer(text):
        kind = m.lastgroup
        val = m.group()
        if kind == "ws":
            continue
        if kind == "other":
            raise ExprError(f"símbolo inesperado {val!r}")
        out.append((kind, val, fold(val) if kind == "word" else val))
    return out


def tokenize(text: str) -> list[tuple[str, str]]:
    raw = _lex(text)
    toks: list[tuple[str, str]] = []
    i = 0
    while i < len(raw):
        kind, val, norm = raw[i]
        if kind == "word":
            if val.lower() in _COPULA and not (val == "e"):
                i += 1
                continue
            matched = False
            for phrase, op in _PHRASES:
                n = len(phrase)
                seq = [r[2] for r in raw[i:i + n] if r[0] == "word"]
                if len(seq) == n and all(r[0] == "word" for r in raw[i:i + n]) and tuple(seq) == phrase:
                    toks.append(("op", op))
                    i += n
                    matched = True
                    break
            if matched:
                continue
            if norm in _TRUE:
                toks.append(("bool", "true"))
            elif norm in _FALSE:
                toks.append(("bool", "false"))
            elif norm in _NULL:
                toks.append(("null", "null"))
            elif norm in _SUFFIX and toks and toks[-1][0] in ("id", "num", ")", "]"):
                toks.extend(_SUFFIX[norm])
            else:
                toks.append(("id", _ident(val)))
        elif kind == "op":
            toks.append(("op", {"===": "==", "!==": "!=", "<>": "!=", "=": "=="}.get(val, val)))
        elif kind == "punct":
            toks.append((val, val))
        elif kind == "str":
            toks.append(("str", _unquote(val)))
        else:
            toks.append((kind, val))
        i += 1
    return toks


def _ident(word: str) -> str:
    return fold(word) if not word.isascii() else word


def _unquote(s: str) -> str:
    body = s[1:-1]
    if s[0] == "`":
        return body
    return re.sub(r"\\(.)", r"\1", body)


# --------------------------------------------------------------------------- parser

_PREC = {"||": 1, "&&": 2, "==": 4, "!=": 4, "<": 5, ">": 5, "<=": 5, ">=": 5,
         "+": 6, "-": 6, "*": 7, "/": 7, "%": 7, "//": 7, "**": 8}


class _Parser:
    def __init__(self, toks: list[tuple[str, str]]):
        self.t = toks
        self.i = 0

    def peek(self, k: int = 0) -> tuple[str, str] | None:
        j = self.i + k
        return self.t[j] if j < len(self.t) else None

    def take(self) -> tuple[str, str]:
        tok = self.peek()
        if tok is None:
            raise ExprError("expressão incompleta")
        self.i += 1
        return tok

    def expect(self, kind: str) -> None:
        tok = self.take()
        if tok[0] != kind:
            raise ExprError(f"esperado {kind!r}, encontrado {tok[1]!r}")

    def parse(self) -> Ast:
        node = self.binary(1)
        if self.peek() is not None:
            raise ExprError(f"sobra na expressão: {self.peek()[1]!r}")
        return node

    def binary(self, min_prec: int) -> Ast:
        left = self.unary()
        while (tok := self.peek()) and tok[0] == "op" and _PREC.get(tok[1], 0) >= min_prec:
            op = tok[1]
            self.take()
            right = self.binary(_PREC[op] + 1)
            left = ("bin", op, left, right)
        return left

    def unary(self) -> Ast:
        tok = self.peek()
        if tok and tok[0] == "op" and tok[1] in ("!", "-"):
            self.take()
            prec = 3 if tok[1] == "!" else 9
            return ("un", tok[1], self.binary(prec) if tok[1] == "!" else self.unary())
        return self.postfix()

    def postfix(self) -> Ast:
        node = self.primary()
        while (tok := self.peek()) and tok[0] in ("(", "[", "."):
            if tok[0] == "(":
                self.take()
                args = self.args(")")
                node = ("call", node, args)
            elif tok[0] == "[":
                self.take()
                idx = self.binary(1)
                self.expect("]")
                node = ("index", node, idx)
            else:
                self.take()
                name = self.take()
                if name[0] != "id":
                    raise ExprError("atributo inválido")
                node = ("attr", node, name[1])
        return node

    def args(self, close: str) -> list[Ast]:
        items: list[Ast] = []
        if self.peek() and self.peek()[0] == close:
            self.take()
            return items
        while True:
            items.append(self.binary(1))
            tok = self.take()
            if tok[0] == close:
                return items
            if tok[0] != ",":
                raise ExprError("esperado ','")

    def primary(self) -> Ast:
        kind, val = self.take()
        if kind == "num":
            return ("num", val)
        if kind == "str":
            return ("str", val)
        if kind == "id":
            return ("id", val)
        if kind == "bool":
            return ("bool", val == "true")
        if kind == "null":
            return ("null",)
        if kind == "(":
            inner = self.binary(1)
            self.expect(")")
            return ("paren", inner)
        if kind == "[":
            return ("list", self.args("]"))
        raise ExprError(f"token inesperado {val!r}")


def parse(text: str) -> Ast:
    toks = tokenize(text)
    if not toks:
        raise ExprError("expressão vazia")
    return _Parser(toks).parse()


def try_parse(text: str) -> Ast | None:
    try:
        return parse(text)
    except ExprError:
        return None


def literal_list(items: list[str]) -> Ast:
    out = []
    for item in items:
        node = try_parse(item)
        out.append(node if node and node[0] in ("num", "str", "bool", "null", "id", "un") else ("str", item.strip()))
    return ("list", out)


# --------------------------------------------------------------------------- tipos

def infer(node: Ast | None) -> str:
    """int | float | str | bool | null | list[T] | dict | ? (desconhecido)."""
    if node is None:
        return "?"
    k = node[0]
    if k == "num":
        return "float" if "." in node[1] else "int"
    if k == "str":
        return "str"
    if k == "bool":
        return "bool"
    if k == "null":
        return "null"
    if k == "paren":
        return infer(node[1])
    if k == "un":
        return "bool" if node[1] == "!" else infer(node[2])
    if k == "list":
        types = {infer(x) for x in node[1]}
        inner = types.pop() if len(types) == 1 else ("?" if types else "?")
        return f"list[{inner}]"
    if k == "dict":
        return "dict"
    if k == "bin":
        op = node[1]
        if op in ("==", "!=", "<", ">", "<=", ">=", "&&", "||"):
            return "bool"
        lt, rt = (("int" if t == "num?" else t) for t in (infer(node[2]), infer(node[3])))
        if "str" in (lt, rt) and op == "+":
            return "str"
        if "float" in (lt, rt) or op == "/":
            return "float" if {lt, rt} <= {"int", "float", "?"} else "?"
        if lt == rt == "int":
            return "int"
        if {lt, rt} <= {"int", "?"}:
            return "num?"  # aritmética com identificadores: provavelmente numérico
        return "?"
    return "?"


def identifiers(node: Any) -> set[str]:
    out: set[str] = set()
    if isinstance(node, tuple):
        if node and node[0] == "id":
            out.add(node[1])
        elif node and node[0] == "call":
            for a in node[2]:
                out |= identifiers(a)
            if node[1][0] != "id":
                out |= identifiers(node[1])
        else:
            for part in node[1:]:
                out |= identifiers(part)
    elif isinstance(node, list):
        for part in node:
            out |= identifiers(part)
    return out


# --------------------------------------------------------------------------- renderização

_BOOL = {
    "python": ("True", "False"), "powershell": ("$true", "$false"),
}
_NULL_LIT = {
    "python": "None", "lua": "nil", "ruby": "nil", "go": "nil", "rust": "None", "powershell": "$null",
    "cpp": "nullptr", "c": "NULL", "php": "null", "bash": '""',
}
_SIGIL = {"php": "$", "powershell": "$"}


def quote(s: str, lang: str) -> str:
    if lang in ("php", "powershell", "bash"):
        if lang == "bash":
            return "'" + s.replace("'", "'\\''") + "'"
        if lang == "php":
            return "'" + s.replace("\\", "\\\\").replace("'", "\\'") + "'"
        return "'" + s.replace("'", "''") + "'"
    esc = s.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n").replace("\t", "\\t")
    if lang == "ruby":
        esc = esc.replace("#{", "\\#{")
    return f'"{esc}"'


def _op(op: str, lang: str) -> str:
    if lang == "python":
        return {"&&": "and", "||": "or"}.get(op, op)
    if lang == "lua":
        return {"&&": "and", "||": "or", "!=": "~="}.get(op, op)
    if lang == "powershell":
        return {"&&": "-and", "||": "-or", "==": "-eq", "!=": "-ne", "<": "-lt", ">": "-gt",
                "<=": "-le", ">=": "-ge", "%": "%"}.get(op, op)
    if lang in ("javascript", "typescript", "php"):
        return {"==": "===", "!=": "!=="}.get(op, op)
    return op


def _len(arg: str, lang: str) -> str:
    return {
        "python": f"len({arg})", "go": f"len({arg})", "javascript": f"{arg}.length",
        "typescript": f"{arg}.length", "rust": f"{arg}.len()", "java": f"{arg}.size()",
        "csharp": f"{arg}.Count", "cpp": f"{arg}.size()", "ruby": f"{arg}.length", "lua": f"#{arg}",
        "php": f"count({arg})", "powershell": f"{arg}.Count", "bash": "${#" + arg.lstrip("$") + "[@]}",
        "c": f"(sizeof {arg} / sizeof {arg}[0])",
    }.get(lang, f"len({arg})")


_LEN_NAMES = {"len", "tamanho", "length", "size", "comprimento", "count"}
_NUM_OPS = ("+", "-", "*", "/", "%", "<", ">", "<=", ">=", "==", "!=")


def _int_lit(node: Ast) -> bool:
    return node[0] == "num" and "." not in node[1]

# divisão de inteiros com resultado decimal precisa de conversão explícita nas linguagens tipadas
_CAST_DIV = {"go": lambda e: f"float64({e})", "rust": lambda e: f"({e} as f64)", "java": lambda e: f"(double) {e}",
             "csharp": lambda e: f"(double){e}", "c": lambda e: f"(double){e}", "cpp": lambda e: f"static_cast<double>({e})"}


class Renderer:
    """Renderiza um AST para uma linguagem. ``arith`` = contexto aritmético do bash ((...))."""

    def __init__(self, lang: str, arith: bool = False, typeof=None):
        self.lang = lang
        self.arith = arith
        self.typeof = typeof

    def __call__(self, node: Ast, parent_prec: int = 0) -> str:
        lang = self.lang
        k = node[0]
        if k == "num":
            return node[1]
        if k == "str":
            return quote(node[1], lang)
        if k == "id":
            name = node[1]
            if lang == "bash":
                return name if self.arith else "$" + name
            return _SIGIL.get(lang, "") + name
        if k == "bool":
            t, f = _BOOL.get(lang, ("true", "false"))
            return t if node[1] else f
        if k == "null":
            return _NULL_LIT.get(lang, "null")
        if k == "paren":
            return f"({self(node[1])})"
        if k == "un":
            inner = self(node[2], 9)
            if node[1] == "!":
                if lang in ("python", "lua"):
                    return f"not {inner}"
                if lang == "powershell":
                    return f"-not {inner}"
                return f"!{inner}"
            return f"-{inner}"
        if k == "bin":
            op = node[1]
            prec = _PREC[op]
            lhs, rhs = self(node[2], prec), self(node[3], prec + 1)
            if lang == "powershell" and op in ("&&", "||"):
                lhs = lhs if node[2][0] in ("paren", "id", "bool", "un") else f"({lhs})"
                rhs = rhs if node[3][0] in ("paren", "id", "bool", "un") else f"({rhs})"
            if lang == "rust" and self.typeof and op in _NUM_OPS:  # Rust não promove `2` para f64
                if _int_lit(node[2]) and self.typeof(node[3]) == "float":
                    lhs += ".0"
                if _int_lit(node[3]) and self.typeof(node[2]) == "float":
                    rhs += ".0"
            if op == "/" and self.typeof and lang in _CAST_DIV and self.typeof(node[2]) == "int" \
                    and self.typeof(node[3]) == "int":
                lhs, rhs = _CAST_DIV[lang](lhs), (_CAST_DIV[lang](rhs) if lang in ("go", "rust") else rhs)
            if lang == "lua" and op == "+" and "str" in (infer(node[2]), infer(node[3])):
                text = f"{lhs} .. {rhs}"
            elif lang == "php" and op == "+" and "str" in (infer(node[2]), infer(node[3])):
                text = f"{lhs} . {rhs}"
            else:
                text = f"{lhs} {_op(op, lang)} {rhs}"
            return f"({text})" if prec < parent_prec else text
        if k == "call":
            fn = node[1]
            args = [self(a) for a in node[2]]
            if fn[0] == "id" and fn[1].lower() in _LEN_NAMES and len(args) == 1:
                return _len(args[0], lang)
            name = self(fn) if fn[0] != "id" else fn[1]
            if lang == "powershell" and fn[0] == "id":
                args = [f"({a})" if n[0] in ("bin", "un") else a for a, n in zip(args, node[2])]
                return f"({name} {' '.join(args)})" if args else f"({name})"
            return f"{name}({', '.join(args)})"
        if k == "attr":
            base = self(node[1], 10)
            return f"{base}->{node[2]}" if lang == "php" else f"{base}.{node[2]}"
        if k == "index":
            return f"{self(node[1], 10)}[{self(node[2])}]"
        if k == "list":
            return self.list_literal(node)
        if k == "dict":
            return self.dict_literal(node)
        raise ExprError(f"nó desconhecido {k}")

    def list_literal(self, node: Ast) -> str:
        items = [self(x) for x in node[1]]
        lang = self.lang
        t = infer(node)[5:-1]
        joined = ", ".join(items)
        if lang in ("python", "javascript", "typescript", "php", "ruby"):
            return f"[{joined}]"
        if lang == "lua":
            return "{" + joined + "}"
        if lang == "powershell":
            return f"@({joined})"
        if lang == "bash":
            return "(" + " ".join(items) + ")"
        if lang == "go":
            return f"[]{go_type(t)}{{{joined}}}"
        if lang == "rust":
            return f"vec![{joined}]"
        if lang == "java":
            return f"List.of({joined})"
        if lang == "csharp":
            return f"new List<{cs_type(t)}> {{ {joined} }}"
        if lang == "cpp":
            return "{" + joined + "}"
        if lang == "c":
            return "{" + joined + "}"
        return f"[{joined}]"

    def dict_literal(self, node: Ast) -> str:
        lang = self.lang
        pairs = [(k, self(v)) for k, v in node[1]]
        if lang == "python":
            return "{" + ", ".join(f"{quote(k, lang)}: {v}" for k, v in pairs) + "}"
        if lang in ("javascript", "typescript"):
            return "{ " + ", ".join(f"{k}: {v}" for k, v in pairs) + " }"
        if lang == "go":
            return "map[string]any{" + ", ".join(f"{quote(k, lang)}: {v}" for k, v in pairs) + "}"
        if lang == "php":
            return "[" + ", ".join(f"{quote(k, lang)} => {v}" for k, v in pairs) + "]"
        if lang == "ruby":
            return "{ " + ", ".join(f"{k}: {v}" for k, v in pairs) + " }"
        if lang == "lua":
            return "{ " + ", ".join(f"{k} = {v}" for k, v in pairs) + " }"
        if lang == "powershell":
            return "[ordered]@{ " + "; ".join(f"{k} = {v}" for k, v in pairs) + " }"
        if lang == "csharp":
            return "new Dictionary<string, object> { " + ", ".join(f"[{quote(k, lang)}] = {v}" for k, v in pairs) + " }"
        if lang == "java":
            return "Map.of(" + ", ".join(f"{quote(k, lang)}, {v}" for k, v in pairs) + ")"
        raise ExprError("dicionário não suportado nesta linguagem")


def _elem(t: str) -> str | None:
    return t[5:-1] if t.startswith("list[") else None


def go_type(t: str) -> str:
    if (e := _elem(t)) is not None:
        return "[]" + go_type(e)
    return {"int": "int", "float": "float64", "str": "string", "bool": "bool"}.get(t, "any")


def cs_type(t: str) -> str:
    if (e := _elem(t)) is not None:
        return f"List<{cs_type(e)}>"
    return {"int": "int", "float": "double", "str": "string", "bool": "bool"}.get(t, "object")


def java_type(t: str, boxed: bool = False) -> str:
    if (e := _elem(t)) is not None:
        return f"List<{java_type(e, boxed=True)}>"
    if boxed:
        return {"int": "Integer", "float": "Double", "str": "String", "bool": "Boolean"}.get(t, "Object")
    return {"int": "int", "float": "double", "str": "String", "bool": "boolean"}.get(t, "var")


def rust_type(t: str) -> str:
    if (e := _elem(t)) is not None:
        return "&[" + ("String" if e in ("str", "?") and e != "?" else rust_type(e) if e != "?" else "i64") + "]"
    return {"int": "i64", "float": "f64", "str": "&str", "bool": "bool"}.get(t, "i64")


def c_type(t: str) -> str:
    if (e := _elem(t)) is not None:
        return "const " + c_type(e if e != "?" else "int") + " *"
    return {"int": "int", "float": "double", "str": "const char *", "bool": "bool"}.get(t, "int")


def ts_type(t: str) -> str:
    if (e := _elem(t)) is not None:
        return ts_type(e) + "[]" if e != "?" else "unknown[]"
    return {"int": "number", "float": "number", "num?": "number", "str": "string", "bool": "boolean"}.get(t, "unknown")


def render(node: Ast, lang: str, arith: bool = False) -> str:
    return Renderer(lang, arith)(node)


def is_numeric_cond(node: Ast) -> bool:
    """True se a condição não envolve strings (bash usa (( )) em vez de [[ ]])."""
    if node[0] == "str":
        return False
    if node[0] in ("bin", "un", "paren", "call", "list", "index", "attr"):
        return all(is_numeric_cond(c) for c in node[1:] if isinstance(c, tuple))
    return True


def py_type(t: str) -> str:
    if (e := _elem(t)) is not None:
        return f"list[{py_type(e)}]" if e != "?" else "list"
    return {"int": "int", "float": "float", "str": "str", "bool": "bool"}.get(t, "")


def ps_type(t: str) -> str:
    if (e := _elem(t)) is not None:
        return {"int": "[int[]]", "float": "[double[]]", "str": "[string[]]"}.get(e, "[object[]]")
    return {"int": "[int]", "float": "[double]", "str": "[string]", "bool": "[bool]"}.get(t, "")
