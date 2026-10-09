"""Back-ends do Estágio 0: IR -> código idiomático em 19 linguagens.

Cada emissor mantém uma tabela de símbolos simples (declaração x reatribuição,
variáveis mutáveis no Rust, const/let no JS) e coleta imports separadamente.
"""

from __future__ import annotations

import re

from codar.engine import expr as E
from codar.engine import ir
from codar.engine.postprocess import reindent
from codar.engine.stage0 import field_type


class EmitError(ValueError):
    """A construção não tem tradução idiomática nesta linguagem (o roteador segue para o Estágio 1/2)."""


def _num(x: float) -> str:
    return str(int(x)) if float(x).is_integer() else f"{x:g}"


def _shift(node: E.Ast, k: int) -> E.Ast:
    if k == 0:
        return node
    if node[0] == "num" and "." not in node[1]:
        return ("num", str(int(node[1]) + k))
    if node[0] == "un" and node[1] == "-" and node[2][0] == "num":
        return ("num", str(-int(node[2][1]) + k))
    return ("bin", "+" if k > 0 else "-", node, ("num", str(abs(k))))


def _is_zero(node: E.Ast) -> bool:
    return node[0] == "num" and float(node[1]) == 0


def _pascal(name: str) -> str:
    return name[:1].upper() + name[1:]


def uses_var(nodes: list[ir.Node], name: str) -> bool:
    for n in _walk(nodes):
        for attr in ("value", "cond", "iterable", "start", "end", "ret", "args"):
            v = getattr(n, attr, None)
            if v is not None and name in E.identifiers(v):
                return True
        if isinstance(n, (ir.Assign, ir.Append)) and getattr(n, "name", getattr(n, "target", None)) == name:
            return True
        if isinstance(n, ir.If):
            for cond, _ in n.elifs:
                if name in E.identifiers(cond):
                    return True
    return False


def _walk(nodes):
    for n in nodes:
        yield n
        if isinstance(n, ir.Block):
            yield from _walk(n.body)
        if isinstance(n, ir.If):
            for _, b in n.elifs:
                yield from _walk(b)
            if n.orelse:
                yield from _walk(n.orelse)


class Emitter:
    lang = "python"
    unit = "    "
    placeholder = "# TODO"
    comment = "#"
    scripting = True  # hello world = só a instrução de saída

    def __init__(self) -> None:
        self.imports: list[str] = []
        self.scopes: list[dict[str, str]] = [{}]
        self.mutable: set[str] = set()
        self.appended: set[str] = set()

    # ------------------------------------------------------------------ infraestrutura
    def render(self, nodes: list[ir.Node]) -> tuple[list[str], str]:
        counts: dict[str, int] = {}
        for n in _walk(nodes):
            if isinstance(n, ir.Assign):
                counts[n.name] = counts.get(n.name, 0) + 1
            elif isinstance(n, ir.Append):
                self.appended.add(n.target)
            elif isinstance(n, ir.Call) and n.target:
                counts[n.target] = counts.get(n.target, 0) + 1
        self.mutable = {k for k, v in counts.items() if v > 1} | self.appended
        lines = self.block(nodes, 0)
        return list(self.imports), "\n".join(lines).rstrip()

    def need(self, *imports: str) -> None:
        for imp in imports:
            if imp not in self.imports:
                self.imports.append(imp)

    def i(self, d: int) -> str:
        return self.unit * d

    def x(self, node: E.Ast, arith: bool = False) -> str:
        return E.Renderer(self.lang, arith, typeof=self.typeof, need=self.need)(node)

    def q(self, s: str) -> str:
        return E.quote(s, self.lang)

    def partes(self, node: E.Ast) -> list[E.Ast] | None:
        """"Total: " + total -> [str, id] quando a soma é de textos (para montar printf, format!, cout <<…)."""
        return E.Renderer(self.lang, typeof=self.typeof, need=self.need).partes_texto(node)

    def tipo_parte(self, node: E.Ast) -> str:
        t = self.typeof(node)
        if t in ("?", "num?") and node[0] == "id":
            t = field_type(node[1]) or "?"
        return "int" if t == "num?" else t

    def block(self, nodes: list[ir.Node], d: int) -> list[str]:
        out: list[str] = []
        for n in nodes:
            out.extend(self.node(n, d))
        return out

    def body(self, nodes: list[ir.Node], d: int, extra: list[str] | None = None,
             names: dict[str, str] | None = None) -> list[str]:
        self.scopes.append(dict(names or {}))
        try:
            lines = self.block(nodes, d)
        finally:
            self.scopes.pop()
        if extra:
            lines += extra
        return lines or [self.i(d) + self.placeholder]

    def node(self, n: ir.Node, d: int) -> list[str]:
        if isinstance(n, ir.Assign) and not n.const and n.name in E.identifiers(n.value):
            # x = x + 1: a variável já existe — nunca declarar de novo (Go :=, JS let, Lua local...)
            if not self.declared(n.name):
                self.scopes[0][n.name] = self.typeof(n.value)
            v = n.value
            if v[0] == "bin" and v[1] in ("+", "-", "*", "/", "%") and v[2] == ("id", n.name):
                return self.compound_assign(n.name, v[1], v[3], d)
        fn = getattr(self, "n_" + type(n).__name__, None)
        if fn is None:
            raise EmitError(f"{type(n).__name__} não suportado em {self.lang}")
        return fn(n, d)

    def compound_assign(self, name: str, op: str, rhs: E.Ast, d: int) -> list[str]:
        return [f"{self.i(d)}{self.x(('id', name))} {op}= {self.x(rhs)}{self.semi}"]

    def declared(self, name: str) -> bool:
        return any(name in s for s in self.scopes)

    def declare(self, name: str, typ: str) -> None:
        self.scopes[-1][name] = typ

    def typeof(self, node: E.Ast | None) -> str:
        if node is None:
            return "?"
        if node[0] == "id":
            for s in reversed(self.scopes):
                if node[1] in s:
                    return s[node[1]]
            return "float" if field_type(node[1]) == "float" else "?"  # variável externa: palpite pelo nome
        if node[0] == "call" and node[1][0] == "id" and node[1][1].lower() in E._LEN_NAMES:
            return "int"
        if node[0] == "index":
            base = self.typeof(node[1])
            return base[5:-1] if base.startswith("list[") else "?"
        if node[0] == "bin" and node[1] in "+-*/%":
            lt, rt = self.typeof(node[2]), self.typeof(node[3])
            if "str" in (lt, rt) and node[1] == "+":
                return "str"
            if "float" in (lt, rt) or node[1] == "/":
                return "float"
            if lt in ("int", "?", "num?") and rt in ("int", "?", "num?"):
                return "int"
        t = E.infer(node)
        return "int" if t == "num?" else t

    def param_types(self, f: ir.FuncDef) -> dict[str, str]:
        """Inferência rasa: parâmetros usados em aritmética viram numéricos; senão heurística pelo nome."""
        types = {p: "" for p in f.params}

        def visit(node):
            if not isinstance(node, tuple) or not node:
                return
            if node[0] == "bin" and node[1] in "+-*/%<>" + "<=>=":
                for side in (node[2], node[3]):
                    if side[0] == "id" and side[1] in types and not types[side[1]]:
                        other = node[3] if side is node[2] else node[2]
                        types[side[1]] = "str" if E.infer(other) == "str" and node[1] == "+" else (
                            "float" if E.infer(other) == "float" else "int")
            for part in node[1:]:
                if isinstance(part, tuple):
                    visit(part)
                elif isinstance(part, list):
                    for p in part:
                        visit(p)

        def lens(node):
            if not isinstance(node, tuple) or not node:
                return
            if node[0] == "call" and node[1][0] == "id" and node[1][1].lower() in E._LEN_NAMES and node[2] \
                    and node[2][0][0] == "id" and node[2][0][1] in types:
                types[node[2][0][1]] = types[node[2][0][1]] if types[node[2][0][1]].startswith("list") else "list[?]"
            for part in node[1:]:
                if isinstance(part, tuple):
                    lens(part)
                elif isinstance(part, list):
                    for q in part:
                        lens(q)

        for n in _walk(f.body):  # parâmetro percorrido num laço = lista
            if isinstance(n, ir.ForEach) and n.iterable[0] == "id" and n.iterable[1] in types:
                numeric = any(isinstance(m, ir.Assign) and n.var in E.identifiers(m.value) and m.value[0] == "bin"
                              and m.value[1] in "+-*/%" for m in _walk(n.body))
                types[n.iterable[1]] = "list[int]" if numeric else "list[?]"
        visit(f.ret)
        lens(f.ret)
        for n in _walk(f.body):
            for attr in ("value", "cond", "iterable", "end", "start"):
                visit(getattr(n, attr, None))
                lens(getattr(n, attr, None))
        return {p: t or field_type(p) for p, t in types.items()}

    def ret_type(self, f: ir.FuncDef, ptypes: dict[str, str]) -> str:
        rets = [f.ret] if f.ret is not None else [n.value for n in _walk(f.body) if isinstance(n, ir.Return)]
        rets = [r for r in rets if r is not None]
        if not rets:
            return "void"
        self.scopes.append(dict(ptypes))
        try:
            t = self.typeof(rets[0])
        finally:
            self.scopes.pop()
        return "int" if t in ("?", "num?") else t

    def with_ret(self, f: ir.FuncDef) -> list[ir.Node]:
        return list(f.body) + ([ir.Return(f.ret)] if f.ret is not None else [])

    # ------------------------------------------------------------------ nós comuns
    def n_Comment(self, n: ir.Comment, d: int) -> list[str]:
        return [f"{self.i(d)}{self.comment} {'TODO: ' if n.todo else ''}{n.text}"]

    def n_Unresolved(self, n: ir.Unresolved, d: int) -> list[str]:
        return [f"{self.i(d)}{self.comment} TODO: {n.text}"]

    def n_Raw(self, n: ir.Raw, d: int) -> list[str]:
        self.need(*n.imports)
        return reindent(n.code, self.unit, self.i(d)).split("\n")

    def n_Break(self, n, d):
        return [self.i(d) + "break" + self.semi]

    def n_Continue(self, n, d):
        return [self.i(d) + "continue" + self.semi]

    semi = ""

    def range_cmp(self, n: ir.ForRange) -> tuple[str, E.Ast, str]:
        """(operador, limite, incremento) para laços estilo C."""
        up = n.step > 0
        op = ("<=" if up else ">=") if n.inclusive else ("<" if up else ">")
        if abs(n.step) == 1:
            inc = f"{n.var}++" if up else f"{n.var}--"
        else:
            inc = f"{n.var} += {n.step}" if up else f"{n.var} -= {abs(n.step)}"
        return op, n.end, inc


# =============================================================================== Python

class PythonEmitter(Emitter):
    lang = "python"
    placeholder = "pass"

    _PY_T = {"int": "int", "float": "float", "str": "str", "bool": "bool"}

    def n_Print(self, n, d):
        return [f"{self.i(d)}print({self.x(n.value)})"]

    def n_Assign(self, n, d):
        self.declare(n.name, self.typeof(n.value))
        return [f"{self.i(d)}{n.name} = {self.x(n.value)}"]

    def n_Input(self, n, d):
        call = f"input({self.q(n.prompt)})"
        if n.kind in ("int", "float"):
            call = f"{n.kind}({call})"
        self.declare(n.var, n.kind)
        return [f"{self.i(d)}{n.var} = {call}"]

    def n_ForRange(self, n, d):
        end = n.end if not n.inclusive else _shift(n.end, 1 if n.step > 0 else -1)
        if _is_zero(n.start) and n.step == 1:
            args = [self.x(end)]
        elif n.step == 1:
            args = [self.x(n.start), self.x(end)]
        else:
            args = [self.x(n.start), self.x(end), str(n.step)]
        var = n.var if uses_var(n.body, n.var) else "_"
        return [f"{self.i(d)}for {var} in range({', '.join(args)}):"] + self.body(n.body, d + 1, names={n.var: "int"})

    def n_ForEach(self, n, d):
        return [f"{self.i(d)}for {n.var} in {self.x(n.iterable)}:"] + self.body(n.body, d + 1, names={n.var: "?"})

    def n_While(self, n, d):
        return [f"{self.i(d)}while {self.x(n.cond)}:"] + self.body(n.body, d + 1)

    def n_If(self, n, d):
        out = [f"{self.i(d)}if {self.x(n.cond)}:"] + self.body(n.body, d + 1)
        for cond, body in n.elifs:
            out += [f"{self.i(d)}elif {self.x(cond)}:"] + self.body(body, d + 1)
        if n.orelse is not None:
            out += [f"{self.i(d)}else:"] + self.body(n.orelse, d + 1)
        return out

    def n_FuncDef(self, n, d):
        pt = self.param_types(n)
        rt = self.ret_type(n, pt)
        params = ", ".join(f"{p}: {E.py_type(pt[p])}" if E.py_type(pt[p]) else p for p in n.params)
        ann = " -> None" if rt == "void" else (f" -> {E.py_type(rt)}" if E.py_type(rt) else "")
        self.scopes.append(dict(pt))
        try:
            body = self.body(self.with_ret(n), d + 1)
        finally:
            self.scopes.pop()
        return [f"{self.i(d)}def {n.name}({params}){ann}:"] + body

    def n_Main(self, n, d):
        if n.hello:
            return self.block(n.body, d)
        return ([f"{self.i(d)}def main() -> None:"] + self.body(n.body, d + 1) +
                ["", "", f'{self.i(d)}if __name__ == "__main__":', f"{self.i(d + 1)}main()"])

    def n_ClassDef(self, n, d):
        self.need("from dataclasses import dataclass")
        fields = [f"{self.i(d + 1)}{f}: {self._PY_T.get(t, 'str')}" for f, t in n.fields] or [self.i(d + 1) + "pass"]
        return [f"{self.i(d)}@dataclass", f"{self.i(d)}class {n.name}:"] + fields

    def n_TryCatch(self, n, d):
        self.need("import logging")
        return ([f"{self.i(d)}try:"] + self.body(n.body, d + 1) +
                [f"{self.i(d)}except Exception:", f'{self.i(d + 1)}logging.exception("Falha na operação")',
                 f"{self.i(d + 1)}raise"])

    def n_Return(self, n, d):
        return [f"{self.i(d)}return" + (f" {self.x(n.value)}" if n.value is not None else "")]

    def n_Import(self, n, d):
        mod = n.module
        if "/" in mod or "\\" in mod:
            raise EmitError("caminho de módulo inválido em Python")
        return [f"{self.i(d)}import {mod}"]

    def n_Sleep(self, n, d):
        self.need("import time")
        return [f"{self.i(d)}time.sleep({_num(n.seconds)})"]

    def n_Call(self, n, d):
        call = f"{n.name}({', '.join(self.x(a) for a in n.args)})"
        return [f"{self.i(d)}{n.target} = {call}" if n.target else f"{self.i(d)}{call}"]

    def n_Append(self, n, d):
        return [f"{self.i(d)}{n.target}.append({self.x(n.value)})"]


# =============================================================================== família C

class CLikeEmitter(Emitter):
    placeholder = "// TODO"
    comment = "//"
    semi = ";"
    allman = False
    cond_parens = True

    def open(self, header: str, d: int) -> list[str]:
        if self.allman:
            return [self.i(d) + header, self.i(d) + "{"]
        return [f"{self.i(d)}{header} {{"]

    def close(self, d: int) -> list[str]:
        return [self.i(d) + "}"]

    def cond(self, node: E.Ast) -> str:
        c = self.x(node)
        return f"({c})" if self.cond_parens else c

    def blk(self, header: str, body: list[ir.Node], d: int, extra: list[str] | None = None,
            names: dict[str, str] | None = None) -> list[str]:
        return self.open(header, d) + self.body(body, d + 1, extra, names) + self.close(d)

    def n_While(self, n, d):
        return self.blk(f"while {self.cond(n.cond)}", n.body, d)

    def n_If(self, n, d):
        out = self.open(f"if {self.cond(n.cond)}", d) + self.body(n.body, d + 1)
        for cond, body in n.elifs:
            if self.allman:
                out += self.close(d) + self.open(f"else if {self.cond(cond)}", d)
            else:
                out += [f"{self.i(d)}}} {self.elseif} {self.cond(cond)} {{"]
            out += self.body(body, d + 1)
        if n.orelse is not None:
            if self.allman:
                out += self.close(d) + self.open("else", d)
            else:
                out += [f"{self.i(d)}}} else {{"]
            out += self.body(n.orelse, d + 1)
        return out + self.close(d)

    elseif = "else if"

    def n_Return(self, n, d):
        return [f"{self.i(d)}return" + (f" {self.x(n.value)}" if n.value is not None else "") + self.semi]

    def n_TryCatch(self, n, d):
        raise EmitError("try/catch")

    def c_for(self, n: ir.ForRange, decl: str) -> str:
        op, end, inc = self.range_cmp(n)
        var = n.var if self.lang != "php" else "$" + n.var
        inc = inc if self.lang != "php" else "$" + inc
        return f"for ({decl}{var} = {self.x(n.start)}; {var} {op} {self.x(end)}; {inc})"


class JSEmitter(CLikeEmitter):
    lang = "javascript"
    unit = "  "

    def decl_kw(self, name: str, const: bool) -> str:
        return "const" if const or name not in self.mutable else "let"

    _RL = ("const rl = readline.createInterface({ input: process.stdin });\n"
           "const linhas = rl[Symbol.asyncIterator]();")

    def render(self, nodes):
        """Uma leitura de linhas para o trecho todo, fechada no fim. O iterador guarda as linhas que chegam antes da
        pergunta (entrada colada ou encadeada); rl.question perderia essas linhas, e fechar a cada pergunta quebra
        a seguinte (ERR_USE_AFTER_CLOSE)."""
        le = any(isinstance(n, ir.Input) for n in _walk(nodes))
        if le:
            self.declare("rl", "?")
        imports, code = super().render(nodes)
        if le:
            code = f"{self._RL}\n{code}\nrl.close();"
        return imports, code

    def n_Print(self, n, d):
        return [f"{self.i(d)}console.log({self.x(n.value)});"]

    def n_Assign(self, n, d):
        if self.declared(n.name):
            return [f"{self.i(d)}{n.name} = {self.x(n.value)};"]
        self.declare(n.name, self.typeof(n.value))
        return [f"{self.i(d)}{self.decl_kw(n.name, n.const)} {n.name}{self.annot(n.value)} = {self.x(n.value)};"]

    def annot(self, value: E.Ast) -> str:
        return ""

    def n_Input(self, n, d):
        self.need('import * as readline from "node:readline";')
        valor = "(await linhas.next()).value"
        valor = f"Number({valor})" if n.kind in ("int", "float") else f'{valor} ?? ""'
        self.declare(n.var, n.kind)
        return [f"{self.i(d)}process.stdout.write({self.q(n.prompt)});", f"{self.i(d)}const {n.var} = {valor};"]

    def n_ForRange(self, n, d):
        return self.blk(self.c_for(n, "let "), n.body, d, names={n.var: "int"})

    def n_ForEach(self, n, d):
        return self.blk(f"for (const {n.var} of {self.x(n.iterable)})", n.body, d, names={n.var: "?"})

    def params(self, n: ir.FuncDef) -> tuple[str, str]:
        return ", ".join(n.params), ""

    def n_FuncDef(self, n, d):
        params, ret = self.params(n)
        self.scopes.append(dict(self.param_types(n)))
        try:
            body = self.body(self.with_ret(n), d + 1)
        finally:
            self.scopes.pop()
        return [f"{self.i(d)}function {n.name}({params}){ret} {{"] + body + self.close(d)

    def n_Main(self, n, d):
        if n.hello:
            return self.block(n.body, d)
        espera = any(isinstance(m, (ir.Input, ir.Sleep)) for m in _walk(n.body))  # usa await: main precisa de async
        if espera:
            return self.blk("async function main()", n.body, d) + ["", f"{self.i(d)}await main();"]
        return self.blk("function main()", n.body, d) + ["", f"{self.i(d)}main();"]

    def n_ClassDef(self, n, d):
        args = ", ".join(f for f, _ in n.fields)
        assigns = [f"{self.i(d + 2)}this.{f} = {f};" for f, _ in n.fields]
        return ([f"{self.i(d)}class {n.name} {{", f"{self.i(d + 1)}constructor({args}) {{"] + assigns +
                [f"{self.i(d + 1)}}}", f"{self.i(d)}}}"])

    def n_TryCatch(self, n, d):
        return (self.open("try", d) + self.body(n.body, d + 1) +
                [f"{self.i(d)}}} catch (err) {{", f'{self.i(d + 1)}console.error("Erro:", err);',
                 f"{self.i(d + 1)}throw err;"] + self.close(d))

    def n_Import(self, n, d):
        mod, _, alias = n.module.partition(" as ")
        name = alias or mod.split("/")[-1].replace("-", "_").replace(".", "_")
        return [f'{self.i(d)}import * as {name} from "{mod}";']

    def n_Sleep(self, n, d):
        return [f"{self.i(d)}await new Promise((resolve) => setTimeout(resolve, {_num(n.seconds * 1000)}));"]

    def n_Call(self, n, d):
        call = f"{n.name}({', '.join(self.x(a) for a in n.args)})"
        if n.target:
            if self.declared(n.target):
                return [f"{self.i(d)}{n.target} = {call};"]
            self.declare(n.target, "?")
            return [f"{self.i(d)}{self.decl_kw(n.target, False)} {n.target} = {call};"]
        return [f"{self.i(d)}{call};"]

    def n_Append(self, n, d):
        return [f"{self.i(d)}{n.target}.push({self.x(n.value)});"]


class TSEmitter(JSEmitter):
    lang = "typescript"

    def annot(self, value: E.Ast) -> str:
        if value[0] == "list" and not value[1]:
            return ": unknown[]"
        return ""

    def params(self, n: ir.FuncDef) -> tuple[str, str]:
        pt = self.param_types(n)
        rt = self.ret_type(n, pt)
        ps = ", ".join(f"{p}: {E.ts_type(pt[p])}" for p in n.params)
        return ps, f": {'void' if rt == 'void' else E.ts_type(rt)}"

    def n_ClassDef(self, n, d):
        fields = [f"{self.i(d + 1)}{f}: {E.ts_type(t)};" for f, t in n.fields]
        args = ", ".join(f"{f}: {E.ts_type(t)}" for f, t in n.fields)
        assigns = [f"{self.i(d + 2)}this.{f} = {f};" for f, _ in n.fields]
        return ([f"{self.i(d)}class {n.name} {{"] + fields + ([""] if fields else []) +
                [f"{self.i(d + 1)}constructor({args}) {{"] + assigns + [f"{self.i(d + 1)}}}", f"{self.i(d)}}}"])


class GoEmitter(CLikeEmitter):
    lang = "go"
    unit = "\t"
    semi = ""
    cond_parens = False
    scripting = False

    def n_Print(self, n, d):
        self.need('import "fmt"')
        partes = self.partes(n.value)
        if partes and any(p[0] != "str" and self.tipo_parte(p) in ("int", "float", "bool") for p in partes):
            fmt = "".join(E.quote(p[1], "go")[1:-1].replace("%", "%%") if p[0] == "str" else "%v" for p in partes)
            args = "".join(f", {self.x(p)}" for p in partes if p[0] != "str")
            return [f'{self.i(d)}fmt.Printf("{fmt}\\n"{args})']
        return [f"{self.i(d)}fmt.Println({self.x(n.value)})"]

    def n_Assign(self, n, d):
        if n.const and not self.declared(n.name):
            self.declare(n.name, self.typeof(n.value))
            return [f"{self.i(d)}const {n.name} = {self.x(n.value)}"]
        if self.declared(n.name):
            return [f"{self.i(d)}{n.name} = {self.x(n.value)}"]
        self.declare(n.name, self.typeof(n.value))
        return [f"{self.i(d)}{n.name} := {self.x(n.value)}"]

    def n_Input(self, n, d):
        self.need('import "bufio"', 'import "fmt"', 'import "log"', 'import "os"', 'import "strings"')
        out = []
        if not self.declared("reader"):
            self.declare("reader", "?")
            out.append(f"{self.i(d)}reader := bufio.NewReader(os.Stdin)")
        raw = n.var if n.kind == "str" else f"{n.var}Txt"
        out += [f"{self.i(d)}fmt.Print({self.q(n.prompt)})",
                f"{self.i(d)}{raw}, err := reader.ReadString('\\n')",
                f"{self.i(d)}if err != nil {{", f"{self.i(d + 1)}log.Fatal(err)", f"{self.i(d)}}}"]
        if n.kind == "str":
            out.append(f"{self.i(d)}{n.var} = strings.TrimSpace({n.var})")
        elif n.kind == "int":
            self.need('import "strconv"')
            out += [f"{self.i(d)}{n.var}, err := strconv.Atoi(strings.TrimSpace({raw}))",
                    f"{self.i(d)}if err != nil {{", f"{self.i(d + 1)}log.Fatal(err)", f"{self.i(d)}}}"]
        else:
            self.need('import "strconv"')
            out += [f"{self.i(d)}{n.var}, err := strconv.ParseFloat(strings.TrimSpace({raw}), 64)",
                    f"{self.i(d)}if err != nil {{", f"{self.i(d + 1)}log.Fatal(err)", f"{self.i(d)}}}"]
        self.declare(n.var, n.kind)
        return out

    def n_ForRange(self, n, d):
        if _is_zero(n.start) and n.step == 1 and not n.inclusive:
            used = uses_var(n.body, n.var)
            header = f"for {n.var} := range {self.x(n.end)}" if used else f"for range {self.x(n.end)}"
        else:
            op, end, inc = self.range_cmp(n)
            header = f"for {n.var} := {self.x(n.start)}; {n.var} {op} {self.x(end)}; {inc}"
        return self.blk(header, n.body, d, names={n.var: "int"})

    def n_ForEach(self, n, d):
        extra = [f"{self.i(d + 1)}_ = {n.var}"] if not n.body else None
        lines = self.open(f"for _, {n.var} := range {self.x(n.iterable)}", d)
        body = self.body(n.body, d + 1) if n.body else extra
        return lines + body + self.close(d)

    def n_While(self, n, d):
        header = "for" if n.cond == ("bool", True) else f"for {self.cond(n.cond)}"
        return self.blk(header, n.body, d)

    def n_FuncDef(self, n, d):
        pt = self.param_types(n)
        rt = self.ret_type(n, pt)
        groups: list[tuple[list[str], str]] = []
        for p in n.params:
            t = E.go_type(pt[p])
            if groups and groups[-1][1] == t:
                groups[-1][0].append(p)
            else:
                groups.append(([p], t))
        params = ", ".join(f"{', '.join(ps)} {t}" for ps, t in groups)
        ret = "" if rt == "void" else " " + E.go_type(rt)
        self.scopes.append(dict(pt))
        try:
            body = self.body(self.with_ret(n), d + 1)
        finally:
            self.scopes.pop()
        return [f"{self.i(d)}func {n.name}({params}){ret} {{"] + body + self.close(d)

    def n_Main(self, n, d):
        lines = self.blk("func main()", n.body, d)
        if n.hello:
            imports, self.imports = self.imports, []
            head = ["package main", ""] + [imp for imp in imports] + ([""] if imports else [])
            return head + lines
        return lines

    def n_ClassDef(self, n, d):
        width = max((len(f) for f, _ in n.fields), default=0)
        fields = [f"{self.i(d + 1)}{_pascal(f).ljust(width)} {E.go_type(t)}" for f, t in n.fields]
        return [f"{self.i(d)}type {n.name} struct {{"] + fields + self.close(d)

    def n_TryCatch(self, n, d):
        self.need('import "fmt"')
        return ([f"{self.i(d)}// TODO: substitua operacao() pela chamada que pode falhar",
                 f"{self.i(d)}if err := operacao(); err != nil {{",
                 f'{self.i(d + 1)}return fmt.Errorf("operacao: %w", err)'] + self.close(d))

    def n_Import(self, n, d):
        return [f'{self.i(d)}import "{n.module.partition(" as ")[0]}"']

    def n_Sleep(self, n, d):
        self.need('import "time"')
        if n.seconds.is_integer():
            return [f"{self.i(d)}time.Sleep({_num(n.seconds)} * time.Second)"]
        return [f"{self.i(d)}time.Sleep({_num(n.seconds * 1000)} * time.Millisecond)"]

    def n_Call(self, n, d):
        call = f"{n.name}({', '.join(self.x(a) for a in n.args)})"
        if n.target:
            op = "=" if self.declared(n.target) else ":="
            self.declare(n.target, "?")
            return [f"{self.i(d)}{n.target} {op} {call}"]
        return [f"{self.i(d)}{call}"]

    def n_Append(self, n, d):
        return [f"{self.i(d)}{n.target} = append({n.target}, {self.x(n.value)})"]


class RustEmitter(CLikeEmitter):
    lang = "rust"
    cond_parens = False
    scripting = False

    def n_Print(self, n, d):
        v = n.value
        if v[0] == "str":
            text = v[1].replace("{", "{{").replace("}", "}}")
            return [f"{self.i(d)}println!({E.quote(text, 'rust')});"]
        if partes := self.partes(v):
            fmt = "".join(E.quote(p[1], "rust")[1:-1].replace("{", "{{").replace("}", "}}") if p[0] == "str" else "{}"
                          for p in partes)
            args = "".join(f", {self.x(p)}" for p in partes if p[0] != "str")
            return [f'{self.i(d)}println!("{fmt}"{args});']
        fmt = "{}" if self.typeof(v) in ("int", "float", "str", "bool") else "{:?}"
        return [f'{self.i(d)}println!("{fmt}", {self.x(v)});']

    def n_Assign(self, n, d):
        t = self.typeof(n.value)
        if n.const and not self.declared(n.name):
            self.declare(n.name, t)
            return [f"{self.i(d)}const {n.name.upper()}: {E.rust_type(t)} = {self.x(n.value)};"]
        if self.declared(n.name):
            return [f"{self.i(d)}{n.name} = {self.x(n.value)};"]
        self.declare(n.name, t)
        value = self.x(n.value)
        if n.value[0] == "dict":
            types = {E.infer(v) for _, v in n.value[1]}
            if len(types) != 1:
                raise EmitError("HashMap com valores de tipos diferentes")
            self.need("use std::collections::HashMap;")
            value = "HashMap::from([" + ", ".join(f'("{k}", {self.x(v)})' for k, v in n.value[1]) + "])"
        mut = "mut " if n.name in self.mutable else ""
        return [f"{self.i(d)}let {mut}{n.name} = {value};"]

    def n_Input(self, n, d):
        self.need("use std::io::{self, Write};")
        raw = n.var if n.kind == "str" else f"{n.var}_txt"
        out = [f"{self.i(d)}let mut {raw} = String::new();",
               f"{self.i(d)}print!({self.q(n.prompt)});",
               f'{self.i(d)}io::stdout().flush().expect("falha ao descarregar stdout");',
               f'{self.i(d)}io::stdin().read_line(&mut {raw}).expect("falha ao ler a entrada");']
        if n.kind == "str":
            out.append(f"{self.i(d)}let {n.var} = {n.var}.trim().to_string();")
        else:
            t = "i64" if n.kind == "int" else "f64"
            out.append(f'{self.i(d)}let {n.var}: {t} = {raw}.trim().parse().expect("número inválido");')
        self.declare(n.var, n.kind)
        return out

    def n_ForRange(self, n, d):
        s, e = self.x(n.start), self.x(n.end)
        if n.step > 0:
            rng = f"{s}..={e}" if n.inclusive else f"{s}..{e}"
            it = rng if n.step == 1 else f"({rng}).step_by({n.step})"
        else:
            low = e if n.inclusive else self.x(_shift(n.end, 1))
            it = f"({low}..={s}).rev()" + (f".step_by({abs(n.step)})" if n.step != -1 else "")
        var = n.var if uses_var(n.body, n.var) else "_"
        return self.blk(f"for {var} in {it}", n.body, d, names={n.var: "int"})

    def n_ForEach(self, n, d):
        amp = "" if self.typeof(n.iterable).startswith("list") else "&"  # parâmetro já é um slice emprestado
        return self.blk(f"for {n.var} in {amp}{self.x(n.iterable)}", n.body, d, names={n.var: "?"})

    def n_While(self, n, d):
        return self.blk("loop" if n.cond == ("bool", True) else f"while {self.x(n.cond)}", n.body, d)

    def n_FuncDef(self, n, d):
        pt = self.param_types(n)
        rt = self.ret_type(n, pt)
        params = ", ".join(f"{p}: {E.rust_type(pt[p])}" for p in n.params)
        ret = "" if rt == "void" else f" -> {'String' if rt == 'str' else E.rust_type(rt)}"
        self.scopes.append(dict(pt))
        try:
            body = self.body(n.body, d + 1) if n.body else []
            if n.ret is not None:
                tail = self.x(n.ret)
                if rt == "str" and n.ret[0] == "str":
                    tail += ".to_string()"
                body = [b for b in body if b.strip() != "// TODO"] + [self.i(d + 1) + tail]
            elif not body:
                body = [self.i(d + 1) + ("todo!()" if rt != "void" else "// TODO")]
        finally:
            self.scopes.pop()
        return [f"{self.i(d)}fn {n.name}({params}){ret} {{"] + body + self.close(d)

    def n_Main(self, n, d):
        return self.blk("fn main()", n.body, d)

    _RS_T = {"str": "String", "int": "i64", "float": "f64", "bool": "bool"}

    def n_ClassDef(self, n, d):
        fields = [f"{self.i(d + 1)}pub {f}: {self._RS_T.get(t, 'String')}," for f, t in n.fields]
        args = ", ".join(f"{f}: {self._RS_T.get(t, 'String')}" for f, t in n.fields)
        names = ", ".join(f for f, _ in n.fields)
        return ([f"{self.i(d)}#[derive(Debug, Clone, PartialEq)]", f"{self.i(d)}pub struct {n.name} {{"] + fields +
                [f"{self.i(d)}}}", "", f"{self.i(d)}impl {n.name} {{",
                 f"{self.i(d + 1)}pub fn new({args}) -> Self {{", f"{self.i(d + 2)}Self {{ {names} }}",
                 f"{self.i(d + 1)}}}", f"{self.i(d)}}}"])

    def n_TryCatch(self, n, d):
        return [f"{self.i(d)}// TODO: substitua operacao() pela chamada que retorna Result",
                f"{self.i(d)}match operacao() {{",
                f'{self.i(d + 1)}Ok(valor) => println!("{{valor:?}}"),',
                f'{self.i(d + 1)}Err(err) => eprintln!("Erro: {{err}}"),', f"{self.i(d)}}}"]

    def n_Import(self, n, d):
        return [f"{self.i(d)}use {n.module.partition(' as ')[0]};"]

    def n_Sleep(self, n, d):
        self.need("use std::thread;", "use std::time::Duration;")
        if n.seconds.is_integer():
            return [f"{self.i(d)}thread::sleep(Duration::from_secs({_num(n.seconds)}));"]
        return [f"{self.i(d)}thread::sleep(Duration::from_millis({_num(n.seconds * 1000)}));"]

    def n_Call(self, n, d):
        call = f"{n.name}({', '.join(self.x(a) for a in n.args)})"
        if n.target:
            if self.declared(n.target):
                return [f"{self.i(d)}{n.target} = {call};"]
            self.declare(n.target, "?")
            return [f"{self.i(d)}let {n.target} = {call};"]
        return [f"{self.i(d)}{call};"]

    def n_Append(self, n, d):
        return [f"{self.i(d)}{n.target}.push({self.x(n.value)});"]


class JavaEmitter(CLikeEmitter):
    lang = "java"
    scripting = False

    def n_Print(self, n, d):
        return [f"{self.i(d)}System.out.println({self.x(n.value)});"]

    def n_Assign(self, n, d):
        if self.declared(n.name):
            return [f"{self.i(d)}{n.name} = {self.x(n.value)};"]
        t = self.typeof(n.value)
        self.declare(n.name, t)
        final = "final " if n.const else ""
        name = n.name.upper() if n.const else n.name
        if n.value[0] == "list":
            inner = E.java_type(t[5:-1], boxed=True)
            self.need("import java.util.List;")
            value = self.x(n.value)
            if n.name in self.appended:
                self.need("import java.util.ArrayList;")
                value = f"new ArrayList<>({value})"
            return [f"{self.i(d)}{final}List<{inner}> {name} = {value};"]
        if n.value[0] == "dict":
            self.need("import java.util.Map;")
            return [f"{self.i(d)}{final}Map<String, Object> {name} = {self.x(n.value)};"]
        return [f"{self.i(d)}{final}{E.java_type(t)} {name} = {self.x(n.value)};"]

    def n_Input(self, n, d):
        self.need("import java.util.Scanner;")
        out = []
        if not self.declared("scanner"):
            self.declare("scanner", "?")
            out.append(f"{self.i(d)}Scanner scanner = new Scanner(System.in);")
        out.append(f"{self.i(d)}System.out.print({self.q(n.prompt)});")
        if n.kind == "int":
            out.append(f"{self.i(d)}int {n.var} = Integer.parseInt(scanner.nextLine().trim());")
        elif n.kind == "float":
            out.append(f"{self.i(d)}double {n.var} = Double.parseDouble(scanner.nextLine().trim());")
        else:
            out.append(f"{self.i(d)}String {n.var} = scanner.nextLine();")
        self.declare(n.var, n.kind)
        return out

    def n_ForRange(self, n, d):
        return self.blk(self.c_for(n, "int "), n.body, d, names={n.var: "int"})

    def n_ForEach(self, n, d):
        return self.blk(f"for (var {n.var} : {self.x(n.iterable)})", n.body, d)

    def n_FuncDef(self, n, d):
        pt = self.param_types(n)
        rt = self.ret_type(n, pt)
        if any(t.startswith("list") for t in pt.values()):
            self.need("import java.util.List;")
        params = ", ".join(f"{E.java_type(pt[p]) if pt[p] != '?' else 'Object'} {p}" for p in n.params)
        ret = "void" if rt == "void" else E.java_type(rt) if rt != "?" else "Object"
        self.scopes.append(dict(pt))
        try:
            body = self.body(self.with_ret(n), d + 1)
        finally:
            self.scopes.pop()
        return [f"{self.i(d)}public static {ret} {n.name}({params}) {{"] + body + self.close(d)

    def n_Main(self, n, d):
        main = self.blk("public static void main(String[] args)", n.body, d + (1 if n.hello else 0))
        if n.hello:
            return [f"{self.i(d)}public class Main {{"] + main + self.close(d)
        return main

    def n_ClassDef(self, n, d):
        comps = ", ".join(f"{E.java_type(t) if t != '?' else 'String'} {f}" for f, t in n.fields)
        return [f"{self.i(d)}public record {n.name}({comps}) {{}}"]

    def n_TryCatch(self, n, d):
        return (self.open("try", d) + self.body(n.body, d + 1) +
                [f"{self.i(d)}}} catch (Exception e) {{",
                 f'{self.i(d + 1)}throw new RuntimeException("Erro: " + e.getMessage(), e);'] + self.close(d))

    def n_Import(self, n, d):
        return [f"{self.i(d)}import {n.module.partition(' as ')[0]};"]

    def n_Sleep(self, n, d):
        return (self.open("try", d) + [f"{self.i(d + 1)}Thread.sleep({_num(n.seconds * 1000)});"] +
                [f"{self.i(d)}}} catch (InterruptedException e) {{",
                 f"{self.i(d + 1)}Thread.currentThread().interrupt();"] + self.close(d))

    def n_Call(self, n, d):
        call = f"{n.name}({', '.join(self.x(a) for a in n.args)})"
        if n.target and not self.declared(n.target):
            self.declare(n.target, "?")
            return [f"{self.i(d)}var {n.target} = {call};"]
        return [f"{self.i(d)}{n.target} = {call};" if n.target else f"{self.i(d)}{call};"]

    def n_Append(self, n, d):
        return [f"{self.i(d)}{n.target}.add({self.x(n.value)});"]


class CSharpEmitter(JavaEmitter):
    lang = "csharp"
    allman = True
    scripting = False

    def n_Print(self, n, d):
        return [f"{self.i(d)}Console.WriteLine({self.x(n.value)});"]

    def n_Assign(self, n, d):
        if self.declared(n.name):
            return [f"{self.i(d)}{n.name} = {self.x(n.value)};"]
        t = self.typeof(n.value)
        self.declare(n.name, t)
        if n.const and t in ("int", "float", "str", "bool"):
            return [f"{self.i(d)}const {E.cs_type(t)} {n.name.upper()} = {self.x(n.value)};"]
        return [f"{self.i(d)}var {n.name} = {self.x(n.value)};"]

    def n_Input(self, n, d):
        out = [f"{self.i(d)}Console.Write({self.q(n.prompt)});"]
        if n.kind == "int":
            out.append(f'{self.i(d)}int {n.var} = int.Parse(Console.ReadLine() ?? "0");')
        elif n.kind == "float":
            out.append(f'{self.i(d)}double {n.var} = double.Parse(Console.ReadLine() ?? "0");')
        else:
            out.append(f'{self.i(d)}string {n.var} = Console.ReadLine() ?? "";')
        self.declare(n.var, n.kind)
        return out

    def n_ForEach(self, n, d):
        return self.blk(f"foreach (var {n.var} in {self.x(n.iterable)})", n.body, d)

    def n_FuncDef(self, n, d):
        pt = self.param_types(n)
        rt = self.ret_type(n, pt)
        params = ", ".join(f"{E.cs_type(pt[p])} {p}" for p in n.params)
        ret = "void" if rt == "void" else E.cs_type(rt)
        self.scopes.append(dict(pt))
        try:
            body = self.body(self.with_ret(n), d + 1)
        finally:
            self.scopes.pop()
        return self.open(f"static {ret} {n.name}({params})", d) + body + self.close(d)

    def n_Main(self, n, d):
        if n.hello:
            return self.block(n.body, d)
        return self.blk("static void Main(string[] args)", n.body, d)

    def n_ClassDef(self, n, d):
        comps = ", ".join(f"{E.cs_type(t)} {_pascal(f)}" for f, t in n.fields)
        return [f"{self.i(d)}public record {n.name}({comps});"]

    def n_TryCatch(self, n, d):
        return (self.open("try", d) + self.body(n.body, d + 1) + self.close(d) + self.open("catch (Exception ex)", d) +
                [f'{self.i(d + 1)}Console.Error.WriteLine($"Erro: {{ex.Message}}");', f"{self.i(d + 1)}throw;"] +
                self.close(d))

    def n_Import(self, n, d):
        return [f"{self.i(d)}using {n.module.partition(' as ')[0]};"]

    def n_Sleep(self, n, d):
        return [f"{self.i(d)}Thread.Sleep({_num(n.seconds * 1000)});"]

    def n_Append(self, n, d):
        return [f"{self.i(d)}{n.target}.Add({self.x(n.value)});"]


class CEmitter(CLikeEmitter):
    lang = "c"
    scripting = False

    def formato_c(self, partes: list[E.Ast]) -> tuple[str, str]:
        fmt, args = "", ""
        for p in partes:
            if p[0] == "str":
                fmt += E.quote(p[1], "c")[1:-1].replace("%", "%%")
            else:
                fmt += {"str": "%s", "float": "%g"}.get(self.tipo_parte(p), "%d")
                args += f", {self.x(p)}"
        return fmt, args

    def n_Print(self, n, d):
        self.need("#include <stdio.h>")
        v = n.value
        if v[0] == "str":
            return [f"{self.i(d)}puts({self.x(v)});"]
        if partes := self.partes(v):
            fmt, args = self.formato_c(partes)
            return [f'{self.i(d)}printf("{fmt}\\n"{args});']
        t = self.typeof(v)
        if t == "bool":
            return [f'{self.i(d)}printf("%s\\n", {self.x(v)} ? "true" : "false");']
        fmt = {"str": "%s", "float": "%g"}.get(t, "%d")
        return [f'{self.i(d)}printf("{fmt}\\n", {self.x(v)});']

    def ctype(self, t: str) -> str:
        if t == "bool":
            self.need("#include <stdbool.h>")
        return E.c_type(t)

    def n_Assign(self, n, d):
        if self.declared(n.name):
            return [f"{self.i(d)}{n.name} = {self.x(n.value)};"]
        t = self.typeof(n.value)
        self.declare(n.name, t)
        const = "const " if n.const and t != "str" else ""
        if n.value[0] == "list":
            if n.name in self.appended or not n.value[1]:
                raise EmitError("arrays dinâmicos em C")
            return [f"{self.i(d)}{const}{self.ctype(t[5:-1])} {n.name}[] = {self.x(n.value)};"]
        if n.value[0] == "dict":
            raise EmitError("dicionário em C")
        if partes := self.partes(n.value):  # texto montado: buffer + snprintf
            self.need("#include <stdio.h>")
            fmt, args = self.formato_c(partes)
            return [f"{self.i(d)}char {n.name}[256];",
                    f'{self.i(d)}snprintf({n.name}, sizeof {n.name}, "{fmt}"{args});']
        return [f"{self.i(d)}{const}{self.ctype(t)} {n.name} = {self.x(n.value)};"]

    def n_Input(self, n, d):
        self.need("#include <stdio.h>")
        p = self.q(n.prompt)
        if n.kind == "str":
            self.need("#include <string.h>")
            out = [f"{self.i(d)}char {n.var}[256];", f"{self.i(d)}printf({p});",
                   f"{self.i(d)}if (fgets({n.var}, sizeof {n.var}, stdin) != NULL) {{",
                   f"{self.i(d + 1)}{n.var}[strcspn({n.var}, \"\\n\")] = '\\0';", f"{self.i(d)}}}"]
        else:
            ct, fmt = ("int", "%d") if n.kind == "int" else ("double", "%lf")
            out = [f"{self.i(d)}{ct} {n.var} = 0;", f"{self.i(d)}printf({p});",
                   f'{self.i(d)}if (scanf("{fmt}", &{n.var}) != 1) {{',
                   f'{self.i(d + 1)}fprintf(stderr, "entrada inválida\\n");', f"{self.i(d)}}}"]
        self.declare(n.var, n.kind)
        return out

    def n_ForRange(self, n, d):
        return self.blk(self.c_for(n, "int "), n.body, d, names={n.var: "int"})

    def n_ForEach(self, n, d):
        it = self.x(n.iterable)
        head = f"for (size_t idx = 0; idx < sizeof {it} / sizeof {it}[0]; idx++)"
        return self.blk(head, n.body, d, None) [:1] + [f"{self.i(d + 1)}int {n.var} = {it}[idx];"] + \
            self.body(n.body, d + 1) + self.close(d)

    def n_FuncDef(self, n, d):
        pt = self.param_types(n)
        rt = self.ret_type(n, pt)
        params = ", ".join(f"{self.ctype(pt[p])} {p}" for p in n.params) or "void"
        ret = "void" if rt == "void" else self.ctype(rt)
        self.scopes.append(dict(pt))
        try:
            body = self.body(self.with_ret(n), d + 1)
        finally:
            self.scopes.pop()
        return [f"{self.i(d)}{ret} {n.name}({params}) {{"] + body + self.close(d)

    def n_Main(self, n, d):
        body = self.block(n.body, d + 1) + [f"{self.i(d + 1)}return 0;"]
        lines = [f"{self.i(d)}int main(void) {{"] + body + self.close(d)
        if n.hello:
            imports, self.imports = self.imports, []
            return imports + [""] + lines
        return lines

    def n_ClassDef(self, n, d):
        fields = [f"{self.i(d + 1)}{self.ctype(t)} {f};" for f, t in n.fields]
        return [f"{self.i(d)}typedef struct {{"] + fields + [f"{self.i(d)}}} {n.name};"]

    def n_TryCatch(self, n, d):
        self.need("#include <stdio.h>")
        return [f"{self.i(d)}// TODO: substitua operacao() pela chamada que pode falhar",
                f"{self.i(d)}if (operacao() != 0) {{", f'{self.i(d + 1)}perror("operacao");',
                f"{self.i(d + 1)}return -1;", f"{self.i(d)}}}"]

    def n_Import(self, n, d):
        mod = n.module.partition(" as ")[0]
        return [f"{self.i(d)}#include <{mod if '.' in mod else mod + '.h'}>"]

    def n_Sleep(self, n, d):
        if n.seconds.is_integer():
            self.need("#include <unistd.h>")
            return [f"{self.i(d)}sleep({_num(n.seconds)});"]
        self.need("#include <time.h>")
        ns = int(round((n.seconds % 1) * 1e9))
        return [f"{self.i(d)}nanosleep(&(struct timespec){{.tv_sec = {int(n.seconds)}, .tv_nsec = {ns}L}}, NULL);"]

    def n_Call(self, n, d):
        call = f"{n.name}({', '.join(self.x(a) for a in n.args)})"
        if n.target and not self.declared(n.target):
            self.declare(n.target, "int")
            return [f"{self.i(d)}int {n.target} = {call};"]
        return [f"{self.i(d)}{n.target} = {call};" if n.target else f"{self.i(d)}{call};"]

    def n_Append(self, n, d):
        raise EmitError("append em C")


class CppEmitter(CLikeEmitter):
    lang = "cpp"
    scripting = False

    def texto_cpp(self, partes: list[E.Ast]) -> str:
        self.need("#include <string>")
        out = []
        for i, p in enumerate(partes):
            if p[0] == "str":
                out.append(f"std::string({self.x(p)})" if i == 0 else self.x(p))
            elif self.tipo_parte(p) in ("int", "float", "bool"):
                out.append(f"std::to_string({self.x(p)})")
            else:
                out.append(self.x(p))
        return " + ".join(out)

    def n_Print(self, n, d):
        self.need("#include <iostream>")
        if partes := self.partes(n.value):
            return [f"{self.i(d)}std::cout << {' << '.join(self.x(p) for p in partes)} << '\\n';"]
        if self.typeof(n.value) == "bool":
            return [f"{self.i(d)}std::cout << std::boolalpha << {self.x(n.value)} << '\\n';"]
        return [f"{self.i(d)}std::cout << {self.x(n.value)} << '\\n';"]

    def n_Assign(self, n, d):
        if self.declared(n.name):
            return [f"{self.i(d)}{n.name} = {self.x(n.value)};"]
        t = self.typeof(n.value)
        self.declare(n.name, t)
        if n.value[0] == "list":
            self.need("#include <vector>")
            inner = {"int": "int", "float": "double", "str": "std::string", "bool": "bool"}.get(t[5:-1], "int")
            if inner == "std::string":
                self.need("#include <string>")
            return [f"{self.i(d)}std::vector<{inner}> {n.name} = {self.x(n.value)};"]
        if partes := self.partes(n.value):
            return [f"{self.i(d)}std::string {n.name} = {self.texto_cpp(partes)};"]
        if n.value[0] == "dict":
            raise EmitError("dicionário heterogêneo em C++")
        if t == "str":
            self.need("#include <string>")
            kw = "const std::string" if n.const else "std::string"
            return [f"{self.i(d)}{kw} {n.name} = {self.x(n.value)};"]
        kw = "constexpr auto" if n.const else "auto"
        return [f"{self.i(d)}{kw} {n.name} = {self.x(n.value)};"]

    def n_Input(self, n, d):
        self.need("#include <iostream>")
        p = self.q(n.prompt)
        if n.kind == "str":
            self.need("#include <string>")
            out = [f"{self.i(d)}std::string {n.var};", f"{self.i(d)}std::cout << {p};",
                   f"{self.i(d)}std::getline(std::cin, {n.var});"]
        else:
            ct = "int" if n.kind == "int" else "double"
            out = [f"{self.i(d)}{ct} {n.var}{{}};", f"{self.i(d)}std::cout << {p};", f"{self.i(d)}std::cin >> {n.var};"]
        self.declare(n.var, n.kind)
        return out

    def n_ForRange(self, n, d):
        op, end, _ = self.range_cmp(n)
        inc = (f"++{n.var}" if n.step == 1 else f"--{n.var}" if n.step == -1 else
               f"{n.var} += {n.step}" if n.step > 0 else f"{n.var} -= {abs(n.step)}")
        header = f"for (int {n.var} = {self.x(n.start)}; {n.var} {op} {self.x(end)}; {inc})"
        return self.blk(header, n.body, d, names={n.var: "int"})

    def n_ForEach(self, n, d):
        return self.blk(f"for (const auto& {n.var} : {self.x(n.iterable)})", n.body, d)

    def n_FuncDef(self, n, d):
        pt = self.param_types(n)
        rt = self.ret_type(n, pt)
        cpp_t = {"int": "int", "float": "double", "str": "const std::string&", "bool": "bool",
                 "list[int]": "const std::vector<int>&", "list[float]": "const std::vector<double>&",
                 "list[?]": "const auto&"}
        if any(pt[p].startswith("list[int]") or pt[p].startswith("list[float]") for p in n.params):
            self.need("#include <vector>")
        if any(pt[p] == "str" for p in n.params):
            self.need("#include <string>")
        params = ", ".join(f"{cpp_t.get(pt[p], 'auto')} {p}" for p in n.params)
        ret = "void" if rt == "void" else {"str": "std::string"}.get(rt, cpp_t.get(rt, "auto"))
        self.scopes.append(dict(pt))
        try:
            body = self.body(self.with_ret(n), d + 1)
        finally:
            self.scopes.pop()
        return [f"{self.i(d)}{ret} {n.name}({params}) {{"] + body + self.close(d)

    def n_Main(self, n, d):
        lines = [f"{self.i(d)}int main() {{"] + self.block(n.body, d + 1) + [f"{self.i(d + 1)}return 0;"] + self.close(d)
        if n.hello:
            imports, self.imports = self.imports, []
            return imports + [""] + lines
        return lines

    def n_ClassDef(self, n, d):
        if any(t == "str" for _, t in n.fields):
            self.need("#include <string>")
        cpp_t = {"int": "int", "float": "double", "str": "std::string", "bool": "bool"}
        fields = [f"{self.i(d + 1)}{cpp_t.get(t, 'std::string')} {f}{'{}' if t != 'str' else ''};" for f, t in n.fields]
        return [f"{self.i(d)}struct {n.name} {{"] + fields + [f"{self.i(d)}}};"]

    def n_TryCatch(self, n, d):
        self.need("#include <exception>", "#include <iostream>")
        return (self.open("try", d) + self.body(n.body, d + 1) +
                [f"{self.i(d)}}} catch (const std::exception& e) {{",
                 f"{self.i(d + 1)}std::cerr << \"Erro: \" << e.what() << '\\n';", f"{self.i(d + 1)}throw;"] +
                self.close(d))

    def n_Import(self, n, d):
        return [f"{self.i(d)}#include <{n.module.partition(' as ')[0]}>"]

    def n_Sleep(self, n, d):
        self.need("#include <chrono>", "#include <thread>")
        if n.seconds.is_integer():
            return [f"{self.i(d)}std::this_thread::sleep_for(std::chrono::seconds({_num(n.seconds)}));"]
        return [f"{self.i(d)}std::this_thread::sleep_for(std::chrono::milliseconds({_num(n.seconds * 1000)}));"]

    def n_Call(self, n, d):
        call = f"{n.name}({', '.join(self.x(a) for a in n.args)})"
        if n.target and not self.declared(n.target):
            self.declare(n.target, "?")
            return [f"{self.i(d)}auto {n.target} = {call};"]
        return [f"{self.i(d)}{n.target} = {call};" if n.target else f"{self.i(d)}{call};"]

    def n_Append(self, n, d):
        return [f"{self.i(d)}{n.target}.push_back({self.x(n.value)});"]


class PHPEmitter(CLikeEmitter):
    lang = "php"
    elseif = "elseif"

    def n_Print(self, n, d):
        return [f"{self.i(d)}echo {self.x(n.value)} . PHP_EOL;"]

    def n_Assign(self, n, d):
        if n.const and n.value[0] in ("num", "str", "bool"):
            return [f"{self.i(d)}const {n.name.upper()} = {self.x(n.value)};"]
        return [f"{self.i(d)}${n.name} = {self.x(n.value)};"]

    def n_Input(self, n, d):
        cast = {"int": "(int) ", "float": "(float) "}.get(n.kind, "")
        return [f"{self.i(d)}${n.var} = {cast}readline({self.q(n.prompt)});"]

    def n_ForRange(self, n, d):
        return self.blk(self.c_for(n, ""), n.body, d, names={n.var: "int"})

    def n_ForEach(self, n, d):
        return self.blk(f"foreach ({self.x(n.iterable)} as ${n.var})", n.body, d)

    _PHP_T = {"int": "int", "float": "float", "str": "string", "bool": "bool"}

    def n_FuncDef(self, n, d):
        pt = self.param_types(n)
        rt = self.ret_type(n, pt)
        params = ", ".join(f"{'array' if pt[p].startswith('list') else self._PHP_T.get(pt[p], '')} ${p}".strip()
                           for p in n.params)
        ret = ": void" if rt == "void" else (f": {self._PHP_T[rt]}" if rt in self._PHP_T else "")
        self.scopes.append(dict(pt))
        try:
            body = self.body(self.with_ret(n), d + 1)
        finally:
            self.scopes.pop()
        return [f"{self.i(d)}function {n.name}({params}){ret}", f"{self.i(d)}{{"] + body + self.close(d)

    def n_Main(self, n, d):
        if n.hello:
            return self.block(n.body, d)
        return ([f"{self.i(d)}function main(): void", f"{self.i(d)}{{"] + self.body(n.body, d + 1) + self.close(d) +
                ["", f"{self.i(d)}main();"])

    def n_ClassDef(self, n, d):
        props = [f"{self.i(d + 2)}public {self._PHP_T.get(t, 'string')} ${f}," for f, t in n.fields]
        return ([f"{self.i(d)}final class {n.name}", f"{self.i(d)}{{",
                 f"{self.i(d + 1)}public function __construct("] + props +
                [f"{self.i(d + 1)}) {{", f"{self.i(d + 1)}}}", f"{self.i(d)}}}"])

    def n_TryCatch(self, n, d):
        return (self.open("try", d) + self.body(n.body, d + 1) +
                [f"{self.i(d)}}} catch (\\Throwable $e) {{", f"{self.i(d + 1)}error_log($e->getMessage());",
                 f"{self.i(d + 1)}throw $e;"] + self.close(d))

    def n_Import(self, n, d):
        mod = n.module.partition(" as ")[0]
        if "\\" in mod:
            return [f"{self.i(d)}use {mod};"]
        return [f"{self.i(d)}require_once '{mod if mod.endswith('.php') else mod + '.php'}';"]

    def n_Sleep(self, n, d):
        if n.seconds.is_integer():
            return [f"{self.i(d)}sleep({_num(n.seconds)});"]
        return [f"{self.i(d)}usleep({int(n.seconds * 1_000_000)});"]

    def n_Call(self, n, d):
        call = f"{n.name}({', '.join(self.x(a) for a in n.args)})"
        return [f"{self.i(d)}${n.target} = {call};" if n.target else f"{self.i(d)}{call};"]

    def n_Append(self, n, d):
        return [f"{self.i(d)}${n.target}[] = {self.x(n.value)};"]


# =============================================================================== Ruby / Lua

class RubyEmitter(Emitter):
    lang = "ruby"
    unit = "  "

    def end(self, d):
        return [self.i(d) + "end"]

    def n_Print(self, n, d):
        return [f"{self.i(d)}puts {self.x(n.value)}"]

    def n_Assign(self, n, d):
        name = n.name.upper() if n.const else n.name
        self.declare(n.name, self.typeof(n.value))
        return [f"{self.i(d)}{name} = {self.x(n.value)}"]

    def n_Input(self, n, d):
        conv = {"int": ".to_i", "float": ".to_f"}.get(n.kind, ".chomp")
        return [f"{self.i(d)}print {self.q(n.prompt)}", f"{self.i(d)}{n.var} = gets.to_s{conv}"]

    def n_ForRange(self, n, d):
        s, e = self.x(n.start), self.x(n.end)
        if n.step == 1:
            head = (f"{e}.times do |{n.var}|" if uses_var(n.body, n.var) else f"{e}.times do") \
                if _is_zero(n.start) and not n.inclusive else \
                f"({s}{'..' if n.inclusive else '...'}{e}).each do |{n.var}|"
        elif n.step == -1 and n.inclusive:
            head = f"{s}.downto({e}) do |{n.var}|"
        else:
            end = e if n.inclusive else self.x(_shift(n.end, -1 if n.step > 0 else 1))
            head = f"{s}.step({end}, {n.step}) do |{n.var}|"
        return [self.i(d) + head] + self.body(n.body, d + 1) + self.end(d)

    def n_ForEach(self, n, d):
        return [f"{self.i(d)}{self.x(n.iterable)}.each do |{n.var}|"] + self.body(n.body, d + 1) + self.end(d)

    def n_While(self, n, d):
        head = "loop do" if n.cond == ("bool", True) else f"while {self.x(n.cond)}"
        return [self.i(d) + head] + self.body(n.body, d + 1) + self.end(d)

    def n_If(self, n, d):
        out = [f"{self.i(d)}if {self.x(n.cond)}"] + self.body(n.body, d + 1)
        for cond, body in n.elifs:
            out += [f"{self.i(d)}elsif {self.x(cond)}"] + self.body(body, d + 1)
        if n.orelse is not None:
            out += [f"{self.i(d)}else"] + self.body(n.orelse, d + 1)
        return out + self.end(d)

    def n_FuncDef(self, n, d):
        body = self.body(n.body, d + 1) if n.body else []
        if n.ret is not None:
            body = [b for b in body if b.strip() != self.placeholder] + [self.i(d + 1) + self.x(n.ret)]
        return [f"{self.i(d)}def {n.name}({', '.join(n.params)})"] + (body or [self.i(d + 1) + self.placeholder]) + \
            self.end(d)

    def n_Main(self, n, d):
        if n.hello:
            return self.block(n.body, d)
        return ([f"{self.i(d)}def main"] + self.body(n.body, d + 1) + self.end(d) +
                ["", f"{self.i(d)}main if __FILE__ == $PROGRAM_NAME"])

    def n_ClassDef(self, n, d):
        names = [f for f, _ in n.fields]
        out = [f"{self.i(d)}class {n.name}"]
        if names:
            out += [f"{self.i(d + 1)}attr_accessor " + ", ".join(f":{f}" for f in names), "",
                    f"{self.i(d + 1)}def initialize({', '.join(names)})"]
            out += [f"{self.i(d + 2)}@{f} = {f}" for f in names] + [f"{self.i(d + 1)}end"]
        return out + self.end(d)

    def n_TryCatch(self, n, d):
        return ([f"{self.i(d)}begin"] + self.body(n.body, d + 1) +
                [f"{self.i(d)}rescue StandardError => e", f'{self.i(d + 1)}warn "Erro: #{{e.message}}"',
                 f"{self.i(d + 1)}raise"] + self.end(d))

    def n_Return(self, n, d):
        return [f"{self.i(d)}return" + (f" {self.x(n.value)}" if n.value is not None else "")]

    def n_Import(self, n, d):
        return [f'{self.i(d)}require "{n.module.partition(" as ")[0]}"']

    def n_Sleep(self, n, d):
        return [f"{self.i(d)}sleep {_num(n.seconds)}"]

    def n_Call(self, n, d):
        call = f"{n.name}({', '.join(self.x(a) for a in n.args)})"
        return [f"{self.i(d)}{n.target} = {call}" if n.target else f"{self.i(d)}{call}"]

    def n_Append(self, n, d):
        return [f"{self.i(d)}{n.target} << {self.x(n.value)}"]

    def n_Break(self, n, d):
        return [self.i(d) + "break"]

    def n_Continue(self, n, d):
        return [self.i(d) + "next"]


class LuaEmitter(RubyEmitter):
    lang = "lua"
    placeholder = "-- TODO"
    comment = "--"

    def compound_assign(self, name, op, rhs, d):
        return [f"{self.i(d)}{name} = {self.x(('bin', op, ('id', name), rhs))}"]

    def n_Print(self, n, d):
        return [f"{self.i(d)}print({self.x(n.value)})"]

    def n_Assign(self, n, d):
        name = n.name.upper() if n.const else n.name
        if self.declared(name):
            return [f"{self.i(d)}{name} = {self.x(n.value)}"]
        self.declare(name, self.typeof(n.value))
        return [f"{self.i(d)}local {name} = {self.x(n.value)}"]

    def n_Input(self, n, d):
        read = 'io.read("*l")'
        if n.kind in ("int", "float"):
            read = f"tonumber({read})"
        self.declare(n.var, n.kind)
        return [f"{self.i(d)}io.write({self.q(n.prompt)})", f"{self.i(d)}local {n.var} = {read}"]

    def n_ForRange(self, n, d):
        end = n.end if n.inclusive else _shift(n.end, -1 if n.step > 0 else 1)
        step = f", {n.step}" if n.step != 1 else ""
        return [f"{self.i(d)}for {n.var} = {self.x(n.start)}, {self.x(end)}{step} do"] + self.body(n.body, d + 1) + \
            self.end(d)

    def n_ForEach(self, n, d):
        return [f"{self.i(d)}for _, {n.var} in ipairs({self.x(n.iterable)}) do"] + self.body(n.body, d + 1) + self.end(d)

    def n_While(self, n, d):
        cond = "true" if n.cond == ("bool", True) else self.x(n.cond)
        return [f"{self.i(d)}while {cond} do"] + self.body(n.body, d + 1) + self.end(d)

    def n_If(self, n, d):
        out = [f"{self.i(d)}if {self.x(n.cond)} then"] + self.body(n.body, d + 1)
        for cond, body in n.elifs:
            out += [f"{self.i(d)}elseif {self.x(cond)} then"] + self.body(body, d + 1)
        if n.orelse is not None:
            out += [f"{self.i(d)}else"] + self.body(n.orelse, d + 1)
        return out + self.end(d)

    def n_FuncDef(self, n, d):
        body = self.body(self.with_ret(n), d + 1)
        return [f"{self.i(d)}local function {n.name}({', '.join(n.params)})"] + body + self.end(d)

    def n_Main(self, n, d):
        if n.hello:
            return self.block(n.body, d)
        return [f"{self.i(d)}local function main()"] + self.body(n.body, d + 1) + self.end(d) + ["", f"{self.i(d)}main()"]

    def n_ClassDef(self, n, d):
        names = [f for f, _ in n.fields]
        return ([f"{self.i(d)}local {n.name} = {{}}", f"{self.i(d)}{n.name}.__index = {n.name}", "",
                 f"{self.i(d)}function {n.name}.new({', '.join(names)})",
                 f"{self.i(d + 1)}local self = setmetatable({{}}, {n.name})"] +
                [f"{self.i(d + 1)}self.{f} = {f}" for f in names] + [f"{self.i(d + 1)}return self"] + self.end(d))

    def n_TryCatch(self, n, d):
        return ([f"{self.i(d)}local ok, err = pcall(function()"] + self.body(n.body, d + 1) +
                [f"{self.i(d)}end)", f"{self.i(d)}if not ok then",
                 f'{self.i(d + 1)}io.stderr:write("Erro: " .. tostring(err) .. "\\n")'] + self.end(d))

    def n_Import(self, n, d):
        mod, _, alias = n.module.partition(" as ")
        return [f'{self.i(d)}local {alias or mod.split(".")[-1]} = require("{mod}")']

    def n_Sleep(self, n, d):
        return [f"{self.i(d)}-- Lua padrão não tem sleep; no Neovim use vim.wait({_num(n.seconds * 1000)})",
                f'{self.i(d)}os.execute("sleep {_num(n.seconds)}")']

    def n_Call(self, n, d):
        call = f"{n.name}({', '.join(self.x(a) for a in n.args)})"
        if n.target:
            prefix = "" if self.declared(n.target) else "local "
            self.declare(n.target, "?")
            return [f"{self.i(d)}{prefix}{n.target} = {call}"]
        return [f"{self.i(d)}{call}"]

    def n_Append(self, n, d):
        return [f"{self.i(d)}table.insert({n.target}, {self.x(n.value)})"]

    def n_Continue(self, n, d):
        raise EmitError("Lua não tem continue")


# =============================================================================== shells

class BashEmitter(Emitter):
    lang = "bash"
    unit = "  "
    placeholder = ":"

    def compound_assign(self, name, op, rhs, d):
        if E.is_numeric_cond(rhs):
            return [f"{self.i(d)}(( {name} {op}= {self.x(rhs, arith=True)} ))"]
        return [f"{self.i(d)}{name}+={self.val(rhs)}"]

    def cond(self, node: E.Ast) -> str:
        if node == ("bool", True):
            return "true"
        if E.is_numeric_cond(node):
            return f"(( {self.x(node, arith=True)} ))"
        return f"[[ {self.x(node)} ]]"

    def texto_bash(self, partes: list[E.Ast]) -> str:
        out = []
        for p in partes:
            if p[0] == "str":
                out.append(p[1].replace("\\", "\\\\").replace('"', '\\"').replace("$", "\\$").replace("`", "\\`"))
            elif p[0] == "id":
                out.append("${" + p[1] + "}")
            elif p[0] == "num":
                out.append(p[1])
            else:
                out.append(f"$(( {self.x(p[1] if p[0] == 'paren' else p, arith=True)} ))")
        return '"' + "".join(out) + '"'

    def val(self, node: E.Ast) -> str:
        t = self.typeof(node)
        if partes := self.partes(node):
            return self.texto_bash(partes)
        if node[0] == "call" and node[1][0] == "id" and node[1][1].lower() not in E._LEN_NAMES:
            args = " ".join(self.val(a) if a[0] != "num" else a[1] for a in node[2])
            return f'"$({node[1][1]}{" " + args if args else ""})"'  # resultado=$(dobro 5)
        if node[0] in ("str", "num", "id"):
            return self.x(node) if node[0] != "id" else f'"${node[1]}"'
        if node[0] == "list":
            return self.x(node)
        if node[0] == "dict":
            return "(" + " ".join(f"[{k}]={self.x(v)}" for k, v in node[1]) + ")"
        if t in ("int", "float", "?", "num?") and E.is_numeric_cond(node):
            return f"$(( {self.x(node, arith=True)} ))"
        return f'"{self.x(node)}"'

    def n_Print(self, n, d):
        v = n.value
        if v[0] == "str":
            return [f"{self.i(d)}echo {self.x(v)}"]
        if v[0] == "id":
            return [f'{self.i(d)}echo "${v[1]}"']
        return [f"{self.i(d)}echo {self.val(v)}"]

    def n_Assign(self, n, d):
        prefix = "readonly " if n.const else ("declare -A " if n.value[0] == "dict" else "")
        return [f"{self.i(d)}{prefix}{n.name}={self.val(n.value)}"]

    def n_Input(self, n, d):
        return [f'{self.i(d)}read -rp "{n.prompt}" {n.var}']

    def n_ForRange(self, n, d):
        op, end, inc = self.range_cmp(n)
        head = f"for (( {n.var} = {self.x(n.start, True)}; {n.var} {op} {self.x(end, True)}; {inc} )); do"
        return [self.i(d) + head] + self.body(n.body, d + 1) + [self.i(d) + "done"]

    def n_ForEach(self, n, d):
        it = n.iterable
        src = f'"${{{it[1]}[@]}}"' if it[0] == "id" else self.x(it)
        return [f"{self.i(d)}for {n.var} in {src}; do"] + self.body(n.body, d + 1) + [self.i(d) + "done"]

    def n_While(self, n, d):
        return [f"{self.i(d)}while {self.cond(n.cond)}; do"] + self.body(n.body, d + 1) + [self.i(d) + "done"]

    def n_If(self, n, d):
        out = [f"{self.i(d)}if {self.cond(n.cond)}; then"] + self.body(n.body, d + 1)
        for cond, body in n.elifs:
            out += [f"{self.i(d)}elif {self.cond(cond)}; then"] + self.body(body, d + 1)
        if n.orelse is not None:
            out += [f"{self.i(d)}else"] + self.body(n.orelse, d + 1)
        return out + [self.i(d) + "fi"]

    def n_FuncDef(self, n, d):
        out = [f"{self.i(d)}{n.name}() {{"]
        if n.params:
            out.append(self.i(d + 1) + "local " + " ".join(f'{p}="${k + 1}"' for k, p in enumerate(n.params)))
        body = self.block(n.body, d + 1)
        if n.ret is not None:
            body.append(f"{self.i(d + 1)}echo {self.val(n.ret)}")
        return out + (body or [self.i(d + 1) + ":"]) + [self.i(d) + "}"]

    def n_Main(self, n, d):
        if n.hello:
            return self.block(n.body, d)
        return [f"{self.i(d)}main() {{"] + self.body(n.body, d + 1) + [self.i(d) + "}", "", f'{self.i(d)}main "$@"']

    def n_ClassDef(self, n, d):
        raise EmitError("bash não tem classes")

    def n_TryCatch(self, n, d):
        return [f"{self.i(d)}set -Eeuo pipefail", f"{self.i(d)}trap 'echo \"Erro na linha $LINENO\" >&2' ERR"] + \
            self.block(n.body, d)

    def n_Return(self, n, d):
        if n.value is None:
            return [self.i(d) + "return"]
        return [f"{self.i(d)}echo {self.val(n.value)}"]

    def n_Import(self, n, d):
        return [f'{self.i(d)}source "{n.module.partition(" as ")[0]}"']

    def n_Sleep(self, n, d):
        return [f"{self.i(d)}sleep {_num(n.seconds)}"]

    def n_Call(self, n, d):
        args = " ".join(self.val(a) for a in n.args)
        call = f"{n.name} {args}".strip()
        return [f'{self.i(d)}{n.target}="$({call})"' if n.target else self.i(d) + call]

    def n_Append(self, n, d):
        return [f"{self.i(d)}{n.target}+=({self.val(n.value)})"]


class PowerShellEmitter(CLikeEmitter):
    lang = "powershell"
    placeholder = "# TODO"
    comment = "#"
    semi = ""
    elseif = "elseif"

    _PS_T = {"int": "[int]", "float": "[double]", "str": "[string]", "bool": "[bool]"}

    def cond(self, node: E.Ast) -> str:
        return f"({self.x(node)})"

    def n_Print(self, n, d):
        v = self.x(n.value)  # modo argumento: `Write-Output $x + $y` imprimiria 3 valores
        return [f"{self.i(d)}Write-Output " + (f"({v})" if n.value[0] in ("bin", "un") else v)]

    def n_Assign(self, n, d):
        if n.const:
            return [f"{self.i(d)}Set-Variable -Name {n.name.upper()} -Value {self.x(n.value)} -Option Constant"]
        value = self.x(n.value)
        if n.value[0] == "list" and n.name in self.appended:
            value = f"[System.Collections.Generic.List[object]]{value}"
        return [f"{self.i(d)}${n.name} = {value}"]

    def n_Input(self, n, d):
        prompt = n.prompt.rstrip().rstrip(":").rstrip()
        call = f"Read-Host -Prompt {self.q(prompt)}"
        if n.kind in ("int", "float"):
            call = f"{self._PS_T[n.kind]}({call})"
        return [f"{self.i(d)}${n.var} = {call}"]

    def n_ForRange(self, n, d):
        op, end, inc = self.range_cmp(n)
        ops = {"<=": "-le", "<": "-lt", ">=": "-ge", ">": "-gt"}
        inc = inc.replace(f"{n.var}", f"${n.var}", 1)
        head = f"for (${n.var} = {self.x(n.start)}; ${n.var} {ops[op]} {self.x(end)}; {inc})"
        return self.blk(head, n.body, d, names={n.var: "int"})

    def n_ForEach(self, n, d):
        return self.blk(f"foreach (${n.var} in {self.x(n.iterable)})", n.body, d)

    def n_While(self, n, d):
        return self.blk(f"while {self.cond(n.cond)}", n.body, d)

    def n_FuncDef(self, n, d):
        pt = self.param_types(n)
        out = [f"{self.i(d)}function {n.name} {{", f"{self.i(d + 1)}[CmdletBinding()]"]
        if n.params:
            out.append(f"{self.i(d + 1)}param(")
            plist = [f"{self.i(d + 2)}[Parameter(Mandatory)]{E.ps_type(pt[p])}${p}" for p in n.params]
            out += [p + ("," if k < len(plist) - 1 else "") for k, p in enumerate(plist)]
            out.append(f"{self.i(d + 1)})")
        else:
            out.append(f"{self.i(d + 1)}param()")
        body = self.block(n.body, d + 1)
        if n.ret is not None:
            body.append(f"{self.i(d + 1)}return {self.x(n.ret)}")
        return out + (body or [self.i(d + 1) + self.placeholder]) + self.close(d)

    def n_Main(self, n, d):
        if n.hello:
            return self.block(n.body, d)
        return self.blk("function Main", n.body, d) + ["", f"{self.i(d)}Main"]

    def n_ClassDef(self, n, d):
        props = [f"{self.i(d + 1)}{self._PS_T.get(t, '[string]')}${_pascal(f)}" for f, t in n.fields]
        args = ", ".join(f"{self._PS_T.get(t, '[string]')}${f}" for f, t in n.fields)
        ctor = ([f"{self.i(d + 1)}{n.name}({args}) {{"] +
                [f"{self.i(d + 2)}$this.{_pascal(f)} = ${f}" for f, _ in n.fields] + [f"{self.i(d + 1)}}}"])
        return [f"{self.i(d)}class {n.name} {{"] + props + ([""] if props else []) + ctor + self.close(d)

    def n_TryCatch(self, n, d):
        return (self.open("try", d) + self.body(n.body, d + 1) + self.close(d) + self.open("catch", d) +
                [f'{self.i(d + 1)}Write-Error "Erro: $_"', f"{self.i(d + 1)}throw"] + self.close(d))

    def n_Return(self, n, d):
        return [f"{self.i(d)}return" + (f" {self.x(n.value)}" if n.value is not None else "")]

    def n_Import(self, n, d):
        return [f"{self.i(d)}Import-Module {n.module.partition(' as ')[0]}"]

    def n_Sleep(self, n, d):
        if n.seconds.is_integer():
            return [f"{self.i(d)}Start-Sleep -Seconds {_num(n.seconds)}"]
        return [f"{self.i(d)}Start-Sleep -Milliseconds {_num(n.seconds * 1000)}"]

    def n_Call(self, n, d):
        call = f"{n.name} {' '.join(self.x(a) for a in n.args)}".strip()
        return [f"{self.i(d)}${n.target} = {call}" if n.target else self.i(d) + call]

    def n_Append(self, n, d):
        return [f"{self.i(d)}${n.target}.Add({self.x(n.value)})"]

    def n_Break(self, n, d):
        return [self.i(d) + "break"]

    def n_Continue(self, n, d):
        return [self.i(d) + "continue"]


# =============================================================================== Kotlin

class KotlinEmitter(CLikeEmitter):
    lang = "kotlin"
    semi = ""
    scripting = False

    def n_Print(self, n, d):
        return [f"{self.i(d)}println({self.x(n.value)})"]

    def n_Assign(self, n, d):
        if self.declared(n.name):
            return [f"{self.i(d)}{n.name} = {self.x(n.value)}"]
        t = self.typeof(n.value)
        self.declare(n.name, t)
        value = self.x(n.value)
        if n.value[0] == "list" and (n.name in self.appended or not n.value[1]):
            inner = E.kotlin_type(t[5:-1]) if t.startswith("list[") else "Any"
            value = f"mutableListOf<{inner}>({', '.join(self.x(v) for v in n.value[1])})"
        kw = "var" if n.name in self.mutable and not n.const and n.name not in self.appended else "val"
        return [f"{self.i(d)}{kw} {n.name} = {value}"]

    def n_Input(self, n, d):
        conv = {"int": ".trim().toInt()", "float": ".trim().toDouble()"}.get(n.kind, "")
        self.declare(n.var, n.kind)
        return [f"{self.i(d)}print({self.q(n.prompt)})", f"{self.i(d)}val {n.var} = readln(){conv}"]

    def n_ForRange(self, n, d):
        s, e = self.x(n.start), self.x(n.end)
        if _is_zero(n.start) and n.step == 1 and not n.inclusive and not uses_var(n.body, n.var):
            return self.blk(f"repeat({e})", n.body, d)  # repetir N vezes, sem variável
        if n.step > 0:
            rng = f"{s}..{e}" if n.inclusive else f"{s} until {e}"
            rng += f" step {n.step}" if n.step != 1 else ""
        else:
            fim = e if n.inclusive else self.x(_shift(n.end, 1))
            rng = f"{s} downTo {fim}" + (f" step {-n.step}" if n.step != -1 else "")
        return self.blk(f"for ({n.var} in {rng})", n.body, d, names={n.var: "int"})

    def n_ForEach(self, n, d):
        return self.blk(f"for ({n.var} in {self.x(n.iterable)})", n.body, d, names={n.var: "?"})

    def n_FuncDef(self, n, d):
        pt = self.param_types(n)
        rt = self.ret_type(n, pt)
        params = ", ".join(f"{p}: {E.kotlin_type(pt[p])}" for p in n.params)
        ret = "" if rt == "void" else f": {E.kotlin_type(rt)}"
        self.scopes.append(dict(pt))
        try:
            body = self.body(self.with_ret(n), d + 1)
        finally:
            self.scopes.pop()
        return [f"{self.i(d)}fun {n.name}({params}){ret} {{"] + body + self.close(d)

    def n_Main(self, n, d):
        return self.blk("fun main()", n.body, d)

    def n_ClassDef(self, n, d):
        campos = ", ".join(f"val {f}: {E.kotlin_type(t) if t != '?' else 'String'}" for f, t in n.fields)
        return [f"{self.i(d)}data class {n.name}({campos})"]

    def n_TryCatch(self, n, d):
        return (self.open("try", d) + self.body(n.body, d + 1) +
                [f"{self.i(d)}}} catch (e: Exception) {{",
                 f'{self.i(d + 1)}System.err.println("Erro: ${{e.message}}")', f"{self.i(d + 1)}throw e"] +
                self.close(d))

    def n_Import(self, n, d):
        return [f"{self.i(d)}import {n.module.partition(' as ')[0]}"]

    def n_Sleep(self, n, d):
        return [f"{self.i(d)}Thread.sleep({_num(n.seconds * 1000)})"]

    def n_Call(self, n, d):
        call = f"{n.name}({', '.join(self.x(a) for a in n.args)})"
        if n.target and not self.declared(n.target):
            self.declare(n.target, "?")
            return [f"{self.i(d)}val {n.target} = {call}"]
        return [f"{self.i(d)}{n.target} = {call}" if n.target else f"{self.i(d)}{call}"]

    def n_Append(self, n, d):
        return [f"{self.i(d)}{n.target}.add({self.x(n.value)})"]


# =============================================================================== Swift

class SwiftEmitter(CLikeEmitter):
    lang = "swift"
    semi = ""
    cond_parens = False

    def n_Print(self, n, d):
        return [f"{self.i(d)}print({self.x(n.value)})"]

    def n_Assign(self, n, d):
        if self.declared(n.name):
            return [f"{self.i(d)}{n.name} = {self.x(n.value)}"]
        t = self.typeof(n.value)
        self.declare(n.name, t)
        kw = "var" if n.name in self.mutable and not n.const else "let"
        if n.value[0] == "list" and not n.value[1]:
            return [f"{self.i(d)}var {n.name}: {E.swift_type(t)} = []"]
        return [f"{self.i(d)}{kw} {n.name} = {self.x(n.value)}"]

    def n_Input(self, n, d):
        out = [f'{self.i(d)}print({self.q(n.prompt)}, terminator: "")']
        if n.kind == "int":
            out.append(f'{self.i(d)}let {n.var} = Int(readLine() ?? "") ?? 0')
        elif n.kind == "float":
            out.append(f'{self.i(d)}let {n.var} = Double(readLine() ?? "") ?? 0')
        else:
            out.append(f'{self.i(d)}let {n.var} = readLine() ?? ""')
        self.declare(n.var, n.kind)
        return out

    def n_ForRange(self, n, d):
        s, e = self.x(n.start), self.x(n.end)
        var = n.var if uses_var(n.body, n.var) else "_"
        if n.step == 1:
            rng = f"{s}...{e}" if n.inclusive else f"{s}..<{e}"
        else:
            rng = f"stride(from: {s}, {'through' if n.inclusive else 'to'}: {e}, by: {n.step})"
        return self.blk(f"for {var} in {rng}", n.body, d, names={n.var: "int"})

    def n_ForEach(self, n, d):
        return self.blk(f"for {n.var} in {self.x(n.iterable)}", n.body, d, names={n.var: "?"})

    def n_FuncDef(self, n, d):
        pt = self.param_types(n)
        rt = self.ret_type(n, pt)
        params = ", ".join(f"_ {p}: {E.swift_type(pt[p])}" for p in n.params)
        ret = "" if rt == "void" else f" -> {E.swift_type(rt)}"
        self.scopes.append(dict(pt))
        try:
            body = self.body(self.with_ret(n), d + 1)
        finally:
            self.scopes.pop()
        return [f"{self.i(d)}func {n.name}({params}){ret} {{"] + body + self.close(d)

    def n_Main(self, n, d):
        if n.hello:
            return self.block(n.body, d)
        return self.blk("func main()", n.body, d) + ["", f"{self.i(d)}main()"]

    def n_ClassDef(self, n, d):
        campos = [f"{self.i(d + 1)}let {f}: {E.swift_type(t) if t != '?' else 'String'}" for f, t in n.fields]
        return [f"{self.i(d)}struct {n.name} {{"] + campos + self.close(d)

    def n_TryCatch(self, n, d):
        return (self.open("do", d) + self.body(n.body, d + 1) +
                [f"{self.i(d)}}} catch {{", f'{self.i(d + 1)}print("Erro: \\(error)")'] + self.close(d))

    def n_Import(self, n, d):
        return [f"{self.i(d)}import {n.module.partition(' as ')[0]}"]

    def n_Sleep(self, n, d):
        self.need("import Foundation")
        return [f"{self.i(d)}Thread.sleep(forTimeInterval: {_num(n.seconds)})"]

    def n_Call(self, n, d):
        call = f"{n.name}({', '.join(self.x(a) for a in n.args)})"
        if n.target and not self.declared(n.target):
            self.declare(n.target, "?")
            return [f"{self.i(d)}let {n.target} = {call}"]
        return [f"{self.i(d)}{n.target} = {call}" if n.target else f"{self.i(d)}{call}"]

    def n_Append(self, n, d):
        return [f"{self.i(d)}{n.target}.append({self.x(n.value)})"]


# =============================================================================== Dart

class DartEmitter(CLikeEmitter):
    lang = "dart"
    unit = "  "
    scripting = False

    def n_Print(self, n, d):
        return [f"{self.i(d)}print({self.x(n.value)});"]

    def n_Assign(self, n, d):
        if self.declared(n.name):
            return [f"{self.i(d)}{n.name} = {self.x(n.value)};"]
        t = self.typeof(n.value)
        self.declare(n.name, t)
        if n.value[0] == "list" and not n.value[1]:
            return [f"{self.i(d)}final {n.name} = <{E.dart_type(_elem_or_any(t))}>[];"]
        kw = "var" if n.name in self.mutable and not n.const and n.name not in self.appended else "final"
        return [f"{self.i(d)}{kw} {n.name} = {self.x(n.value)};"]

    def n_Input(self, n, d):
        self.need("import 'dart:io';")
        leitura = '(stdin.readLineSync() ?? "")'
        valor = {"int": f"int.parse({leitura}.trim())", "float": f"double.parse({leitura}.trim())"}.get(n.kind, leitura)
        self.declare(n.var, n.kind)
        return [f"{self.i(d)}stdout.write({self.q(n.prompt)});", f"{self.i(d)}final {n.var} = {valor};"]

    def n_ForRange(self, n, d):
        return self.blk(self.c_for(n, "var "), n.body, d, names={n.var: "int"})

    def n_ForEach(self, n, d):
        return self.blk(f"for (final {n.var} in {self.x(n.iterable)})", n.body, d, names={n.var: "?"})

    def n_FuncDef(self, n, d):
        pt = self.param_types(n)
        rt = self.ret_type(n, pt)
        params = ", ".join(f"{E.dart_type(pt[p])} {p}" for p in n.params)
        ret = "void" if rt == "void" else E.dart_type(rt)
        self.scopes.append(dict(pt))
        try:
            body = self.body(self.with_ret(n), d + 1)
        finally:
            self.scopes.pop()
        return [f"{self.i(d)}{ret} {n.name}({params}) {{"] + body + self.close(d)

    def n_Main(self, n, d):
        return self.blk("void main()", n.body, d)

    def n_ClassDef(self, n, d):
        campos = [f"{self.i(d + 1)}final {E.dart_type(t) if t != '?' else 'String'} {f};" for f, t in n.fields]
        args = ", ".join(f"this.{f}" for f, _ in n.fields)
        return ([f"{self.i(d)}class {n.name} {{"] + campos + ([""] if campos else []) +
                [f"{self.i(d + 1)}{n.name}({args});"] + self.close(d))

    def n_TryCatch(self, n, d):
        return (self.open("try", d) + self.body(n.body, d + 1) +
                [f"{self.i(d)}}} catch (e) {{", f'{self.i(d + 1)}print("Erro: $e");', f"{self.i(d + 1)}rethrow;"] +
                self.close(d))

    def n_Import(self, n, d):
        mod, _, alias = n.module.partition(" as ")
        alvo = mod if ":" in mod else f"package:{mod}/{mod}.dart"
        return [f"{self.i(d)}import '{alvo}'{' as ' + alias if alias else ''};"]

    def n_Sleep(self, n, d):
        self.need("import 'dart:io';")
        return [f"{self.i(d)}sleep(Duration(milliseconds: {_num(n.seconds * 1000)}));"]

    def n_Call(self, n, d):
        call = f"{n.name}({', '.join(self.x(a) for a in n.args)})"
        if n.target and not self.declared(n.target):
            self.declare(n.target, "?")
            return [f"{self.i(d)}final {n.target} = {call};"]
        return [f"{self.i(d)}{n.target} = {call};" if n.target else f"{self.i(d)}{call};"]

    def n_Append(self, n, d):
        return [f"{self.i(d)}{n.target}.add({self.x(n.value)});"]


def _elem_or_any(t: str) -> str:
    return t[5:-1] if t.startswith("list[") else "?"


# =============================================================================== R

class REmitter(CLikeEmitter):
    lang = "r"
    unit = "  "
    semi = ""
    comment = "#"
    placeholder = "# TODO"

    def n_Print(self, n, d):
        v = n.value
        if v[0] == "str" or self.typeof(v) in ("str", "int", "float") or (v[0] == "bin" and v[1] == "+"):
            return [f'{self.i(d)}cat({self.x(v)}, "\\n", sep = "")']  # valor sem o [1] e as aspas do print
        return [f"{self.i(d)}print({self.x(v)})"]

    def n_Assign(self, n, d):
        self.declare(n.name, self.typeof(n.value))
        return [f"{self.i(d)}{n.name} <- {self.x(n.value)}"]

    def compound_assign(self, name, op, rhs, d):
        return [f"{self.i(d)}{name} <- {self.x(('bin', op, ('id', name), rhs))}"]

    def n_Input(self, n, d):
        out = []
        if not self.declared("entrada"):  # no Rscript, readline() não espera: lê-se do stdin
            self.declare("entrada", "?")
            out.append(f'{self.i(d)}entrada <- file("stdin", "r")')
        leitura = "readLines(entrada, n = 1)"
        valor = {"int": f"as.integer({leitura})", "float": f"as.numeric({leitura})"}.get(n.kind, leitura)
        self.declare(n.var, n.kind)
        return out + [f"{self.i(d)}cat({self.q(n.prompt)})", f"{self.i(d)}{n.var} <- {valor}"]

    def n_ForRange(self, n, d):
        s, e = self.x(n.start), self.x(n.end)
        if _is_zero(n.start) and n.step == 1 and not n.inclusive:
            seq = f"seq_len({e})" + (" - 1" if uses_var(n.body, n.var) else "")
        else:
            fim = e if n.inclusive else self.x(_shift(n.end, -1 if n.step > 0 else 1))
            seq = f"seq({s}, {fim})" if n.step == 1 else f"seq({s}, {fim}, by = {n.step})"
        return self.blk(f"for ({n.var} in {seq})", n.body, d, names={n.var: "int"})

    def n_ForEach(self, n, d):
        lista = self.typeof(n.iterable)
        item = lista[5:-1] if lista.startswith("list[") else "?"
        return self.blk(f"for ({n.var} in {self.x(n.iterable)})", n.body, d, names={n.var: item})

    def n_FuncDef(self, n, d):
        self.scopes.append(dict(self.param_types(n)))
        try:
            body = self.body(self.with_ret(n), d + 1)
        finally:
            self.scopes.pop()
        return [f"{self.i(d)}{n.name} <- function({', '.join(n.params)}) {{"] + body + self.close(d)

    def n_Return(self, n, d):
        return [f"{self.i(d)}return({self.x(n.value) if n.value is not None else 'invisible(NULL)'})"]

    def n_Main(self, n, d):
        if n.hello:
            return self.block(n.body, d)
        return self.blk("main <- function()", n.body, d) + ["", f"{self.i(d)}main()"]

    def n_ClassDef(self, n, d):
        nomes = [f for f, _ in n.fields]
        lista = ", ".join(f"{f} = {f}" for f in nomes)
        return ([f"{self.i(d)}{n.name} <- function({', '.join(nomes)}) {{",
                 f'{self.i(d + 1)}structure(list({lista}), class = "{n.name}")'] + self.close(d))

    def n_TryCatch(self, n, d):
        return ([f"{self.i(d)}tryCatch({{"] + self.body(n.body, d + 1) +
                [f"{self.i(d)}}}, error = function(e) {{", f'{self.i(d + 1)}message("Erro: ", conditionMessage(e))',
                 f"{self.i(d + 1)}stop(e)", f"{self.i(d)}}})"])

    def n_Import(self, n, d):
        return [f"{self.i(d)}library({n.module.partition(' as ')[0]})"]

    def n_Sleep(self, n, d):
        return [f"{self.i(d)}Sys.sleep({_num(n.seconds)})"]

    def n_Call(self, n, d):
        call = f"{n.name}({', '.join(self.x(a) for a in n.args)})"
        return [f"{self.i(d)}{n.target} <- {call}" if n.target else f"{self.i(d)}{call}"]

    def n_Append(self, n, d):
        return [f"{self.i(d)}{n.target} <- c({n.target}, {self.x(n.value)})"]

    def n_Continue(self, n, d):
        return [self.i(d) + "next"]


# =============================================================================== Julia

class JuliaEmitter(RubyEmitter):
    lang = "julia"
    unit = "    "
    funcoes = 0  # profundidade dentro de function: lá dentro não há o problema de escopo global

    def globais(self, corpo: list[ir.Node]) -> list[str]:
        """Variáveis de fora alteradas dentro de um laço no topo do script: precisam de `global x` no Julia."""
        if self.funcoes:
            return []
        nomes = []
        for n in _walk(corpo):
            alvo = n.name if isinstance(n, ir.Assign) else n.target if isinstance(n, ir.Call) else None
            if alvo and self.declared(alvo) and alvo not in nomes:
                nomes.append(alvo)
        return nomes

    def corpo_laco(self, corpo: list[ir.Node], d: int, names: dict | None = None) -> list[str]:
        g = self.globais(corpo)
        return ([f"{self.i(d)}global {', '.join(g)}"] if g else []) + self.body(corpo, d, names=names)

    def n_Print(self, n, d):
        return [f"{self.i(d)}println({self.x(n.value)})"]

    def n_Assign(self, n, d):
        self.declare(n.name, self.typeof(n.value))
        if n.const and d == 0:
            return [f"{self.i(d)}const {n.name.upper()} = {self.x(n.value)}"]
        return [f"{self.i(d)}{n.name} = {self.x(n.value)}"]

    def n_Input(self, n, d):
        valor = {"int": "parse(Int, strip(readline()))", "float": "parse(Float64, strip(readline()))"}.get(
            n.kind, "readline()")
        self.declare(n.var, n.kind)
        return [f"{self.i(d)}print({self.q(n.prompt)})", f"{self.i(d)}{n.var} = {valor}"]

    def n_ForRange(self, n, d):
        s = self.x(n.start)
        fim = self.x(n.end if n.inclusive else _shift(n.end, -1 if n.step > 0 else 1))
        rng = f"{s}:{fim}" if n.step == 1 else f"{s}:{n.step}:{fim}"
        var = n.var if uses_var(n.body, n.var) else "_"
        return [f"{self.i(d)}for {var} in {rng}"] + self.corpo_laco(n.body, d + 1, {n.var: "int"}) + self.end(d)

    def n_ForEach(self, n, d):
        return [f"{self.i(d)}for {n.var} in {self.x(n.iterable)}"] + self.corpo_laco(n.body, d + 1) + self.end(d)

    def n_While(self, n, d):
        return [f"{self.i(d)}while {self.x(n.cond)}"] + self.corpo_laco(n.body, d + 1) + self.end(d)

    def n_If(self, n, d):
        out = [f"{self.i(d)}if {self.x(n.cond)}"] + self.body(n.body, d + 1)
        for cond, body in n.elifs:
            out += [f"{self.i(d)}elseif {self.x(cond)}"] + self.body(body, d + 1)
        if n.orelse is not None:
            out += [f"{self.i(d)}else"] + self.body(n.orelse, d + 1)
        return out + self.end(d)

    def n_FuncDef(self, n, d):
        self.scopes.append(dict(self.param_types(n)))
        self.funcoes += 1
        try:
            body = self.body(self.with_ret(n), d + 1)
        finally:
            self.scopes.pop()
            self.funcoes -= 1
        return [f"{self.i(d)}function {n.name}({', '.join(n.params)})"] + body + self.end(d)

    def n_Main(self, n, d):
        if n.hello:
            return self.block(n.body, d)
        return ([f"{self.i(d)}function main()"] + self.body(n.body, d + 1) + self.end(d) +
                ["", f"{self.i(d)}if abspath(PROGRAM_FILE) == @__FILE__", f"{self.i(d + 1)}main()", f"{self.i(d)}end"])

    def n_ClassDef(self, n, d):
        campos = [f"{self.i(d + 1)}{f}::{E.julia_type(t) if t != '?' else 'String'}" for f, t in n.fields]
        return [f"{self.i(d)}struct {n.name}"] + campos + self.end(d)

    def n_TryCatch(self, n, d):
        return ([f"{self.i(d)}try"] + self.body(n.body, d + 1) +
                [f"{self.i(d)}catch e", f'{self.i(d + 1)}@error "Erro" exception = e', f"{self.i(d + 1)}rethrow()"] +
                self.end(d))

    def n_Import(self, n, d):
        return [f"{self.i(d)}using {n.module.partition(' as ')[0]}"]

    def n_Sleep(self, n, d):
        return [f"{self.i(d)}sleep({_num(n.seconds)})"]

    def n_Append(self, n, d):
        return [f"{self.i(d)}push!({n.target}, {self.x(n.value)})"]

    def n_Continue(self, n, d):
        return [self.i(d) + "continue"]


EMITTERS: dict[str, type[Emitter]] = {
    "python": PythonEmitter, "javascript": JSEmitter, "typescript": TSEmitter, "go": GoEmitter,
    "rust": RustEmitter, "java": JavaEmitter, "csharp": CSharpEmitter, "c": CEmitter, "cpp": CppEmitter,
    "php": PHPEmitter, "ruby": RubyEmitter, "lua": LuaEmitter, "bash": BashEmitter,
    "powershell": PowerShellEmitter, "kotlin": KotlinEmitter, "swift": SwiftEmitter, "dart": DartEmitter,
    "r": REmitter, "julia": JuliaEmitter,
}


# Linguagens em que o else precisa ficar colado ao fechamento do if ("} else {" no Go, "else … end" no Lua e no
# Ruby, "else … fi" no Bash): uma linha "senão" sozinha não dá para traduzir sem mexer na linha de cima.
_ELSE_GRUDADO = {"go", "lua", "ruby", "bash", "powershell", "julia", "r"}
_LINHA_ELSE = re.compile(r"^\s*(?:\}\s*)?((?:else|elif)\b.*)$")


def emit_else(node: ir.Else, lang: str) -> tuple[list[str], str]:
    """Uma linha "senão …" traduzida sozinha, como continuação do if que já está acima no arquivo."""
    if lang in _ELSE_GRUDADO:
        raise EmitError("em {} o senão precisa ficar junto do se: selecione as linhas do se e do senão e traduza o "
                        "bloco inteiro".format(lang))
    body = node.body or [ir.Comment("TODO")]
    falso = ir.If(body=[ir.Comment("_")], cond=("bool", True),
                  elifs=[(node.cond, body)] if node.cond is not None else [],
                  orelse=None if node.cond is not None else body)
    imports, code = emit([falso], lang)
    linhas = code.split("\n")
    for i, linha in enumerate(linhas[1:], start=1):
        if (m := _LINHA_ELSE.match(linha)) and len(linha) - len(linha.lstrip()) == 0:
            return imports, "\n".join([m.group(1), *linhas[i + 1:]])
    raise EmitError(f"não consegui separar o senão em {lang}")


def emit(nodes: list[ir.Node], lang: str) -> tuple[list[str], str]:
    cls = EMITTERS.get(lang)
    if cls is None:
        raise EmitError(f"Estágio 0 não cobre {lang}")
    return cls().render(nodes)
