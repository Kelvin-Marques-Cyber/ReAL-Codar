"""Registro de linguagens: aliases (CLI, VS Code languageId, filetype do Neovim), extensões, comentários."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Lang:
    id: str
    name: str
    aliases: tuple[str, ...]
    exts: tuple[str, ...]
    comment: str
    fence: str
    indent: str = "    "
    runner: tuple[str, ...] | None = None  # comando para executar um arquivo; {file} é substituído
    programa: bool = True  # lê a entrada padrão e escreve a saída: vale para os exercícios de comportamento
    codigo: bool = True  # entra no índice de código do projeto (símbolos, contexto, vínculos entre arquivos)


_LANGS = [
    Lang("python", "Python", ("py", "python3", "python"), (".py", ".pyw"), "#", "python",
         runner=("{python}", "{file}")),
    Lang("javascript", "JavaScript", ("js", "node", "javascriptreact", "jsx", "mjs", "cjs"),
         (".js", ".mjs", ".cjs", ".jsx"), "//", "javascript", "  ", ("node", "{file}")),
    Lang("typescript", "TypeScript", ("ts", "typescriptreact", "tsx", "mts"), (".ts", ".mts", ".cts", ".tsx"),
         "//", "typescript", "  ", ("node", "{file}")),
    Lang("go", "Go", ("golang",), (".go",), "//", "go", "\t", ("go", "run", "{file}")),
    Lang("rust", "Rust", ("rs",), (".rs",), "//", "rust"),
    Lang("java", "Java", (), (".java",), "//", "java", runner=("java", "{file}")),
    Lang("c", "C", ("h",), (".c", ".h"), "//", "c"),
    Lang("cpp", "C++", ("c++", "cc", "cxx", "hpp"), (".cpp", ".cc", ".cxx", ".hpp", ".hh"), "//", "cpp"),
    Lang("csharp", "C#", ("cs", "c#"), (".cs", ".csx"), "//", "csharp"),
    Lang("bash", "Bash", ("sh", "shell", "shellscript", "zsh", "ksh"), (".sh", ".bash", ".zsh"), "#", "bash",
         "  ", ("bash", "{file}")),
    Lang("powershell", "PowerShell", ("ps1", "pwsh", "ps", "psm1"), (".ps1", ".psm1", ".psd1"), "#",
         "powershell", runner=("pwsh", "-NoProfile", "-File", "{file}")),
    Lang("lua", "Lua", ("luau",), (".lua",), "--", "lua", "  ", ("lua", "{file}")),
    Lang("ruby", "Ruby", ("rb",), (".rb",), "#", "ruby", "  ", ("ruby", "{file}")),
    Lang("php", "PHP", (), (".php",), "//", "php", runner=("php", "{file}")),
    Lang("sql", "SQL", ("postgres", "postgresql", "mysql", "sqlite", "plsql", "tsql"), (".sql",), "--", "sql",
         programa=False),
    Lang("kotlin", "Kotlin", ("kt", "kts"), (".kt", ".kts"), "//", "kotlin"),
    Lang("swift", "Swift", (), (".swift",), "//", "swift", runner=("swift", "{file}")),
    Lang("dart", "Dart", ("flutter",), (".dart",), "//", "dart", "  ", ("dart", "run", "{file}")),
    Lang("r", "R", ("rlang", "rscript"), (".r",), "#", "r", "  ", ("Rscript", "{file}")),
    Lang("julia", "Julia", ("jl",), (".jl",), "#", "julia", "    ", ("julia", "{file}")),
    Lang("html", "HTML", ("htm",), (".html", ".htm"), "<!--", "html", "  ", programa=False),
    Lang("css", "CSS", ("scss", "less"), (".css", ".scss", ".less"), "/*", "css", "  ", programa=False),
    Lang("yaml", "YAML", ("yml",), (".yml", ".yaml"), "#", "yaml", "  ", programa=False),
    Lang("dockerfile", "Dockerfile", ("docker",), (), "#", "dockerfile", programa=False),
    # Documentos, dados e build: estudo, realce e comentários; não são programas de entrada e saída.
    Lang("latex", "LaTeX", ("tex",), (".tex", ".sty", ".cls", ".ltx"), "%", "latex", "  ",
         ("pdflatex", "-interaction=nonstopmode", "-halt-on-error", "{file}"), programa=False),
    Lang("markdown", "Markdown", ("md", "mdown", "gfm"), (".md", ".markdown", ".mdx"), "<!--", "markdown", "  ",
         programa=False, codigo=False),
    Lang("json", "JSON", ("jsonc", "geojson"), (".json", ".jsonc", ".geojson", ".webmanifest"), "", "json",
         "  ", programa=False, codigo=False),
    Lang("toml", "TOML", (), (".toml",), "#", "toml", programa=False, codigo=False),
    Lang("xml", "XML", ("xsd", "xsl", "xslt", "svg", "plist"), (".xml", ".xsd", ".xsl", ".xslt", ".svg", ".plist"),
         "<!--", "xml", "  ", programa=False, codigo=False),
    Lang("makefile", "Makefile", ("make", "gnumake", "mk"), (".mk", ".mak"), "#", "makefile", "\t",
         ("make", "-f", "{file}"), programa=False),
    Lang("graphql", "GraphQL", ("gql",), (".graphql", ".gql"), "#", "graphql", "  ", programa=False),
    Lang("protobuf", "Protocol Buffers", ("proto", "proto3"), (".proto",), "//", "protobuf", "  ", programa=False),
    Lang("terraform", "Terraform", ("hcl", "tf", "opentofu"), (".tf", ".tfvars", ".hcl"), "#", "hcl", "  ",
         programa=False),
    Lang("verilog", "Verilog", ("systemverilog", "sv"), (".v", ".sv", ".vh", ".svh"), "//", "verilog", "  ",
         programa=False),
    Lang("vhdl", "VHDL", (), (".vhd", ".vhdl"), "--", "vhdl", "  ", programa=False),
    Lang("solidity", "Solidity", ("sol",), (".sol",), "//", "solidity", programa=False),
]

LANGS: dict[str, Lang] = {lang.id: lang for lang in _LANGS}
_ALIASES: dict[str, str] = {}
_EXTS: dict[str, str] = {}
for _l in _LANGS:
    _ALIASES[_l.id] = _l.id
    _ALIASES[_l.name.lower()] = _l.id
    for _a in _l.aliases:
        _ALIASES[_a] = _l.id
    for _e in _l.exts:
        _EXTS[_e] = _l.id
        _ALIASES.setdefault(_e.lstrip("."), _l.id)
_NOMES = {"dockerfile": "dockerfile", "containerfile": "dockerfile", "makefile": "makefile",
          "gnumakefile": "makefile", "cargo.lock": "toml"}


class UnknownLanguage(ValueError):
    pass


def resolve(name: str | None, default: str = "python") -> Lang:
    key = (name or default).strip().lower()
    if key.startswith("."):
        key = key[1:]
    if key in _ALIASES:
        return LANGS[_ALIASES[key]]
    raise UnknownLanguage(f"linguagem desconhecida: {name!r} (conhecidas: {', '.join(sorted(LANGS))})")


def try_resolve(name: str | None) -> Lang | None:
    try:
        return resolve(name) if name else None
    except UnknownLanguage:
        return None


def from_path(path: str | Path | None) -> Lang | None:
    if not path:
        return None
    p = Path(str(path))
    if p.name.lower() in _NOMES:
        return LANGS[_NOMES[p.name.lower()]]
    lid = _EXTS.get(p.suffix.lower())
    return LANGS[lid] if lid else None


_FECHA = {"<!--": "-->", "/*": "*/"}


def comment_line(lang: Lang, text: str) -> str:
    if lang.comment in _FECHA:
        return f"{lang.comment} {text} {_FECHA[lang.comment]}"
    if not lang.comment:  # JSON não tem comentários
        raise ValueError(f"{lang.name} não aceita comentários")
    return f"{lang.comment} {text}"
