"""Extras opcionais (Studio e IA local) e o comando certo para instalá-los em cada tipo de instalação.

O núcleo do codar não tem dependências. Pelos pacotes do sistema (apt, zypper, dnf, pacman, apk), o código fica em
/usr/lib/codar e roda no Python do sistema, onde o pip não pode instalar nada (PEP 668). Os extras vão então para um
ambiente virtual do usuário (<dados>/venv), que o lançador /usr/bin/codar passa a usar quando existe.
"""

from __future__ import annotations

import importlib.util
import os
import shutil
import subprocess
import sys
from pathlib import Path

from codar import paths

CPU_WHEELS = "https://abetlen.github.io/llama-cpp-python/whl/cpu"
EXTRAS: dict[str, dict] = {
    "studio": {"module": "textual", "requirements": ["textual[syntax]>=1.0"], "pip_args": [],
               "what": "Studio (IDE no terminal)"},
    "syntax": {"module": "tree_sitter_dart", "requirements": ["tree-sitter>=0.23", "tree-sitter-dart",
               "tree-sitter-javascript", "tree-sitter-typescript", "tree-sitter-go", "tree-sitter-rust"],
               "pip_args": [], "what": "Gramáticas para validação e edição por funções"},
    # --only-binary: sem pacote pronto para esta máquina, falha na hora em vez de compilar o llama.cpp (10+ minutos
    # de CPU a 100%, ruim para notebooks)
    "llm": {"module": "llama_cpp", "requirements": ["llama-cpp-python>=0.3.16"],
            "pip_args": ["--prefer-binary", "--only-binary", "llama-cpp-python", "--extra-index-url", CPU_WHEELS],
            "what": "IA local (llama.cpp)"},
}


def packaged() -> bool:
    """Instalado por pacote do sistema (o lançador /usr/bin/codar define CODAR_PACKAGED)."""
    return os.environ.get("CODAR_PACKAGED") == "1"


def pipx_env() -> bool:
    return "pipx" in Path(sys.prefix).parts


def in_venv() -> bool:
    return sys.prefix != getattr(sys, "base_prefix", sys.prefix)


def venv_dir() -> Path:
    return paths.data_dir() / "venv"


def installed(name: str) -> bool:
    return importlib.util.find_spec(EXTRAS[name]["module"]) is not None


def hint(name: str) -> str:
    """Comando que o usuário deve rodar para ter o extra `name`, de acordo com a forma de instalação."""
    spec = EXTRAS[name]
    if packaged():
        return f"codar extras install {name}"
    reqs = " ".join(f"'{r}'" for r in spec["requirements"])
    if pipx_env():
        args = f" --pip-args='{' '.join(spec['pip_args'])}'" if spec["pip_args"] else ""
        return f"pipx inject codar {reqs}{args}"
    return f"pip install {reqs}" + (" " + " ".join(spec["pip_args"]) if spec["pip_args"] else "")


def _python_for_install() -> list[str] | None:
    """Python cujo pip vai receber os pacotes, ou None se não houver onde instalar com segurança."""
    if packaged():
        venv = venv_dir()
        py = venv / ("Scripts/python.exe" if paths.IS_WIN else "bin/python3")
        if not py.exists():
            print(f"criando o ambiente virtual dos extras em {venv}")
            r = subprocess.run([sys.executable, "-m", "venv", str(venv)])
            if r.returncode != 0 or not py.exists():
                shutil.rmtree(venv, ignore_errors=True)
                raise RuntimeError("não consegui criar o ambiente virtual. No Debian/Ubuntu instale o python3-venv "
                                   "(sudo apt install python3-venv) e tente de novo.")
        return [str(py)]
    if in_venv():
        return [sys.executable]
    return None


def install(names: list[str]) -> int:
    py = _python_for_install()
    if py is None:
        print("codar está no Python do sistema, fora de um ambiente virtual. Para não mexer nele, instale os extras "
              "assim:\n  " + "\n  ".join(hint(n) for n in names), file=sys.stderr)
        return 1
    status = 0
    for name in names:
        spec = EXTRAS[name]
        print(f"instalando {spec['what']}…")
        cmd = py + ["-m", "pip", "install", "--upgrade", *spec["requirements"], *spec["pip_args"]]
        if subprocess.run(cmd).returncode != 0:
            print(f"falhou: {' '.join(cmd)}", file=sys.stderr)
            status = 1
    if status == 0 and packaged():
        print("pronto. O comando codar já usa o ambiente novo; reinicie o daemon com: codar restart")
    return status


def remove() -> int:
    if not packaged():
        print("remova os pacotes com o mesmo pip/pipx usado para instalar o codar", file=sys.stderr)
        return 1
    shutil.rmtree(venv_dir(), ignore_errors=True)
    print(f"removido: {venv_dir()}")
    return 0


def status_lines() -> list[tuple[str, bool, str]]:
    return [(EXTRAS[n]["what"], installed(n), hint(n)) for n in EXTRAS]
