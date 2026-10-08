"""Caminhos por sistema operacional e descoberta do endpoint IPC.

Contrato com os clientes (VS Code, Neovim, PowerShell, shell):
  1. ``CODAR_ENDPOINT`` (``unix:/x.sock`` | ``pipe:\\\\.\\pipe\\nome`` | ``tcp://127.0.0.1:porta``)
     tem precedência; o token TCP vem de ``CODAR_TOKEN``.
  2. Caso contrário leem ``<runtime>/endpoint.json`` escrito pelo daemon, onde
     ``<runtime>`` = ``$CODAR_HOME/run`` | ``%LOCALAPPDATA%\\codar\\run`` |
     ``$XDG_RUNTIME_DIR/codar`` | ``/tmp/codar-<uid>``.
"""

from __future__ import annotations

import getpass
import hashlib
import json
import os
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

APP = "codar"
IS_WIN = sys.platform == "win32"
IS_MAC = sys.platform == "darwin"
_UDS_MAX = 100  # limite seguro (108 no Linux, 104 no macOS)


def _home() -> Path | None:
    v = os.environ.get("CODAR_HOME")
    return Path(v).expanduser().resolve() if v else None


def config_dir() -> Path:
    if h := _home():
        return h / "config"
    if IS_WIN:
        return Path(os.environ.get("APPDATA") or Path.home() / "AppData" / "Roaming") / APP
    return Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config") / APP


def data_dir() -> Path:
    if h := _home():
        return h / "data"
    if IS_WIN:
        return Path(os.environ.get("LOCALAPPDATA") or Path.home() / "AppData" / "Local") / APP
    return Path(os.environ.get("XDG_DATA_HOME") or Path.home() / ".local" / "share") / APP


def runtime_dir() -> Path:
    if h := _home():
        return h / "run"
    if IS_WIN:
        return data_dir() / "run"
    xdg = os.environ.get("XDG_RUNTIME_DIR")
    if xdg and Path(xdg).is_dir():
        return Path(xdg) / APP
    return Path(tempfile.gettempdir()) / f"{APP}-{os.getuid()}"


def models_dir() -> Path:
    return data_dir() / "models"


def db_path() -> Path:
    return data_dir() / "patterns.db"


def log_dir() -> Path:
    return data_dir() / "logs"


def config_file() -> Path:
    return config_dir() / "config.toml"


def user_plugins_dir() -> Path:
    return config_dir() / "plugins"


def usage_file() -> Path:
    return data_dir() / "usage.json"


def endpoint_file() -> Path:
    return runtime_dir() / "endpoint.json"


def pid_file() -> Path:
    return runtime_dir() / "daemon.pid"


def ensure_private_dir(path: Path) -> Path:
    """Cria o diretório com permissão 0700 e recusa diretórios de outro usuário."""
    path.mkdir(parents=True, exist_ok=True)
    if not IS_WIN:
        st = path.stat()
        if st.st_uid != os.getuid():
            raise PermissionError(f"{path} pertence a outro usuário (uid {st.st_uid})")
        if st.st_mode & 0o077:
            path.chmod(0o700)
    return path


@dataclass(frozen=True)
class Endpoint:
    transport: str  # unix | pipe | tcp
    address: str  # caminho do socket, nome do pipe ou host:porta
    token: str = ""

    def uri(self) -> str:
        return f"tcp://{self.address}" if self.transport == "tcp" else f"{self.transport}:{self.address}"

    def to_json(self, pid: int, version: str) -> str:
        return json.dumps(
            {"transport": self.transport, "address": self.address, "token": self.token,
             "uri": self.uri(), "pid": pid, "version": version},
            ensure_ascii=False,
        )


def parse_endpoint(spec: str, token: str = "") -> Endpoint:
    spec = spec.strip()
    if spec.startswith("tcp://"):
        return Endpoint("tcp", spec[6:], token)
    if spec.startswith("unix:"):
        return Endpoint("unix", spec[5:], token)
    if spec.startswith("pipe:"):
        return Endpoint("pipe", spec[5:], token)
    if spec.startswith("\\\\.\\pipe\\"):
        return Endpoint("pipe", spec, token)
    return Endpoint("unix", spec, token)


def default_endpoint() -> Endpoint:
    if IS_WIN:
        user = "".join(c for c in getpass.getuser() if c.isalnum()) or "user"
        suffix = f"-{hashlib.sha1(str(_home()).encode()).hexdigest()[:8]}" if _home() else ""
        return Endpoint("pipe", f"\\\\.\\pipe\\{APP}-{user}{suffix}")
    sock = runtime_dir() / f"{APP}.sock"
    if len(str(sock)) > _UDS_MAX:
        digest = hashlib.sha1(str(sock).encode()).hexdigest()[:10]
        sock = Path(tempfile.gettempdir()) / f"{APP}-{os.getuid()}" / f"{digest}.sock"
    return Endpoint("unix", str(sock))


def discover_endpoint() -> Endpoint | None:
    """Endpoint de um daemon em execução (ou o configurado por variável de ambiente)."""
    if spec := os.environ.get("CODAR_ENDPOINT"):
        return parse_endpoint(spec, os.environ.get("CODAR_TOKEN", ""))
    try:
        data = json.loads(endpoint_file().read_text(encoding="utf-8"))
        return Endpoint(data["transport"], data["address"], data.get("token", ""))
    except (OSError, ValueError, KeyError):
        return None
