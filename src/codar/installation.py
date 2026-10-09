"""Identifica o código em execução sem consultar a rede nem iniciar o daemon."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from importlib import metadata
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

from codar import __version__


def _git(root: Path, *args: str) -> str | None:
    try:
        result = subprocess.run(["git", "-C", str(root), *args], capture_output=True, text=True, timeout=2)
        return (result.stdout.strip() or None) if result.returncode == 0 else None
    except (OSError, subprocess.TimeoutExpired):
        return None


def _public_url(url: str) -> str:
    """Credenciais e parâmetros de uma URL de instalação não pertencem ao diagnóstico."""
    parts = urlsplit(url)
    return urlunsplit((parts.scheme, parts.netloc.rsplit("@", 1)[-1], parts.path, "", ""))


def installation_info() -> dict:
    module = Path(__file__).resolve().with_name("__init__.py")
    info = {"version": __version__, "python": sys.version.split()[0], "platform": sys.platform,
            "executable": sys.executable, "module": str(module), "source": None, "commit": None,
            "ref": None, "dirty": False}
    # Só considera o checkout que contém este módulo; nunca o repositório do diretório de trabalho.
    root = module.parents[2]
    if module.parent.parent.name == "src" and (root / ".git").exists():
        info.update(source=str(root), commit=_git(root, "rev-parse", "HEAD"),
                    ref=_git(root, "symbolic-ref", "--short", "HEAD"),
                    dirty=bool(_git(root, "status", "--porcelain", "--", "src", "pyproject.toml")))
        return info
    try:
        dist = metadata.distribution("codar")
        # Outra cópia no Python não deve fornecer a procedência da cópia carregada.
        if Path(dist.locate_file("codar/__init__.py")).resolve() != module:
            return info
        direct = json.loads(dist.read_text("direct_url.json") or "{}")
        if not isinstance(direct, dict):
            return info
        url = direct.get("url")
        vcs = direct.get("vcs_info") or {}
        info.update(source=_public_url(url) if isinstance(url, str) else None,
                    commit=vcs.get("commit_id"), ref=vcs.get("requested_revision"))
    except (metadata.PackageNotFoundError, OSError, ValueError, AttributeError, TypeError):
        pass  # Pacotes da distro e wheels podem não trazer procedência Git.
    return info


def daemon_mismatch(remote: dict, local: dict | None = None) -> str | None:
    local = local or installation_info()
    if remote.get("version") != local["version"]:
        return f"daemon {remote.get('version', '?')}, CLI {local['version']}"
    installed = remote.get("installation") or {}
    if installed.get("commit") and local["commit"] and installed["commit"] != local["commit"]:
        return "daemon e CLI usam commits diferentes"
    if installed.get("module") and os.path.realpath(installed["module"]) != local["module"]:
        return "daemon e CLI usam instalações diferentes"
    return None
