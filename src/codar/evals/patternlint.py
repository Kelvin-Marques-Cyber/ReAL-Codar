"""Lint do banco de padrões: valida a sintaxe de cada variante (tree-sitter + compile do Python).

Fragmentos (ex.: instruções Java soltas) são "embrulhados" em função/classe antes do parse, pois
padrões podem ser trechos para colar dentro de um método. Uso: `python -m codar.evals.patternlint`.
"""

from __future__ import annotations

import importlib
import os
import re
import shutil
import sys
from dataclasses import dataclass

from codar.engine.postprocess import split_imports

GRAMMARS = {
    "python": ("tree_sitter_python", "language"), "javascript": ("tree_sitter_javascript", "language"),
    "typescript": ("tree_sitter_typescript", "language_typescript"), "tsx": ("tree_sitter_typescript", "language_tsx"),
    "go": ("tree_sitter_go", "language"), "rust": ("tree_sitter_rust", "language"), "java": ("tree_sitter_java", "language"),
    "c": ("tree_sitter_c", "language"), "cpp": ("tree_sitter_cpp", "language"), "csharp": ("tree_sitter_c_sharp", "language"),
    "bash": ("tree_sitter_bash", "language"), "powershell": ("tree_sitter_powershell", "language"),
    "lua": ("tree_sitter_lua", "language"), "php": ("tree_sitter_php", "language_php"), "ruby": ("tree_sitter_ruby", "language"),
    "sql": ("tree_sitter_sql", "language"), "json": ("tree_sitter_json", "language"), "yaml": ("tree_sitter_yaml", "language"),
    "toml": ("tree_sitter_toml", "language"), "css": ("tree_sitter_css", "language"), "html": ("tree_sitter_html", "language"),
    "kotlin": ("tree_sitter_kotlin", "language"), "swift": ("tree_sitter_swift", "language"),
    "dart": ("tree_sitter_dart", "language"), "julia": ("tree_sitter_julia", "language"),
}
# gramáticas que só existem no tree-sitter-language-pack (baixadas na primeira vez e guardadas em cache)
PACK = {"r": "r"}

WRAPS = {
    "java": [lambda c: f"class W {{ void m() throws Exception {{\n{c}\n}} }}", lambda c: f"class W {{\n{c}\n}}"],
    "c": [lambda c: f"void w(void) {{\n{c}\n}}"],
    "cpp": [lambda c: f"void w() {{\n{c}\n}}", lambda c: f"struct W {{\n{c}\n}};"],
    "csharp": [lambda c: f"class W {{ async System.Threading.Tasks.Task M() {{\n{c}\n}} }}", lambda c: f"class W {{\n{c}\n}}"],
    "rust": [lambda c: f"fn w() {{\n{c}\n}}", lambda c: f"async fn w() {{\n{c}\n}}", lambda c: f"impl W {{\n{c}\n}}"],
    "go": [lambda c: f"package p\nfunc w() {{\n{c}\n}}", lambda c: f"package p\n{c}"],
    "php": [lambda c: f"<?php\n{c}"],
    "typescript": [lambda c: f"async function w() {{\n{c}\n}}"],
    "javascript": [lambda c: f"async function w() {{\n{c}\n}}"],
    "kotlin": [lambda c: f"fun w() {{\n{c}\n}}"],
    "dart": [lambda c: f"void w() {{\n{c}\n}}", lambda c: f"class W {{\n{c}\n}}"],
}


@dataclass
class LintError:
    pattern: str
    lang: str
    line: int
    col: int
    snippet: str


_parsers: dict[str, object] = {}


def _parser(lang: str):
    if lang in _parsers:
        return _parsers[lang]
    spec = GRAMMARS.get(lang)
    parser = None
    if lang in PACK:
        try:
            from tree_sitter_language_pack import get_parser

            parser = get_parser(PACK[lang])
        except Exception:
            parser = None
    if spec:
        try:
            from tree_sitter import Language, Parser

            mod = importlib.import_module(spec[0])
            parser = Parser(Language(getattr(mod, spec[1])()))
        except Exception:
            parser = None
    _parsers[lang] = parser
    return parser


def _first_error(node):
    if node.type == "ERROR" or node.is_missing:
        return node
    if not node.has_error:
        return None
    for child in node.children:
        found = _first_error(child)
        if found is not None:
            return found
    return node if node.has_error else None


def check(code: str, lang: str) -> tuple[bool, int, int] | None:
    """None = sem validador disponível; (ok, linha, coluna)."""
    if lang == "python":
        try:
            compile(code, "<pattern>", "exec", flags=0x2000, dont_inherit=True)  # PyCF_ALLOW_TOP_LEVEL_AWAIT
            return True, 0, 0
        except SyntaxError as exc:
            return False, exc.lineno or 0, exc.offset or 0
    gl = "tsx" if lang == "typescript" and re.search(r"return\s*\(\s*<|<[A-Z][A-Za-z]*[\s/>]|</\w+>", code) else lang
    parser = _parser(gl)
    if parser is None:
        return None
    tree = parser.parse(code.encode("utf-8"))
    if not tree.root_node.has_error:
        return True, 0, 0
    err = _first_error(tree.root_node)
    first = (False, (err.start_point[0] + 1) if err else 0, (err.start_point[1] + 1) if err else 0)
    imports, body = split_imports(code, lang)
    for wrap in WRAPS.get(lang, []):
        wrapped = wrap(body)
        if lang in ("go",):
            wrapped = wrapped.replace("package p\n", "package p\n" + "\n".join(imports) + "\n", 1)
        elif imports:
            wrapped = "\n".join(imports) + "\n" + wrapped
        if not parser.parse(wrapped.encode("utf-8")).root_node.has_error:
            return True, 0, 0
    return first


GO_STD = {"fmt", "errors", "strings", "strconv", "os", "io", "bufio", "time", "math", "sort", "slices", "maps", "sync",
          "context", "http", "json", "log", "slog", "regexp", "filepath", "bytes", "unicode", "rand", "sha256", "hex",
          "heap", "exec", "signal", "atomic", "utf8", "base64", "csv", "url", "net", "hmac", "subtle", "aes", "cipher",
          "zip", "gzip", "tar", "fs", "errgroup", "testing", "httptest", "template", "sql", "flag", "runtime", "big",
          "list", "ring", "path", "user", "tls", "x509", "pem", "binary", "md5", "sha1", "sha512", "crc32", "cmp", "iter"}


def _fill(p, code: str) -> str:
    for slot, default in p.slots.items():
        code = code.replace("{{" + slot + "}}", default)
    return code


def missing_imports(code: str, lang: str) -> list[str]:
    """Pacotes/módulos usados sem import (erro que o parser de sintaxe não pega)."""
    out: list[str] = []
    if lang == "python":
        try:
            import pyflakes.api
            import pyflakes.reporter
        except ImportError:
            return out
        import io

        buf = io.StringIO()
        pyflakes.api.check(code, "p.py", pyflakes.reporter.Reporter(buf, buf))
        for line in buf.getvalue().splitlines():
            m = re.search(r"undefined name '([a-z_][a-z0-9_]*)'", line)
            if m and re.search(rf"\b{m.group(1)}\.\w", code):
                out.append(m.group(1))
    elif lang == "go":
        from codar.audit.lexer import mask

        code = mask(code, "go", strings=False)
        def pkg_name(path: str) -> str:
            parts = path.strip('"').split("/")
            return parts[-2] if len(parts) > 1 and re.fullmatch(r"v\d+", parts[-1]) else parts[-1]

        imported = {pkg_name(imp) for imp in re.findall(r'"([\w./-]+)"', "\n".join(
            ln for ln in code.split("\n") if ln.strip().startswith(("import", '"')) or ln.startswith("\t\"")))}
        imported |= set(re.findall(r'^\s*(\w+)\s+"[\w./-]+"', code, re.M))
        declared = set(re.findall(r"\b(\w+)\s*:?=", code)) | set(re.findall(r"\bfunc\s*\(?\s*(\w+)", code))
        declared |= set(re.findall(r"\b(?:var|type)\s+(\w+)", code)) | set(re.findall(r"\((\w+)\s+\*?\w", code))
        for pkg in sorted(set(re.findall(r"(?<![\w.])([a-z][a-z0-9]*)\.[A-Z]\w*", code))):
            if pkg in GO_STD and pkg not in imported and pkg not in declared:
                out.append(pkg)
    return out


_PWSH_PARSE = r"""
$entrada = Get-Content -Raw -LiteralPath $args[0] | ConvertFrom-Json
$saida = [ordered]@{}
foreach ($p in $entrada.PSObject.Properties) {
    $tokens = $null; $erros = $null
    [void][System.Management.Automation.Language.Parser]::ParseInput($p.Value, [ref]$tokens, [ref]$erros)
    if ($erros.Count) { $saida[$p.Name] = @($erros[0].Extent.StartLineNumber, $erros[0].Extent.StartColumnNumber, $erros[0].Message) }
}
$saida | ConvertTo-Json -Compress -Depth 3
"""


def pwsh_bin() -> str | None:
    import os
    import shutil

    return os.environ.get("CODAR_PWSH") or shutil.which("pwsh")


def pwsh_check_many(snippets: dict[str, str]) -> dict[str, tuple[int, int, str]] | None:
    """Valida vários scripts PowerShell com o parser oficial numa única invocação."""
    import json
    import subprocess
    import tempfile
    from pathlib import Path

    exe = pwsh_bin()
    if not exe or not snippets:
        return None
    with tempfile.TemporaryDirectory() as tmp:
        data = Path(tmp, "in.json")
        data.write_text(json.dumps(snippets), encoding="utf-8")
        script = Path(tmp, "parse.ps1")
        script.write_text(_PWSH_PARSE, encoding="utf-8")
        r = subprocess.run([exe, "-NoProfile", "-NonInteractive", "-File", str(script), str(data)],
                           capture_output=True, text=True, timeout=120)
    if r.returncode != 0:
        return None
    out = json.loads(r.stdout or "{}") or {}
    return {k: (int(v[0]), int(v[1]), str(v[2])) for k, v in out.items()}


def lint(patterns) -> tuple[int, int, list[LintError]]:
    checked = skipped = 0
    errors: list[LintError] = []
    ps_snippets = {f"{p.id}": _fill(p, p.code["powershell"]) for p in patterns if "powershell" in p.code}
    ps_results = pwsh_check_many(ps_snippets)
    for p in patterns:
        used = {m for code in p.code.values() for m in re.findall(r"\{\{(\w+)\}\}", code)}
        for slot in sorted(set(p.slots) - used):
            errors.append(LintError(p.id, "*", 0, 0, f"slot '{slot}' declarado mas nenhuma variante usa {{{{{slot}}}}}"))
        for slot in sorted(used - set(p.slots)):
            errors.append(LintError(p.id, "*", 0, 0, f"{{{{{slot}}}}} usado sem valor padrão em slots"))
        for lang, code in p.code.items():
            text = _fill(p, code)
            if lang == "powershell":
                if ps_results is None:  # a gramática tree-sitter de PowerShell dá falsos positivos: só o parser oficial
                    skipped += 1
                    continue
                checked += 1
                if p.id in ps_results:
                    line, col, msg = ps_results[p.id]
                    errors.append(LintError(p.id, lang, line, col, msg[:100]))
                continue
            res = check(text, lang)
            if res is None:
                skipped += 1
                continue
            checked += 1
            ok, line, col = res
            for mod in missing_imports(text, lang):
                errors.append(LintError(p.id, lang, 0, 0, f"usa '{mod}' sem import"))
            if not ok:
                src_line = text.split("\n")[line - 1].strip() if 0 < line <= text.count("\n") + 1 else ""
                errors.append(LintError(p.id, lang, line, col, src_line[:100]))
    return checked, skipped, errors


def run_tests(patterns, timeout: float = 20.0) -> tuple[int, list[str]]:
    """Executa os testes de [pattern.test] (python, javascript, typescript, powershell, bash) e as sessões
    interativas (stdin/expect) em toda linguagem com toolchain disponível nesta máquina."""
    import shutil
    import subprocess
    import tempfile
    from pathlib import Path

    from codar.evals.runner import check as run_python

    node = shutil.which("node")
    ran, failures = 0, []
    for p in patterns:
        for lang, test in p.tests.items():
            code = p.code.get(lang)
            if code is None or lang.endswith("_setup"):
                continue
            for slot, default in p.slots.items():
                code = code.replace("{{" + slot + "}}", default)
            if p.tests.get(f"{lang}_setup"):
                code = p.tests[f"{lang}_setup"] + "\n" + code
            if lang == "python":
                ok, err = run_python(code, test, timeout=timeout)
            elif lang in ("powershell", "bash") and (pwsh_bin() if lang == "powershell" else shutil.which("bash")):
                with tempfile.TemporaryDirectory() as tmp:
                    f = Path(tmp, "t.ps1" if lang == "powershell" else "t.sh")
                    prelude = "$ErrorActionPreference = 'Stop'\n" if lang == "powershell" else "set -euo pipefail\n"
                    f.write_text(prelude + code + "\n" + test + "\n", encoding="utf-8")
                    cmd = [pwsh_bin(), "-NoProfile", "-NonInteractive", "-File", str(f)] if lang == "powershell" \
                        else ["bash", str(f)]
                    try:
                        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, cwd=tmp)
                        ok, err = r.returncode == 0, (r.stderr.strip().splitlines() or ["?"])[-1]
                    except subprocess.TimeoutExpired:
                        ok, err = False, "timeout"
            elif lang in ("javascript", "typescript") and node:
                with tempfile.TemporaryDirectory() as tmp:
                    f = Path(tmp, "t.mts" if lang == "typescript" else "t.mjs")
                    f.write_text(code + "\n" + test + "\n", encoding="utf-8")
                    try:
                        r = subprocess.run([node, str(f)], capture_output=True, text=True, timeout=timeout)
                        ok, err = r.returncode == 0, (r.stderr.strip().splitlines() or ["?"])[-1]
                    except subprocess.TimeoutExpired:
                        ok, err = False, "timeout"
            else:
                continue
            ran += 1
            if not ok:
                failures.append(f"{p.id} [{lang}]: {err}")
        sessions = [{"stdin": p.tests["stdin"], "expect": p.tests.get("expect", [])}] if "stdin" in p.tests else []
        sessions += list(p.tests.get("runs", []))  # [[pattern.test.runs]]: args, stdin, expect, status
        for k, run in enumerate(sessions):
            for lang, code in p.code.items():
                if run.get("langs") and lang not in run["langs"]:  # convenções diferentes (-Opcao no PowerShell)
                    continue
                result = run_session(lang, code, run.get("stdin", ""), list(run.get("expect", [])), timeout,
                                     args=[str(a) for a in run.get("args", [])], status=int(run.get("status", 0)))
                if result is None:
                    continue  # sem toolchain para essa linguagem nesta máquina
                ran += 1
                if result:
                    label = " ".join(run.get("args", [])) or "stdin"
                    failures.append(f"{p.id} [{lang}] execução {k + 1} ({label}): {result}")
    return ran, failures


# Programas interativos: arquivo + comando para executar com a sessão digitada na entrada padrão.
_SESSION = {
    "python": ("t.py", lambda f: [sys.executable, "-I", f]),
    "javascript": ("t.mjs", lambda f: [shutil.which("node"), f]),
    "typescript": ("t.mts", lambda f: [shutil.which("node"), f]),
    "java": ("t.java", lambda f: [shutil.which("java"), f]),
    "go": ("main.go", lambda f: [shutil.which("go"), "run", f]),
    "powershell": ("t.ps1", lambda f: [pwsh_bin(), "-NoProfile", "-NonInteractive", "-File", f]),
    "bash": ("t.sh", lambda f: [shutil.which("bash"), f]),
}


def run_session(lang: str, code: str, stdin: str, expect: list[str], timeout: float = 20.0, *,
                args: list[str] | None = None, status: int = 0) -> str | None:
    """Executa o programa com `args` e `stdin` e confere o código de saída e se a saída (stdout + stderr) contém
    cada trecho de `expect`, em ordem. Devolve "" se passou, a descrição da falha, ou None se não há como executar
    `lang` aqui."""
    import subprocess
    import tempfile
    from pathlib import Path

    if lang not in _SESSION:
        return None
    name, cmd = _SESSION[lang]
    with tempfile.TemporaryDirectory() as tmp:
        argv = cmd(str(Path(tmp, name)))
        if not argv[0]:
            return None
        argv += args or []
        Path(tmp, name).write_text(code, encoding="utf-8")
        try:
            r = subprocess.run(argv, input=stdin, capture_output=True, text=True, timeout=timeout, cwd=tmp,
                               env={**os.environ, "NO_COLOR": "1"})
        except subprocess.TimeoutExpired:
            return "timeout (o programa não terminou com a entrada dada)"
    if r.returncode != status:
        last = (r.stderr.strip().splitlines() or ["?"])[-1][:160]
        return f"saiu com código {r.returncode} (esperava {status}): {last}"
    output = r.stdout + r.stderr
    pos = 0
    for want in expect:
        found = output.find(want, pos)
        if found < 0:
            got = output[pos:pos + 120].replace("\n", "⏎")
            return f"esperava {want!r} na saída; depois do último acerto veio: {got!r}"
        pos = found + len(want)
    return ""


def main() -> int:
    from codar import config
    from codar.plugin_loader import discover

    bundle = discover(config.load())
    checked, skipped, errors = lint(bundle.patterns)
    for e in errors:
        print(f"ERRO {e.pattern} [{e.lang}] linha {e.line}:{e.col}: {e.snippet}")
    ran, failures = run_tests(bundle.patterns)
    for f in failures:
        print(f"FALHA {f}")
    if not pwsh_bin():
        print("aviso: pwsh não encontrado; PowerShell não foi validado (instale o PowerShell 7 ou defina CODAR_PWSH)")
    print(f"{len(bundle.patterns)} padrões · {checked} variantes validadas · {skipped} sem validador · "
          f"{len(errors)} erros de sintaxe · {ran} testes executados · {len(failures)} falhas")
    return 1 if errors or failures else 0


if __name__ == "__main__":
    sys.exit(main())
