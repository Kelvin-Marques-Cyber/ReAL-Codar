"""Representação intermediária (IR) do Estágio 0.

Intenções curtas e pseudocódigo indentado são compilados para esta árvore e só
depois emitidos para a linguagem-alvo (emit.py) — um front-end, vários back-ends.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

Ast = Any  # tuple produzido por engine.expr


@dataclass
class Node:
    pass


@dataclass
class Block(Node):
    body: list[Node] = field(default_factory=list)


@dataclass
class Print(Node):
    value: Ast


@dataclass
class Assign(Node):
    name: str
    value: Ast
    const: bool = False


@dataclass
class Input(Node):
    var: str
    prompt: str
    kind: str = "str"  # str | int | float


@dataclass
class ForRange(Block):
    var: str = "i"
    start: Ast = ("num", "0")
    end: Ast = ("num", "10")
    step: int = 1
    inclusive: bool = False


@dataclass
class ForEach(Block):
    var: str = "item"
    iterable: Ast = ("id", "items")


@dataclass
class While(Block):
    cond: Ast = ("bool", True)


@dataclass
class If(Block):
    cond: Ast = ("bool", True)
    elifs: list[tuple[Ast, list[Node]]] = field(default_factory=list)
    orelse: list[Node] | None = None


@dataclass
class FuncDef(Block):
    name: str = "f"
    params: list[str] = field(default_factory=list)
    ret: Ast | None = None


@dataclass
class ClassDef(Node):
    name: str
    fields: list[tuple[str, str]]  # (nome, tipo)


@dataclass
class Main(Block):
    hello: bool = False


@dataclass
class TryCatch(Block):
    pass


@dataclass
class Return(Node):
    value: Ast | None


@dataclass
class Import(Node):
    module: str


@dataclass
class Comment(Node):
    text: str
    todo: bool = False


@dataclass
class Sleep(Node):
    seconds: float


@dataclass
class Call(Node):
    name: str
    args: list[Ast]
    target: str | None = None  # "x = f(...)"


@dataclass
class Append(Node):
    target: str
    value: Ast


@dataclass
class Break(Node):
    pass


@dataclass
class Continue(Node):
    pass


@dataclass
class Else(Block):
    """Marcador usado só pelo compilador de pseudocódigo ("senão")."""
    cond: Ast | None = None  # "senão se ..."


@dataclass
class Raw(Node):
    """Código já pronto (vindo dos Estágios 1/2) inserido no ponto certo da árvore."""
    code: str
    imports: list[str] = field(default_factory=list)


@dataclass
class Unresolved(Node):
    """Linha de pseudocódigo que o Estágio 0 não entendeu; o roteador resolve via 1/2."""
    text: str


BLOCKS = (ForRange, ForEach, While, If, FuncDef, Main, TryCatch, Else)
