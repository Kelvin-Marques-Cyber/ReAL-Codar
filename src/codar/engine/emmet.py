"""Abreviações no estilo Emmet, sem IA: "ul>li.item$*3" vira HTML, "df+jcc" vira CSS.

HTML: tag, #id, .classe, [atributos], {texto}, *N (com $ numerando), > filho, + irmão, ^ sobe um nível, (grupos),
tags implícitas (".x" dentro de ul vira li), atalhos (!, a:link, input:email, btn:s, form:post, lorem…).
Em arquivos .jsx/.tsx, class vira className e for vira htmlFor.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

VOID = frozenset("area base br col embed hr img input link meta source track wbr".split())
INLINE = frozenset("""a abbr b bdi bdo br button cite code data del dfn em i img input kbd label mark q s samp select
small span strong sub sup textarea time u var wbr""".split())
KNOWN_TAGS = frozenset("""a abbr address area article aside audio b base bdi bdo blockquote body br button canvas
caption cite code col colgroup data datalist dd del details dfn dialog div dl dt em embed fieldset figcaption figure
footer form h1 h2 h3 h4 h5 h6 head header hgroup hr html i iframe img input ins kbd label legend li link main map mark
menu meta meter nav noscript object ol optgroup option output p picture pre progress q s samp script search section
select slot small source span strong style sub summary sup svg table tbody td template textarea tfoot th thead time
title tr track u ul var video wbr""".split())
ALIASES = {"bq": "blockquote", "fig": "figure", "figc": "figcaption", "pic": "picture", "ifr": "iframe",
           "emb": "embed", "obj": "object", "cap": "caption", "colg": "colgroup", "fst": "fieldset", "btn": "button",
           "optg": "optgroup", "tarea": "textarea", "leg": "legend", "sect": "section", "art": "article",
           "hdr": "header", "ftr": "footer", "adr": "address", "dlg": "dialog", "str": "strong", "prog": "progress",
           "mn": "main", "tem": "template", "datal": "datalist", "out": "output", "det": "details", "sum": "summary"}
# atributos padrão (como no Emmet): tag -> [(nome, valor)]
DEFAULT_ATTRS: dict[str, list[tuple[str, str]]] = {
    "a": [("href", "")], "img": [("src", ""), ("alt", "")], "input": [("type", "text")],
    "link": [("rel", "stylesheet"), ("href", "")], "form": [("action", "")], "label": [("for", "")],
    "select": [("name", ""), ("id", "")], "textarea": [("name", ""), ("id", ""), ("cols", "30"), ("rows", "10")],
    "option": [("value", "")], "iframe": [("src", ""), ("frameborder", "0")], "abbr": [("title", "")],
    "audio": [("src", "")], "video": [("src", "")], "source": [("src", ""), ("type", "")], "area": [("href", "")],
    "object": [("data", ""), ("type", "")], "embed": [("src", ""), ("type", "")], "base": [("href", "")],
    "script": [], "style": [], "html": [("lang", "pt-BR")],
}
SNIPPETS: dict[str, tuple[str, list[tuple[str, str]]]] = {
    "a:link": ("a", [("href", "http://")]), "a:mail": ("a", [("href", "mailto:")]),
    "a:tel": ("a", [("href", "tel:+")]), "a:blank": ("a", [("href", "http://"), ("target", "_blank"),
                                                             ("rel", "noopener noreferrer")]),
    "link:css": ("link", [("rel", "stylesheet"), ("href", "style.css")]),
    "link:favicon": ("link", [("rel", "shortcut icon"), ("type", "image/x-icon"), ("href", "favicon.ico")]),
    "script:src": ("script", [("src", "")]), "script:module": ("script", [("type", "module"), ("src", "")]),
    "meta:utf": ("meta", [("charset", "UTF-8")]),
    "meta:vp": ("meta", [("name", "viewport"), ("content", "width=device-width, initial-scale=1.0")]),
    "form:get": ("form", [("action", ""), ("method", "get")]),
    "form:post": ("form", [("action", ""), ("method", "post")]),
    "btn:s": ("button", [("type", "submit")]), "btn:r": ("button", [("type", "reset")]),
    "btn:b": ("button", [("type", "button")]), "button:s": ("button", [("type", "submit")]),
    "button:submit": ("button", [("type", "submit")]), "img:lazy": ("img", [("src", ""), ("alt", ""),
                                                                            ("loading", "lazy")]),
}
INPUT_TYPES = frozenset("""hidden text search email url password datetime-local date month week time number color
checkbox radio range file submit image reset button tel""".split())
INLINE_BREAK = 3  # como no Emmet: 3 ou mais elementos em linha (input+input+button) vão para linhas separadas
BOILERPLATE = """<!DOCTYPE html>
<html lang="pt-BR">
<head>
{i}<meta charset="UTF-8">
{i}<meta name="viewport" content="width=device-width, initial-scale=1.0">
{i}<title>Documento</title>
</head>
<body>
{i}{body}
</body>
</html>"""
LOREM = ("lorem ipsum dolor sit amet consectetur adipiscing elit sed do eiusmod tempor incididunt ut labore et "
         "dolore magna aliqua ut enim ad minim veniam quis nostrud exercitation ullamco laboris nisi ut aliquip ex ea "
         "commodo consequat duis aute irure dolor in reprehenderit in voluptate velit esse cillum dolore eu fugiat "
         "nulla pariatur").split()

_TAG = re.compile(r"[A-Za-z][\w-]*(?::[\w-]+)?")
_LOREM = re.compile(r"(?:lorem|lipsum)(\d*)$")
_NUMBER = re.compile(r"(\$+)(?:@(-)?(\d+)?)?")


class EmmetError(ValueError):
    pass


@dataclass
class Node:
    tag: str | None = None          # None: só texto (ou grupo)
    implicit: bool = False          # tag omitida (".x"): decidida pelo pai na hora de gerar
    id: str = ""
    classes: list[str] = field(default_factory=list)
    attrs: list[tuple[str, str | None]] = field(default_factory=list)
    text: str = ""
    count: int = 1
    group: bool = False
    children: list[Node] = field(default_factory=list)
    parent: Node | None = field(default=None, repr=False)


class _Parser:
    def __init__(self, src: str) -> None:
        self.s = src
        self.i = 0

    def peek(self) -> str:
        return self.s[self.i] if self.i < len(self.s) else ""

    def parse(self) -> Node:
        root = Node(group=True)
        self.chain(root)
        if self.i != len(self.s):
            raise EmmetError(f"caractere inesperado {self.peek()!r}")
        return root

    def chain(self, root: Node) -> None:
        parent, last = root, None
        while True:
            item = self.item()
            item.parent = parent
            parent.children.append(item)
            last = item
            op = self.peek()
            if op == ">":
                self.i += 1
                parent = last if not last.group else (last.children[-1] if last.children else last)
            elif op == "+":
                self.i += 1
            elif op == "^":
                while self.peek() == "^":
                    self.i += 1
                    if parent is not root and parent.parent is not None:
                        parent = parent.parent
            else:
                return

    def item(self) -> Node:
        if self.peek() == "(":
            self.i += 1
            node = Node(group=True)
            self.chain(node)
            if self.peek() != ")":
                raise EmmetError("parêntese não fechado")
            self.i += 1
            node.count = self.multiplier()
            return node
        return self.element()

    def element(self) -> Node:
        node = Node()
        m = _TAG.match(self.s, self.i)
        if m:
            node.tag = m.group(0)
            self.i = m.end()
        elif self.peek() and self.peek() in ".#[":  # ("" in ".#[" é verdadeiro em Python: o fim do texto não vale)
            node.implicit = True
        elif self.peek() != "{":
            raise EmmetError("esperava uma tag")
        while self.i < len(self.s):
            c = self.peek()
            if c == "#":
                node.id = self.word(1)
            elif c == ".":
                node.classes.append(self.word(1))
            elif c == "[":
                node.attrs.extend(self.attributes())
            elif c == "{":
                node.text += self.braced()
            else:
                break
        node.count = self.multiplier()
        return node

    def word(self, skip: int) -> str:
        self.i += skip
        m = re.compile(r"[\w$@:-]+").match(self.s, self.i)
        if not m:
            raise EmmetError("nome vazio depois de # ou .")
        self.i = m.end()
        return m.group(0)

    def braced(self) -> str:
        end = self.s.find("}", self.i + 1)
        if end < 0:
            raise EmmetError("chave não fechada")
        text = self.s[self.i + 1:end]
        self.i = end + 1
        return text

    def attributes(self) -> list[tuple[str, str | None]]:
        end = self.s.find("]", self.i + 1)
        if end < 0:
            raise EmmetError("colchete não fechado")
        body = self.s[self.i + 1:end]
        self.i = end + 1
        out = []
        for m in re.finditer(r"""([^\s="'\]]+)(?:=(?:"([^"]*)"|'([^']*)'|([^\s\]]+)))?""", body):
            val = m.group(2) if m.group(2) is not None else m.group(3) if m.group(3) is not None else m.group(4)
            out.append((m.group(1), val))
        return out

    def multiplier(self) -> int:
        if self.peek() != "*":
            return 1
        m = re.compile(r"\*(\d+)").match(self.s, self.i)
        if not m:
            raise EmmetError("* sem número")
        self.i = m.end()
        n = int(m.group(1))
        if not 1 <= n <= 500:
            raise EmmetError("multiplicador fora de 1..500")
        return n


def _outside_brackets(text: str) -> str:
    """O texto sem o conteúdo de {…} e […] (onde espaços são permitidos)."""
    return re.sub(r"\{[^}]*\}|\[[^\]]*\]", "", text)


def is_abbreviation(text: str) -> bool:
    """Parece abreviação Emmet? Frases ("criar um formulário") não; "ul>li*3", "a.btn", "!" sim."""
    t = text.strip()
    if not t or re.search(r"\s", _outside_brackets(t)):
        return False
    if t in ("!", "html:5") or _LOREM.match(t):
        return True
    if not re.search(r"[>+^*.#\[{(]", _outside_brackets(t)) and not re.search(r"[\[{]", t):
        # palavra sozinha: só se for tag conhecida, atalho, input:tipo ou elemento customizado (com hífen)
        if not (t in KNOWN_TAGS or t in ALIASES or t in SNIPPETS or "-" in t
                or (t.startswith("input:") and t[6:] in INPUT_TYPES)):
            return False
    try:
        _Parser(t).parse()
    except EmmetError:
        return False
    return True


def extract_abbreviation(before_cursor: str) -> tuple[int, str] | None:
    """A abreviação que termina no cursor: ("  <p>ul>li*3", ...) -> (5, "ul>li*3"). Espaços só dentro de {} e []."""
    depth, i = 0, len(before_cursor)
    while i > 0:
        c = before_cursor[i - 1]
        if c in "}]":
            depth += 1
        elif c in "{[":
            if depth == 0:
                break
            depth -= 1
        elif c.isspace() and depth == 0:
            break
        i -= 1
    token = before_cursor[i:]
    if "<" in token:  # texto colado numa tag: "<div>ul>li" -> "ul>li"
        close = token.find(">", token.rfind("<"))
        if close < 0:
            return None
        i += close + 1
        token = token[close + 1:]
    return (i, token) if token and is_abbreviation(token) else None


def first_stop(code: str) -> int:
    """Onde o cursor para depois de expandir: entre as aspas do primeiro atributo vazio ou dentro da primeira tag
    vazia (o que vier antes); sem nenhum dos dois, no fim."""
    stops = []
    if (i := code.find('=""')) >= 0:
        stops.append(i + 2)
    if (j := code.find("><")) >= 0:
        stops.append(j + 1)
    return min(stops) if stops else len(code)


def jsx_candidate(text: str) -> bool:
    """Em .jsx/.tsx só expande o que não pode ser JavaScript: "items.map" fica de fora, "ul>li*3" entra."""
    t = text.strip()
    outside = _outside_brackets(t)
    return is_abbreviation(t) and (bool(re.search(r"[>*]", outside)) or t[:1] in ".#")


def _number(text: str, index: int, count: int) -> str:
    """$ numera a repetição ($$ com zeros, $@3 começa em 3, $@- decresce); \\$ é um cifrão literal."""
    if "$" not in text:
        return text

    def sub(m: re.Match[str]) -> str:
        start = int(m.group(3) or 1)
        n = start + (count - index) if m.group(2) else start + index - 1
        return str(n).zfill(len(m.group(1)))
    parts = text.split("\\$")
    return "$".join(_NUMBER.sub(sub, p) for p in parts)


def _implicit(parent_tag: str | None) -> str:
    if parent_tag in ("ul", "ol", "menu"):
        return "li"
    if parent_tag in ("table", "tbody", "thead", "tfoot"):
        return "tr"
    if parent_tag == "tr":
        return "td"
    if parent_tag in ("select", "optgroup", "datalist"):
        return "option"
    if parent_tag in INLINE or parent_tag in ("p", "h1", "h2", "h3", "h4", "h5", "h6"):
        return "span"
    return "div"


def _lorem(n: int) -> str:
    words = [LOREM[i % len(LOREM)] for i in range(n)]
    return (" ".join(words)).capitalize() + "."


class _Renderer:
    def __init__(self, indent: str, jsx: bool) -> None:
        self.indent = indent
        self.jsx = jsx

    def resolve(self, node: Node, parent_tag: str | None) -> tuple[str | None, list[tuple[str, str | None]], str]:
        """Tag final, atributos (padrões + do usuário) e texto (com lorem resolvido)."""
        tag, text = node.tag, node.text
        defaults: list[tuple[str, str]] = []
        if node.implicit:
            tag = _implicit(parent_tag)
        elif tag:
            if m := _LOREM.match(tag):
                text = _lorem(int(m.group(1) or 30)) + text
                tag = None if not (node.id or node.classes or node.attrs) else _implicit(parent_tag)
            elif tag in SNIPPETS:
                tag, defaults = SNIPPETS[tag][0], list(SNIPPETS[tag][1])
            elif tag.startswith("input:") and tag[6:] in INPUT_TYPES:
                tag, defaults = "input", [("type", tag[6:]), ("name", ""), ("id", "")]
            else:
                tag = ALIASES.get(tag, tag)
                defaults = list(DEFAULT_ATTRS.get(tag, []))
        attrs: list[tuple[str, str | None]] = []
        if node.id:
            attrs.append(("id", node.id))
        if node.classes:
            attrs.append(("class", " ".join(node.classes)))
        user = {k for k, _ in node.attrs} | ({"id"} if node.id else set()) | ({"class"} if node.classes else set())
        attrs += [(k, v) for k, v in defaults if k not in user]
        attrs += node.attrs
        return tag, attrs, text

    def attr_text(self, attrs: list[tuple[str, str | None]], index: int, count: int) -> str:
        out = []
        for k, v in attrs:
            if self.jsx:
                k = {"class": "className", "for": "htmlFor"}.get(k, k)
            out.append(k if v is None else f'{k}="{_number(v, index, count)}"')
        return (" " + " ".join(out)) if out else ""

    def render(self, nodes: list[Node], parent_tag: str | None, depth: int, ctx: tuple[int, int]) -> list[str]:
        lines: list[str] = []
        for node in nodes:
            for i in range(1, node.count + 1):
                here = (i, node.count) if node.count > 1 else ctx
                if node.group:
                    lines += self.render(node.children, parent_tag, depth, here)
                else:
                    lines += self.element(node, parent_tag, depth, here)
        return lines

    def element(self, node: Node, parent_tag: str | None, depth: int, ctx: tuple[int, int]) -> list[str]:
        pad = self.indent * depth
        tag, attrs, text = self.resolve(node, parent_tag)
        text = _number(text, *ctx)
        if tag is None:
            return [pad + text] if text else []
        tag_name = _number(tag, *ctx)
        open_tag = f"<{tag_name}{self.attr_text(attrs, *ctx)}"
        if tag in VOID and not node.children:
            return [pad + open_tag + (" />" if self.jsx else ">")]
        open_tag += ">"
        close = f"</{tag_name}>"
        if not node.children:
            return [pad + open_tag + text + close]
        if all(self.inline_only(c, tag) for c in node.children) and _inline_count(node.children) < INLINE_BREAK:
            inner = "".join(line.strip() for line in self.render(node.children, tag, 0, ctx))
            return [pad + open_tag + text + inner + close]
        lines = [pad + open_tag + (text if text else "")]
        lines += self.render(node.children, tag, depth + 1, ctx)
        return lines + [pad + close]

    def inline_only(self, node: Node, parent_tag: str | None) -> bool:
        if node.group:
            return all(self.inline_only(c, parent_tag) for c in node.children)
        tag, _, _ = self.resolve(node, parent_tag)
        if tag is None:
            return True
        return tag in INLINE and node.count == 1 and all(self.inline_only(c, tag) for c in node.children)


def _inline_count(nodes: list[Node]) -> int:
    """Quantos elementos (não texto) saem destes nós, contando as repetições."""
    total = 0
    for n in nodes:
        if n.group:
            total += n.count * _inline_count(n.children)
        elif n.tag is not None or n.implicit:
            total += n.count
    return total


def expand(text: str, indent: str = "  ", jsx: bool = False) -> str | None:
    """Expande a abreviação; None se o texto não for uma abreviação Emmet."""
    t = text.strip()
    if not is_abbreviation(t):
        return None
    if t in ("!", "html:5"):
        return BOILERPLATE.format(i=indent, body="")
    root = _Parser(t).parse()
    return "\n".join(_Renderer(indent, jsx).render(root.children, None, 0, (1, 1)))


# --------------------------------------------------------------------------- CSS
_CSS_KEYWORDS = {
    "df": "display: flex", "dif": "display: inline-flex", "dg": "display: grid", "db": "display: block",
    "di": "display: inline", "dib": "display: inline-block", "dn": "display: none",
    "posa": "position: absolute", "posr": "position: relative", "posf": "position: fixed",
    "poss": "position: sticky", "fl": "float: left", "fr": "float: right", "cb": "clear: both",
    "tac": "text-align: center", "tal": "text-align: left", "tar": "text-align: right", "taj": "text-align: justify",
    "fwb": "font-weight: bold", "fwn": "font-weight: normal", "fsi": "font-style: italic",
    "tdn": "text-decoration: none", "tdu": "text-decoration: underline", "ttu": "text-transform: uppercase",
    "ttl": "text-transform: lowercase", "ttc": "text-transform: capitalize",
    "jcc": "justify-content: center", "jcsb": "justify-content: space-between",
    "jcsa": "justify-content: space-around", "jcse": "justify-content: space-evenly",
    "jcfs": "justify-content: flex-start", "jcfe": "justify-content: flex-end",
    "aic": "align-items: center", "aifs": "align-items: flex-start", "aife": "align-items: flex-end",
    "ais": "align-items: stretch", "aib": "align-items: baseline", "asc": "align-self: center",
    "fdc": "flex-direction: column", "fdr": "flex-direction: row", "fww": "flex-wrap: wrap",
    "fxa": "flex: auto", "fx1": "flex: 1", "ovh": "overflow: hidden", "ova": "overflow: auto",
    "ovs": "overflow: scroll", "cup": "cursor: pointer", "curp": "cursor: pointer", "bxzbb": "box-sizing: border-box",
    "bsbb": "box-sizing: border-box", "lsn": "list-style: none", "wsnw": "white-space: nowrap",
    "ma": "margin: auto", "m0a": "margin: 0 auto", "vh": "visibility: hidden", "vv": "visibility: visible",
    "bdn": "border: none", "ol0": "outline: 0", "usn": "user-select: none", "ofc": "object-fit: cover",
}
_CSS_VALUES = {
    "m": "margin", "mt": "margin-top", "mr": "margin-right", "mb": "margin-bottom", "ml": "margin-left",
    "p": "padding", "pt": "padding-top", "pr": "padding-right", "pb": "padding-bottom", "pl": "padding-left",
    "w": "width", "h": "height", "maw": "max-width", "mah": "max-height", "miw": "min-width", "mih": "min-height",
    "t": "top", "r": "right", "b": "bottom", "l": "left", "fz": "font-size", "lh": "line-height",
    "bdrs": "border-radius", "g": "gap", "gap": "gap", "zi": "z-index", "op": "opacity", "fw": "font-weight",
    "ti": "text-indent", "ls": "letter-spacing", "fxg": "flex-grow", "fxs": "flex-shrink", "fxb": "flex-basis",
    "gtc": "grid-template-columns",
}
_UNITLESS = {"z-index", "opacity", "font-weight", "line-height", "flex-grow", "flex-shrink"}
_COLOR_PROPS = {"c": "color", "bgc": "background-color", "bg": "background", "bdc": "border-color"}
_UNITS = {"p": "%", "e": "em", "r": "rem", "x": "ex", "vw": "vw", "vh": "vh", "px": "px", "fr": "fr"}


def _css_color(hexpart: str) -> str:
    h = hexpart.lower()
    if len(h) == 1:  # como no Emmet: #3 -> #333, #e0 -> #e0e0e0
        h = h * 3
    elif len(h) == 2:
        h = h * 3
    return "#" + h


def _css_value(raw: str, prop: str) -> str:
    out = []
    for i, part in enumerate(p for p in re.split(r"(?<=[\d%a-z])-", raw) if p):
        m = re.fullmatch(r"(-?\d*\.?\d+)(p|e|r|x|vw|vh|px|fr)?", part)
        if not m:
            raise EmmetError(f"valor CSS inválido: {part}")
        num, unit = m.group(1), m.group(2)
        if unit:
            out.append(num + _UNITS[unit])
        elif prop in _UNITLESS or float(num) == 0:
            out.append(num)
        else:
            out.append(num + "px")
    return " ".join(out)


def _css_one(abbr: str) -> str:
    important = abbr.endswith("!")
    a = abbr.rstrip("!")
    suffix = " !important;" if important else ";"
    if a in _CSS_KEYWORDS:
        return _CSS_KEYWORDS[a] + suffix
    if m := re.fullmatch(r"(c|bgc|bg|bdc)#([0-9a-fA-F]{1,6})", a):
        return f"{_COLOR_PROPS[m.group(1)]}: {_css_color(m.group(2))}{suffix}"
    if m := re.fullmatch(r"bd(\d+)(?:-(s|d|dt))?(?:-?#([0-9a-fA-F]{1,6}))?", a):
        style = {"s": "solid", "d": "dashed", "dt": "dotted"}[m.group(2) or "s"]
        color = " " + _css_color(m.group(3)) if m.group(3) else ""
        return f"border: {m.group(1)}px {style}{color}{suffix}"
    if m := re.fullmatch(r"([a-z]+?)(-?\.?\d.*)", a):
        prop = _CSS_VALUES.get(m.group(1))
        if prop:
            return f"{prop}: {_css_value(m.group(2), prop)}{suffix}"
    raise EmmetError(f"abreviação CSS desconhecida: {abbr}")


def expand_css(text: str) -> str | None:
    """"df+jcc+aic" -> três declarações; None se não for abreviação CSS."""
    t = text.strip()
    if not t or re.search(r"\s", t) or not re.fullmatch(r"[\w#.!+%-]+", t):
        return None
    try:
        return "\n".join(_css_one(part) for part in t.split("+"))
    except EmmetError:
        return None
