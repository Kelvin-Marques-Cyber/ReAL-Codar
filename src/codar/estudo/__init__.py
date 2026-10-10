"""Modo estudo: o material de estudo acompanha o que você programa e comenta.

- conceitos_da_linha: os conceitos da linha do cursor (no código ou nas palavras de um comentário);
- exemplo: o exemplo do conceito na linguagem do arquivo (compilado do pseudocódigo quando dá);
- trilha_poo: o que da trilha de orientação a objetos o arquivo já usa e o próximo passo, com os nomes do seu código;
- sugestao_main: quando o arquivo só define classes, sugere um main.py comentado que as usa (você decide criar);
- pelo_comentario: "# classe Pessoa com nome e idade" vira um exemplo com esses nomes.

O objetivo é ensinar, não fazer por você: o painel mostra o caminho e você escreve o código.
"""

from __future__ import annotations

import ast
import builtins
import functools
import re
from dataclasses import dataclass, field
from pathlib import Path

from codar.estudo.conteudo import CONCEITOS, POR_ID, TRILHA_POO, TRILHAS, Conceito

__all__ = ["CONCEITOS", "POR_ID", "TRILHA_POO", "TRILHAS", "Conceito", "EstadoPoo", "Sugestao", "conceitos_da_linha",
           "exemplo", "pelo_comentario", "sugestao_main", "trilha_poo"]

from codar.estudo.ampliado import EXEMPLOS_R, FONTES

_GRUPO = {**{lang: lang for lang in FONTES}, "python": "py", "javascript": "js", "typescript": "js"}
# a linha "class Poupanca(Conta):" é herança antes de ser classe; "conta = Conta()" é objeto antes de variável
_PRIORIDADE = ["treino_teste", "agrupamento", "grafico", "imagem_matriz", "numpy_array", "dataframe",
               "heranca", "super", "polimorfismo", "composicao", "encapsulamento", "str", "construtor", "metodo",
               "atributo", "objeto", "classe", "componente", "async", "array_metodos", "arrow", "tipos_ts", "main",
               "compreensao", "excecao", "arquivo", "fstring", "conversao", "input", "dicionario", "lista", "for",
               "while", "if", "funcao", "import", "texto", "let_const", "print", "variavel", "indentacao"]
_COMENTARIO = ("#", "//", "--", "/*", "*", "<!--")
_EXCECOES = {n for n in dir(builtins) if n[:1].isupper()}


def grupo(lang: str | None) -> str:
    return _GRUPO.get(lang or "", "*")


def _ordem(c: Conceito) -> int:
    if c.id.startswith('guia_'):
        return 1000
    if c.fontes:
        return -1
    return _PRIORIDADE.index(c.id) if c.id in _PRIORIDADE else len(_PRIORIDADE)


def conceitos_da_linha(linha: str, lang: str | None) -> list[Conceito]:
    """Conceitos que a linha usa (o mais específico primeiro). Num comentário, pelas palavras: "# laço para cada
    aluno" -> repetição com for."""
    texto = linha.strip()
    if not texto:
        return []
    if texto.startswith(_COMENTARIO):
        baixo = texto.lower()  # palavra (ou começo de palavra): "se " não casa dentro de "classe com"
        achados = [c for c in CONCEITOS if any(re.search(r"(?<!\w)" + re.escape(p), baixo) for p in c.palavras)
                   and exemplo(c, lang)[0]]
    else:
        g = grupo(lang)
        achados = []
        for c in CONCEITOS:
            padroes = c.linha.get(lang or '', ()) + c.linha.get(g, ())
            if g not in ('py', 'js'):
                padroes += c.linha.get('*', ())
            if any(re.search(p, linha, re.I if lang in ('sql', 'powershell', 'dockerfile') else 0) for p in padroes) \
                    and exemplo(c, lang)[0]:
                achados.append(c)
    if not achados and lang and 'guia_' + lang in POR_ID:
        achados = [POR_ID['guia_' + lang]]
    return sorted(achados, key=_ordem)


@functools.lru_cache(maxsize=256)
def _compilar(pseudo: str, lang: str) -> str | None:
    from codar.engine.emit import EmitError, emit
    from codar.engine.postprocess import join_imports
    from codar.engine.stage0 import Stage0

    try:
        nodes, misses = Stage0().parse_program(pseudo, set())
        if misses:
            return None
        imports, corpo = emit(nodes, lang)
    except (EmitError, ValueError, KeyError, TypeError):
        return None
    codigo = join_imports(imports, corpo.strip("\n"), lang)
    return None if "TODO" in codigo else codigo


def exemplo(c: Conceito, lang: str | None) -> tuple[str, str]:
    """(código, linguagem do código): o escrito à mão para a linguagem; senão o pseudocódigo compilado para ela;
    senão o de Python."""
    g = grupo(lang)
    if lang == 'r' and c.id in EXEMPLOS_R:
        return EXEMPLOS_R[c.id], lang
    if lang in c.exemplos:
        return c.exemplos[lang], lang
    if g in c.exemplos:
        return c.exemplos[g], lang or "python"
    if c.pseudo and lang and (codigo := _compilar(c.pseudo, lang)):
        return codigo, lang
    if lang and lang != 'python':
        return '', lang
    if "py" in c.exemplos:
        return c.exemplos["py"], "python"
    if c.pseudo and (codigo := _compilar(c.pseudo, "python")):
        return codigo, "python"
    return "", lang or "python"


def catalogo(lang: str | None):
    """Apenas tópicos com exemplo nativo ou compilável para a linguagem solicitada."""
    return [c for c in CONCEITOS if exemplo(c, lang)[0]]


def explicacao(c, lang):
    if not lang or lang == 'python' or c.fontes or c.trilha not in ('fundamentos', 'poo'):
        return c.texto
    generic = {
        'variavel': 'Uma variável dá um nome a um valor para usar e, quando permitido, alterar depois. Confira declaração, tipo e mutabilidade no exemplo.',
        'print': 'Mostrar valores ajuda a acompanhar a execução e conferir o estado do programa. Use a operação de saída própria da linguagem.',
        'input': 'Uma entrada vem do usuário ou de outra fonte. Trate ausência, texto inválido e conversão antes de fazer contas.',
        'conversao': 'Converter muda a representação do valor. A conversão pode falhar; confira os formatos aceitos e valide antes de usar o resultado.',
        'fstring': 'Interpolação e formatação montam texto com valores. Use o mecanismo da linguagem e defina formatos quando precisão e apresentação importam.',
        'texto': 'Strings representam texto. Confira índices, codificação e se uma operação muda o valor ou devolve um novo.',
        'if': 'Uma condição escolhe o bloco que será executado. Compare valores, trate os demais casos e confira os limites da condição.',
        'for': 'Uma repetição percorre uma sequência ou intervalo. Observe o primeiro e o último valor, a ordem e os índices da linguagem.',
        'while': 'O bloco repete enquanto a condição permitir. Alguma operação deve aproximar o laço do fim para evitar repetição infinita.',
        'lista': 'Uma coleção ordenada guarda vários valores. Confira índices, tipo dos elementos e operações para adicionar e percorrer.',
        'dicionario': 'Um mapa associa chaves a valores. Trate chaves ausentes e confira como a linguagem devolve ou sinaliza ausência.',
        'funcao': 'Uma função recebe parâmetros, executa uma tarefa e pode devolver um resultado. Defina o contrato e teste entradas normais e limites.',
        'import': 'Módulos organizam código reutilizável. Importar código e instalar uma dependência são passos diferentes.',
        'excecao': 'Trate uma falha no ponto em que você consegue decidir o que fazer. Algumas linguagens usam exceções; outras devolvem valores de erro.',
        'arquivo': 'Abrir, ler e escrever arquivos exige tratar caminhos, codificação, permissões e fechamento dos recursos.',
        'indentacao': 'A organização visual ajuda a entender os blocos. Confira se a linguagem usa indentação, delimitadores ou palavras para marcar o bloco.',
        'main': 'O ponto de entrada inicia a execução. Separar definição e uso permite testar e reutilizar seu código.',
        'classe': 'Uma classe descreve estado e comportamento de objetos. Algumas linguagens usam estruturas, métodos ou composição no lugar de classes tradicionais.',
    }
    return generic.get(c.id, c.texto)


def fontes(c, lang):
    return c.fontes or ((FONTES[lang],) if lang in FONTES else ())


# ------------------------------------------------------------------------------------------- trilha de POO
@dataclass
class EstadoPoo:
    feitos: dict[str, bool]
    classe: str | None = None
    attrs: list[str] = field(default_factory=list)
    params: list[str] = field(default_factory=list)  # do construtor, sem self
    metodos: list[str] = field(default_factory=list)
    exportada: bool = True  # JavaScript: a classe tem export?

    @property
    def proximo(self) -> str | None:
        return next((k for k in TRILHA_POO if not self.feitos.get(k)), None)

    def passo(self, lang: str | None) -> str:
        """O próximo passo da trilha, escrito com os nomes do seu código."""
        C = self.classe or "Produto"
        a = (self.attrs or self.params or ["nome"])[0].lstrip("_#")
        p = (self.params or ["nome"])[0]
        m = (self.metodos or ["descrever"])[0]
        args = ", ".join(_valor(x) for x in self.params) or ""
        js = grupo(lang) == "js"
        if js:
            textos = {
                "classe": "Crie uma classe para algo do seu programa: class Produto { } (nome com maiúscula).",
                "construtor": f"Dê um construtor a {C}: constructor({p}) {{ ... }}: ele roda quando o objeto nasce.",
                "atributo": f"No constructor de {C}, guarde os dados no objeto: this.{p} = {p};",
                "metodo": f"Crie um método em {C} que use os atributos: descrever() {{ return `${{this.{a}}}`; }}",
                "objeto": f"Crie um objeto e use: const x = new {C}({args}); de preferência em outro arquivo (main.js).",
                "str": f"Ensine {C} a virar texto: toString() {{ return `{C}(${{this.{a}}})`; }}",
                "encapsulamento": f"Proteja um dado: troque this.{a} por this.#{a} e crie get {a}() {{ return this.#{a}; }}",
                "heranca": f"Crie uma classe filha: class {C}Especial extends {C} {{ }}: ela herda tudo de {C}.",
                "super": "No constructor da filha, chame super(...) antes de usar this.",
                "polimorfismo": f"Na filha, redefina {m}() com outro comportamento e chame nos dois tipos de objeto.",
                "composicao": f"Dê a {C} um atributo que seja outro objeto: this.endereco = new Endereco(...);",
            }
        else:
            textos = {
                "classe": "Crie uma classe para algo do seu programa: class Produto: (nome com maiúscula).",
                "construtor": f"Dê um construtor a {C}: def __init__(self, {p}): ele roda quando o objeto nasce.",
                "atributo": f"No __init__ de {C}, guarde os dados no objeto: self.{p} = {p}",
                "metodo": f"Crie um método em {C} que use os atributos: def descrever(self): "
                          f"return f\"{{self.{a}}}\"",
                "objeto": f"Crie um objeto e use: x = {C}({args}). Melhor ainda num main.py (veja a sugestão).",
                "str": f"Ensine {C} a aparecer no print: def __str__(self): return f\"{C}({{self.{a}}})\"",
                "encapsulamento": f"Proteja um dado: troque self.{a} por self._{a} e crie @property def {a}(self).",
                "heranca": f"Crie uma classe filha: class {C}Especial({C}): ela herda tudo de {C}.",
                "super": "No __init__ da filha, chame super().__init__(...) para a mãe preparar os atributos dela.",
                "polimorfismo": f"Na filha, redefina {m}() com outro comportamento e chame nos dois tipos de objeto.",
                "composicao": f"Dê a {C} um atributo que seja outro objeto: self.endereco = Endereco(...)",
            }
        prox = self.proximo
        return textos.get(prox, "Trilha completa: você já usa os pilares da orientação a objetos.") if prox else \
            "Trilha completa: você já usa os pilares da orientação a objetos."


def trilha_poo(codigo: str, lang: str | None, uso_externo: bool = False) -> EstadoPoo | None:
    """O que da trilha de POO o código já usa. None se não der para analisar (linguagem sem trilha, ou o código está
    no meio da digitação e não compila: o painel mantém o último estado)."""
    g = grupo(lang)
    if g == "py":
        try:
            estado = _poo_python(ast.parse(codigo))
        except (SyntaxError, ValueError):
            return None
    elif g == "js":
        estado = _poo_js(codigo)
    else:
        return None
    if uso_externo:
        estado.feitos["objeto"] = True
    return estado


def _poo_python(arvore: ast.AST) -> EstadoPoo:
    feitos = {k: False for k in TRILHA_POO}
    classes = [n for n in ast.walk(arvore) if isinstance(n, ast.ClassDef)]
    estado = EstadoPoo(feitos)
    metodos_de: dict[str, set[str]] = {}
    bases_de: dict[str, list[str]] = {}
    for c in classes:
        feitos["classe"] = True
        bases = [b.id for b in c.bases if isinstance(b, ast.Name) and b.id != "object"]
        bases_de[c.name] = bases
        feitos["heranca"] |= bool(bases)
        metodos_de[c.name] = set()
        for item in c.body:
            if not isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            metodos_de[c.name].add(item.name)
            args = [a.arg for a in item.args.args]
            if item.name == "__init__":
                feitos["construtor"] = True
                if estado.classe in (None, c.name):
                    n_padrao = len(item.args.defaults)
                    obrigatorios = args[1:len(args) - n_padrao] if n_padrao else args[1:]
                    estado.params = obrigatorios
            elif item.name in ("__str__", "__repr__"):
                feitos["str"] = True
            elif not item.name.startswith("__") and args[:1] == ["self"]:
                feitos["metodo"] = True
                if estado.classe in (None, c.name):
                    estado.metodos.append(item.name)
            if any(isinstance(d, ast.Name) and d.id == "property" or isinstance(d, ast.Attribute) and d.attr == "setter"
                   for d in item.decorator_list):
                feitos["encapsulamento"] = True
        for n in ast.walk(c):
            if isinstance(n, ast.Attribute) and isinstance(n.value, ast.Name) and n.value.id == "self" \
                    and isinstance(n.ctx, ast.Store):
                feitos["atributo"] = True
                feitos["encapsulamento"] |= n.attr.startswith("_") and not n.attr.startswith("__")
                if estado.classe in (None, c.name) and n.attr not in estado.attrs:
                    estado.attrs.append(n.attr)
            elif isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id == "super":
                feitos["super"] = True
            elif isinstance(n, ast.Assign) and isinstance(n.value, (ast.Call, ast.List)) and any(
                    isinstance(t, ast.Attribute) and isinstance(t.value, ast.Name) and t.value.id == "self"
                    for t in n.targets):
                chamada = n.value
                if isinstance(chamada, ast.Call) and isinstance(chamada.func, ast.Name) \
                        and chamada.func.id[:1].isupper() and chamada.func.id not in _EXCECOES:
                    feitos["composicao"] = True
        if estado.classe is None:
            estado.classe = c.name
    for nome, bases in bases_de.items():
        if any((metodos_de.get(nome, set()) & metodos_de.get(b, set())) - {"__init__"} for b in bases):
            feitos["polimorfismo"] = True
    nomes = set(metodos_de)
    dentro_de_classe = {id(n) for c in classes for n in ast.walk(c)}
    for n in ast.walk(arvore):
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and id(n) not in dentro_de_classe and \
                (n.func.id in nomes or (n.func.id[:1].isupper() and n.func.id not in _EXCECOES)):
            feitos["objeto"] = True
    return estado


_JS_CLASSE = re.compile(r"^\s*(export\s+(?:default\s+)?)?class\s+(\w+)(?:\s+extends\s+(\w+))?", re.M)


def _poo_js(codigo: str) -> EstadoPoo:
    feitos = {k: False for k in TRILHA_POO}
    estado = EstadoPoo(feitos)
    classes = list(_JS_CLASSE.finditer(codigo))
    metodos_de: dict[str, set[str]] = {}
    for i, m in enumerate(classes):
        exportada, nome, mae = m.group(1), m.group(2), m.group(3)
        corpo = codigo[m.end(): classes[i + 1].start() if i + 1 < len(classes) else len(codigo)]
        feitos["classe"] = True
        feitos["heranca"] |= bool(mae)
        metodos = {x for x in re.findall(r"^\s+(?:async\s+|static\s+)?(\w+)\s*\([^)]*\)\s*\{", corpo, re.M)
                   if x not in ("if", "for", "while", "switch", "catch", "function", "constructor")}
        metodos_de[nome] = metodos
        if cons := re.search(r"constructor\s*\(([^)]*)\)", corpo):
            feitos["construtor"] = True
            if estado.classe in (None, nome):
                estado.params = [p.split("=")[0].strip() for p in cons.group(1).split(",") if p.strip()
                                 and "=" not in p]
        attrs = re.findall(r"this\.(#?\w+)\s*=(?!=)", corpo)
        feitos["atributo"] |= bool(attrs)
        feitos["encapsulamento"] |= bool(re.search(r"this\.#\w+|^\s*#\w+|^\s*get\s+\w+\(", corpo, re.M))
        feitos["super"] |= bool(re.search(r"\bsuper\s*[(.]", corpo))
        feitos["str"] |= "toString" in metodos
        feitos["composicao"] |= bool(re.search(r"this\.\w+\s*=\s*new\s+[A-Z]", corpo))
        feitos["metodo"] |= bool(metodos - {"toString"})
        if estado.classe is None:
            estado.classe, estado.exportada = nome, bool(exportada)
            estado.attrs = list(dict.fromkeys(attrs))
            estado.metodos = sorted(metodos - {"toString"})
    for m in classes:
        if m.group(3) and metodos_de.get(m.group(2), set()) & metodos_de.get(m.group(3), set()):
            feitos["polimorfismo"] = True
    feitos["objeto"] = bool(re.search(r"\bnew\s+[A-Z]\w*\(", codigo))
    return estado


# ------------------------------------------------------------------------------------------- sugestões
@dataclass
class Sugestao:
    titulo: str
    motivo: str
    caminho: str  # relativo ao projeto
    conteudo: str


_VALORES = {"nome": '"Ana"', "titular": '"Ana"', "autor": '"Machado de Assis"', "titulo": '"Dom Casmurro"',
            "idade": "20", "ano": "2024", "saldo": "100.0", "valor": "100.0", "preco": "9.9", "quantidade": "1",
            "estoque": "10", "email": '"ana@exemplo.com"', "cidade": '"Recife"', "cor": '"azul"', "raio": "2.0",
            "lado": "3.0", "nota": "8.5", "salario": "3500.0", "descricao": '"…"', "tipo": '"comum"'}


def _valor(param: str) -> str:
    """Valor de exemplo para um parâmetro, pelo nome; "?" quando não dá para adivinhar (é para você trocar)."""
    nome = param.lower().strip("_")
    if nome in _VALORES:
        return _VALORES[nome]
    if nome.endswith(("nome", "texto", "titulo")):
        return '"exemplo"'
    if nome.startswith(("qtd", "quant", "num", "n_", "total")):
        return "1"
    return '"?"'


def sugestao_main(raiz: Path, arquivo: Path, codigo: str, lang: str | None) -> Sugestao | None:
    """Arquivo que só define classes e ninguém usa: sugere um main.py (main.js) comentado que cria e usa um objeto."""
    estado = trilha_poo(codigo, lang)
    if estado is None or not estado.classe or estado.feitos["objeto"]:
        return None
    g = grupo(lang)
    if arquivo.stem in ("main", "index", "app", "__main__"):
        return None
    try:
        rel = arquivo.resolve().relative_to(raiz.resolve())
    except ValueError:
        return None
    C, var = estado.classe, estado.classe.lower()
    args = ", ".join(_valor(p) for p in estado.params)
    if g == "py":
        destino = raiz / "main.py"
        modulo = ".".join(rel.with_suffix("").parts)
        if destino.exists() and (f"import {C}" in destino.read_text(encoding="utf-8", errors="ignore")
                                 or modulo in destino.read_text(encoding="utf-8", errors="ignore")):
            return None
        chamadas = "\n    ".join(f"{var}.{m}()  # confira os parâmetros de {m}" for m in estado.metodos[:2]) or \
            f"# {C} ainda não tem métodos: crie um (é o próximo passo da trilha) e chame aqui"
        conteudo = f'''"""Ponto de entrada do programa: aqui você USA o que {rel.as_posix()} define.

{rel.name} diz como uma {C} funciona; main.py conta a história do programa. Separar definição de uso deixa cada
arquivo com uma responsabilidade (e {rel.name} pode ser importado por outros arquivos sem rodar nada).
"""

from {modulo} import {C}


def main() -> None:
    # 1. crie um objeto: o Python chama o __init__ de {C} com estes valores (troque pelos seus)
    {var} = {C}({args})
    # 2. use o objeto: métodos e atributos com ponto
    {chamadas}
    # 3. mostre o estado (se {C} tiver __str__, o print usa ele)
    print({var})
    # sua vez: crie um segundo objeto e mostre que cada um tem os próprios atributos


if __name__ == "__main__":  # só roda quando este arquivo é executado (F5), não quando é importado
    main()
'''
        return Sugestao(f"criar main.py para usar {C}", f"{rel.as_posix()} define {C}, mas nada cria objetos dela.",
                        "main.py", conteudo)
    if g == "js":
        ext = ".ts" if arquivo.suffix in (".ts", ".tsx") else ".js"
        destino = raiz / f"main{ext}"
        if destino.exists():
            return None
        imp = "./" + rel.with_suffix(".js" if ext == ".js" else "").as_posix()
        aviso = "" if estado.exportada else f"// atenção: em {rel.name}, escreva export class {C} para poder importar\n"
        chamadas = "\n".join(f"{var}.{m}(); // confira os parâmetros de {m}" for m in estado.metodos[:2]) or \
            f"// {C} ainda não tem métodos: crie um (próximo passo da trilha) e chame aqui"
        conteudo = (f"// Ponto de entrada: aqui você USA a classe {C} definida em {rel.as_posix()}.\n{aviso}"
                    f"import {{ {C} }} from \"{imp}\";\n\n// 1. crie um objeto com new (chama o constructor)\n"
                    f"const {var} = new {C}({args});\n// 2. use os métodos\n{chamadas}\n// 3. mostre o estado\n"
                    f"console.log({var});\n")
        return Sugestao(f"criar main{ext} para usar {C}", f"{rel.as_posix()} define {C}, mas nada cria objetos dela.",
                        f"main{ext}", conteudo)
    return None


_COMENTARIO_CLASSE = re.compile(r"classe\s+(?:chamada\s+)?([A-Z]\w*)(?:\s+(?:com|que tem|tendo)\s+(.+))?", re.I)


def pelo_comentario(comentario: str, lang: str | None) -> tuple[str, str] | None:
    """"# classe Pessoa com nome e idade" -> (exemplo com esses nomes, linguagem). O exemplo é para estudar e
    digitar; não é inserido no arquivo."""
    m = _COMENTARIO_CLASSE.search(comentario)
    if not m:
        return None
    nome = m.group(1)
    attrs = [a for a in re.split(r"\s*(?:,|\be\b)\s*", re.sub(r"\b(?:atributos?|métodos?.*$)", "", m.group(2) or ""))
             if re.fullmatch(r"[a-zà-ú_]\w*", a.strip(), re.I)][:5] or ["nome"]
    attrs = [re.sub(r"\W", "_", a.strip().lower()) for a in attrs]
    g = grupo(lang)
    if g == "js":
        corpo = "\n".join(f"    this.{a} = {a};" for a in attrs)
        return f"class {nome} {{\n  constructor({', '.join(attrs)}) {{\n{corpo}\n  }}\n}}", "javascript"
    if g == "py" or lang is None:
        corpo = "\n".join(f"        self.{a} = {a}" for a in attrs)
        return f"class {nome}:\n    def __init__(self, {', '.join(attrs)}):\n{corpo}", "python"
    codigo = _compilar(f"criar uma classe {nome} com {' e '.join(attrs)}", lang)
    return (codigo, lang) if codigo else None
