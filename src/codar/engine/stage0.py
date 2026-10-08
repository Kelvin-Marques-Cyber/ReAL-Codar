"""Estágio 0 — compilador de intenções (regex + gramática de expressões), alvo < 1 ms.

Front-end: frase PT/EN -> IR (engine.ir). Conservador por design: se a frase não
casar inteira com uma construção conhecida, devolve None e o roteador segue para
o banco de padrões (Estágio 1) ou para o SLM (Estágio 2).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from codar import langs
from codar.engine import expr as E
from codar.engine import ir
from codar.textutil import fold, fold_keep_len

ID = r"[a-z_][a-z0-9_]*"
_CREATE = (r"(?:(?:criar|crie|cria|declarar|declare|declara|definir|defina|define|fazer|faca|faz|gerar|gere|gera|"
           r"escrever|escreva|implementar|implemente|create|make|write|generate|implement|nova|novo|new)\s+)?")
_ART = r"(?:(?:um|uma|o|a|the|an?)\s+)?"
_PRINT = (r"(?:imprimir|imprima|imprime|printar|printe|print|mostrar|mostre|mostra|exibir|exiba|exibe|"
          r"escrever\s+na\s+tela|escreva\s+na\s+tela|logar|echo|display|show|output|console\.log|puts|dizer|diga|say)")
_RESERVED = {"retorna", "retornar", "returns", "return", "que", "com", "with", "e", "and", "de", "of"}
_PRINT_REJECT = ("arquiv", "file", "lista", "list", "tabel", "table", "relat", "report", "pdf", "csv", "json",
                 "xml", "excel", "plani", "banco", "datab", "dados", "data", "hora", "time", "tempo", "agora",
                 "now", "matri", "matrix", "arvor", "tree", "grafo", "graph", "usuar", "user", "memor", "disco",
                 "disk", "proce", "pasta", "folder", "diret", "tabua", "calen", "conte", "todos", "cada")

_LANG_HINT = re.compile(
    r"\s+(?:em|in|usando|using|com|with|no|na)\s+(?P<lang>python|python3|py|javascript|js|node(?:js)?|typescript|ts|"
    r"golang|go|rust|java|c\+\+|cpp|c#|csharp|c|bash|shell|sh|zsh|powershell|pwsh|lua|ruby|php|sql|kotlin|swift)\s*$",
    re.I,
)


@dataclass
class Parsed:
    nodes: list[ir.Node]
    construct: str
    confidence: float = 1.0
    imports: list[str] = field(default_factory=list)


def extract_lang_hint(intent: str) -> tuple[str, str | None]:
    """'conectar ao redis em go' -> ('conectar ao redis', 'go')."""
    m = _LANG_HINT.search(intent)
    if not m:
        return intent, None
    lang = langs.try_resolve(m.group("lang").lower())
    return (intent[: m.start()].rstrip(), lang.id) if lang else (intent, None)


def clean_intent(text: str) -> str:
    t = text.strip()
    t = re.sub(r"^(?:#+|//+|--+|/\*+|;+|>>+|codar:)\s*", "", t, flags=re.I)
    t = re.sub(r"\s*\*/\s*$", "", t)
    return t.strip().rstrip(".;:").strip()


# --------------------------------------------------------------------------- utilitários

def _rx(pattern: str) -> re.Pattern[str]:
    return re.compile(pattern, re.I)


def _span(text: str, m: re.Match[str], group: str) -> str | None:
    if m.group(group) is None:
        return None
    s, e = m.span(group)
    return text[s:e].strip()


def _ident(word: str) -> str:
    w = fold(word.strip())
    w = re.sub(r"[^a-z0-9_]", "_", w) if not word.isascii() else word.strip()
    return w if re.fullmatch(r"[A-Za-z_]\w*", w) else ""


def _split_items(text: str) -> list[str]:
    text = text.strip()
    parts = re.split(r"\s*,\s*|\s+(?:e|and)\s+(?=[^,]*$)", text)
    return [p.strip() for p in parts if p.strip()]


def _literal(item: str) -> E.Ast:
    item = item.strip()
    node = E.try_parse(item)
    if node is not None and node[0] in ("num", "str", "bool", "null"):
        return node
    if node is not None and node[0] == "un" and node[2][0] == "num":
        return node
    return ("str", item.strip("'\""))


def _has_reject_word(text: str) -> bool:
    return any(w.startswith(_PRINT_REJECT) for w in fold(text).split())


def _plain_text(text: str) -> bool:
    return bool(re.fullmatch(r"[^\W\d_][\w\s,!?.'-]*", text, re.U))


_DE = r"\s+(?:de|do|da|dos|das|entre|of|between)\s+(?:the\s+)?"
_OPND = r"(?:" + ID + r"|-?\d+(?:\.\d+)?)"
_LEAD_ART = re.compile(r"^(?:(?:o|a|os|as|ao|aos|um|uma|the)\s+)")
_NL_LEN = re.compile(r"^(?:tamanho|comprimento|quantidade(?:\s+de\s+(?:itens|elementos))?|numero\s+de\s+(?:itens|elementos)|"
                     r"total\s+de\s+(?:itens|elementos)|length|size|count|number\s+of\s+items)" + _DE
                     + r"(?:(?:lista|list|array|vetor)\s+)?(?P<x>" + ID + r")$")
_NL_PAIR = re.compile(r"^(?P<op>soma|adicao|sum|media|average|mean|produto|product|diferenca|difference|subtracao)" + _DE
                      + r"(?P<a>" + _OPND + r")\s+(?:e|com|and|with)\s+(?P<b>" + _OPND + r")$")
_NL_UNARY = re.compile(r"^(?P<op>dobro|double|triplo|triple|metade|half|quadrado|square|cubo|cube)" + _DE
                       + r"(?P<x>" + _OPND + r")$")


def _nl_value(text: str) -> E.Ast | None:
    """Valor descrito em português/inglês: "o tamanho de itens" -> len(itens), "a soma de x e y" -> x + y."""
    t = _LEAD_ART.sub("", fold(text.strip()))
    if m := _NL_LEN.match(t):
        return ("call", ("id", "len"), [("id", m.group("x"))])
    if m := _NL_PAIR.match(t):
        a, b = E.parse(m.group("a")), E.parse(m.group("b"))
        op = m.group("op")
        if op in ("media", "average", "mean"):
            return ("bin", "/", ("paren", ("bin", "+", a, b)), ("num", "2"))
        return ("bin", {"produto": "*", "product": "*", "diferenca": "-", "difference": "-",
                        "subtracao": "-"}.get(op, "+"), a, b)
    if m := _NL_UNARY.match(t):
        x, op = E.parse(m.group("x")), m.group("op")
        if op in ("quadrado", "square"):
            return ("bin", "*", x, x)
        if op in ("cubo", "cube"):
            return ("bin", "*", ("bin", "*", x, x), x)
        if op in ("metade", "half"):
            return ("bin", "/", x, ("num", "2"))
        return ("bin", "*", x, ("num", "3" if op in ("triplo", "triple") else "2"))
    return None


def _is_reference(text: str) -> bool:
    """Frase com artigo ("o tamanho de pedidos", "ao total") descreve um valor; nunca deve virar texto literal."""
    return bool(_LEAD_ART.match(fold(text.strip()))) and len(text.split()) >= 2


_TYPE_WORDS = {
    "str": "str", "string": "str", "texto": "str", "text": "str",
    "int": "int", "inteiro": "int", "integer": "int", "numero": "int", "number": "int",
    "float": "float", "decimal": "float", "double": "float", "real": "float",
    "bool": "bool", "boolean": "bool", "booleano": "bool",
    "data": "str", "date": "str", "datetime": "str",
}

_INT_NAMES = {"idade", "age", "count", "contador", "quantidade", "qtd", "qty", "total", "ano", "year", "id",
              "numero", "number", "n", "i", "j", "k", "x", "y", "z", "a", "b", "c", "dias", "days", "pontos",
              "score", "nivel", "level", "estoque", "stock", "porta", "port", "tamanho", "size", "codigo"}
_FLOAT_NAMES = {"preco", "price", "valor", "value", "salario", "salary", "amount", "peso", "weight", "altura",
                "height", "nota", "media", "saldo", "balance", "taxa", "rate", "desconto", "discount", "latitude",
                "longitude", "lat", "lng", "temperatura", "temperature"}
_BOOL_PREFIX = ("is_", "has_", "tem_", "eh_", "ativo", "active", "enabled", "habilitado", "admin")


def field_type(name: str) -> str:
    n = fold(name)
    if n in _INT_NAMES or n.endswith("_id"):
        return "int"
    if n in _FLOAT_NAMES:
        return "float"
    if n.startswith(_BOOL_PREFIX):
        return "bool"
    return "str"


# --------------------------------------------------------------------------- padrões

_P_COMMENT = _rx(r"^(?:comentario|comentar|comente|comment|nota|note)\s*[:\-]?\s+(?P<text>.+)$")
_P_TODO = _rx(r"^(?:todo|fixme|pendente)\s*[:\-]?\s+(?P<text>.+)$")
_P_IMPORT = _rx(
    r"^(?:importar|importe|importa|import|incluir|inclua|include|require|requerer|"
    r"usar\s+(?:a\s+|o\s+)?(?:biblioteca|lib|modulo|pacote)|use\s+(?:the\s+)?(?:library|module|package))\s+"
    r"(?:(?:a|o|the)\s+)?(?:(?:biblioteca|lib|modulo|pacote|module|package|library|header|cabecalho)\s+)?"
    r"(?P<mod>[a-z_][\w.:/\\-]*)(?:\s+(?:as|como)\s+(?P<alias>" + ID + r"))?$"
)
_P_HELLO = _rx(r"^(?:(?:um|uma|o|a|the|an?)\s+)?(?:programa\s+|program\s+)?(?:hello[\s,]*world|ola[\s,]*mundo)\s*!?$")
_P_MAIN = _rx(r"^" + _CREATE + _ART + r"(?:(?:funcao|metodo|function|method)\s+(?:principal|main)|main(?:\s+function)?|"
              r"ponto\s+de\s+entrada|entry\s*point|programa\s+principal)$")
_P_TRY = _rx(r"^(?:(?:bloco\s+)?try[\s/-]*(?:catch|except)(?:\s+block)?|(?:tratar|trate|tratamento\s+de|capturar|capture|"
             r"handle)\s+(?:(?:o|a|os|as)\s+)?(?:erros?|excecao|excecoes|exceptions?|errors?)|bloco\s+try|try\s+block)$")
_P_BREAK = _rx(r"^(?:parar|pare|sair|saia|interromper|interrompa|quebrar|break)(?:\s+(?:o|do|the|out\s+of(?:\s+the)?))?"
               r"(?:\s+(?:loop|laco))?$")
_P_CONTINUE = _rx(r"^(?:continuar|continue|pular|pule|skip)(?:\s+(?:para\s+)?(?:a\s+)?(?:proxima\s+)?"
                  r"(?:iteracao|iteration))?$")
_P_SLEEP = _rx(r"^(?:esperar|espere|aguardar|aguarde|dormir|durma|pausar|pause|sleep|wait|delay)\s+(?:(?:por|for)\s+)?"
               r"(?P<n>\d+(?:[.,]\d+)?)\s*(?P<unit>segundos?|seg|s|seconds?|secs?|milissegundos?|ms|milliseconds?|"
               r"minutos?|min|minutes?)$")
_P_RETURN = _rx(r"^(?:retornar|retorne|retorna|return|devolver|devolva)(?:\s+(?P<expr>.+))?$")
_P_PRINT_RANGE = _rx(r"^" + _PRINT + r"\s+(?:(?:os|todos\s+os|the|all|all\s+the)\s+)?(?:numeros|numbers|valores|values|"
                     r"inteiros|integers)\s+(?:(?P<parity>pares|impares|even|odd)\s+)?(?:de|from|entre|between)\s+"
                     r"(?P<a>-?\d+)\s+(?:a|ate|to|e|and)\s+(?P<b>-?\d+)$")
_P_PRINT = _rx(r"^" + _PRINT + r"(?:\s+(?:na|no|em|to|on)\s+(?:a\s+|o\s+|the\s+)?(?:tela|console|terminal|saida|screen|"
               r"stdout))?\s+(?P<marker>(?:(?:o|a|the)\s+)?(?:texto|mensagem|string|frase|text|message|palavra|word)(?:\s*:)?\s+)?"
               r"(?P<arg>.+?)(?:\s+(?P<times>\d+)\s+(?:vezes|times|x))?$")
_P_ASK = _rx(r"^(?:pedir|peca|perguntar|pergunte|solicitar|solicite|ask(?:\s+for)?|prompt(?:\s+for)?)\s+"
             r"(?:(?:o|a|os|as|um|uma|the|an?)\s+)?(?P<var>" + ID + r")(?:\s+(?:do|ao|for|from|of)\s+(?:(?:o|the)\s+)?"
             r"(?:usuario|user))?(?:\s+(?:como|as)\s+(?P<kind>inteiro|int|integer|numero|number|float|decimal|real|"
             r"texto|string|text))?$")
_P_READ = _rx(r"^(?:ler|leia|le|read|capturar|capture|receber|receba|get|obter|obtenha)\s+(?:(?:a|o|um|uma|the|an?)\s+)?"
              r"(?P<kind>entrada|input|linha|line|numero|number|inteiro|integer|int|float|decimal|texto|text|string|valor|"
              r"value)(?:\s+(?:inteiro|integer|decimal))?(?:\s+(?:do|da|from)\s+(?:(?:o|a|the)\s+)?(?:usuario|user|"
              r"teclado|keyboard|stdin|console|terminal))?(?:\s+(?:em|na|no|into|para|como|as|to|e\s+(?:guardar|salvar|"
              r"armazenar)\s+em)\s+(?:(?:a\s+)?(?:variavel|variable)\s+)?(?P<var>" + ID + r"))?(?:\s+(?:com|with)\s+"
              r"(?:(?:a|o|the)\s+)?(?:mensagem|pergunta|prompt|message)\s+(?P<prompt>.+))?$")
_P_FOR_PY = _rx(r"^(?:for|para)\s+(?P<var>" + ID + r")\s+(?:in|em)\s+range\s*\(?\s*(?P<a>-?[\w.]+)\s*(?:,\s*(?P<b>-?[\w.]+)"
                r"\s*)?(?:,\s*(?P<s>-?\d+)\s*)?\)?\s*:?(?P<rest>.*)$")
_P_FOR_RANGE = _rx(r"^(?:(?:um|uma|faca|fazer|criar|crie|cria|make|create|a)\s+)*(?:loop|laco|for|para|repetir|repita|iterar|"
                   r"itere|contar|conte|count|percorrer)\s+(?:(?:com|usando|using|with)\s+)?(?:(?!de\b|from\b|desde\b)"
                   r"(?P<var>" + ID + r")\s+)?(?:de|from|=|desde|indo\s+de|comecando\s+em|starting\s+at)\s+(?P<a>-?[\w.]+)"
                   r"\s+(?:a|ate|to|\.\.|until|through|thru)\s+(?P<b>-?[\w.]+)(?:\s+(?:de\s+(?P<s1>\d+)\s+em\s+\d+|"
                   r"(?:com\s+)?(?:passo|step|incremento|by)\s+(?P<s2>-?\d+)))?(?P<rest>.*)$")
_P_TIMES = _rx(r"^(?:(?:repetir|repita|repeat|loop|laco|executar|execute|faca|fazer|do)\s+(?:isso\s+|this\s+)?)?"
               r"(?P<n>\d+|" + ID + r")\s+(?:vezes|times)\s*:?(?P<rest>.*)$")
_P_FOREACH = _rx(r"^(?:para\s+cada|for\s+each|foreach|for\s+every|percorrer|percorra|percorre|iterar\s+(?:sobre|em|por|pela|"
                 r"pelo|pelos|pelas)|itere\s+(?:sobre|em|por|pela|pelo)|iterate\s+(?:over|through)|loop\s+(?:over|through|"
                 r"sobre|em|por)|for)\s+(?:(?:o|a|os|as|cada|the|each|every)\s+)?(?:(?P<var>" + ID + r")\s+(?:em|in|de|of|"
                 r"da|do|na|no|dentro\s+de)\s+)?(?:(?:a|o|os|as|the)\s+)?(?:(?:lista|array|vetor|list|colecao|collection)"
                 r"\s+(?:de\s+)?)?(?P<iter>[a-z_][\w.]*)(?P<rest>.*)$")
_P_INFINITE = _rx(r"^(?:(?:um|uma|a|an)\s+)?(?:loop|laco)\s+(?:infinito|eterno|forever)$|^(?:infinite\s+loop|while\s+true|"
                  r"loop\s+forever|para\s+sempre|enquanto\s+(?:verdadeiro|true))$")
_P_WHILE = _rx(r"^(?:enquanto|while)\s+(?P<cond>.+)$")
_P_UNTIL = _rx(r"^(?:ate\s+que|until)\s+(?P<cond>.+)$")
_P_IF = _rx(r"^(?:se|if|caso|quando|when)\s+(?P<cond>.+)$")
_P_ELSE = _rx(r"^(?:senao|else|caso\s+contrario|otherwise)(?:\s+(?:se|if)\s+(?P<cond>.+))?$|^elif\s+(?P<cond2>.+)$")
_P_FUNC = _rx(r"^" + _CREATE + _ART + r"(?:funcao|function|func|def|metodo|method|procedimento|procedure|rotina|fn)\s+"
              r"(?:(?:chamada|chamado|named|called|de\s+nome)\s+)?(?P<name>" + ID + r")(?:\s*\((?P<pp>[^)]*)\)|\s+(?:que\s+"
              r"recebe|recebendo|com\s+(?:os\s+)?(?:parametros|params|argumentos|args)|com|with\s+(?:the\s+)?(?:parameters|"
              r"params|arguments|args)|with|taking|that\s+takes|params?|parametros?|argumentos?|args?)\s+"
              r"(?P<params>" + ID + r"(?:\s*(?:,|e|and)\s*" + ID + r")*))?(?:\s*,?\s*(?:e\s+|and\s+)?(?:que\s+)?"
              r"(?:retorna|retornando|retorne|devolve|returns?|returning|=>|->)\s+(?P<ret>.+))?$")
_P_CLASS = _rx(r"^" + _CREATE + _ART + r"(?:classe|class|struct|estrutura|modelo|model|record|registro|entidade|entity|"
               r"dataclass)\s+(?:(?:chamada|chamado|named|called|de\s+nome)\s+)?(?P<name>" + ID + r")(?:\s+(?:com|with|"
               r"contendo|containing|tendo|having)\s+(?:(?:os|as|the)\s+)?(?:(?:campos|atributos|propriedades|fields|"
               r"attributes|properties|membros|members)\s+)?(?P<fields>[a-z_]\w*(?:\s*:\s*\w+)?(?:\s*(?:,|e|and)\s*"
               r"[a-z_]\w*(?:\s*:\s*\w+)?)*))?$")
_P_LIST_EMPTY = _rx(r"^" + _CREATE + _ART + r"(?:(?:lista|array|vetor)\s+vazi[oa]|empty\s+(?:list|array))\s+"
                    r"(?:(?:chamada|chamado|named|called)\s+)?(?P<name>" + ID + r")$")
_P_LIST = _rx(r"^" + _CREATE + _ART + r"(?:lista|array|vetor|list|arranjo)\s+(?:(?:de|of)\s+(?P<of>" + ID + r")\s+)?"
              r"(?:(?:chamada|chamado|named|called)\s+)?(?:(?P<name>" + ID + r")\s+)?(?:com|contendo|with|containing|=|:)\s+"
              r"(?:(?:os|as|the)\s+)?(?:(?:valores|elementos|itens|values|elements|items)\s+)?(?P<items>.+)$")
_P_DICT = _rx(r"^" + _CREATE + _ART + r"(?:dicionario|dict|dictionary|mapa|map|objeto|object|hashmap|hash)\s+"
              r"(?:(?:chamado|chamada|named|called)\s+)?(?P<name>" + ID + r")\s+(?:com|with|contendo|containing|=|:)\s+"
              r"(?P<pairs>.+)$")
_P_INCR = _rx(r"^(?P<verb>incrementar|incremente|incrementa|increment|aumentar|aumente|decrementar|decremente|decrementa|"
              r"decrement|diminuir|diminua)\s+(?:(?:a|o|the)\s+)?(?:(?:variavel|variable)\s+)?(?P<name>" + ID + r")"
              r"(?:\s+(?:em|by|de)\s+(?P<n>\d+(?:\.\d+)?))?$")
_P_PLUSPLUS = _rx(r"^(?P<name>" + ID + r")\s*(?P<op>\+\+|--)$")
_P_APPEND = _rx(r"^(?P<verb>adicionar|adicione|adiciona|inserir|insira|colocar|coloque|append|push|add|somar|some)\s+"
                r"(?P<v>.+?)\s+(?:a|ao|na|no|em|to|into|onto)\s+(?P<list>(?:lista|array|vetor|list)\s+)?"
                r"(?P<name>" + ID + r")$")
_P_ASSIGN_DECL = _rx(r"^" + _CREATE + _ART + r"(?:(?P<const>constante|constant|const)|variavel|variable|var|let)\s+"
                     r"(?:(?:chamada|chamado|named|called)\s+)?(?P<name>" + ID + r")\s*(?:=|:=|<-|igual\s+a|recebe(?:ndo)?|"
                     r"com\s+(?:o\s+)?valor(?:\s+de)?|valendo|to|equal\s+to|equals|as|como|de\s+valor)\s*(?P<value>.+)$")
_P_ASSIGN_SET = _rx(r"^(?:set|definir|defina|atribuir|atribua)\s+(?P<name>" + ID + r")\s+(?:to|para|como|=|igual\s+a)\s+"
                    r"(?P<value>.+)$")
_P_ASSIGN_TO = _rx(r"^(?:atribuir|atribua|assign)\s+(?P<value>.+?)\s+(?:a|para|to|em|na|no)\s+(?P<name>" + ID + r")$")
_P_ASSIGN = _rx(r"^(?:const\s+|let\s+|var\s+)?(?P<name>" + ID + r")\s*(?:=(?!=)|:=|<-|\s+recebe\s+)\s*(?P<value>.+)$")
# Atribuição em linguagem natural: "x é igual a 10", "total vale 0", "nome passa a ser 'Ana'", "let x be 5"
_P_ASSIGN_NL = _rx(r"^(?:seja\s+|let\s+|faca\s+|fazer\s+)?(?P<name>" + ID + r")\s+(?:e\s+igual\s+a|eh\s+igual\s+a|"
                   r"for\s+igual\s+a|igual\s+a|e\s+igual|vale|valendo|recebe|passa\s+a\s+ser|passa\s+a\s+valer|"
                   r"fica\s+igual\s+a|fica|deve\s+ser|agora\s+e|e|eh|is\s+equal\s+to|is|equals|becomes|be|=)\s+"
                   r"(?P<value>.+)$")
_P_ASSIGN_OP = _rx(r"^(?P<name>" + ID + r")\s*(?P<op>\+|-|\*|/|%)=\s*(?P<value>.+)$")
_STATEMENT_WORDS = {"se", "if", "for", "while", "para", "enquanto", "print", "imprimir", "imprima", "mostrar", "mostre",
                    "exibir", "retornar", "retorne", "return", "senao", "else", "funcao", "function", "classe", "class",
                    "chamar", "call", "ler", "leia", "read", "importar", "import", "criar", "crie", "fazer", "faca",
                    "repetir", "loop", "caso", "quando", "until", "ate", "elif", "def", "return"}
_P_CALL = _rx(r"^(?:chamar|chame|chama|invocar|invoque|call|invoke|executar\s+(?:a\s+)?funcao|run\s+(?:the\s+)?function)\s+"
              r"(?:(?:a\s+)?(?:funcao|function)\s+)?(?P<name>[a-z_][\w.]*)(?:\s*\((?P<pp>[^)]*)\)|\s+(?:com|with|passando|"
              r"passing)\s+(?:(?:os\s+)?(?:argumentos|parametros|valores)\s+|(?:the\s+)?(?:arguments|args|values)\s+)?"
              r"(?P<args>.+?))?(?:\s+(?:e\s+)?(?:guardar|salvar|armazenar|atribuir|store|save|assign)\s+(?:(?:o\s+)?resultado"
              r"\s+|(?:the\s+)?result\s+)?(?:em|na|no|in|into|to)\s+(?P<target>" + ID + r"))?$")
_ACTION = re.compile(
    r"(?:^|\s|,)(?:(?:e|and|then|entao|faca|fazer|do)\s+)?(?P<act>imprim\w*|printa\w*|print(?:ing)?|mostr\w*|exib\w*|"
    r"show(?:ing)?|display|retorn\w*|return|devolv\w*|incrementa\w*|incremente|increment|decrementa\w*|parar|pare|sair|"
    r"break|continu\w*|chamar|chame|call|adicion\w*|append|somar|some|esperar|espere|sleep)\b",
    re.I,
)
_GERUND = {"imprimindo": "imprimir", "printando": "printar", "mostrando": "mostrar", "exibindo": "exibir",
           "printing": "print", "showing": "show", "retornando": "retornar", "incrementando": "incrementar",
           "adicionando": "adicionar", "somando": "somar", "chamando": "chamar"}


class Stage0:
    """Compilador de intenções. Stateless e thread-safe."""

    def __init__(self) -> None:
        self._rules = [
            ("comment", self._comment), ("import", self._import), ("main", self._main), ("try", self._try),
            ("break", self._break), ("sleep", self._sleep), ("return", self._return), ("input", self._input),
            ("print_range", self._print_range), ("print", self._print), ("for_py", self._for_py),
            ("for_range", self._for_range), ("times", self._times), ("foreach", self._foreach),
            ("while", self._while), ("if", self._if), ("else", self._else), ("func", self._func),
            ("class", self._class), ("list", self._list), ("dict", self._dict), ("incr", self._incr),
            ("append", self._append), ("assign", self._assign), ("call", self._call), ("expr", self._expr_stmt),
        ]

    # ------------------------------------------------------------------ API
    def parse(self, intent: str, known_ids: set[str] | None = None) -> Parsed | None:
        text = clean_intent(intent)
        if not text or len(text) > 400:
            return None
        return self._parse(text, known_ids or set(), depth=0)

    def _parse(self, text: str, known: set[str], depth: int) -> Parsed | None:
        if depth > 3:
            return None
        folded = fold_keep_len(text)
        for name, rule in self._rules:
            try:
                nodes = rule(text, folded, known, depth)
            except E.ExprError:
                nodes = None
            if nodes:
                conf = 0.85 if name == "print" and isinstance(nodes[0], ir.Print) and nodes[0].value[0] == "str" else 1.0
                return Parsed(nodes, name, conf)
        return None

    def parse_program(self, text: str, known_ids: set[str] | None = None) -> tuple[list[ir.Node], int]:
        """Pseudocódigo multilinha -> árvore IR. Linhas não entendidas viram ir.Unresolved."""
        known = set(known_ids or ())
        lines = [ln.rstrip() for ln in text.splitlines()]
        root: list[ir.Node] = []
        stack: list[tuple[int, list[ir.Node], ir.Node | None]] = [(-1, root, None)]
        misses = 0
        for raw in lines:
            if not raw.strip():
                continue
            indent = len(raw.expandtabs(4)) - len(raw.expandtabs(4).lstrip())
            while len(stack) > 1 and indent <= stack[-1][0]:
                stack.pop()
            parent_body = stack[-1][1]
            parsed = self.parse(raw.strip(), known)
            if parsed is None:
                misses += 1
                parent_body.append(ir.Unresolved(clean_intent(raw.strip())))
                continue
            for node in parsed.nodes:
                if isinstance(node, ir.Else):
                    host = self._find_if(parent_body)
                    if host is None:
                        misses += 1
                        parent_body.append(ir.Unresolved(raw.strip()))
                        continue
                    branch: list[ir.Node] = list(node.body)
                    if node.cond is not None:
                        host.elifs.append((node.cond, branch))
                    else:
                        host.orelse = branch
                    stack.append((indent, branch, node))
                    continue
                parent_body.append(node)
                if isinstance(node, (ir.Assign, ir.Input)):
                    known.add(node.name if isinstance(node, ir.Assign) else node.var)
                elif isinstance(node, (ir.ForEach, ir.ForRange)):
                    known.add(node.var)  # "imprimir nome" dentro do laço é a variável, não o texto "nome"
                elif isinstance(node, ir.FuncDef):
                    known.update(node.params)
                elif isinstance(node, ir.Call) and node.target:
                    known.add(node.target)
                if isinstance(node, ir.ClassDef):
                    continue
                if isinstance(node, ir.BLOCKS):
                    stack.append((indent, node.body, node))
        return root, misses

    @staticmethod
    def _find_if(body: list[ir.Node]) -> ir.If | None:
        for node in reversed(body):
            if isinstance(node, ir.If):
                return node
            if not isinstance(node, ir.Comment):
                return None
        return None

    # ------------------------------------------------------------------ helpers
    def _action(self, text: str, known: set[str], depth: int) -> list[ir.Node] | None:
        """Ação embutida: 'imprimindo i', ', retornar x', 'e imprimir total'."""
        rest = text.strip(" ,:;-")
        if not rest:
            return []
        rest = re.sub(r"^(?:e|and|then|entao|faca|fazer|do)\s+", "", rest, flags=re.I)
        first, _, tail = rest.partition(" ")
        if (g := _GERUND.get(fold(first))):
            rest = f"{g} {tail}".strip()
        parsed = self._parse(rest, known, depth + 1)
        return parsed.nodes if parsed else None

    def _split_cond(self, cond_text: str, known: set[str], depth: int):
        """'x > 10 imprimir x senão imprimir y' -> (cond, body, orelse)."""
        orelse = None
        m_else = re.search(r"\s*[,;]?\s+(?:senao|else|caso\s+contrario|otherwise)\s+", fold_keep_len(cond_text), re.I)
        if m_else:
            orelse = self._action(cond_text[m_else.end():], known, depth)
            if orelse is None:
                return None
            cond_text = cond_text[: m_else.start()]
        m = _ACTION.search(fold_keep_len(cond_text))
        body: list[ir.Node] = []
        if m and m.start() > 0:
            body_nodes = self._action(cond_text[m.start():], known, depth)
            if body_nodes is None:
                return None
            body = body_nodes
            cond_text = cond_text[: m.start()]
        cond_text = re.sub(r"\s*(?:,|:|\bentao\b|\bthen\b|\bfaca\b|\bdo\b)\s*$", "", cond_text.strip(), flags=re.I)
        cond = E.parse(cond_text)
        return cond, body, orelse

    def _range_bound(self, raw: str) -> E.Ast:
        node = E.parse(raw)
        if node[0] not in ("num", "id", "un", "attr", "call"):
            raise E.ExprError("limite de intervalo inválido")
        return node

    # ------------------------------------------------------------------ regras
    def _comment(self, t, f, known, depth):
        if m := _P_TODO.match(f):
            return [ir.Comment(_span(t, m, "text"), todo=True)]
        if m := _P_COMMENT.match(f):
            return [ir.Comment(_span(t, m, "text"))]
        return None

    def _import(self, t, f, known, depth):
        m = _P_IMPORT.match(f)
        if not m:
            return None
        mod = _span(t, m, "mod")
        alias = _span(t, m, "alias")
        return [ir.Import(f"{mod} as {alias}" if alias else mod)]

    def _main(self, t, f, known, depth):
        if _P_HELLO.match(f):
            return [ir.Main(body=[ir.Print(("str", "Hello, world!"))], hello=True)]
        if _P_MAIN.match(f):
            return [ir.Main()]
        return None

    def _try(self, t, f, known, depth):
        return [ir.TryCatch()] if _P_TRY.match(f) else None

    def _break(self, t, f, known, depth):
        if _P_BREAK.match(f):
            return [ir.Break()]
        if _P_CONTINUE.match(f):
            return [ir.Continue()]
        return None

    def _sleep(self, t, f, known, depth):
        m = _P_SLEEP.match(f)
        if not m:
            return None
        n = float(m.group("n").replace(",", "."))
        unit = m.group("unit").lower()
        if unit.startswith("mil") or unit == "ms":
            n /= 1000
        elif unit.startswith("min"):
            n *= 60
        return [ir.Sleep(n)]

    def _return(self, t, f, known, depth):
        m = _P_RETURN.match(f)
        if not m:
            return None
        raw = _span(t, m, "expr")
        return [ir.Return(E.parse(raw) if raw else None)]

    def _input(self, t, f, known, depth):
        m = _P_ASK.match(f) or _P_READ.match(f)
        if not m:
            return None
        kind_word = fold(m.group("kind") or "")
        kind = "int" if kind_word in ("numero", "number", "inteiro", "integer", "int") else \
            "float" if kind_word in ("float", "decimal", "real") else "str"
        var = _ident(_span(t, m, "var") or "")
        is_pt = not fold(f.split()[0]) in ("read", "get", "capture", "ask", "prompt")
        if not var:
            var = "entrada" if is_pt else "value"
        prompt = _span(t, m, "prompt") if "prompt" in m.groupdict() else None
        prompt = (prompt or var.replace("_", " ").capitalize()).strip("'\"")
        if not prompt.endswith((":", "?", ": ")):
            prompt += ": "
        elif not prompt.endswith(" "):
            prompt += " "
        return [ir.Input(var, prompt, kind)]

    def _print_range(self, t, f, known, depth):
        m = _P_PRINT_RANGE.match(f)
        if not m:
            return None
        a, b = int(m.group("a")), int(m.group("b"))
        step = 1 if b >= a else -1
        body: list[ir.Node] = [ir.Print(("id", "i"))]
        parity = fold(m.group("parity") or "")
        if parity:
            op = "==" if parity in ("pares", "even") else "!="
            cond = ("bin", op, ("bin", "%", ("id", "i"), ("num", "2")), ("num", "0"))
            body = [ir.If(body=body, cond=cond)]
        return [ir.ForRange(body=body, var="i", start=("num", str(a)), end=("num", str(b)), step=step, inclusive=True)]

    def _print(self, t, f, known, depth):
        m = _P_PRINT.match(f)
        if not m:
            return None
        arg = _span(t, m, "arg") or ""
        value = self._print_value(arg, bool(m.group("marker")), known)
        if value is None:
            return None
        node: ir.Node = ir.Print(value)
        if m.group("times"):
            n = int(m.group("times"))
            return [ir.ForRange(body=[node], var="i", start=("num", "0"), end=("num", str(n)))]
        return [node]

    def _print_value(self, arg: str, marker: bool, known: set[str]) -> E.Ast | None:
        a = arg.strip()
        if not a:
            return None
        if not marker and (nl := _nl_value(a)) is not None:
            return nl  # "imprima a soma de x e y"
        if not marker and (_is_reference(a) or re.fullmatch(r"(?:d|n)(?:o|a|os|as)\s+[^\W\d]+(?:\s+[^\W\d]+)?", fold(a))):
            return None  # "imprima o resultado": referência a um valor, não texto literal
        if marker:
            if re.match(r"(?:de|do|da|of)\s", fold(a)):
                return None  # "a mensagem de boas-vindas" descreve o texto, não é o texto
            return ("str", a.lstrip(":").strip().strip("'\""))
        if len(a) >= 2 and a[0] == a[-1] and a[0] in "'\"`":
            return ("str", a[1:-1])
        node = E.try_parse(a)
        if node is not None and node[0] != "id":
            if node[0] == "attr" and _has_reject_word(a):
                return None
            return node
        if node is not None:  # identificador isolado
            name = node[1]
            if name in known or len(name) <= 3 or "_" in name or any(c.isdigit() for c in name) or name != name.lower():
                return node
            if _has_reject_word(a):
                return None
            return ("str", a)
        n_words = len(a.split())
        if n_words <= 6 and _plain_text(a) and not _has_reject_word(a):
            return ("str", a)
        return None

    def _for_py(self, t, f, known, depth):
        m = _P_FOR_PY.match(f)
        if not m:
            return None
        a, b = _span(t, m, "a"), _span(t, m, "b")
        start, end = (("num", "0"), self._range_bound(a)) if b is None else (self._range_bound(a), self._range_bound(b))
        step = int(m.group("s") or 1)
        body = self._action(_span(t, m, "rest") or "", known | {m.group("var")}, depth)
        if body is None:
            return None
        return [ir.ForRange(body=body, var=_span(t, m, "var"), start=start, end=end, step=step, inclusive=False)]

    def _for_range(self, t, f, known, depth):
        m = _P_FOR_RANGE.match(f)
        if not m:
            return None
        var = _ident(_span(t, m, "var") or "i") or "i"
        start, end = self._range_bound(_span(t, m, "a")), self._range_bound(_span(t, m, "b"))
        step = int(m.group("s1") or m.group("s2") or 1)
        if start[0] == "num" and end[0] == "num" and float(start[1]) > float(end[1]):
            step = -abs(step)
        body = self._action(_span(t, m, "rest") or "", known | {var}, depth)
        if body is None:
            return None
        return [ir.ForRange(body=body, var=var, start=start, end=end, step=step, inclusive=True)]

    def _times(self, t, f, known, depth):
        m = _P_TIMES.match(f)
        if not m:
            return None
        n_raw = _span(t, m, "n")
        if not n_raw.isdigit() and n_raw not in known and len(n_raw) > 2:
            return None
        body = self._action(_span(t, m, "rest") or "", known | {"i"}, depth)
        if body is None:
            return None
        return [ir.ForRange(body=body, var="i", start=("num", "0"), end=E.parse(n_raw), inclusive=False)]

    def _foreach(self, t, f, known, depth):
        m = _P_FOREACH.match(f)
        if not m:
            return None
        it = _span(t, m, "iter")
        if fold(it) in ("range", "linha", "arquivo", "file", "line", "lines", "linhas", "cada"):
            return None
        var = _ident(_span(t, m, "var") or "")
        if not var:
            base = it.split(".")[-1]
            var = base[:-1] if len(base) > 3 and base.endswith("s") else "item"
            if var == base:
                var = "item"
        body = self._action(_span(t, m, "rest") or "", known | {var}, depth)
        if body is None:
            return None
        iterable = E.parse(it)
        return [ir.ForEach(body=body, var=var, iterable=iterable)]

    def _while(self, t, f, known, depth):
        if _P_INFINITE.match(f):
            return [ir.While(cond=("bool", True))]
        m = _P_WHILE.match(f)
        negate = False
        if not m:
            m = _P_UNTIL.match(f)
            negate = True
        if not m:
            return None
        split = self._split_cond(_span(t, m, "cond"), known, depth)
        if split is None or split[2] is not None:
            return None
        cond, body, _ = split
        if negate:
            cond = ("un", "!", ("paren", cond))
        return [ir.While(body=body, cond=cond)]

    def _if(self, t, f, known, depth):
        m = _P_IF.match(f)
        if not m:
            return None
        split = self._split_cond(_span(t, m, "cond"), known, depth)
        if split is None:
            return None
        cond, body, orelse = split
        return [ir.If(body=body, cond=cond, orelse=orelse)]

    def _else(self, t, f, known, depth):
        m = _P_ELSE.match(f)
        if not m:
            return None
        raw = _span(t, m, "cond") or _span(t, m, "cond2")
        if raw is None:
            return [ir.Else()]
        split = self._split_cond(raw, known, depth)
        if split is None or split[2] is not None:
            return None
        return [ir.Else(body=split[1], cond=split[0])]

    def _func(self, t, f, known, depth):
        m = _P_FUNC.match(f)
        if not m:
            return None
        name = _span(t, m, "name")
        if fold(name) in ("principal", "main"):
            return [ir.Main()]
        raw_params = _span(t, m, "pp") if m.group("pp") is not None else _span(t, m, "params")
        params = []
        if raw_params:
            for p in re.split(r"\s*,\s*|\s+(?:e|and)\s+", raw_params.strip()):
                p = p.strip().split(":")[0].split("=")[0].strip()
                if p and p.split()[-1] not in _RESERVED:
                    params.append(_ident(p.split()[-1]))
        if any(not p for p in params):
            return None
        ret_raw = _span(t, m, "ret")
        ret = E.parse(ret_raw) if ret_raw else None
        return [ir.FuncDef(name=_ident(name), params=params, ret=ret)]

    def _class(self, t, f, known, depth):
        m = _P_CLASS.match(f)
        if not m:
            return None
        name = _ident(_span(t, m, "name"))
        name = name[:1].upper() + name[1:]
        fields: list[tuple[str, str]] = []
        raw = _span(t, m, "fields")
        if raw:
            for part in re.split(r"\s*,\s*|\s+(?:e|and)\s+", raw):
                fname, _, ftype = part.partition(":")
                fname = _ident(fname.strip())
                if not fname:
                    return None
                ftype = _TYPE_WORDS.get(fold(ftype.strip()), "") if ftype else ""
                fields.append((fname, ftype or field_type(fname)))
        return [ir.ClassDef(name, fields)]

    def _list(self, t, f, known, depth):
        if m := _P_LIST_EMPTY.match(f):
            return [ir.Assign(_ident(_span(t, m, "name")), ("list", []))]
        m = _P_LIST.match(f)
        if not m:
            return None
        name = _ident(_span(t, m, "name") or _span(t, m, "of") or "itens")
        items = [_literal(x) for x in _split_items(_span(t, m, "items"))]
        if not name or not items:
            return None
        return [ir.Assign(name, ("list", items))]

    def _dict(self, t, f, known, depth):
        m = _P_DICT.match(f)
        if not m:
            return None
        pairs = []
        for part in _split_items(_span(t, m, "pairs")):
            mm = re.match(r"^([A-Za-z_]\w*)\s*(?::|=|\s)\s*(.+)$", part)
            if not mm:
                return None
            pairs.append((mm.group(1), _literal(mm.group(2))))
        return [ir.Assign(_ident(_span(t, m, "name")), ("dict", pairs))]

    def _incr(self, t, f, known, depth):
        if m := _P_PLUSPLUS.match(f):
            name = _span(t, m, "name")
            op = "+" if m.group("op") == "++" else "-"
            return [ir.Assign(name, ("bin", op, ("id", name), ("num", "1")))]
        m = _P_INCR.match(f)
        if not m:
            return None
        name = _ident(_span(t, m, "name"))
        op = "+" if fold(m.group("verb")).startswith(("incre", "aumen")) else "-"
        return [ir.Assign(name, ("bin", op, ("id", name), ("num", m.group("n") or "1")))]

    def _append(self, t, f, known, depth):
        m = _P_APPEND.match(f)
        if not m:
            return None
        verb = fold(m.group("verb"))
        name = _ident(_span(t, m, "name"))
        value = E.try_parse(_span(t, m, "v")) or ("str", _span(t, m, "v"))
        numeric = value[0] == "num" or E.infer(value) in ("int", "float", "num?")
        if verb in ("somar", "some") or (verb in ("adicionar", "adicione", "adiciona", "add") and numeric
                                        and not m.group("list")):
            return [ir.Assign(name, ("bin", "+", ("id", name), value))]
        return [ir.Append(name, value)]

    def _assign(self, t, f, known, depth):
        if m := _P_ASSIGN_OP.match(f):  # total += preco
            name = _ident(_span(t, m, "name"))
            value = E.try_parse(_span(t, m, "value"))
            if not name or value is None:
                return None
            return [ir.Assign(name, ("bin", m.group("op"), ("id", name), value))]
        for pat in (_P_ASSIGN_DECL, _P_ASSIGN_SET, _P_ASSIGN_TO, _P_ASSIGN, _P_ASSIGN_NL):
            m = pat.match(f)
            if not m:
                continue
            name = _ident(_span(t, m, "name"))
            if not name or fold(name) in _STATEMENT_WORDS:
                return None
            raw = _span(t, m, "value")
            if (nl := _nl_value(raw)) is not None:
                return [ir.Assign(name, nl, const=bool(m.groupdict().get("const")))]
            value = E.try_parse(raw)
            if value is not None and value[0] == "id" and pat is _P_ASSIGN_NL and value[1] not in known and \
                    (value[1][:1].isupper() or not raw.isascii()):
                value = ("str", raw.strip())  # "nome é Ana" -> texto, não identificador
            quoted = len(raw) >= 2 and raw[0] == raw[-1] and raw[0] in "'\""
            if value is None and not quoted and _is_reference(raw):
                return None  # "quantidade é igual ao tamanho de pedidos" que não sei compilar: fica com a IA
            if value is None:
                if pat in (_P_ASSIGN, _P_ASSIGN_NL) and not quoted:
                    if pat is _P_ASSIGN or not _plain_text(raw) or len(raw.split()) > 4:
                        return None
                elif not _plain_text(raw) or len(raw.split()) > 6:
                    return None
                value = ("str", raw.strip("'\""))
            const = bool(m.groupdict().get("const"))
            return [ir.Assign(name, value, const=const)]
        return None

    def _expr_stmt(self, t, f, known, depth):
        """Chamada solta escrita como código: salvar(dados), lista.ordenar(), log.info("x")."""
        node = E.try_parse(t)
        if node is None or node[0] != "call":
            return None
        fn = node[1]
        parts = []
        while fn[0] == "attr":
            parts.append(fn[2])
            fn = fn[1]
        if fn[0] != "id":
            return None
        parts.append(fn[1])
        return [ir.Call(".".join(reversed(parts)), node[2])]

    def _call(self, t, f, known, depth):
        m = _P_CALL.match(f)
        if not m:
            return None
        raw = _span(t, m, "pp") if m.group("pp") is not None else _span(t, m, "args")
        args = [E.parse(a) for a in _split_items(raw)] if raw else []
        target = _span(t, m, "target")
        return [ir.Call(_span(t, m, "name"), args, _ident(target) if target else None)]
