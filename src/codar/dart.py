"""Projetos Dart/Flutter: pubspec mais próximo e ferramentas do SDK, sem dependências Python extras."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class PubProject:
    root: Path
    name: str
    flutter: bool
    dependencies: frozenset[str]

    @property
    def tool(self) -> str:
        return "flutter" if self.flutter else "dart"


def project_for(file: Path, root: Path) -> PubProject | None:
    """Respeita projetos aninhados; não procura acima da pasta aberta no Studio."""
    file, root = file.resolve(), root.resolve()
    if not file.is_relative_to(root):
        return None
    for folder in (file.parent, *file.parent.parents):
        manifest = folder / "pubspec.yaml"
        if manifest.is_file():
            try:
                text = manifest.read_text(encoding="utf-8")
            except OSError:
                return None
            # Campos simples do pubspec padrão; não executa nem carrega tags YAML.
            name = re.search(r"^name:\s*['\"]?([a-zA-Z_]\w*)", text, re.M)
            deps = set()
            section = ""
            flutter = False
            package = ""
            for line in text.splitlines():
                top = re.match(r"^([a-zA-Z_]\w*):", line)
                if top:
                    section, package = top[1], ""
                if section not in ("dependencies", "dev_dependencies", "dependency_overrides"):
                    continue
                item = re.match(r"^  ['\"]?([a-zA-Z_]\w*)['\"]?:\s*(.*)", line)
                if item:
                    package = item[1]
                    deps.add(package)
                    if package == "flutter" and re.search(r"\bsdk:\s*flutter\b", item[2]):
                        flutter = True
                if package == "flutter" and re.match(r"^\s+sdk:\s*['\"]?flutter\b", line):
                    flutter = True
            return PubProject(folder, name[1] if name else "", flutter, frozenset(deps))
        if folder == root:
            break
    return None


def runner(file: Path, root: Path) -> tuple[tuple[str, ...], Path]:
    project = project_for(file, root)
    if project and project.flutter:
        relative = file.resolve().relative_to(project.root)
        if relative.parts[0] == "test" and file.name.endswith("_test.dart"):
            return ("flutter", "test", "{file}"), project.root
        if relative.parts[0] == "lib":
            main = project.root / "lib" / "main.dart"
            return ("flutter", "run", "--target", str(main if main.is_file() else file)), project.root
    return ("dart", "run", "{file}"), project.root if project else root
