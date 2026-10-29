"""Pedidos encadeados: "agora adicione tipagem" altera a implementação já escrita, não cria outra função.

Sem seleção, o alvo é a declaração sob o cursor; depois, a que o pedido anterior acabou de inserir; por
fim, a declaração logo acima do cursor (separada dele só por linhas vazias). Com várias candidatas e nenhuma
dessas evidências, não há alvo confiável: o cliente pede uma seleção em vez de reescrever o arquivo.

A análise é estática e sem dependências: Python usa `ast` (com o recuo como reserva para arquivos com erro) e
as linguagens de chaves usam o léxico que mascara strings e comentários. Outras linguagens devolvem None.
"""

from __future__ import annotations

import ast
import re
from dataclasses import dataclass

from codar.audit.lexer import mask
from codar.textutil import fold

_POLITE = r"(?:por favor[, ]+|please[, ]+)?"
_MARKER = r"(?:(?:e|y|and)\s+)?(?:agora|now|ahora|tambem|tambien|also|ainda|depois|then|entao|luego)\b[,\s]*"
_ARTICLE = r"(?:(?:a|o|as|os|um|uma|uns|umas|the|some|el|la|los|las|un|una|unos|unas)\s+)?"
_ADD = r"(?:adicion\w*|acrescent\w*|inclu\w*|coloqu\w*|ponha|poe|add|include|put|anad\w*|agreg\w*|pon|incorpor\w*)"
# Acréscimos que só fazem sentido sobre código existente; "adicione uma função" continua sendo geração.
_ON_CODE = (r"(?:tipagem|tipos?|type\s*hints?|types?|anotac\w*(?:\s+de\s+tipos?)?|(?:type\s+)?annotations?|"
            r"docstrings?|documentac\w*|documentation|comentarios?|comments?|jsdoc|"
            r"tratamento\s+de\s+(?:erros?|excec\w*)|(?:error|exception)\s+handling|manejo\s+de\s+(?:errores|excepciones))")
# Ambíguos sem marcador: "adicione validação de CPF" pode pedir uma função nova.
_ON_CODE_MARKED = r"(?:validac\w*|validation|validacion|logs?|logging|registro\s+de\s+logs?)"
_DOCUMENT = r"(?:documente|documenta|documentar|document|annotate|anote|anota|anotar|tipe|tipar)"
_FUNCTION = (r"(?:(?:esta|essa|a|this|the|esta|la)\s+(?:funcao|metodo|classe|function|method|class|funcion|metodo|clase)|"
             r"ela|ele|isso|isto|it|this|la|lo|esto|este\s+metodo|o\s+metodo|el\s+metodo)")
_TRANSFORM = (r"(?:torn\w*|transform\w*|deix\w*|faca|faz|make|turn|convert\w*|conviert\w*|haz|vuelve)\s+"
              rf"(?:{_FUNCTION}\s+)?(?:(?:em|en|into|in)\s+)?{_ARTICLE}"
              r"(?:async\w*|assincron\w*|asincron\w*|recursiv\w*|iterativ\w*|generic\w*|pur[ao]s?|pure)")
_RENAME = r"(?:renome\w*|rename|renombr\w*|mude\s+o\s+nome|change\s+the\s+name|cambi\w*\s+el\s+nombre)"
_EDIT = (r"(?:corri[gj]\w*|consert\w*|arrum\w*|refator\w*|reescrev\w*|melhor\w*|otimiz\w*|ajust\w*|simplifi\w*|"
         r"fix|rewrite|refactor|improve|optimi[sz]e|simplify|arregl\w*|mejor\w*|optimic\w*|reescrib\w*|refactori\w*)")

_FOLLOWUP = re.compile(
    rf"^{_POLITE}(?:{_MARKER})?(?:{_ADD}\s+{_ARTICLE}{_ON_CODE}\b|{_DOCUMENT}\b|{_TRANSFORM}|{_RENAME}\b)"
    rf"|^{_POLITE}{_MARKER}(?:{_ADD}\s+{_ARTICLE}{_ON_CODE_MARKED}\b|{_EDIT}\b)"
    rf"|^{_POLITE}{_EDIT}\s+{_FUNCTION}\b")


def wants_followup(intent: str) -> bool:
    """O pedido modifica o código já escrito ("agora adicione tipagem", "add type hints", "añade tipos")?"""
    text = fold(intent).strip().lstrip("#/;- ").strip()
    return bool(_FOLLOWUP.match(text))


@dataclass(frozen=True)
class Declaration:
    start: int  # linhas 0-based, inclusivas; inclui decoradores, atributos e comentários de documentação
    end: int
    name: str
    container: bool = False  # classe, struct, impl: agrupa outras declarações

    @property
    def span(self) -> int:
        return self.end - self.start


_PY_HEAD = re.compile(r"^(\s*)(?:async\s+def|def|class)\s+(\w+)")
_KEYWORDS = frozenset("""if for while switch catch foreach using lock sizeof return synchronized fixed checked do try
else new throw case await yield delete typeof echo goto function elif when match""".split())
_TYPE_WORD = r"(?:[\w$<>\[\],.?*&~]+(?:\s*<[^>\n]*>)?\s+)"
_C_LIKE = re.compile(rf"^\s*(?:@\w+(?:\([^)\n]*\))?\s+)*{_TYPE_WORD}+(?:\w+::)*(~?[A-Za-z_]\w*)\s*(?:<[^>\n]*>)?\s*\(")
_C_TYPE = re.compile(r"^\s*(?:[\w]+\s+)*(?:class|struct|interface|enum|record|namespace|extension|mixin|union)\s+(\w+)")
_HEADS: dict[str, tuple[re.Pattern, ...]] = {
    "js": (re.compile(r"^\s*(?:export\s+)?(?:default\s+)?(?:async\s+)?function\s*\*?\s*([\w$]*)"),
           re.compile(r"^\s*(?:export\s+)?(?:default\s+)?(?:abstract\s+)?class\s+([\w$]+)"),
           re.compile(r"^\s*(?:export\s+)?(?:const|let|var)\s+([\w$]+)\s*(?::[^=\n]+)?=\s*(?:async\s+)?"
                      r"(?:function\b|\([^()\n]*\)\s*(?::\s*[^=\n]+)?=>|[\w$]+\s*=>)"),
           re.compile(r"^\s*(?:(?:public|private|protected|static|async|readonly|override|abstract|get|set)\s+)*"
                      r"\*?\s*(#?[A-Za-z_$][\w$]*)\s*(?:<[^>\n]*>)?\s*\(")),
    "go": (re.compile(r"^\s*func\s+(?:\([^)]*\)\s*)?(\w+)"), re.compile(r"^\s*type\s+(\w+)\s+(?:struct|interface)\b")),
    "rust": (re.compile(r"^\s*(?:pub(?:\([^)]*\))?\s+)?(?:(?:async|unsafe|const|extern(?:\s+\"[^\"]*\")?)\s+)*"
                        r"(?:fn|impl(?:<[^>]*>)?|struct|enum|trait|mod)\s+([\w:<>]+)"),),
    "kotlin": (re.compile(r"^\s*(?:(?:public|private|protected|internal|open|override|suspend|inline|abstract|final|"
                          r"data|sealed|inner|enum|operator|infix|tailrec)\s+)*(?:fun|class|object|interface)\s+"
                          r"(?:<[^>]*>\s*)?(?:[\w.]+\.)?(\w+)"),),
    "swift": (re.compile(r"^\s*(?:(?:public|private|fileprivate|internal|open|static|final|override|mutating|class|"
                         r"@\w+)\s+)*(?:func|class|struct|enum|extension|protocol)\s+(\w+)"),
              re.compile(r"^\s*(?:(?:public|private|internal|convenience|required|override)\s+)*(init)\s*[?!]?\s*\(")),
    "php": (re.compile(r"^\s*(?:(?:public|private|protected|static|abstract|final)\s+)*"
                       r"(?:function|class|interface|trait|enum)\s+&?(\w+)"),),
    "powershell": (re.compile(r"(?i)^\s*(?:function|filter|class)\s+([\w:-]+)"),),
    "bash": (re.compile(r"^\s*function\s+([\w:-]+)"), re.compile(r"^\s*([\w:-]+)\s*\(\s*\)")),
    "c": (_C_LIKE, _C_TYPE),
}
_FAMILY = {"javascript": "js", "typescript": "js", "go": "go", "rust": "rust", "kotlin": "kotlin", "swift": "swift",
           "php": "php", "powershell": "powershell", "bash": "bash", "java": "c", "csharp": "c", "c": "c", "cpp": "c",
           "dart": "c"}
# Corpos de expressão sem chaves: `=>` (Dart, C#, JS) e `=` (Kotlin).
_INLINE = {"dart": "=>", "csharp": "=>", "kotlin": "="}
_CONTAINER = re.compile(r"\b(?:class|struct|interface|enum|impl|trait|mod|object|extension|protocol|record|namespace|"
                        r"mixin|union|type)\b")
_DOC_ABOVE = re.compile(r"^\s*(?:@|#\[|///|//!|/\*\*|\*|\*/)")


def declarations(text: str, lang: str) -> list[Declaration] | None:
    """Funções, métodos e classes do arquivo; None quando a linguagem não é analisada."""
    if len(text) > 400_000:
        return None  # o alvo precisa ser calculado na interface sem atraso perceptível
    if lang == "python":
        return _python(text)
    family = _FAMILY.get(lang)
    if family is None:
        return None
    return _braces(text, lang, family)


def _python(text: str) -> list[Declaration]:
    try:
        tree = ast.parse(text)
    except (SyntaxError, ValueError):
        return _python_by_indent(text)
    out = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            first = min([node.lineno] + [d.lineno for d in node.decorator_list])
            out.append(Declaration(first - 1, (node.end_lineno or node.lineno) - 1, node.name,
                                   isinstance(node, ast.ClassDef)))
    return out


def _python_by_indent(text: str) -> list[Declaration]:
    """Reserva para um arquivo que ainda não compila (o pedido digitado numa linha do próprio editor)."""
    lines = text.split("\n")
    out = []
    for i, line in enumerate(lines):
        head = _PY_HEAD.match(line)
        if not head:
            continue
        depth, end = len(head[1].expandtabs(4)), i
        for j in range(i + 1, len(lines)):
            current = lines[j]
            if not current.strip():
                continue
            if len(current.expandtabs(4)) - len(current.expandtabs(4).lstrip()) <= depth:
                break
            end = j
        first = i
        while first > 0 and lines[first - 1].strip().startswith("@"):
            first -= 1
        out.append(Declaration(first, end, head[2], line.lstrip().startswith("class")))
    return out


def _braces(text: str, lang: str, family: str) -> list[Declaration]:
    # Dart compartilha comentários e aspas com Java; sem máscara, chaves em strings confundiriam os corpos.
    masked = mask(text, "java" if lang == "dart" else lang, strings=True)
    lines = masked.split("\n")
    original = text.split("\n")
    starts = [0]
    for line in lines:
        starts.append(starts[-1] + len(line) + 1)
    out = []
    for row, line in enumerate(lines):
        name = _head(line, family)
        if name is None:
            continue
        end = _body_end(masked, starts[row] + len(line) - len(line.lstrip()), lang, family, line)
        if end is None:
            continue
        last = masked.count("\n", 0, end)
        first = row
        while first > 0 and _DOC_ABOVE.match(original[first - 1]):
            first -= 1
        out.append(Declaration(first, last, name, bool(_CONTAINER.search(line[:line.find(name)] if name in line else line))))
    return out


def _head(line: str, family: str) -> str | None:
    first = re.match(r"\s*([\w$]+)", line)
    if family == "c" and first and first[1] in _KEYWORDS:
        return None  # "return soma(1, 2);" e "else if (x) {" são instruções
    for pattern in _HEADS[family]:
        match = pattern.match(line)
        if match and (match[1] or "").split("::")[-1] not in _KEYWORDS:
            return match[1] or "function"
    return None


def _body_end(masked: str, at: int, lang: str, family: str, line: str) -> int | None:
    """Posição do fim do corpo (chave final ou fim da expressão), ou None para chamadas e protótipos."""
    inline = _INLINE.get(lang) or ("=>" if family == "js" and re.search(r"=>", line) else None)
    depth, i, limit = 0, at, min(len(masked), at + 4000)
    while i < limit:
        char = masked[i]
        if char in "([":
            depth += 1
        elif char in ")]":
            depth -= 1
        elif depth <= 0:
            if char == "{":
                return _closing(masked, i)
            if char == ";":
                return None  # chamada, protótipo ou declaração sem corpo
            if inline and masked.startswith(inline, i) and not masked.startswith("==", i) \
                    and (inline != "=" or masked[i - 1] not in "!<>=+-*/%&|^"):
                rest = masked[i + len(inline):].lstrip(" \t")
                if rest.startswith("{"):
                    return _closing(masked, i + len(inline) + masked[i + len(inline):].index("{"))
                stop = masked.find("\n", i)
                semicolon = masked.find(";", i)
                if semicolon >= 0 and (stop < 0 or semicolon < stop or lang != "kotlin"):
                    return semicolon + 1
                return len(masked) if stop < 0 else stop
            if char == "\n":
                following = masked[i + 1:].lstrip()
                # Chave de abertura na linha seguinte (estilo Allman em C#/Java/C).
                if not following.startswith(("{", "=>", ":", "where", "throws", "->")) and not line.rstrip().endswith(","):
                    return None
        i += 1
    return None


def _closing(masked: str, at: int) -> int | None:
    depth = 0
    for i in range(at, len(masked)):
        depth += (masked[i] == "{") - (masked[i] == "}")
        if depth == 0:
            return i + 1
    return None


def followup_target(text: str, row: int, lang: str, recent: tuple[int, int] | None = None
                    ) -> tuple[int, int, str] | None:
    """(primeira linha, última linha, descrição) do código a modificar, ou None sem evidência confiável.

    `recent` são as linhas inseridas pelo pedido anterior, já verificadas pelo cliente contra o texto atual.
    """
    found = declarations(text, lang)
    if not found:
        return None
    lines = text.split("\n")

    def just_above(candidates):
        """A declaração separada do cursor só por linhas vazias: a que acabou de ser escrita."""
        above = [d for d in candidates if d.end < row and
                 not any(lines[r].strip() for r in range(d.end + 1, min(row, len(lines))))]
        if not above:
            return None
        last = max(d.end for d in above)
        return max((d for d in above if d.end == last), key=lambda d: d.span)

    inside = [d for d in found if d.start <= row <= d.end]
    if inside:
        best = min(inside, key=lambda d: d.span)
        # Linha vazia entre métodos: o método logo acima, não a classe inteira.
        if best.container:
            best = just_above([d for d in found if best.start < d.start and d.end < best.end]) or best
        return best.start, best.end, best.name
    if recent is not None:
        first, last = recent
        fresh = [d for d in found if first <= d.start <= last]
        if fresh:
            start, end = min(d.start for d in fresh), max(d.end for d in fresh)
            names = [d.name for d in fresh if not any(o is not d and o.start <= d.start and d.end <= o.end for o in fresh)]
            return start, end, ", ".join(names)
    best = just_above(found)
    return (best.start, best.end, best.name) if best else None
