"""Configuração e contexto de projeto, sem embeddings nem dependências do núcleo."""

from __future__ import annotations

import ast
import fnmatch
import os
import re
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

from codar import langs
from codar._compat import tomllib

CONFIG_NAME = "codar.toml"
MAX_FILE_BYTES = 512_000
EXCLUDED_DIRS = {".git", ".codar", ".dart_tool", ".pub-cache", ".gradle", ".idea", ".venv", "venv",
                 "node_modules", "__pycache__", "build", "dist", "target", "vendor", "coverage"}
SECRET_NAMES = {".env", "credentials", "credentials.json", "secrets.json", "secrets.toml", "id_rsa", "id_ed25519"}
MARKERS = (CONFIG_NAME, ".git", "pubspec.yaml", "pyproject.toml", "package.json", "Cargo.toml", "go.mod")


def find_root(file: str | Path | None = None) -> Path | None:
    if not file:
        return None
    path = Path(file).expanduser().absolute()
    directory = path if path.is_dir() else path.parent
    for parent in (directory, *directory.parents):
        if any((parent / marker).exists() for marker in MARKERS):
            return parent.resolve()
    return None


def safe_path(root: Path, relative: str) -> Path:
    """Recusa caminhos absolutos, escapes e links em qualquer componente."""
    path = Path(relative)
    if not relative or path.is_absolute() or ".." in path.parts or "\\" in relative or ":" in relative:
        raise ValueError(f"caminho inválido: {relative}")
    root = root.resolve()
    candidate = root / path
    for part in (candidate, *candidate.parents):
        if part == root:
            break
        if part.is_symlink():
            raise ValueError(f"link simbólico não é um alvo de edição: {relative}")
    if not candidate.resolve().is_relative_to(root):
        raise ValueError(f"caminho fora do projeto: {relative}")
    return candidate


def read_source(path: Path) -> str:
    if path.stat().st_size > MAX_FILE_BYTES:
        raise ValueError(f"arquivo excede {MAX_FILE_BYTES} bytes: {path.name}")
    with path.open(encoding="utf-8", newline="") as handle:
        text = handle.read(MAX_FILE_BYTES + 1)
    if "\0" in text or len(text.encode("utf-8")) > MAX_FILE_BYTES:
        raise ValueError(f"arquivo não é código UTF-8 ou é grande demais: {path.name}")
    return text


@dataclass
class Project:
    root: Path
    commands: dict[str, list[str]] = field(default_factory=dict)
    toolchains: dict[str, str] = field(default_factory=dict)
    skills: list[str] = field(default_factory=list)
    guidance: list[str] = field(default_factory=list)
    exclude: list[str] = field(default_factory=list)
    max_files: int = 2000
    context_chars: int = 4000
    repair_attempts: int = 1

    @classmethod
    def load(cls, root: str | Path) -> Project:
        root = Path(root).expanduser().resolve()
        if not root.is_dir():
            raise ValueError(f"projeto não encontrado: {root}")
        p = cls(root)
        config = root / CONFIG_NAME
        if not config.exists():
            return p
        if config.is_symlink() or config.stat().st_size > 64_000:
            raise ValueError("codar.toml deve ser um arquivo local de até 64 KB")
        data = tomllib.loads(config.read_text(encoding="utf-8"))
        project = data.get("project", {})
        p.commands = data.get("commands", {})
        p.toolchains = data.get("toolchains", {})
        if not isinstance(project, dict) or not isinstance(p.commands, dict) or not isinstance(p.toolchains, dict):
            raise ValueError("project, commands e toolchains devem ser tabelas TOML")
        for name, command in p.commands.items():
            if name not in ("run", "test", "analyze", "format") or not isinstance(command, list) or not command \
                    or any(not isinstance(arg, str) or not arg or "\0" in arg for arg in command):
                raise ValueError(f"commands.{name}: informe uma lista de argumentos, sem shell")
        if any(not isinstance(k, str) or not isinstance(v, str) or not v for k, v in p.toolchains.items()):
            raise ValueError("toolchains: informe linguagem = versão")
        for key in ("skills", "guidance", "exclude"):
            value = project.get(key, [])
            if not isinstance(value, list) or any(not isinstance(x, str) for x in value):
                raise ValueError(f"project.{key}: informe uma lista de textos")
            setattr(p, key, value)
        for key, lower, upper in (("max_files", 1, 10000), ("context_chars", 0, 16000), ("repair_attempts", 0, 2)):
            value = project.get(key, getattr(p, key))
            if type(value) is not int or not lower <= value <= upper:
                raise ValueError(f"project.{key}: use um inteiro entre {lower} e {upper}")
            setattr(p, key, value)
        if sum(map(len, p.guidance)) > 4000:
            raise ValueError("project.guidance excede 4000 caracteres")
        return p

    def allowed(self, relative: str) -> bool:
        path = Path(relative)
        return not (any(x in EXCLUDED_DIRS for x in path.parts) or path.name in SECRET_NAMES or
                    path.name.startswith(".env.") or path.suffix.lower() in (".pem", ".key", ".p12", ".pfx") or
                    path.name.endswith((".g.dart", ".freezed.dart", ".min.js", ".lock")) or
                    any(fnmatch.fnmatch(relative, rule) or fnmatch.fnmatch(path.name, rule) for rule in self.exclude))

    def files(self, *, code_only: bool = True) -> list[str]:
        """O Git faz a seleção quando disponível, respeitando suas regras de ignore."""
        names = None
        if shutil.which("git"):
            try:
                proc = subprocess.run(["git", "-C", str(self.root), "ls-files", "--cached", "--others",
                                       "--exclude-standard", "-z"], capture_output=True, timeout=5)
                if proc.returncode == 0:
                    names = proc.stdout.decode("utf-8").split("\0")
            except (OSError, UnicodeError, subprocess.TimeoutExpired):
                pass
        if names is None:
            names = []
            # Fora de um repositório, regras usuais de .gitignore também são respeitadas.
            rules = self._ignore_rules()
            for directory, folders, files in os.walk(self.root, followlinks=False):
                relative_dir = Path(directory).relative_to(self.root)
                folders[:] = sorted(d for d in folders if d not in EXCLUDED_DIRS and
                                    not (Path(directory) / d).is_symlink() and
                                    not _ignored((relative_dir / d).as_posix() + "/", rules))
                for file in sorted(files):
                    name = (relative_dir / file).as_posix()
                    if not _ignored(name, rules):
                        names.append(name)
                if len(names) >= self.max_files * 4:
                    break
        out = []
        for name in sorted(set(names)):
            if not name or not self.allowed(name) or (code_only and not langs.from_path(name)):
                continue
            try:
                if safe_path(self.root, name).is_file():
                    out.append(name)
            except ValueError:
                continue
            if len(out) >= self.max_files:
                break
        return out

    def _ignore_rules(self):
        file = self.root / ".gitignore"
        try:
            return [s.strip() for s in file.read_text(encoding="utf-8").splitlines()
                    if s.strip() and not s.lstrip().startswith("#")]
        except (OSError, UnicodeError):
            return []

    def context(self, intent: str, current: str = "", overrides: dict[str, str] | None = None) -> dict:
        if self.context_chars < 100:
            return {"root": str(self.root), "files": [], "guidance": self.guidance, "skills": self.skills, "context": ""}
        tokens = set(re.findall(r"[\w]+", intent.lower()))
        references = set()
        if current:
            try:
                source = (overrides or {}).get(current)
                if source is None:
                    source = read_source(safe_path(self.root, current))
                references = set(re.findall(r"\b([A-Za-z_]\w*)\s*\(", source[:64000]))
                for line in source.splitlines():
                    if re.match(r"\s*(?:import|from|export|using|Import-Module)\b", line):
                        references.update(re.findall(r"[\w]+", line))
                references -= {"print", "input", "str", "int", "list", "dict", "len", "import", "from", "package"}
            except (OSError, UnicodeError, ValueError):
                pass
        ranked = []
        current_path = Path(current)
        for name in self.files():
            if name == current:
                continue
            try:
                text = (overrides or {}).get(name)
                if text is None:
                    text = read_source(safe_path(self.root, name))
            except (OSError, ValueError, UnicodeError):
                continue
            symbols = extract_symbols(text, name)
            words = set(re.findall(r"[\w]+", name.lower() + " " + " ".join(symbols)))
            score = 4 * len(tokens & words)
            score += 3 * len({r.lower() for r in references} & words)
            if current and Path(name).parent == current_path.parent:
                score += 2
            if current and Path(name).suffix == current_path.suffix:
                score += 1
            if score:
                ranked.append((score, name, text, symbols))
                ranked.sort(key=lambda item: (-item[0], item[1]))
                del ranked[8:]  # não mantém o conteúdo de milhares de arquivos na RAM
        budget, snippets = self.context_chars, []
        for score, name, text, symbols in sorted(ranked, key=lambda x: (-x[0], x[1]))[:8]:
            if budget < 100:
                break
            sample = excerpt(text, symbols, min(1500, budget - len(name) - 30))
            snippets.append({"path": name, "symbols": symbols[:20], "code": sample, "score": score})
            budget -= len(sample) + len(name) + 30
        return {"root": str(self.root), "files": snippets, "guidance": self.guidance, "skills": self.skills,
                "context": "\n\n".join(f"File {s['path']} (reference only):\n{s['code']}" for s in snippets)}

    def as_dict(self):
        return {"root": str(self.root), "commands": self.commands, "toolchains": self.toolchains,
                "skills": self.skills, "guidance": self.guidance, "exclude": self.exclude,
                "context_chars": self.context_chars, "repair_attempts": self.repair_attempts}


def _ignored(name: str, rules: list[str]) -> bool:
    ignored = False
    for rule in rules:
        negate = rule.startswith("!")
        rule = rule.removeprefix("!").lstrip("/")
        directory = rule.endswith("/")
        rule = rule.rstrip("/")
        match = fnmatch.fnmatch(name.rstrip("/"), rule) or fnmatch.fnmatch(Path(name).name, rule)
        if directory:
            match |= any(fnmatch.fnmatch(part, rule) for part in Path(name).parts)
        if match:
            ignored = not negate
    return ignored


def extract_symbols(text: str, name: str) -> list[str]:
    if name.endswith(".py"):
        try:
            tree = ast.parse(text)
            return [node.name for node in ast.walk(tree) if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))]
        except SyntaxError:
            pass
    return _regex_symbols(text)


def _regex_symbols(text: str) -> list[str]:
    matches = re.findall(r"(?m)^\s*(?:export\s+)?(?:class|function|def|enum|interface|struct|fn)\s+([\w-]+)|"
                         r"^\s*(?:[\w<>?]+\s+)+([\w]+)\s*\(", text)
    return list(dict.fromkeys(a or b for a, b in matches))


def excerpt(text: str, symbols: list[str], budget: int) -> str:
    if len(text) <= budget:
        return text
    lines = text.splitlines()
    useful = [line for line in lines if re.match(r"\s*(?:import|from|export|using|Import-Module|#requires)\b", line)]
    useful += [line for line in lines if any(re.search(r"\b" + re.escape(s) + r"\b", line) for s in symbols[:20])]
    return ("\n".join(useful) or text[:budget])[:budget] + "\n[reference excerpt]"
