"""Regras de auditoria para Python baseadas na AST (precisas e baratas: ~0,2 ms por snippet)."""

from __future__ import annotations

import ast
import re
from collections.abc import Iterator

Hit = tuple[str, str, str, str, int, str]  # id, severidade, categoria, mensagem, linha, sugestão

_SQL = re.compile(r"(?i)\b(select|insert|update|delete|replace|merge|create|drop|alter)\b")
_SECRET_NAME = re.compile(r"(?i)(pass(word|wd)?|pwd|senha|secret|segredo|token|api_?key|private_?key|client_?secret)")
_SQL_SINKS = {"execute", "executemany", "executescript", "read_sql", "read_sql_query", "raw", "text", "query", "exec_driver_sql"}
_HTTP = {"get", "post", "put", "patch", "delete", "head", "request", "options"}


def _name(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        base = _name(node.value)
        return f"{base}.{node.attr}" if base else node.attr
    if isinstance(node, ast.Call):
        return _name(node.func)
    return ""


def _is_dynamic_str(node: ast.AST) -> bool:
    """f-string, concatenação, % ou .format() envolvendo texto."""
    if isinstance(node, ast.JoinedStr):
        return any(isinstance(v, ast.FormattedValue) for v in node.values)
    if isinstance(node, ast.BinOp) and isinstance(node.op, (ast.Add, ast.Mod)):
        return any(isinstance(x, (ast.Constant, ast.JoinedStr, ast.BinOp)) for x in (node.left, node.right))
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "format":
        return True
    return False


def _str_value(node: ast.AST) -> str:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.JoinedStr):
        return "".join(v.value for v in node.values if isinstance(v, ast.Constant) and isinstance(v.value, str))
    if isinstance(node, ast.BinOp):
        return _str_value(node.left) + _str_value(node.right)
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
        return _str_value(node.func.value)
    return ""


class _Visitor(ast.NodeVisitor):
    def __init__(self) -> None:
        self.hits: list[Hit] = []
        self.loop_depth = 0
        self.async_depth = 0
        self.with_items: set[int] = set()
        self.str_vars: set[str] = set()

    def add(self, rid, sev, cat, msg, node, sug=""):
        self.hits.append((rid, sev, cat, msg, getattr(node, "lineno", 1), sug))

    # -------------------------------------------------------------- estruturas
    def visit_For(self, node):
        self.loop_depth += 1
        if isinstance(node.iter, ast.Call) and _name(node.iter.func) == "range" and node.iter.args \
                and isinstance(node.iter.args[0], ast.Call) and _name(node.iter.args[0].func) == "len":
            self.add("PY016", "info", "style", "range(len(x)) é pouco idiomático", node, "use enumerate(x)")
        self.generic_visit(node)
        self.loop_depth -= 1

    visit_AsyncFor = visit_For

    def visit_While(self, node):
        self.loop_depth += 1
        self.generic_visit(node)
        self.loop_depth -= 1

    def visit_AsyncFunctionDef(self, node):
        self.async_depth += 1
        self._defaults(node)
        self.generic_visit(node)
        self.async_depth -= 1

    def visit_FunctionDef(self, node):
        self._defaults(node)
        depth = self.async_depth
        self.async_depth = 0
        for dec in node.decorator_list:
            dname = _name(dec)
            if dname in ("functools.cache", "cache") or (isinstance(dec, ast.Call) and _name(dec.func).endswith("lru_cache")
                                                       and any(k.arg == "maxsize" and isinstance(k.value, ast.Constant)
                                                               and k.value.value is None for k in dec.keywords)):
                self.add("PY012", "warning", "memory", "Cache sem limite cresce para sempre (vazamento de memória)", node,
                         "use @lru_cache(maxsize=256) ou um cache com TTL")
        self.generic_visit(node)
        self.async_depth = depth

    def _defaults(self, node):
        for d in node.args.defaults + node.args.kw_defaults:
            if isinstance(d, (ast.List, ast.Dict, ast.Set)):
                self.add("PY009", "warning", "reliability", "Argumento padrão mutável é compartilhado entre chamadas",
                         d, "use None como padrão e crie o objeto dentro da função")

    def visit_With(self, node):
        for item in node.items:
            self.with_items.add(id(item.context_expr))
        self.generic_visit(node)

    visit_AsyncWith = visit_With

    def visit_ExceptHandler(self, node):
        if node.type is None:
            self.add("PY008", "warning", "reliability", "except sem tipo captura até KeyboardInterrupt e SystemExit",
                     node, "capture exceções específicas (ex.: except ValueError)")
        elif len(node.body) == 1 and isinstance(node.body[0], ast.Pass):
            self.add("PY008", "warning", "reliability", "Exceção engolida silenciosamente (except ...: pass)", node,
                     "registre com logging.exception ou trate o erro")
        self.generic_visit(node)

    def visit_AugAssign(self, node):
        if self.loop_depth and isinstance(node.op, ast.Add) and isinstance(node.target, ast.Name) and \
                (isinstance(node.value, (ast.JoinedStr,)) or (isinstance(node.value, ast.Constant) and
                                                             isinstance(node.value.value, str))
                 or node.target.id in self.str_vars):
            self.add("PY011", "info", "performance", "Concatenação de string dentro de laço é O(n²)", node,
                     "acumule em lista e use ''.join(partes)")
        self.generic_visit(node)

    def visit_Assign(self, node):
        if isinstance(node.value, ast.Constant) and isinstance(node.value.value, str):
            for t in node.targets:
                if isinstance(t, ast.Name):
                    self.str_vars.add(t.id)
                    val = node.value.value
                    if _SECRET_NAME.search(t.id) and len(val) >= 4 and not re.match(
                            r"(?i)^(changeme|senha|password|secret|xxx+|\*+|<.*>|\$\{.*\}|your.*|test.*|example.*)$", val):
                        self.add("PY017", "critical", "secret", f"Segredo fixo no código em '{t.id}'", node,
                                 f"leia de variável de ambiente: os.environ['{t.id.upper()}']")
        self.generic_visit(node)

    # -------------------------------------------------------------- chamadas
    def visit_Call(self, node):
        fn = _name(node.func)
        short = fn.rsplit(".", 1)[-1]
        kw = {k.arg: k.value for k in node.keywords if k.arg}
        if fn in ("eval", "exec"):
            self.add("PY001", "critical", "security", f"{fn}() executa código arbitrário", node,
                     "use ast.literal_eval ou um parser específico")
        if fn in ("os.system", "os.popen") or (fn.startswith("subprocess.") and isinstance(kw.get("shell"), ast.Constant)
                                              and kw["shell"].value is True):
            dyn = any(_is_dynamic_str(a) for a in node.args)
            self.add("PY002", "critical" if dyn else "warning", "security",
                     "Comando de shell" + (" montado com dados dinâmicos (injeção de comando)" if dyn else ""), node,
                     "use subprocess.run([...lista de args...]) sem shell=True")
        if short in _SQL_SINKS and node.args and _is_dynamic_str(node.args[0]) and _SQL.search(_str_value(node.args[0]) or "select"):
            self.add("PY003", "critical", "security", "SQL montado com f-string/concatenação (injeção de SQL)", node,
                     "use parâmetros: cursor.execute('... WHERE id = %s', (valor,))")
        if fn in ("pickle.load", "pickle.loads", "marshal.loads", "shelve.open", "dill.loads"):
            self.add("PY004", "warning", "security", f"{fn} desserializa código arbitrário de dados não confiáveis",
                     node, "use JSON ou valide a origem dos dados")
        if fn in ("yaml.load", "yaml.load_all") and not any(k in kw for k in ("Loader",)) or \
                (fn in ("yaml.load", "yaml.load_all") and "Loader" in kw and "Safe" not in _name(kw["Loader"])):
            self.add("PY005", "warning", "security", "yaml.load sem SafeLoader permite construir objetos arbitrários",
                     node, "use yaml.safe_load")
        if isinstance(kw.get("verify"), ast.Constant) and kw["verify"].value is False:
            self.add("PY006", "warning", "security", "Verificação de certificado TLS desativada (verify=False)", node,
                     "mantenha verify=True ou aponte um CA bundle")
        if fn.startswith(("requests.", "httpx.")) and short in _HTTP and "timeout" not in kw:
            self.add("PY007", "warning", "reliability", "Requisição HTTP sem timeout pode travar para sempre", node,
                     "passe timeout=10 (segundos)")
        if fn == "open" and id(node) not in self.with_items:
            self.add("PY010", "info", "memory", "open() fora de 'with' pode vazar o descritor de arquivo", node,
                     "use: with open(...) as f:")
        if fn == "time.sleep" and self.async_depth:
            self.add("PY013", "warning", "performance", "time.sleep bloqueia o event loop dentro de async def", node,
                     "use await asyncio.sleep(...)")
        if fn in ("hashlib.md5", "hashlib.sha1"):
            self.add("PY014", "info", "security", f"{short.upper()} é fraco para senhas e assinaturas", node,
                     "para senhas use hashlib.scrypt/argon2; para integridade use sha256")
        if fn.startswith("random.") and short in ("random", "randint", "choice", "choices", "getrandbits", "sample"):
            parent_names = " ".join(_name(t) for t in getattr(node, "_targets", []))
            if _SECRET_NAME.search(parent_names) or self._near_secret:
                self.add("PY015", "warning", "security", "módulo random não é criptograficamente seguro", node,
                         "use o módulo secrets (secrets.token_urlsafe)")
        if fn == "tempfile.mktemp":
            self.add("PY023", "warning", "security", "tempfile.mktemp tem condição de corrida", node,
                     "use tempfile.NamedTemporaryFile ou mkstemp")
        if fn == "os.chmod" and len(node.args) > 1 and isinstance(node.args[1], ast.Constant) and node.args[1].value == 0o777:
            self.add("PY024", "warning", "security", "Permissão 0o777 deixa o arquivo gravável por todos", node,
                     "use 0o755 (executável) ou 0o644")
        if short == "run" and isinstance(kw.get("debug"), ast.Constant) and kw["debug"].value is True:
            self.add("PY026", "warning", "security", "Servidor com debug=True expõe console interativo", node,
                     "desative debug em produção")
        if short == "iterrows":
            self.add("PY028", "info", "performance", "DataFrame.iterrows é lento", node,
                     "prefira operações vetorizadas ou itertuples()")
        if short == "readlines" and not node.args:
            self.add("PY019", "info", "memory", "readlines() carrega o arquivo inteiro na memória", node,
                     "itere sobre o arquivo linha a linha: for linha in f:")
        if self.loop_depth and short in ("execute", "query", "fetchone", "get_or_create", "find_one", "first") and \
                not fn.startswith(("re.", "self.re")):
            self.add("PY030", "warning", "performance", "Consulta ao banco dentro de laço (N+1)", node,
                     "busque em lote (IN (...)) ou use JOIN")
        self.generic_visit(node)

    _near_secret = False

    def visit_ImportFrom(self, node):
        if any(a.name == "*" for a in node.names):
            self.add("PY031", "warning", "style", f"from {node.module} import * esconde a origem dos nomes e causa conflitos",
                     node, "importe só o que usa: from modulo import nome")
        self.generic_visit(node)

    def visit_Assert(self, node):
        self.add("PY018", "info", "reliability", "assert é removido com python -O; não use para validar entrada", node,
                 "lance ValueError/TypeError explicitamente")
        self.generic_visit(node)


def check(code: str) -> Iterator[Hit]:
    try:
        tree = ast.parse(code)
    except SyntaxError as exc:
        yield ("PY000", "error", "syntax", f"Erro de sintaxe: {exc.msg}", exc.lineno or 1, "")
        return
    v = _Visitor()
    for node in ast.walk(tree):  # marca alvos de atribuição para a regra PY015
        if isinstance(node, ast.Assign) and isinstance(node.value, ast.Call):
            node.value._targets = node.targets  # type: ignore[attr-defined]
    v.visit(tree)
    yield from v.hits


def statement_starts(code: str) -> dict[int, int]:
    """linha -> linha onde começa a instrução que a contém (para injetar dicas sem quebrar expressões)."""
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return {}
    starts: dict[int, int] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.stmt) and hasattr(node, "end_lineno"):
            body_start = None
            for field in ("body", "orelse", "finalbody", "handlers"):
                sub = getattr(node, field, None)
                if isinstance(sub, list) and sub:
                    first = getattr(sub[0], "lineno", None)
                    body_start = first if body_start is None else min(body_start, first or body_start)
            end = (body_start - 1) if body_start else node.end_lineno
            for ln in range(node.lineno, (end or node.lineno) + 1):
                if ln not in starts or starts[ln] < node.lineno:
                    starts[ln] = node.lineno
    return starts
