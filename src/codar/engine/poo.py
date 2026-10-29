"""Programação orientada a objetos no compilador determinístico, com o contexto real das classes.

Construções reconhecidas (Python, JavaScript e TypeScript):

- herança — "classe Aluno herda de Pessoa com matricula": o construtor repassa à classe-mãe exatamente os
  parâmetros dela, lidos do arquivo ou do projeto; mãe desconhecida repassa os argumentos sem inventar nomes;
- classe com métodos — "classe Conta com saldo e métodos depositar e sacar": campos e métodos declarados, com
  corpo que sinaliza a implementação pendente (nunca um corpo inventado);
- método com corpo dentro da classe — "método depositar com valor que soma valor ao saldo": atributos da classe
  viram self./this. e parâmetros continuam parâmetros;
- objeto — "objeto conta da classe Conta com saldo 100": argumentos conferidos com o construtor real;
- chamada de método — "chame depositar de conta com 50": o método precisa existir na classe do objeto.

Nada é executado: classes são lidas por ast (Python) e por expressões regulares com máscara (JS/TS). Pedidos que
dependem de algo que não existe no código produzem um erro explicativo em vez de código que falharia ao rodar.
"""

from __future__ import annotations

import ast
import re
from dataclasses import dataclass, field
from pathlib import Path

from codar.audit.lexer import mask
from codar.engine import expr as E
from codar.engine.stage0 import _TYPE_WORDS, field_type
from codar.textutil import fold, fold_keep_len

LINGUAGENS = ("python", "javascript", "typescript")
_ID = r"[A-Za-z_]\w*"
_CRIAR = (r"(?:(?:crie|criar|cria|create|defina|definir|define|faca|fazer|make|declare|declarar|escreva|write|"
          r"adicione|adicionar|add)\s+)?(?:(?:uma|um|a|an|la|el|o)\s+)?")
_CLASSE = r"(?:classe|class|clase)"
_HERDA = (r"(?:herda|herde|herdando|herdar|estende|estenda|estendendo|extends|extend|extending|inherits|inheriting|"
          r"hereda|heredando|derivada|derivado|deriva|filha|subclasse|subclass)")
_P_CLASSE = re.compile(
    rf"^{_CRIAR}{_CLASSE}\s+(?:(?:chamada|chamado|named|called|llamada)\s+)?(?P<nome>{_ID})"
    rf"(?:\s*,?\s+(?:que\s+|which\s+|that\s+)?{_HERDA}\s+(?:(?:de|from|da|do|of)\s+)?(?:(?:a|o|the|la)\s+)?"
    rf"(?:{_CLASSE}\s+)?(?P<base>{_ID}))?(?:\s*,?\s+(?:com|with|con|tendo|having|contendo)\s+(?P<resto>.+))?$", re.I)
_P_METODOS = re.compile(r"^(?:(?P<campos>.*?)\s*,?\s+(?:e|and|y)\s+)?(?:(?:os|the|los)\s+)?(?:metodos?|methods?)\s+"
                        r"(?P<metodos>.+)$", re.I)
_P_METODO = re.compile(
    rf"^{_CRIAR}(?:metodo|method)\s+(?:(?:chamado|named|called)\s+)?(?P<nome>{_ID})(?:\s*\((?P<pp>[^)]*)\)|"
    rf"\s+(?:que\s+recebe|recebendo|com|with|taking|con)\s+(?P<params>{_ID}(?:\s*(?:,|\se\s|\sand\s|\sy\s)\s*{_ID})*))?"
    rf"\s*,?\s+(?:que|which|that|para|to)\s+(?P<acao>.+)$", re.I)
_P_OBJETO = re.compile(
    rf"^{_CRIAR}(?:objeto|instancia|instance|object|instancie|instanciar|instantiate|nuevo\s+objeto)\s+"
    rf"(?:(?:chamado|chamada|named|called|llamado)\s+)?(?P<var>{_ID})\s+(?:da|de|do|of|from|del)\s+"
    rf"(?:(?:a|la|the)\s+)?(?:{_CLASSE}\s+)?(?P<cls>{_ID})(?:\s*,?\s+(?:com|with|con|passando|passing)\s+(?P<args>.+))?$",
    re.I)
_P_CHAMADA = re.compile(
    rf"^(?:chame|chamar|chama|invoque|invocar|call|invoke|llame|llama)\s+(?:(?:o|a|the|el)\s+)?(?:(?:metodo|method)\s+)?"
    rf"(?P<met>{_ID})\s+(?:de|do|da|of|on|del)\s+(?:(?:o|a|the|el)\s+)?(?:(?:objeto|object)\s+)?(?P<obj>{_ID})"
    rf"(?:\s*,?\s+(?:com|with|con|passando|passing)\s+(?P<args>.+?))?"
    rf"(?:\s*,?\s+(?:e\s+|and\s+)?(?:guarde|guardar|salve|salvar|store|save)\s+(?:o\s+resultado\s+|the\s+result\s+)?"
    rf"(?:em|in|en)\s+(?P<dest>{_ID}))?$", re.I)
_P_SOMA = re.compile(rf"^(?:soma|some|somar|adiciona|adicione|adicionar|acrescenta|acrescente|incrementa|incrementar|"
                     rf"aumenta|aumentar|add|adds)\s+(?P<v>.+?)\s+(?:a|ao|aos|as|no|na|em|to)\s+(?:o\s+|a\s+)?"
                     rf"(?P<alvo>{_ID})$", re.I)
_P_SUBTRAI = re.compile(rf"^(?:subtrai|subtraia|subtrair|diminui|diminua|diminuir|retira|retire|retirar|desconta|"
                        rf"desconte|descontar|tira|tire|subtract|subtracts)\s+(?P<v>.+?)\s+(?:de|do|da|dos|das|from)\s+"
                        rf"(?:o\s+|a\s+)?(?P<alvo>{_ID})$", re.I)
_P_DEFINE = re.compile(rf"^(?:define|defina|definir|altera|altere|alterar|muda|mude|mudar|atualiza|atualize|atualizar|"
                       rf"sets?|updates?|changes?)\s+(?:o\s+|a\s+|the\s+)?(?P<alvo>{_ID})\s+(?:para|como|to|=)\s+(?P<v>.+)$",
                       re.I)
_VERBOS = {"imprime": "imprimir", "mostra": "mostrar", "exibe": "exibir", "escreve": "escrever", "retorna": "retornar",
           "devolve": "retornar", "prints": "print", "returns": "return", "shows": "show", "displays": "display"}


@dataclass
class Classe:
    nome: str
    params: list[tuple[str, bool, str]] = field(default_factory=list)  # construtor: (nome, tem padrão, anotação)
    atributos: dict[str, str] = field(default_factory=dict)  # nome -> tipo/anotação conhecida ("" se não houver)
    metodos: set[str] = field(default_factory=set)
    base: str | None = None
    dataclass: bool = False
    variadico: bool = False  # *args/**kwargs no construtor: a assinatura não é conhecida inteira


# ---------------------------------------------------------------------------------------- leitura de classes
def _classes_python(texto: str) -> dict[str, Classe]:
    try:
        arvore = ast.parse(texto)
    except (SyntaxError, ValueError, RecursionError):
        return {}
    out = {}
    for no in ast.walk(arvore):
        if not isinstance(no, ast.ClassDef):
            continue
        c = Classe(no.name, base=next((b.id for b in no.bases if isinstance(b, ast.Name) and b.id != "object"), None))
        c.dataclass = any((isinstance(d, ast.Name) and d.id == "dataclass") or (isinstance(d, ast.Call) and getattr(
            d.func, "id", getattr(d.func, "attr", "")) == "dataclass") or (isinstance(d, ast.Attribute) and d.attr == "dataclass")
            for d in no.decorator_list)
        for item in no.body:
            if isinstance(item, ast.AnnAssign) and isinstance(item.target, ast.Name):
                anotacao = ast.unparse(item.annotation)
                if anotacao.startswith(("ClassVar", "typing.ClassVar")):
                    continue
                c.atributos[item.target.id] = anotacao
                if c.dataclass:
                    c.params.append((item.target.id, item.value is not None, anotacao))
            elif isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                c.metodos.add(item.name)
                if item.name == "__init__":
                    args = item.args
                    posicionais = args.posonlyargs + args.args
                    padroes = len(args.defaults)
                    c.params = [(a.arg, i >= len(posicionais) - padroes, ast.unparse(a.annotation) if a.annotation else "")
                                for i, a in enumerate(posicionais) if i > 0]
                    c.params += [(a.arg, d is not None, ast.unparse(a.annotation) if a.annotation else "")
                                 for a, d in zip(args.kwonlyargs, args.kw_defaults)]
                    c.variadico = bool(args.vararg or args.kwarg)
                for sub in ast.walk(item):
                    if isinstance(sub, ast.Attribute) and isinstance(sub.value, ast.Name) and sub.value.id == "self" \
                            and isinstance(sub.ctx, ast.Store):
                        c.atributos.setdefault(sub.attr, "")
        out[c.nome] = c
    return out


_JS_CLASSE = re.compile(r"\bclass\s+([A-Za-z_$][\w$]*)(?:\s+extends\s+([A-Za-z_$][\w$.]*))?[^{]*\{")


def _corpo(texto: str, abre: int) -> str:
    profundidade = 0
    for i in range(abre, len(texto)):
        profundidade += (texto[i] == "{") - (texto[i] == "}")
        if profundidade == 0:
            return texto[abre + 1:i]
    return texto[abre + 1:]


def _classes_js(texto: str) -> dict[str, Classe]:
    mascarado = mask(texto, "javascript", strings=True)
    out = {}
    for m in _JS_CLASSE.finditer(mascarado):
        corpo = _corpo(mascarado, m.end() - 1)
        c = Classe(m[1], base=m[2])
        construtor = re.search(r"\bconstructor\s*\(([^)]*)\)", corpo)
        if construtor:
            for parte in [p.strip() for p in construtor[1].split(",") if p.strip()]:
                if parte.startswith("..."):
                    c.variadico = True
                    continue
                nome = re.match(r"(?:(?:public|private|protected|readonly)\s+)*([A-Za-z_$][\w$]*)", parte)
                if nome:
                    tipo = re.search(r":\s*([^=]+)", parte)
                    c.params.append((nome[1], "=" in parte or "?" in parte.split(":")[0], tipo[1].strip() if tipo else ""))
        for campo in re.finditer(r"^\s*(?:(?:public|private|protected|readonly|static)\s+)*#?([A-Za-z_$][\w$]*)\s*[?!]?"
                                 r"\s*:\s*([^;=\n]+)", corpo, re.M):
            c.atributos[campo[1]] = campo[2].strip()
        for atribuido in re.finditer(r"\bthis\.#?([A-Za-z_$][\w$]*)\s*=(?!=)", corpo):
            c.atributos.setdefault(atribuido[1], "")
        for metodo in re.finditer(r"^\s*(?:(?:async|static|public|private|protected|get|set)\s+)*\*?([A-Za-z_$][\w$]*)"
                                  r"\s*\([^)]*\)\s*(?::[^{]+)?\{", corpo, re.M):
            if metodo[1] not in ("constructor", "if", "for", "while", "switch", "catch", "function"):
                c.metodos.add(metodo[1])
        out[c.nome] = c
    return out


def _ler(lang: str, texto: str) -> dict[str, Classe]:
    return _classes_python(texto) if lang == "python" else _classes_js(texto)


def _no_projeto(nome: str, lang: str, raiz: Path | None, atual: str | None) -> Classe | None:
    if raiz is None:
        return None
    from codar.engine.vinculos import _JS_EXTS, _analisado, _arquivos

    extensoes = (".py",) if lang == "python" else _JS_EXTS
    encontradas = []
    for arquivo in _arquivos(Path(raiz).resolve(), extensoes):
        if atual and arquivo.resolve() == Path(atual).resolve():
            continue
        classes = _analisado(arquivo, lambda texto: _ler(lang, texto), "poo-" + lang) or {}
        if nome in classes:
            encontradas.append(classes[nome])
    return encontradas[0] if len(encontradas) == 1 else None


def _classe(nome: str, lang: str, contexto: str, raiz, atual) -> Classe | None:
    local = _ler(lang, contexto).get(nome)
    if local is None and atual and Path(atual).is_file():
        try:
            local = _ler(lang, Path(atual).read_text(encoding="utf-8", errors="replace")).get(nome)
        except OSError:
            local = None
    return local or _no_projeto(nome, lang, raiz, atual)


def _metodos_com_herdados(c: Classe, lang: str, contexto: str, raiz, atual) -> set[str]:
    metodos, visitadas = set(c.metodos), {c.nome}
    while c.base and c.base not in visitadas:
        visitadas.add(c.base)
        mae = _classe(c.base, lang, contexto, raiz, atual)
        if mae is None:
            return set()  # herança de algo desconhecido: não dá para afirmar que o método falta
        metodos |= mae.metodos
        c = mae
    return metodos


# ------------------------------------------------------------------------------------------------ utilitários
def _span(texto: str, m: re.Match, grupo: str) -> str | None:
    if m.group(grupo) is None:
        return None
    return texto[m.start(grupo):m.end(grupo)].strip()


def _nomes(texto: str) -> list[str]:
    return [p.strip() for p in re.split(r"\s*,\s*|\s+(?:e|and|y)\s+", texto.strip()) if p.strip()]


def _campos(texto: str | None) -> list[tuple[str, str]]:
    if not texto:
        return []
    texto = re.sub(r"^(?:(?:os|as|the|los|las)\s+)?(?:(?:campos|atributos|propriedades|fields|attributes|properties)\s+)",
                   "", texto.strip(), flags=re.I)
    out = []
    for parte in _nomes(texto):
        nome, _, tipo = parte.partition(":")
        nome = nome.strip()
        if not re.fullmatch(_ID, nome):
            raise ValueError(f"campo inválido: {parte!r}")
        out.append((nome, _TYPE_WORDS.get(fold(tipo.strip()), "") if tipo else field_type(nome)))
    return out


def _metodos_declarados(texto: str) -> list[tuple[str, list[str]]]:
    out = []
    for parte in re.findall(rf"{_ID}\s*(?:\([^)]*\))?", texto):
        nome = re.match(_ID, parte)[0]
        params = re.search(r"\(([^)]*)\)", parte)
        lista = [p.strip() for p in params[1].split(",") if p.strip()] if params else []
        if nome.lower() not in ("e", "and", "y") and all(re.fullmatch(_ID, p) for p in lista):
            out.append((nome, lista))
    return out


def _argumentos(texto: str | None) -> list[tuple[str | None, E.Ast]]:
    """'nome 'Ana' e idade 20' -> [('nome', str), ('idade', num)]; valores entre aspas podem conter ' e '."""
    if not texto:
        return []
    partes, atual, aspas = [], "", None
    i = 0
    while i < len(texto):
        ch = texto[i]
        if aspas:
            atual += ch
            if ch == aspas:
                aspas = None
        elif ch in "'\"":
            aspas, atual = ch, atual + ch
        elif ch == ",":
            partes.append(atual)
            atual = ""
        elif re.match(r"\s+(?:e|and|y)\s+", texto[i:], re.I) and not re.match(r"\s+(?:e|and|y)\s+[-+*/]", texto[i:]):
            fim = re.match(r"\s+(?:e|and|y)\s+", texto[i:], re.I).end()
            partes.append(atual)
            atual = ""
            i += fim
            continue
        else:
            atual += ch
        i += 1
    partes.append(atual)
    out = []
    for parte in (p.strip() for p in partes if p.strip()):
        m = re.match(rf"^(?P<k>{_ID})\s*(?:=(?!=)|:|\s)\s*(?P<v>.+)$", parte)
        # "nome 'Ana'", "idade=20" e "saldo: 100" são nomeados; "x + 1" e "n" são posicionais.
        nomeado = m is not None and (re.match(rf"^{_ID}\s*(?:=(?!=)|:)", parte) is not None or E.try_parse(parte) is None)
        if nomeado:
            valor = E.try_parse(m["v"].strip())
            if valor is None:
                raise ValueError(f"valor não reconhecido: {m['v']!r}")
            out.append((m["k"], valor))
        else:
            valor = E.try_parse(parte)
            if valor is None:
                raise ValueError(f"argumento não reconhecido: {parte!r}")
            out.append((None, valor))
    return out


def _py_tipo(tipo: str) -> str:
    return {"int": "int", "float": "float", "str": "str", "bool": "bool"}.get(tipo, tipo or "str")


def _ts_tipo(tipo: str) -> str:
    return E.ts_type(tipo) if tipo in ("int", "float", "str", "bool") else (tipo or "unknown")


def _indent(linhas: list[str], unidade: str) -> list[str]:
    return [unidade + linha if linha else linha for linha in linhas]


def _pendente(nome: str, params: list[str], lang: str, ts_tipos: dict[str, str] | None = None) -> list[str]:
    if lang == "python":
        return [f"def {nome}(self{''.join(', ' + p for p in params)}):", f'    raise NotImplementedError("implemente {nome}")']
    assinatura = ", ".join(f"{p}: {(ts_tipos or {}).get(p, 'unknown')}" if lang == "typescript" else p for p in params)
    retorno = ": void" if lang == "typescript" else ""
    return [f"{nome}({assinatura}){retorno} {{", f'  throw new Error("implemente {nome}");', "}"]


# ------------------------------------------------------------------------------------------------- herança
def _classe_nova(texto: str, lang: str, contexto: str, raiz, atual) -> tuple[str, list[str], list[str]] | None:
    m = _P_CLASSE.match(fold_keep_len(texto))
    if not m:
        return None
    nome, base, resto = _span(texto, m, "nome"), _span(texto, m, "base"), _span(texto, m, "resto")
    metodos_txt = None
    if resto and (mm := _P_METODOS.match(fold_keep_len(resto))):
        metodos_txt = _span(resto, mm, "metodos")
        resto = _span(resto, mm, "campos")
    if base is None and metodos_txt is None:
        return None  # classe simples: o Estágio 0 comum já emite em todas as linguagens
    nome = nome[:1].upper() + nome[1:]
    campos = _campos(resto)
    metodos = _metodos_declarados(metodos_txt) if metodos_txt else []
    if metodos_txt and not metodos:
        raise ValueError("informe os nomes dos métodos, por exemplo: métodos depositar e sacar")
    mae = _classe(base, lang, contexto, raiz, atual) if base else None
    notas = []
    if base and mae is None:
        notas.append(f"{base} não foi encontrada no arquivo nem no projeto: o construtor repassa os argumentos a ela")
    elif mae is not None and mae.variadico:
        notas.append(f"o construtor de {base} aceita argumentos variáveis: eles são repassados como estão")
    if lang == "python":
        linhas = _python_classe(nome, base, mae, campos, metodos)
        imports = ["from dataclasses import dataclass"] if any(ln.startswith("@dataclass") for ln in linhas) else []
    else:
        linhas, imports = _js_classe(nome, base, mae, campos, metodos, lang), []
    return "\n".join(linhas), imports, notas


def _python_classe(nome, base, mae, campos, metodos) -> list[str]:
    cabecalho = f"class {nome}({base}):" if base else f"class {nome}:"
    metodos_py = [linha for nome_m, params in metodos for linha in ["", *_pendente(nome_m, params, "python")]]
    if base is None and not campos:
        return [cabecalho, *(_indent(metodos_py[1:], "    ") if metodos_py else ["    pass"])]
    if base is None or (mae is not None and mae.dataclass):
        com_padrao = mae is not None and any(padrao for _, padrao, _ in mae.params)
        decorador = "@dataclass(kw_only=True)" if com_padrao and campos else "@dataclass"
        corpo = [f"{f}: {_py_tipo(t)}" for f, t in campos]
        if base and not corpo and not metodos:
            return [cabecalho, "    pass"]
        corpo = corpo or ([] if metodos else ["pass"])
        return [decorador, cabecalho, *_indent(corpo, "    "), *_indent(metodos_py, "    ")]
    if not campos:
        return [cabecalho, *(_indent(metodos_py[1:], "    ") if metodos_py else ["    pass"])]
    proprios = ", ".join(f"{f}: {_py_tipo(t)}" for f, t in campos)
    if mae is None or mae.variadico:
        assinatura, repasse = f"self, *args, {proprios}, **kwargs", "*args, **kwargs"
    else:
        obrigatorios = [p for p in mae.params if not p[1]]
        opcionais = [p for p in mae.params if p[1]]
        if opcionais:  # com padrões na mãe, os campos novos vêm só por nome
            assinatura = "self, " + ", ".join(p[0] + (f": {p[2]}" if p[2] else "") for p in obrigatorios) + \
                (", " if obrigatorios else "") + f"*, {proprios}, **kwargs"
            repasse = ", ".join(p[0] for p in obrigatorios) + (", " if obrigatorios else "") + "**kwargs"
        else:
            herdados = ", ".join(p[0] + (f": {p[2]}" if p[2] else "") for p in obrigatorios)
            assinatura = "self, " + (herdados + ", " if herdados else "") + proprios
            repasse = ", ".join(p[0] for p in obrigatorios)
    corpo = [f"def __init__({assinatura}):", f"    super().__init__({repasse})", *(f"    self.{f} = {f}" for f, _ in campos)]
    return [cabecalho, *_indent(corpo, "    "), *_indent(metodos_py, "    ")]


def _js_classe(nome, base, mae, campos, metodos, lang) -> list[str]:
    ts = lang == "typescript"
    cabecalho = f"class {nome} extends {base} {{" if base else f"class {nome} {{"
    declaracoes = [f"  {f}: {_ts_tipo(t)};" for f, t in campos] if ts else []
    proprios = [f"{f}: {_ts_tipo(t)}" if ts else f for f, t in campos]
    construtor = []
    if campos:
        if base is None:
            params, chamada = proprios, None
        elif mae is None or mae.variadico:
            params = proprios + [f"...args: ConstructorParameters<typeof {base}>" if ts else "...args"]
            chamada = "super(...args);"
        else:
            herdados = [p[0] + (f": {p[2]}" if ts and p[2] else ": unknown" if ts else "") for p in mae.params]
            params = herdados + proprios
            chamada = f"super({', '.join(p[0] for p in mae.params)});"
        construtor = [f"  constructor({', '.join(params)}) {{", *([f"    {chamada}"] if chamada else []),
                      *(f"    this.{f} = {f};" for f, _ in campos), "  }"]
    tipos = {f: _ts_tipo(t) for f, t in campos}
    corpo_metodos = [linha for nome_m, params in metodos for linha in ["", *_indent(_pendente(nome_m, params, lang, tipos), "  ")]]
    corpo = [*declaracoes, *([""] if declaracoes and construtor else []), *construtor, *corpo_metodos]
    if corpo and not corpo[0]:
        corpo = corpo[1:]
    return [cabecalho, *corpo, "}"]


# --------------------------------------------------------------------------------------- método com corpo
def _classe_envolvente(antes: str, recuo: str, lang: str) -> str | None:
    profundidade = len(recuo.expandtabs(4))
    if profundidade == 0:
        return None
    for linha in reversed(antes.splitlines()):
        if not linha.strip() or linha.lstrip().startswith(("#", "//", "*")):
            continue
        nivel = len(linha.expandtabs(4)) - len(linha.expandtabs(4).lstrip())
        if nivel >= profundidade:
            continue
        m = re.match(r"\s*class\s+(\w+)" if lang == "python" else r"\s*(?:export\s+)?(?:default\s+)?class\s+([A-Za-z_$][\w$]*)", linha)
        return m[1] if m else None
    return None


def _qualificar(codigo: str, atributos: set[str], prefixo: str) -> str:
    """Atributos da classe viram self.x/this.x fora de strings (e dentro das chaves de f-strings)."""
    if not atributos:
        return codigo
    padrao = re.compile(r"(?<![\w.$])(" + "|".join(map(re.escape, sorted(atributos, key=len, reverse=True))) + r")\b")

    def trocar(trecho: str) -> str:
        def um(m):
            antes = trecho[:m.start()].rstrip()
            # Declarações (const nome, def nome, nome=valor em chamada) não viram atributo.
            if re.search(r"(?:\b(?:const|let|var|def|class|function)|\(|,)\s*$", antes) and \
                    re.match(r"\s*=(?!=)", trecho[m.end():]) or re.search(r"\b(?:const|let|var|def|class|function)$", antes):
                return m[0]
            return f"{prefixo}.{m[1]}"
        return padrao.sub(um, trecho)
    partes = re.split(r"""((?:f|rf|fr)?"(?:\\.|[^"\\])*"|(?:f|rf|fr)?'(?:\\.|[^'\\])*'|`(?:\\.|[^`\\])*`)""", codigo)
    for i, parte in enumerate(partes):
        if i % 2 == 0:
            partes[i] = trocar(parte)
        elif parte[:1] in "fr" and parte.lstrip("rf")[:1] in "\"'":
            partes[i] = re.sub(r"\{([^{}]*)\}", lambda m: "{" + trocar(m[1]) + "}", parte)
        elif parte.startswith("`"):
            partes[i] = re.sub(r"\$\{([^{}]*)\}", lambda m: "${" + trocar(m[1]) + "}", parte)
    return "".join(partes)


def _metodo(texto: str, lang: str, contexto: str, antes: str, recuo: str, raiz, atual):
    m = _P_METODO.match(fold_keep_len(texto))
    if not m:
        return None
    nome_classe = _classe_envolvente(antes, recuo, lang)
    if nome_classe is None:
        raise ValueError("Método POO precisa ficar dentro de uma classe: escreva o pedido com recuo no corpo da "
                         "classe; fora dela, use 'função'.")
    classe = _classe(nome_classe, lang, contexto, raiz, atual) or Classe(nome_classe)
    nome = _span(texto, m, "nome")
    bruto = _span(texto, m, "pp") if m.group("pp") is not None else _span(texto, m, "params")
    params = _nomes(bruto) if bruto else []
    if not all(re.fullmatch(_ID, p) for p in params):
        return None
    acao = _span(texto, m, "acao")
    prefixo = "self" if lang == "python" else "this"
    atributos = set(classe.atributos) - set(params)
    if not any(re.search(rf"\b{re.escape(a)}\b", acao) for a in atributos):
        from codar.engine import ir
        from codar.engine.stage0 import Stage0

        inteiro = Stage0().parse(texto, set(params))
        if inteiro and len(inteiro.nodes) == 1 and isinstance(inteiro.nodes[0], ir.FuncDef):
            return None  # sem atributos, o compilador comum já faz o método (e deduz os tipos pelo uso)
    linhas = _acao_poo(acao, lang, atributos, prefixo, params)
    if linhas is None:
        return None
    if lang == "python":
        corpo = [f"def {nome}(self{''.join(', ' + p for p in params)}):", *_indent(linhas, "    ")]
    else:
        tipos = {}
        if lang == "typescript":
            for p in params:  # o tipo do atributo com que o parâmetro é combinado; senão, unknown
                alvo = next((a for a in atributos if re.search(rf"this\.{a}\s*[-+]?=\s*.*\b{p}\b", "\n".join(linhas))), None)
                tipos[p] = _ts_tipo(classe.atributos.get(alvo, "")) if alvo and classe.atributos.get(alvo) else \
                    ("number" if alvo else "unknown")
        assinatura = ", ".join(f"{p}: {tipos[p]}" if lang == "typescript" else p for p in params)
        retorno = "" if lang != "typescript" or any(ln.lstrip().startswith("return") for ln in linhas) else ": void"
        corpo = [f"{nome}({assinatura}){retorno} {{", *_indent(linhas, "  "), "}"]
    return "\n".join(corpo), [], []


def _acao_poo(acao: str, lang: str, atributos: set[str], prefixo: str, params: list[str]) -> list[str] | None:
    js = lang != "python"
    fim = ";" if js else ""
    for padrao, operador in ((_P_SOMA, "+="), (_P_SUBTRAI, "-="), (_P_DEFINE, "=")):
        if m := padrao.match(fold_keep_len(acao)):
            alvo = _span(acao, m, "alvo")
            valor = E.try_parse(_span(acao, m, "v"))
            if alvo not in atributos or valor is None:
                return None
            expressao = _qualificar(E.render(valor, lang), atributos, prefixo)
            return [f"{prefixo}.{alvo} {operador} {expressao}{fim}"]
    from codar.engine.emit import EmitError, emit
    from codar.engine.stage0 import Stage0

    primeiro, _, resto = acao.partition(" ")
    acao = f"{_VERBOS.get(fold(primeiro), primeiro)} {resto}".strip()
    if atributos:  # "retorna o nome": o artigo esconderia o atributo do compilador
        acao = re.sub(r"\b(?:o|a|os|as|the|el|la|seu|sua)\s+(?=(?:" + "|".join(map(re.escape, atributos)) + r")\b)", "",
                      acao, flags=re.I)
    parsed = Stage0().parse(acao, atributos | set(params))
    if parsed is None:
        return None
    try:
        imports, corpo = emit(parsed.nodes, lang)
    except EmitError:
        return None
    if imports:
        return None  # um método não deveria depender de um import novo inventado pela frase
    return _qualificar(corpo, atributos, prefixo).split("\n")


# ------------------------------------------------------------------------------------------ objeto e chamada
def _objeto(texto: str, lang: str, contexto: str, raiz, atual):
    m = _P_OBJETO.match(fold_keep_len(texto))
    if not m:
        return None
    var, cls = _span(texto, m, "var"), _span(texto, m, "cls")
    cls = cls[:1].upper() + cls[1:] if cls[:1].islower() and _classe(cls, lang, contexto, raiz, atual) is None else cls
    args = _argumentos(_span(texto, m, "args"))
    classe = _classe(cls, lang, contexto, raiz, atual)
    notas = []
    nomes = [k for k, _ in args if k]
    if classe is not None and not classe.variadico and classe.params:
        conhecidos = [p[0] for p in classe.params]
        desconhecidos = [k for k in nomes if k not in conhecidos]
        if desconhecidos:
            raise ValueError(f"{cls} não tem o(s) parâmetro(s) {', '.join(desconhecidos)}; o construtor recebe: "
                             f"{', '.join(conhecidos)}")
        posicionais = [v for k, v in args if not k]
        preenchidos = set(conhecidos[:len(posicionais)]) | set(nomes)
        faltando = [p[0] for p in classe.params if not p[1] and p[0] not in preenchidos]
        if faltando:
            raise ValueError(f"faltam argumentos obrigatórios para {cls}: {', '.join(faltando)}")
    elif classe is None:
        notas.append(f"{cls} não foi encontrada no arquivo nem no projeto: confira o nome e os argumentos do construtor")
    if lang == "python":
        lista = [E.render(v, lang) for k, v in args if not k] + [f"{k}={E.render(v, lang)}" for k, v in args if k]
        return f"{var} = {cls}({', '.join(lista)})", [], notas
    if nomes and classe is not None and classe.params:  # JS não tem argumentos nomeados: ordem do construtor
        valores = dict((k, v) for k, v in args if k)
        posicionais = [v for k, v in args if not k]
        ordem = [p[0] for p in classe.params]
        lista, sobra = [], list(posicionais)
        for p in ordem:
            if p in valores:
                lista.append(E.render(valores[p], lang))
            elif sobra:
                lista.append(E.render(sobra.pop(0), lang))
            else:
                lista.append("undefined")
        while lista and lista[-1] == "undefined":
            lista.pop()
    else:
        lista = [E.render(v, lang) for _, v in args]
        if nomes:
            notas.append("JavaScript não tem argumentos nomeados: os valores seguem a ordem do pedido")
    declaracao = "" if re.search(rf"\b(?:const|let|var)\s+{re.escape(var)}\b", contexto) else "const "
    return f"{declaracao}{var} = new {cls}({', '.join(lista)});", [], notas


def _classe_do_objeto(obj: str, lang: str, contexto: str) -> str | None:
    padrao = rf"\b{re.escape(obj)}\s*(?::\s*[\w<>]+\s*)?=\s*(?:new\s+)?([A-Z][\w$]*)\s*\("
    achado = re.findall(padrao, contexto)
    return achado[-1] if achado else None


def _chamada(texto: str, lang: str, contexto: str, raiz, atual):
    m = _P_CHAMADA.match(fold_keep_len(texto))
    if not m:
        return None
    met, obj, dest = _span(texto, m, "met"), _span(texto, m, "obj"), _span(texto, m, "dest")
    args = _argumentos(_span(texto, m, "args"))
    if any(k for k, _ in args) and lang != "python":
        raise ValueError("JavaScript não tem argumentos nomeados: passe os valores na ordem dos parâmetros")
    notas = []
    nome_classe = _classe_do_objeto(obj, lang, contexto)
    if nome_classe and (classe := _classe(nome_classe, lang, contexto, raiz, atual)) is not None:
        metodos = _metodos_com_herdados(classe, lang, contexto, raiz, atual)
        if metodos and met not in metodos:
            publicos = sorted(x for x in metodos if not x.startswith("_") and x != "constructor")
            raise ValueError(f"{nome_classe} não tem o método {met}; métodos disponíveis: {', '.join(publicos) or 'nenhum'}")
    elif not re.search(rf"\b{re.escape(obj)}\b", contexto):
        notas.append(f"{obj} não aparece no arquivo: crie o objeto antes de chamar o método")
    lista = ", ".join((f"{k}={E.render(v, lang)}" if k else E.render(v, lang)) for k, v in args)
    chamada = f"{obj}.{met}({lista})"
    if lang == "python":
        return (f"{dest} = {chamada}" if dest else chamada), [], notas
    if dest:
        declaracao = "" if re.search(rf"\b(?:const|let|var)\s+{re.escape(dest)}\b", contexto) else "const "
        return f"{declaracao}{dest} = {chamada};", [], notas
    return f"{chamada};", [], notas


def compilar(intent: str, lang: str, antes: str, depois: str, recuo: str, raiz=None, atual: str | None = None
             ) -> tuple[str, list[str], str, list[str]] | None:
    """(corpo, imports, construção, notas) de um pedido de POO, ou None quando ele não é desta parte.

    Lança ValueError com a explicação quando o pedido usa algo que o código não tem.
    """
    if lang not in LINGUAGENS:
        return None
    texto = re.sub(r"\s+", " ", intent.strip().strip(".")).strip()
    texto = re.sub(r"^(?:#|//)\s*", "", texto)
    if len(texto) > 400:
        return None
    contexto = antes + "\n" + depois
    for construcao, regra in (("metodo", lambda: _metodo(texto, lang, contexto, antes, recuo, raiz, atual)),
                              ("classe", lambda: _classe_nova(texto, lang, contexto, raiz, atual)),
                              ("objeto", lambda: _objeto(texto, lang, contexto, raiz, atual)),
                              ("chamada", lambda: _chamada(texto, lang, contexto, raiz, atual))):
        feito = regra()
        if feito is not None:
            corpo, imports, notas = feito
            return corpo, imports, construcao, notas
    return None
