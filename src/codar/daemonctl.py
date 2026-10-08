"""Ciclo de vida do daemon: subir em segundo plano (com teto de memória do SO quando possível), parar, status."""

from __future__ import annotations

import os
import shutil
import signal
import subprocess
import sys
import time
from pathlib import Path

from codar import config, paths


def memory_controller_delegated() -> bool:
    """True se o systemd de usuário pode aplicar MemoryMax (controlador 'memory' delegado)."""
    if not sys.platform.startswith("linux") or not shutil.which("systemd-run"):
        return False
    base = Path(f"/sys/fs/cgroup/user.slice/user-{os.getuid()}.slice/user@{os.getuid()}.service")
    try:
        return "memory" in (base / "cgroup.subtree_control").read_text().split()
    except OSError:
        return False


def daemon_command(cfg: dict) -> tuple[list[str], str]:
    cmd = [sys.executable, "-m", "codar.daemon"]
    enforce = cfg["memory"].get("enforce", "auto")
    if enforce in ("auto", "cgroup") and memory_controller_delegated():
        budget = int(cfg["memory"]["budget_mb"])
        soft = int(budget * float(cfg["memory"]["soft_pct"]) / 100)
        return (["systemd-run", "--user", "--scope", "--quiet", "--collect",
                 "-p", f"MemoryMax={budget}M", "-p", f"MemoryHigh={soft}M", "-p", "MemorySwapMax=0", "--"] + cmd,
                f"cgroup MemoryMax={budget}M")
    return cmd, "watchdog"


def start_daemon(wait: float = 30.0, cfg: dict | None = None) -> tuple[int, str]:
    """Sobe o daemon desacoplado do terminal e espera ele responder. Retorna (pid, modo de contenção)."""
    from codar.client import Client, DaemonNotRunning

    cfg = cfg or config.load()
    paths.ensure_private_dir(paths.runtime_dir())
    paths.log_dir().mkdir(parents=True, exist_ok=True)
    cmd, mode = daemon_command(cfg)
    env = os.environ.copy()
    env.setdefault("MALLOC_ARENA_MAX", str(cfg["memory"].get("malloc_arena_max", 2)))
    env["PYTHONUNBUFFERED"] = "1"
    env.setdefault("NEEDLE_TELEMETRY", "0")
    env.setdefault("DO_NOT_TRACK", "1")
    env.setdefault("HF_HUB_DISABLE_TELEMETRY", "1")
    out = open(paths.log_dir() / "daemon.out", "ab")  # noqa: SIM115 - herdado pelo processo filho
    kwargs: dict = {"stdin": subprocess.DEVNULL, "stdout": out, "stderr": out, "env": env, "close_fds": True}
    if paths.IS_WIN:
        kwargs["creationflags"] = 0x00000008 | 0x00000200 | 0x08000000  # DETACHED | NEW_GROUP | NO_WINDOW
    else:
        kwargs["start_new_session"] = True
    proc = subprocess.Popen(cmd, **kwargs)
    out.close()
    deadline = time.monotonic() + wait
    while time.monotonic() < deadline:
        if proc.poll() is not None and mode != "watchdog":
            cmd, mode = daemon_command({**cfg, "memory": {**cfg["memory"], "enforce": "soft"}})
            proc = subprocess.Popen(cmd, **kwargs)
            continue
        if proc.poll() is not None:
            raise RuntimeError("o daemon terminou ao iniciar; veja " + str(paths.log_dir() / "daemon.out") +
                               "\n" + tail_log())
        if paths.discover_endpoint():
            try:
                with Client.connect(autostart=False, timeout=2.0) as c:
                    c.call("ping")
                return proc.pid, mode
            except (DaemonNotRunning, OSError, ConnectionError):
                pass
        time.sleep(0.05)
    raise TimeoutError(f"o daemon não respondeu em {wait:.0f}s\n" + tail_log())


def tail_log(n: int = 15) -> str:
    for name in ("daemon.out", "daemon.log"):
        f = paths.log_dir() / name
        if f.exists():
            return "\n".join(f.read_text(encoding="utf-8", errors="replace").splitlines()[-n:])
    return ""


def stop_daemon(timeout: float = 10.0) -> bool:
    from codar.client import Client, DaemonNotRunning

    pid = None
    try:
        pid = int(paths.pid_file().read_text())
    except (OSError, ValueError):
        pass
    try:
        with Client.connect(autostart=False, timeout=3.0) as c:
            c.call("shutdown")
    except (DaemonNotRunning, OSError, ConnectionError):
        if pid and not paths.IS_WIN:
            try:
                os.kill(pid, signal.SIGTERM)
            except ProcessLookupError:
                pid = None
    deadline = time.monotonic() + timeout
    while pid and time.monotonic() < deadline:
        if not _alive(pid):
            break
        time.sleep(0.05)
    for f in (paths.endpoint_file(), paths.pid_file()):
        if f.exists() and (pid is None or not _alive(pid)):
            try:
                f.unlink()
            except OSError:
                pass
    return pid is None or not _alive(pid)


def _alive(pid: int) -> bool:
    if paths.IS_WIN:
        out = subprocess.run(["tasklist", "/FI", f"PID eq {pid}"], capture_output=True, text=True)
        return str(pid) in out.stdout
    try:  # se o daemon é nosso filho (ex.: autostart pela TUI), colhe o zumbi
        if os.waitpid(pid, os.WNOHANG)[0] == pid:
            return False
    except ChildProcessError:
        pass
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
