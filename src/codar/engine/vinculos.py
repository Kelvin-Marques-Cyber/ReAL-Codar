"""Vínculos entre arquivos: o código gerado usa funções e classes do projeto com o import certo.

Quando o resultado chama `somar(2, 3)` ou cria `Conta(100)` e esses nomes não existem no arquivo atual, o projeto é
consultado: uma única definição em outro arquivo vira o import (`from calculos import somar`, `import { somar } from
"./calculos.js"`). Nomes com mais de uma origem, funções JS não exportadas ou módulos com nomes inválidos ficam como
nota, sem adivinhar. A análise é estática (ast e expressões regulares com máscara de strings); nada é importado
nem executado, e os arquivos lidos ficam em cache pela data de modificação.
"""

from __future__ import annotations

import ast
import builtins
import keyword
import re
import textwrap
from pathlib import Path

from codar.audit.lexer import mask

_LIMITE_ARQUIVO = 400_000
_MAX_ARQUIVOS = 2000
_cache_arquivos: dict[Path, tuple[float, int, object]] = {}

_JS_LANGS = ("javascript", "typescript")
_JS_EXTS = (".js", ".mjs", ".cjs", ".jsx", ".ts", ".mts", ".cts", ".tsx")
_JS_GLOBAIS = frozenset("""console Math JSON Promise Object Array String Number Boolean Date Error TypeError RangeError
Map Set WeakMap WeakSet Symbol BigInt RegExp Intl Reflect Proxy parseInt parseFloat isNaN isFinite setTimeout
clearTimeout setInterval clearInterval queueMicrotask structuredClone fetch require module exports process Buffer
globalThis window document navigator alert prompt confirm URL URLSearchParams TextEncoder TextDecoder AbortController
encodeURIComponent decodeURIComponent encodeURI decodeURI super this import new typeof await async function return
if for while switch catch""".split())


def _arquivos(raiz: Path, extensoes: tuple[str, ...]) -> list[Path]:
    """Arquivos do projeto (regras do Git e exclusões do projeto). A lista é refeita a cada pedido, para enxergar um
    arquivo recém-criado; a análise de cada arquivo é que fica em cache pela data de modificação."""
    from codar.project import Project, is_secret

    projeto = Project.load(raiz)
    arquivos = []
    for relativo in projeto.files():
        if not relativo.endswith(extensoes) or is_secret(relativo) or not projeto.allowed(relativo):
            continue
        arquivo = raiz / relativo
        if arquivo.is_symlink() or not arquivo.resolve().is_relative_to(raiz):
            continue
        arquivos.append(arquivo)
        if len(arquivos) >= _MAX_ARQUIVOS:
            break
    return arquivos


def _analisado(arquivo: Path, analisar):
    try:
        estado = arquivo.stat()
    except OSError:
        return None
    guardado = _cache_arquivos.get(arquivo)
    if guardado and guardado[:2] == (estado.st_mtime, estado.st_size):
        return guardado[2]
    if estado.st_size > _LIMITE_ARQUIVO:
        valor = None
    else:
        try:
            valor = analisar(arquivo.read_text(encoding="utf-8", errors="replace"))
        except (OSError, ValueError, RecursionError):
            valor = None
    _cache_arquivos[arquivo] = (estado.st_mtime, estado.st_size, valor)
    return valor


# ------------------------------------------------------------------------------------------------ Python
def _python_livres(codigo: str) -> list[str]:
    """Nomes lidos no código e não definidos nele, na ordem em que aparecem."""
    try:
        arvore = ast.parse(textwrap.dedent(codigo))
    except (SyntaxError, ValueError, RecursionError):
        return []
    definidos, lidos = set(), []
    for no in ast.walk(arvore):
        if isinstance(no, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            definidos.add(no.name)
        elif isinstance(no, ast.arg):
            definidos.add(no.arg)
        elif isinstance(no, (ast.Import, ast.ImportFrom)):
            definidos.update((a.asname or a.name).split(".")[0] for a in no.names)
        elif isinstance(no, ast.Name):
            (definidos.add(no.id) if isinstance(no.ctx, (ast.Store, ast.Del)) else lidos.append((no.lineno, no.col_offset, no.id)))
        elif isinstance(no, ast.ExceptHandler) and no.name:
            definidos.add(no.name)
    vistos = []
    for *_, nome in sorted(lidos):
        if nome not in definidos and nome not in vistos and not hasattr(builtins, nome):
            vistos.append(nome)
    return vistos


def _python_topo(texto: str) -> set[str]:
    try:
        arvore = ast.parse(texto)
    except (SyntaxError, ValueError, RecursionError):
        return set()
    nomes = set()
    for no in arvore.body:
        if isinstance(no, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            nomes.add(no.name)
        elif isinstance(no, ast.Assign):
            nomes.update(t.id for t in no.targets if isinstance(t, ast.Name) and t.id.isupper())
    return nomes


def _definidos_no_contexto(texto: str) -> set[str]:
    """Nomes que o próprio arquivo já define ou importa (o contexto pode ser um trecho que não compila)."""
    nomes = set(re.findall(r"^\s*(?:async\s+)?(?:def|class)\s+(\w+)", texto, re.M))
    nomes.update(re.findall(r"^\s*(\w+)\s*(?::[^=\n]+)?=(?!=)", texto, re.M))
    for linha in re.findall(r"^\s*(?:from\s+[\w.]+\s+)?import\s+([^\n#]+)", texto, re.M):
        for parte in linha.strip("() ").split(","):
            parte = parte.strip()
            if parte:
                nomes.add((parte.split(" as ")[-1].strip()).split(".")[0])
    return nomes


def _python(codigo, raiz, atual, contexto):
    from codar.libraries import _module_for, _relative_module

    # Um nome que já aparece no arquivo (parâmetro, variável, import) é de lá: nunca vira import de outro arquivo.
    conhecidos = _definidos_no_contexto(contexto) | set(re.findall(r"[A-Za-z_]\w*", contexto))
    livres = [n for n in _python_livres(codigo) if n not in conhecidos]
    if not livres:
        return [], []
    atual_path = Path(atual).resolve() if atual else None
    if atual_path and atual_path.is_file():
        definidos_atual = _analisado(atual_path, _python_topo) or set()
        livres = [n for n in livres if n not in definidos_atual]
    if not livres:
        return [], []
    origens: dict[str, list[Path]] = {}
    for arquivo in _arquivos(raiz, (".py",)):
        if atual_path and arquivo.resolve() == atual_path:
            continue
        nomes = _analisado(arquivo, _python_topo) or set()
        for nome in livres:
            if nome in nomes:
                origens.setdefault(nome, []).append(arquivo)
    por_modulo: dict[str, list[str]] = {}
    notas = []
    for nome in livres:
        arquivos = origens.get(nome, [])
        if len(arquivos) > 1:
            notas.append(f"{nome} existe em {', '.join(a.relative_to(raiz).as_posix() for a in arquivos[:4])}; "
                         "importe a origem desejada")
            continue
        if not arquivos:
            continue
        try:
            modulo = _relative_module(_module_for(arquivos[0], raiz), atual, raiz)
        except ValueError:
            notas.append(f"{nome} está em {arquivos[0].relative_to(raiz).as_posix()}, mas o caminho não é um módulo Python")
            continue
        por_modulo.setdefault(modulo, []).append(nome)
    imports = [f"from {modulo} import {', '.join(nomes)}" for modulo, nomes in por_modulo.items()]
    if imports:
        notas.append("importado do projeto: " + "; ".join(imports))
    return imports, notas


# ------------------------------------------------------------------------------------- JavaScript/TypeScript
_JS_EXPORT = re.compile(r"^\s*export\s+(?:default\s+)?(?:async\s+)?(?:function\*?|class|const|let|var)\s+([A-Za-z_$][\w$]*)", re.M)
_JS_EXPORT_LISTA = re.compile(r"^\s*export\s*\{([^}]*)\}", re.M)
_JS_DEFAULT = re.compile(r"^\s*export\s+default\s+(?:async\s+)?(?:function\*?|class)\s+([A-Za-z_$][\w$]*)", re.M)
_JS_CJS = re.compile(r"\bmodule\.exports\s*=\s*\{([^}]*)\}|\b(?:module\.)?exports\.([A-Za-z_$][\w$]*)\s*=")
_JS_DECL = re.compile(r"^\s*(?:export\s+)?(?:default\s+)?(?:async\s+)?(?:function\*?|class)\s+([A-Za-z_$][\w$]*)|"
                      r"^\s*(?:export\s+)?(?:const|let|var)\s+([A-Za-z_$][\w$]*)", re.M)


def _js_exportados(texto: str) -> dict:
    texto = mask(texto, "javascript", strings=True)
    nomeados = set(_JS_EXPORT.findall(texto))
    for lista in _JS_EXPORT_LISTA.findall(texto):
        nomeados.update(p.split(" as ")[-1].strip() for p in lista.split(",") if p.strip())
    cjs = set()
    for objeto, propriedade in _JS_CJS.findall(texto):
        if propriedade:
            cjs.add(propriedade)
        for parte in objeto.split(","):
            parte = parte.split(":")[0].strip()
            if re.fullmatch(r"[A-Za-z_$][\w$]*", parte):
                cjs.add(parte)
    padrao = set(_JS_DEFAULT.findall(texto))
    declarados = {a or b for a, b in _JS_DECL.findall(texto)}
    return {"nomeados": nomeados - padrao, "padrao": padrao, "cjs": cjs, "declarados": declarados}


def _js_livres(codigo: str) -> list[str]:
    texto = mask(codigo, "javascript", strings=True)
    definidos = {a or b for a, b in _JS_DECL.findall(texto)}
    for grupo in re.findall(r"\b(?:const|let|var)\s*\{([^}]*)\}", texto):
        definidos.update(p.split(":")[-1].strip() for p in grupo.split(",") if p.strip())
    definidos.update(re.findall(r"\b(?:const|let|var)\s+([A-Za-z_$][\w$]*)", texto))
    for lista in re.findall(r"\(([^()]*)\)\s*(?:=>|\{)", texto):
        definidos.update(re.findall(r"[A-Za-z_$][\w$]*", lista))
    usados = re.findall(r"(?<![\w$.])(?:new\s+)?([A-Za-z_$][\w$]*)\s*\(", texto)
    usados += re.findall(r"\bnew\s+([A-Za-z_$][\w$]*)", texto)
    vistos = []
    for nome in usados:
        if nome not in definidos and nome not in _JS_GLOBAIS and nome not in vistos and not keyword.iskeyword(nome):
            vistos.append(nome)
    return vistos


def _js_estilo(contexto: str, raiz: Path, lang: str, atual: str | None) -> str:
    """esm ou cjs, pelo que o arquivo já usa; depois pelo package.json; TypeScript usa import."""
    if re.search(r"^\s*import\s.+\sfrom\s|^\s*export\s", contexto, re.M):
        return "esm"
    if re.search(r"\brequire\(\s*['\"]", contexto):
        return "cjs"
    if lang == "typescript" or (atual and atual.endswith((".mjs", ".mts"))):
        return "esm"
    try:
        import json

        tipo = json.loads((raiz / "package.json").read_text(encoding="utf-8")).get("type")
    except (OSError, ValueError, AttributeError):
        tipo = None
    return "esm" if tipo == "module" else "cjs"


def _js_caminho(arquivo: Path, atual: str | None, raiz: Path, lang: str, contexto: str) -> str:
    import os

    base = Path(atual).resolve().parent if atual else raiz
    relativo = Path(os.path.relpath(arquivo, base)).as_posix()
    if not relativo.startswith("."):
        relativo = "./" + relativo
    sem_extensao = relativo.rsplit(".", 1)[0]
    # Segue a convenção dos imports relativos que o arquivo já tem; sem exemplo, TypeScript omite a extensão.
    exemplos = re.findall(r"""from\s+['"](\.{1,2}/[^'"]+)['"]|require\(\s*['"](\.{1,2}/[^'"]+)['"]""", contexto)
    caminhos = [a or b for a, b in exemplos]
    if caminhos:
        return relativo if any(re.search(r"\.[cm]?[jt]sx?$", c) for c in caminhos) else sem_extensao
    if lang == "typescript" or arquivo.suffix in (".ts", ".tsx", ".mts", ".cts"):
        return sem_extensao
    return relativo


def _javascript(codigo, raiz, atual, contexto, lang):
    conhecidos = _js_livres_contexto(contexto) | set(re.findall(r"[A-Za-z_$][\w$]*", contexto))
    livres = [n for n in _js_livres(codigo) if n not in conhecidos]
    if not livres:
        return [], []
    atual_path = Path(atual).resolve() if atual else None
    origens: dict[str, list[tuple[Path, str]]] = {}
    nao_exportados: dict[str, Path] = {}
    for arquivo in _arquivos(raiz, _JS_EXTS):
        if atual_path and arquivo.resolve() == atual_path or arquivo.name.endswith((".d.ts", ".min.js")):
            continue
        info = _analisado(arquivo, _js_exportados)
        if not info:
            continue
        for nome in livres:
            if nome in info["nomeados"]:
                origens.setdefault(nome, []).append((arquivo, "nomeado"))
            elif nome in info["padrao"]:
                origens.setdefault(nome, []).append((arquivo, "padrao"))
            elif nome in info["cjs"]:
                origens.setdefault(nome, []).append((arquivo, "cjs"))
            elif nome in info["declarados"]:
                nao_exportados.setdefault(nome, arquivo)
    estilo = _js_estilo(contexto, raiz, lang, atual)
    imports, notas = [], []
    agrupados: dict[str, list[str]] = {}
    for nome in livres:
        encontrados = origens.get(nome, [])
        if len(encontrados) > 1:
            notas.append(f"{nome} é exportado por {', '.join(a.relative_to(raiz).as_posix() for a, _ in encontrados[:4])}; "
                         "importe a origem desejada")
            continue
        if not encontrados:
            if nome in nao_exportados:
                notas.append(f"{nome} existe em {nao_exportados[nome].relative_to(raiz).as_posix()}, mas não é "
                             "exportado; acrescente export para usá-lo aqui")
            continue
        arquivo, tipo = encontrados[0]
        caminho = _js_caminho(arquivo, atual, raiz, lang, contexto)
        if tipo == "padrao":
            imports.append(f'const {nome} = require("{caminho}");' if estilo == "cjs" else f'import {nome} from "{caminho}";')
        else:
            agrupados.setdefault(caminho, []).append(nome)
    for caminho, nomes in agrupados.items():
        lista = ", ".join(nomes)
        imports.append(f'const {{ {lista} }} = require("{caminho}");' if estilo == "cjs" else
                       f'import {{ {lista} }} from "{caminho}";')
    if imports:
        notas.append("importado do projeto: " + " ".join(imports))
    return imports, notas


def _js_livres_contexto(contexto: str) -> set[str]:
    texto = mask(contexto, "javascript", strings=True)
    nomes = {a or b for a, b in _JS_DECL.findall(texto)}
    for grupo in re.findall(r"\bimport\s+(?:([A-Za-z_$][\w$]*)\s*,?\s*)?(?:\{([^}]*)\})?\s*from", texto):
        if grupo[0]:
            nomes.add(grupo[0])
        nomes.update(p.split(" as ")[-1].strip() for p in grupo[1].split(",") if p.strip())
    for grupo in re.findall(r"\b(?:const|let|var)\s*\{([^}]*)\}\s*=\s*require", texto):
        nomes.update(p.split(":")[-1].strip() for p in grupo.split(",") if p.strip())
    nomes.update(re.findall(r"\b(?:const|let|var)\s+([A-Za-z_$][\w$]*)\s*=\s*require", texto))
    return nomes


def imports_do_projeto(codigo: str, lang: str, raiz: Path | None, atual: str | None, contexto: str
                       ) -> tuple[list[str], list[str]]:
    """(imports a acrescentar, notas) para nomes do código definidos em outros arquivos do projeto."""
    if raiz is None or not codigo.strip():
        return [], []
    raiz = Path(raiz).resolve()
    if lang == "python":
        return _python(codigo, raiz, atual, contexto)
    if lang in _JS_LANGS:
        return _javascript(codigo, raiz, atual, contexto, lang)
    return [], []
