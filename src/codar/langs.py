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
    Lang("sql", "SQL", ("postgres", "postgresql", "mysql", "sqlite", "plsql", "tsql"), (".sql",), "--", "sql"),
    Lang("kotlin", "Kotlin", ("kt", "kts"), (".kt", ".kts"), "//", "kotlin"),
    Lang("swift", "Swift", (), (".swift",), "//", "swift", runner=("swift", "{file}")),
    Lang("dart", "Dart", ("flutter",), (".dart",), "//", "dart", "  ", ("dart", "run", "{file}")),
    Lang("r", "R", ("rlang", "rscript"), (".r",), "#", "r", "  ", ("Rscript", "{file}")),
    Lang("julia", "Julia", ("jl",), (".jl",), "#", "julia", "    ", ("julia", "{file}")),
    Lang("html", "HTML", ("htm",), (".html", ".htm"), "<!--", "html", "  "),
    Lang("css", "CSS", ("scss", "less"), (".css", ".scss", ".less"), "/*", "css", "  "),
    Lang("yaml", "YAML", ("yml",), (".yml", ".yaml"), "#", "yaml", "  "),
    Lang("dockerfile", "Dockerfile", ("docker",), (), "#", "dockerfile"),
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
    if p.name.lower() == "dockerfile":
        return LANGS["dockerfile"]
    lid = _EXTS.get(p.suffix.lower())
    return LANGS[lid] if lid else None


def comment_line(lang: Lang, text: str) -> str:
    if lang.comment == "<!--":
        return f"<!-- {text} -->"
    if lang.comment == "/*":
        return f"/* {text} */"
    return f"{lang.comment} {text}"
