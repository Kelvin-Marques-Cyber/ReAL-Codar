"""Confere a versão Python e os manifestos distribuídos; não requer instalar o projeto."""

from __future__ import annotations

import argparse
import ast
import json
import re
from pathlib import Path


def check(root: Path, tag: str | None = None) -> list[str]:
    def read(path: str) -> str:
        return (root / path).read_text(encoding="utf-8")

    module = ast.parse(read("src/codar/__init__.py"))
    version = next(ast.literal_eval(node.value) for node in module.body if isinstance(node, ast.Assign)
                   and any(isinstance(target, ast.Name) and target.id == "__version__" for target in node.targets))
    errors = []
    if not re.fullmatch(r"\d+\.\d+\.\d+", version):
        errors.append(f"versão de release inválida: {version}")

    versions = {}
    for path, pattern in {
        "packaging/rpm/codar.spec": r"^Version:\s*(\S+)",
        "packaging/debian/changelog": r"\Acodar \(([^)]+)-\d+\)",
        "clients/powershell/Codar/Codar.psd1": r"ModuleVersion\s*=\s*'([^']+)'",
        "packaging/codar.1": r'"codar ([^"]+)"',
    }.items():
        match = re.search(pattern, read(path), re.MULTILINE)
        versions[path] = match.group(1) if match else None
    versions["clients/vscode/package.json"] = json.loads(read("clients/vscode/package.json"))["version"]
    lock = json.loads(read("clients/vscode/package-lock.json"))
    versions["clients/vscode/package-lock.json"] = lock["version"]
    versions["clients/vscode/package-lock.json packages['']"] = lock["packages"][""]["version"]
    for path, actual in versions.items():
        if actual != version:
            errors.append(f"{path}: {actual!r}; esperado {version}")

    # TOML é lido pelo mesmo compatível usado pelo projeto (Python 3.10: tomli).
    import sys

    sys.path.insert(0, str(root / "src"))
    try:
        from codar._compat import tomllib

        project = tomllib.loads(read("pyproject.toml"))
    finally:
        sys.path.pop(0)
    if ("version" in project["project"] or "version" not in project["project"].get("dynamic", []) or
            project["tool"]["setuptools"].get("dynamic", {}).get("version") != {"attr": "codar.__version__"}):
        errors.append("pyproject.toml deve obter a versão de codar.__version__")
    if f"## [{version}]" not in read("CHANGELOG.md"):
        errors.append(f"CHANGELOG.md não tem a seção [{version}]")
    if tag is not None and tag != f"v{version}":
        errors.append(f"tag {tag!r}; esperado v{version}")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tag", help="tag que será publicada, ex.: v0.1.1")
    args = parser.parse_args()
    errors = check(Path(__file__).resolve().parents[1], args.tag)
    if errors:
        print("\n".join(errors))
        return 1
    print("Versões dos pacotes e changelog consistentes.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
