"""Instala a wheel incluída no arquivo de distribuição usando o pipx do usuário."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys


def verify_bundle(root: Path) -> dict:
    manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
    if not isinstance(manifest, dict) or not isinstance(manifest.get("sha256"), dict):
        raise ValueError("Manifesto inválido")
    for name, expected in manifest["sha256"].items():
        if not isinstance(name, str) or not isinstance(expected, str):
            raise ValueError("Entrada inválida no manifesto")
        path = (root / name).resolve()
        if not path.is_relative_to(root.resolve()) or not path.is_file():
            raise ValueError(f"Arquivo ausente ou inválido: {name}")
        if hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            raise ValueError(f"SHA-256 não confere: {name}. Baixe o pacote novamente.")
    wheel = manifest["wheel"]
    if wheel not in manifest["sha256"] or Path(wheel).name != wheel:
        raise ValueError("Wheel não registrada no manifesto")
    return manifest


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--core", action="store_true", help="instala só a CLI, sem Studio e gramáticas opcionais")
    parser.add_argument("--verify-only", action="store_true", help="confere os arquivos sem instalar")
    parser.add_argument("--no-path", action="store_true", help="não executa pipx ensurepath")
    args = parser.parse_args(argv)
    if sys.version_info < (3, 10):
        print("É necessário Python 3.10 ou mais recente.", file=sys.stderr)
        return 2
    root = Path(__file__).resolve().parent
    try:
        manifest = verify_bundle(root)
        version = manifest["version"]
        print(f"Arquivos do Codar {version} conferidos.")
        if args.verify_only:
            return 0
        executable = shutil.which("pipx")
        if executable:
            pipx = [executable]
        elif importlib.util.find_spec("pipx"):
            pipx = [sys.executable, "-m", "pipx"]
        else:
            print("Instale pipx antes de continuar. Veja o README incluído neste arquivo.", file=sys.stderr)
            return 2
        requirement = str(root / manifest["wheel"]) + ("" if args.core else "[studio,syntax]")
        subprocess.run([*pipx, "install", "--force", "--python", sys.executable,
                        "--pip-args=--no-cache-dir", requirement], check=True)
        bindir = Path(subprocess.check_output([*pipx, "environment", "--value", "PIPX_BIN_DIR"], text=True).strip())
        codar = bindir / ("codar.exe" if os.name == "nt" else "codar")
        installed = json.loads(subprocess.check_output([str(codar), "version", "--json"], text=True))
        if installed.get("version") != version:
            raise ValueError("A versão instalada não corresponde ao pacote")
        if not args.no_path:
            subprocess.run([*pipx, "ensurepath", "--prepend"], check=True)
        print(f"Codar {version} instalado em {codar}.")
        print("Abra um novo terminal para usar o PATH atualizado.")
        print(f'Para reiniciar uma sessão anterior: "{codar}" restart')
        print("IA local é opcional: codar extras install llm; codar init")
        if (root / "codar.vsix").is_file():
            print(f'VS Code: code --install-extension "{root / "codar.vsix"}" --force')
        return 0
    except (OSError, ValueError, KeyError, subprocess.CalledProcessError) as exc:
        print(f"Instalação não concluída: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
