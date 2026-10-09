"""`codar doctor`: diagnóstico do ambiente com correções sugeridas."""

from __future__ import annotations

import importlib.util
import os
import platform
import shutil
import sqlite3
import sys

from codar import config, paths
from codar.extras import hint


def _meminfo() -> tuple[int, int]:
    try:
        data = {}
        with open("/proc/meminfo", encoding="ascii") as fh:
            for line in fh:
                k, v = line.split(":", 1)
                data[k] = int(v.split()[0]) // 1024
        return data.get("MemTotal", 0), data.get("MemAvailable", 0)
    except OSError:
        return 0, 0


def checks() -> list[tuple[str, str, str, str]]:
    """[(status ok|warn|fail, item, detalhe, correção)]"""
    out = []
    from codar.installation import daemon_mismatch, installation_info

    installation = installation_info()
    revision = f" · commit {installation['commit'][:12]}" if installation["commit"] else ""
    out.append(("ok", "codar", f"{installation['version']}{revision} · {installation['module']}", ""))
    cfg = config.load()
    v = sys.version_info
    out.append(("ok" if v >= (3, 10) else "fail", "python", sys.version.split()[0], "use Python >= 3.10"))
    try:
        con = sqlite3.connect(":memory:")
        con.execute("CREATE VIRTUAL TABLE t USING fts5(a)")
        out.append(("ok", "sqlite/fts5", sqlite3.sqlite_version, ""))
    except sqlite3.OperationalError:
        out.append(("fail", "sqlite/fts5", "FTS5 ausente", "instale um Python com SQLite compilado com FTS5"))
    total, avail = _meminfo()
    if total:
        budget = int(cfg["memory"]["budget_mb"])
        out.append(("ok" if avail > budget * 0.8 else "warn", "ram do sistema", f"{total} MB total, {avail} MB livres",
                    f"o orçamento é {budget} MB; feche programas ou reduza [memory] budget_mb"))
    flags = ""
    try:
        flags = open("/proc/cpuinfo", encoding="ascii").read()
    except OSError:
        pass
    simd = [f for f in ("avx512f", "avx2", "fma", "f16c", "neon", "asimd") if f" {f}" in flags]
    out.append(("ok" if simd or not flags else "warn", "cpu", f"{platform.machine()} {os.cpu_count()} threads "
                f"{'/'.join(simd) or 'sem AVX2'}", "sem AVX2 o Estágio 2 fica bem mais lento"))
    if importlib.util.find_spec("llama_cpp"):
        import llama_cpp

        out.append(("ok", "llama-cpp-python", getattr(llama_cpp, "__version__", "?"), ""))
    else:
        out.append(("warn", "llama-cpp-python", "não instalado (Estágio 2 desativado)", hint("llm")))
    from codar.engine.models import resolve_model

    card, path = resolve_model(cfg["model"])
    if path and path.is_file():
        try:
            from codar.engine.gguf import estimate, read_gguf

            g = read_gguf(path)
            est = estimate(g, int(cfg["model"]["n_ctx"]), int(cfg["model"].get("n_ubatch") or cfg["model"]["n_batch"]),
                           use_mmap=bool(cfg["model"].get("use_mmap")))
            hard = int(cfg["memory"]["budget_mb"]) * float(cfg["memory"]["hard_pct"]) / 100
            out.append(("ok" if est.total_mb <= hard else "fail", "modelo",
                        f"{path.name} ({g.arch}, ~{est.total_mb:.0f} MB estimados, teto {hard:.0f} MB)",
                        "escolha um modelo menor: codar model list"))
        except Exception as exc:
            out.append(("fail", "modelo", f"{path.name}: {exc}", "baixe de novo: codar model pull"))
    else:
        out.append(("warn", "modelo", f"{path or cfg['model']['name']} não encontrado", "codar model pull"))
    if importlib.util.find_spec("textual"):
        out.append(("ok", "studio (textual)", "instalado", ""))
    else:
        out.append(("warn", "studio (textual)", "não instalado", hint("studio")))
    from codar.daemon.memguard import cgroup_limit
    from codar.daemonctl import memory_controller_delegated

    if sys.platform.startswith("linux"):
        if memory_controller_delegated() or cgroup_limit():
            out.append(("ok", "teto duro de RAM", "cgroup v2 (systemd-run --user MemoryMax)", ""))
        else:
            out.append(("warn", "teto duro de RAM", "controlador 'memory' não delegado ao usuário; só o watchdog atua",
                        "sudo mkdir -p /etc/systemd/system/user@.service.d && printf '[Service]\\nDelegate=memory pids "
                        "cpu\\n' | sudo tee /etc/systemd/system/user@.service.d/delegate.conf && sudo systemctl "
                        "daemon-reload  (depois faça logout/login)"))
    elif sys.platform == "win32":
        out.append(("ok", "teto duro de RAM", "Job Object (JOB_OBJECT_LIMIT_PROCESS_MEMORY)", ""))
    else:
        out.append(("warn", "teto duro de RAM", "macOS não oferece limite de RSS; só o watchdog atua", ""))
    ep = paths.discover_endpoint()
    if ep:
        try:
            from codar.client import Client

            with Client.connect(autostart=False, timeout=3) as c:
                info = c.ping()
            mismatch = daemon_mismatch(info, installation)
            detail = f"online pid {info['pid']} · versão {info['version']} em {ep.uri()}"
            out.append(("warn" if mismatch else "ok", "daemon", detail + (f"; {mismatch}" if mismatch else ""),
                        "codar restart" if mismatch else ""))
        except Exception as exc:
            out.append(("warn", "daemon", f"endpoint existe mas não responde ({exc})", "codar restart"))
    else:
        out.append(("warn", "daemon", "parado", "codar start"))
    from codar.plugin_loader import discover

    bundle = discover(cfg)
    errs = [e for p in bundle.plugins for e in p.errors]
    out.append(("ok" if not errs else "warn", "plugins", f"{len(bundle.plugins)} plugins, {len(bundle.patterns)} padrões, "
                f"{len(bundle.rules)} regras" + (f"; {len(errs)} erros: {errs[0]}" if errs else ""), "corrija o TOML indicado"))
    out.append(("ok" if shutil.which("code") else "warn", "vscode cli", shutil.which("code") or "ausente",
                "instale o comando `code` no PATH para alternar com o VS Code"))
    if sys.platform.startswith("linux"):
        tools = [t for t in ("xdotool", "xclip", "xsel", "wtype", "ydotool", "wl-copy") if shutil.which(t)]
        out.append(("ok" if tools else "warn", "hook global", ", ".join(tools) or "sem ferramentas",
                    "X11: xdotool + xclip | Wayland: wtype + wl-clipboard"))
    return out


def cmd_doctor(args) -> int:
    from codar.cli.hud import Hud

    hud = Hud(sys.stdout)
    print(hud.rule("codar doctor"))
    worst = 0
    for status, item, detail, fix in checks():
        color = {"ok": "mint", "warn": "orange", "fail": "red"}[status]
        mark = {"ok": "✓", "warn": "!", "fail": "✖"}[status]
        print(" " + hud.c(mark, color, bold=True) + " " + hud.c(f"{item:20}", "text") + hud.c(detail, "green" if status == "ok" else color))
        if status != "ok" and fix:
            print("   " + hud.c("→ " + fix, "dim"))
        worst = max(worst, {"ok": 0, "warn": 1, "fail": 2}[status])
    return 0 if worst < 2 else 1
