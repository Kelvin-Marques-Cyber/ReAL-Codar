"""CLI `codar`: pipes Unix, REPL, Studio (TUI), daemon, banco de padrões, modelos, consultor de projeto.

Caminho rápido: `codar run` importa só o SDK (biblioteca padrão) e fala com o daemon pelo socket.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
from pathlib import Path

from codar import __version__

EXIT_OK, EXIT_ERR, EXIT_UNRESOLVED, EXIT_NO_DAEMON = 0, 1, 3, 4


def _hud(stream=None):
    from codar.cli.hud import Hud

    return Hud(stream or sys.stderr)


def _client(args, need_model: bool = True):
    if getattr(args, "local", False):
        from codar.engine.local import LocalClient

        return LocalClient(with_model=need_model)
    from codar.client import Client

    return Client.connect(autostart=not getattr(args, "no_autostart", False))


def _stages(raw: str | None) -> tuple[int, ...]:
    if not raw:
        return (0, 1, 2)
    return tuple(int(x) for x in raw.replace(" ", "").split(",") if x != "")


def _read_input(args) -> str | None:
    if getattr(args, "intent", None):
        return " ".join(args.intent)
    if not sys.stdin.isatty():
        return sys.stdin.read()
    return None


# =============================================================================== run / compile / audit

def print_result(res: dict, args, hud) -> None:
    from codar.cli.hud import SEV_COLOR, STAGE_COLOR, STAGE_LABEL

    code = res.get("annotated") if getattr(args, "hints", False) and res.get("annotated") else res["code"]
    if getattr(args, "json", False):
        print(json.dumps(res, ensure_ascii=False, indent=2))
        return
    sys.stdout.write(code.rstrip("\n") + "\n")
    sys.stdout.flush()
    if getattr(args, "quiet", False) or hud.mode == "none" and not getattr(args, "verbose", False):
        if res.get("findings") and not getattr(args, "quiet", False):
            for f in res["findings"]:
                if f["severity"] in ("warning", "error", "critical"):
                    print(f"codar: {f['severity']} {f['id']} linha {f['line']}: {f['message']}", file=sys.stderr)
        return
    stage = res["stage"]
    parts = [hud.pill(STAGE_LABEL.get(stage, stage), STAGE_COLOR.get(stage, "red")),
             hud.c(res["source"], "green"), hud.c(f"{res['timings'].get('total_ms', 0):.2f}MS", "mint")]
    if res.get("cached"):
        parts.append(hud.c("CACHE", "cyan"))
    n = len(res.get("findings", []))
    parts.append(hud.c(f"AUDIT {'✓' if not n else n}", "green" if not n else "orange"))
    print(" ".join(parts), file=sys.stderr)
    for f in res.get("findings", []):
        mark = "✖" if f["severity"] in ("critical", "error") else "⚠" if f["severity"] == "warning" else "ℹ"
        print("  " + hud.c(f"{mark} {f['id']}", SEV_COLOR.get(f["severity"], "orange"), bold=True) + " " +
              hud.c(f"L{f['line']}", "dim") + " " + hud.c(f["message"], "text") +
              (hud.c(f"  → {f['suggestion']}", "dim") if f.get("suggestion") else ""), file=sys.stderr)
    for note in res.get("notes", []):
        print("  " + hud.bullet(note, "dim"), file=sys.stderr)
    if res.get("slots") and getattr(args, "verbose", False):
        print("  " + hud.kv("slots", ", ".join(f"{k}={v}" for k, v in res["slots"].items())), file=sys.stderr)


def cmd_run(args) -> int:
    from codar.client import DaemonNotRunning, RpcError

    text = _read_input(args)
    if not text or not text.strip():
        print("uso: codar run \"intenção\" [-l linguagem]   (ou via stdin)", file=sys.stderr)
        return EXIT_ERR
    hud = _hud()
    intents = [ln for ln in text.splitlines() if ln.strip()] if args.each else [text.strip("\n")]
    try:
        client = _client(args)
    except (DaemonNotRunning, OSError, TimeoutError, RuntimeError) as exc:
        print(f"codar: daemon indisponível: {exc}", file=sys.stderr)
        return EXIT_NO_DAEMON
    before = ""
    ctx = args.context or (args.file if args.file and args.file != "-" and Path(args.file).is_file() else None)
    if ctx:  # a intenção entra logo depois desse código (o fim do arquivo, ou o trecho que o editor mandou)
        before = "\n".join(Path(ctx).read_text(encoding="utf-8", errors="replace").splitlines()[-200:]) + "\n"
    status = EXIT_OK
    with client:
        for k, intent in enumerate(intents):
            on_delta = None
            if args.stream and hud.mode != "none":
                def on_delta(d: str) -> None:
                    sys.stderr.write(hud.c(d, "dim"))
                    sys.stderr.flush()
            try:
                res = client.translate(intent, args.lang, file=args.file, before=before, indent=args.indent or "", stages=_stages(args.stages),
                                       audit=not args.no_audit, hints=args.hints, mode=args.mode, on_delta=on_delta,
                                       indent_unit=args.indent_unit)
            except RpcError as exc:
                cands = (exc.data or {}).get("candidates") or []
                print(hud.pill("UNRESOLVED", "red") + " " + hud.c(exc.message, "text"), file=sys.stderr)
                for cnd in cands[:3]:
                    print("  " + hud.bullet(f"{cnd['id']} ({cnd['score']:.2f}) {cnd['title']}", "dim"), file=sys.stderr)
                status = EXIT_UNRESOLVED
                continue
            if args.stream and hud.mode != "none":
                sys.stderr.write("\n")
            if k:
                print()
            print_result(res, args, hud)
    return status


def cmd_compile(args) -> int:
    src = Path(args.file).read_text(encoding="utf-8") if args.file and args.file != "-" else sys.stdin.read()
    args.intent, args.each, args.mode, args.file = None, False, "block", None
    sys.stdin = _StrIn(src)
    return cmd_run(args)


class _StrIn:
    def __init__(self, text: str) -> None:
        self.text = text

    def isatty(self) -> bool:
        return False

    def read(self) -> str:
        return self.text


def cmd_servir(args) -> int:
    """Ver no celular: serve uma pasta (páginas, imagens, gráficos salvos) na rede local, ou repassa um servidor de
    desenvolvimento que só escuta em localhost (--proxy 5173). Mostra os endereços e o QR code."""
    import time

    from codar import rede
    from codar.qr import QR

    hud = _hud(sys.stdout)
    try:
        if args.proxy:
            servidor = rede.ProxyRede(args.proxy, porta=args.porta, rede=not args.local).iniciar()
            url, local, titulo = servidor.url_rede, f"http://127.0.0.1:{args.proxy}/", f"repassando a porta {args.proxy}"
        else:
            pasta = Path(args.pasta).expanduser().resolve()
            if not pasta.is_dir():
                print(f"codar: {pasta} não é uma pasta", file=sys.stderr)
                return EXIT_ERR
            servidor = rede.ServidorPrevia(pasta, porta=args.porta, rede=not args.local).iniciar()
            url, local, titulo = servidor.url_rede or servidor.url_local, servidor.url_local, f"prévia de {pasta}"
    except OSError as exc:
        print(f"codar: não consegui abrir a porta: {exc.strerror or exc}", file=sys.stderr)
        return EXIT_ERR
    print(hud.pill("REDE", "mint") + " " + hud.c(titulo, "text", bold=True))
    print("  neste computador:  " + hud.c(local, "cyan"))
    if not args.local:
        print("  no celular (mesmo Wi-Fi):  " + hud.c(url, "mint", bold=True))
        print(QR(url).texto(cores=hud.mode != "none"))
        if aviso := rede.aviso_firewall(servidor.porta):
            print("  " + hud.c(aviso, "orange"))
    print(hud.c("  Ctrl+C para parar", "dim"))
    try:
        while True:
            time.sleep(3600)
    except KeyboardInterrupt:
        servidor.parar()
    return EXIT_OK


def cmd_explicar(args) -> int:
    """Explica o erro de um programa: lê a saída pelo stdin (python app.py 2>&1 | codar explicar) ou roda o comando
    passado depois de -- e explica se ele falhar."""
    import subprocess

    from codar.explicar import explicar

    codigo = 0
    comando = args.comando[1:] if args.comando[:1] == ["--"] else args.comando
    if comando:
        r = subprocess.run(comando, capture_output=True, text=True)
        sys.stdout.write(r.stdout)
        sys.stdout.flush()
        sys.stderr.write(r.stderr)
        sys.stderr.flush()
        saida, codigo = r.stdout + r.stderr, r.returncode
        if codigo == 0:
            return EXIT_OK
    else:
        saida = sys.stdin.read()
    exp = explicar(saida, Path.cwd())
    if exp is None:
        print("codar: não reconheci um erro nessa saída", file=sys.stderr)
        return codigo or EXIT_ERR
    hud = _hud(sys.stdout)
    arquivo = exp.arquivo
    if arquivo and Path(arquivo).is_absolute() and Path(arquivo).is_relative_to(Path.cwd()):
        arquivo = str(Path(arquivo).relative_to(Path.cwd()))
    onde = f" · linha {exp.linha} de {arquivo}" if arquivo and exp.linha else ""
    print(hud.pill("ERRO", "red") + " " + hud.c(f"{exp.tipo}{onde}", "red", bold=True))
    print("  " + hud.c(exp.titulo, "text", bold=True))
    if exp.trecho:
        print("    " + hud.c(exp.trecho.strip(), "moon"))
    print("  " + hud.c("o que aconteceu: ", "dim") + exp.oque)
    print("  " + hud.c("como corrigir:   ", "dim") + hud.c(exp.como, "mint"))
    return codigo or 1


def cmd_audit(args) -> int:
    from codar import langs

    path = None if not args.file or args.file == "-" else Path(args.file)
    code = path.read_text(encoding="utf-8") if path else sys.stdin.read()
    lang = langs.try_resolve(args.lang) or langs.from_path(path)
    if lang is None:
        print("codar: informe --lang (não deu para detectar pela extensão)", file=sys.stderr)
        return EXIT_ERR
    with _client(args, need_model=False) as c:
        res = c.audit(code, lang.id, hints=args.hints)
    if args.json:
        print(json.dumps(res, ensure_ascii=False, indent=2))
        return EXIT_OK if not res["findings"] else 2
    if args.hints:
        sys.stdout.write(res["annotated"].rstrip("\n") + "\n")
        return EXIT_OK
    hud = _hud(sys.stdout)
    from codar.cli.hud import SEV_COLOR

    name = str(path) if path else "<stdin>"
    print(hud.pill("AUDIT", "red") + " " + hud.c(name, "green") + " " +
          hud.c(f"{len(res['findings'])} achado(s) · {res['ms']:.2f}MS", "mint"))
    for f in res["findings"]:
        print("  " + hud.c(f"{f['severity'].upper():9}", SEV_COLOR.get(f["severity"], "orange"), bold=True) +
              hud.c(f"{f['id']:8}", "red") + hud.c(f"{name}:{f['line']}:{f['col']}", "dim") + "  " +
              hud.c(f["message"], "text"))
        if f.get("suggestion"):
            print("  " + " " * 17 + hud.c("→ " + f["suggestion"], "green"))
    worst = max((f["severity"] for f in res["findings"]), key=lambda s: ["info", "warning", "error", "critical"].index(s),
                default="info")
    return 2 if worst in ("error", "critical") else EXIT_OK


# =============================================================================== daemon

def cmd_start(args) -> int:
    if args.foreground:
        from codar.daemon.server import main as dmain

        return dmain(["--foreground"])
    from codar import paths
    from codar.daemonctl import start_daemon

    hud = _hud(sys.stdout)
    if paths.discover_endpoint():
        try:
            from codar.client import Client

            with Client.connect(autostart=False, timeout=2) as c:
                info = c.ping()
            print(hud.pill("DAEMON", "green") + " " + hud.c(f"já em execução (pid {info['pid']})", "green"))
            return EXIT_OK
        except Exception:
            pass
    try:
        pid, mode = start_daemon()
    except (RuntimeError, TimeoutError) as exc:
        print(hud.pill("ERRO", "red") + f" {exc}", file=sys.stderr)
        return EXIT_ERR
    print(hud.pill("DAEMON ONLINE", "mint") + " " + hud.kv("pid", str(pid)) + "  " + hud.kv("contenção", mode) + "  " +
          hud.kv("endpoint", paths.discover_endpoint().uri()))
    return EXIT_OK


def cmd_stop(args) -> int:
    from codar.daemonctl import stop_daemon

    ok = stop_daemon()
    print("daemon parado" if ok else "não foi possível confirmar a parada do daemon")
    return EXIT_OK if ok else EXIT_ERR


def cmd_restart(args) -> int:
    if cmd_stop(args) != EXIT_OK:
        return EXIT_ERR
    args.foreground = False
    return cmd_start(args)


def cmd_status(args) -> int:
    from codar.client import Client, DaemonNotRunning

    try:
        with Client.connect(autostart=False, timeout=3) as c:
            s = c.stats()
    except (DaemonNotRunning, OSError, ConnectionError):
        if args.json:
            print(json.dumps({"running": False}))
        else:
            hud = _hud(sys.stdout)
            print(hud.pill("DAEMON OFFLINE", "red") + " " + hud.c("rode `codar start`", "dim"))
        return EXIT_NO_DAEMON
    if args.json:
        print(json.dumps(s, ensure_ascii=False, indent=2))
        return EXIT_OK
    hud = _hud(sys.stdout)
    mem, model = s["memory"], s["model"]
    rows = [
        hud.kv("versão", s["version"]) + "   " + hud.kv("pid", str(s["pid"])) + "   " + hud.kv("uptime", f"{s['uptime_s']}s") +
        "   " + hud.kv("conexões", str(s["connections"])) + "   " + hud.kv("requisições", str(s["requests"])),
        hud.kv("endpoint", s["endpoint"] or "-"),
        hud.kv("ram", f"{mem['total_mb']:.0f}/{mem['budget_mb']} MB") + " " + hud.bar(mem["total_mb"], mem["budget_mb"], 30) +
        " " + hud.kv("pico", f"{mem['peak_mb']:.0f} MB") + " " + hud.kv("teto", mem["enforcement"], "cyan"),
        hud.kv("modelo", f"{model['name']} [{model['backend']}]") + "  " +
        (hud.c("● CARREGADO", "mint") if model["loaded"] else hud.c("○ DESCARREGADO", "orange")) +
        (hud.c(f"  {model['error']}", "red") if model.get("error") else ""),
        hud.kv("banco", f"{s['patterns']['patterns']} padrões · {s['patterns']['variants']} variantes · "
                        f"{len(s['patterns']['langs'])} linguagens") + "   " + hud.kv("regras", str(s["rules"])) +
        "   " + hud.kv("skills", str(s["skills"])) + "   " + hud.kv("plugins", str(s["plugins"])),
    ]
    for stage, m in sorted(s.get("stages", {}).items()):
        rows.append(hud.kv(f"estágio {stage}", f"n={m['n']}  p50={m['p50_ms']}ms  p95={m['p95_ms']}ms", "cyan"))
    print(hud.panel("codar daemon", rows))
    from codar.installation import daemon_mismatch

    if mismatch := daemon_mismatch(s):
        print(f"codar: {mismatch}; rode `codar restart` com o executável atualizado", file=sys.stderr)
    return EXIT_OK


# =============================================================================== padrões

def cmd_patterns(args) -> int:
    hud = _hud(sys.stdout)
    with _client(args, need_model=False) as c:
        if args.action == "search":
            rows = c.call("patterns.search", {"intent": " ".join(args.terms), "lang": args.lang, "limit": 15})
            for r in rows:
                print(hud.c(f"{r['score']:.2f}", "mint") + " " + hud.c(f"{r['id']:34}", "green") + " " +
                      hud.c(r["title"], "text") + " " + hud.c(",".join(r["langs"]), "dim"))
            return EXIT_OK if rows else EXIT_UNRESOLVED
        if args.action == "list":
            rows = c.call("patterns.list", {"lang": args.lang, "query": " ".join(args.terms) or None})
            for r in rows:
                print(hud.c(f"{r['id']:36}", "green") + hud.c(f"{r['title'][:44]:46}", "text") +
                      hud.c(",".join(r["langs"]), "dim"))
            print(hud.c(f"{len(rows)} padrões", "mint"), file=sys.stderr)
            return EXIT_OK
        if args.action == "show":
            p = c.call("patterns.get", {"id": args.terms[0]})
            langs_ = [args.lang] if args.lang else sorted(p["code"])
            for lg in langs_:
                print(hud.rule(f"{p['id']} · {lg}"))
                print(p["code"].get(lg, "(sem variante)").rstrip())
            return EXIT_OK
        if args.action == "add":
            code = Path(args.code_file).read_text(encoding="utf-8") if args.code_file else sys.stdin.read()
            res = c.call("patterns.add", {"id": args.terms[0], "title": args.title or args.terms[0], "lang": args.lang,
                                          "code": code, "keywords": args.keywords or ""})
            print(hud.pill("SALVO", "mint") + " " + hud.c(res["id"], "green"))
            return EXIT_OK
        if args.action == "remove":
            res = c.call("patterns.remove", {"id": args.terms[0]})
            print("removido" if res["removed"] else "não encontrado (só padrões do usuário podem ser removidos)")
            return EXIT_OK
    return EXIT_ERR


# =============================================================================== diversos

def cmd_init(args) -> int:
    from codar import config, paths
    from codar.engine.models import MODELS
    from codar.engine.stage1 import PatternStore
    from codar.plugin_loader import discover

    hud = _hud(sys.stdout)
    print(hud.banner())
    cfg_path = config.write_default(force=args.force)
    print(hud.bullet(f"configuração: {cfg_path}"))
    if args.model:
        config.set_value("model.name", json.dumps(args.model), cfg_path)
    cfg = config.load()
    bundle = discover(cfg)
    store = PatternStore(paths.db_path())
    store.sync(bundle.patterns, bundle.fingerprint, force=True)
    st = store.stats()
    store.close()
    print(hud.bullet(f"banco de padrões: {st['patterns']} padrões, {st['variants']} variantes, "
                     f"{len(bundle.rules)} regras, {len(bundle.skills)} skills ({paths.db_path()})"))
    paths.user_plugins_dir().mkdir(parents=True, exist_ok=True)
    print(hud.bullet(f"plugins do usuário: {paths.user_plugins_dir()}"))
    card = MODELS.get(cfg["model"]["name"])
    if args.no_model or card is None:
        print(hud.bullet("modelo: pulado (Estágio 2 desativado até `codar model pull`)", "orange"))
        return EXIT_OK
    if card.local_path().is_file():
        print(hud.bullet(f"modelo: {card.title} já presente"))
        return EXIT_OK
    from codar.cli.modelcmd import pull

    return pull(card.key, hud)


def cmd_config(args) -> int:
    from codar import config, paths

    if args.action == "path":
        print(paths.config_file())
    elif args.action == "get":
        cfg = config.load()
        node = cfg
        for part in (args.key or "").split("."):
            if part:
                node = node[part]
        print(json.dumps(node, ensure_ascii=False, indent=2))
    elif args.action == "set":
        config.set_value(args.key, args.value)
        print(f"{args.key} = {args.value}")
    elif args.action == "edit":
        path = config.write_default()
        editor = os.environ.get("EDITOR") or ("notepad" if os.name == "nt" else "vi")
        os.execvp(editor, [editor, str(path)])
    return EXIT_OK


def cmd_vscode(args) -> int:
    """Alterna para o VS Code: abre o arquivo (e linha) na janela atual se estiver no terminal integrado."""
    import shutil
    import subprocess

    code_bin = shutil.which("code") or shutil.which("code-insiders") or shutil.which("codium")
    if not code_bin:
        print("codar: CLI `code` não encontrada no PATH", file=sys.stderr)
        return EXIT_ERR
    target = args.path or "."
    cmd = [code_bin, "-r" if os.environ.get("TERM_PROGRAM") == "vscode" else "-n"]
    cmd += ["-g", f"{target}:{args.line}"] if args.line else [target]
    subprocess.Popen(cmd, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return EXIT_OK


def cmd_extras(args) -> int:
    from codar import extras

    unknown = [n for n in args.names if n not in (*extras.EXTRAS, "all")]
    if unknown:
        print(f"codar extras: desconhecido: {', '.join(unknown)} (use studio, llm ou all)", file=sys.stderr)
        return EXIT_ERR
    if args.action == "install":
        names = [n for n in (args.names or ["all"]) if n != "all"] or list(extras.EXTRAS)
        return extras.install(names)
    if args.action == "remove":
        return extras.remove()
    hud = _hud()
    for what, ok, hint in extras.status_lines():
        print(hud.bullet(f"{what}: instalado" if ok else f"{what}: não instalado  →  {hint}", "green" if ok else "orange"))
    if extras.packaged():
        print(hud.bullet(f"ambiente dos extras: {extras.venv_dir()}", "dim"))
    return EXIT_OK


def _terminal_interativo() -> bool:
    return sys.stdin.isatty() and sys.stdout.isatty()


def _perguntar_sim(pergunta: str) -> bool:
    """Sim/não com Enter = sim; entrada fechada (pipe, Ctrl+D) = não."""
    try:
        resposta = input(f"{pergunta} [S/n] ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        print()
        return False
    return resposta in ("", "s", "sim", "y", "yes")


def _reabrir_studio(args) -> None:
    """Reabre o codar já com os extras: pelo lançador do pacote (que passa a usar o ambiente novo) ou pelo mesmo
    Python, quando os extras foram instalados no ambiente atual. Não retorna."""
    from codar import extras

    argv = ["studio", args.path] + (["-l", args.lang] if args.lang else [])
    launcher = shutil.which("codar") if extras.packaged() else None
    if launcher:
        os.execv(launcher, [launcher, *argv])
    os.execv(sys.executable, [sys.executable, "-m", "codar", *argv])


def cmd_studio(args) -> int:
    try:
        from codar.studio.app import run_studio
    except ImportError as exc:
        from codar import extras

        hud = _hud()
        if _terminal_interativo() and (extras.packaged() or extras.in_venv()):
            # em vez de cair no REPL sem explicar: oferece instalar e abre o Studio em seguida
            print(hud.pill("STUDIO", "orange") + " " + hud.c("o Studio (IDE no terminal) ainda não está instalado.", "text"))
            print(hud.c("  ele e a IA local vêm do PyPI e ficam só no seu usuário (~60 MB, pacotes já compilados)",
                        "dim"))
            if _perguntar_sim("Instalar agora?") and extras.install(list(extras.EXTRAS)) == 0:
                _reabrir_studio(args)
        print(f"codar: o Studio precisa do Textual ({exc}). Instale com: {extras.hint('studio')}. "
              "Abrindo o REPL.", file=sys.stderr)
        from codar.cli.repl import repl

        return repl(args)
    return run_studio(args.path, args.lang)


def cmd_repl(args) -> int:
    from codar.cli.repl import repl

    return repl(args)


def cmd_version(args) -> int:
    if getattr(args, "json", False) or getattr(args, "verbose", False):
        from codar.installation import installation_info

        info = installation_info()
        if getattr(args, "json", False):
            print(json.dumps(info, ensure_ascii=False, indent=2))
            return EXIT_OK
        print(f"codar {__version__} (Python {info['python']}, {info['platform']})")
        for label, key in (("Python", "executable"), ("Código", "module"), ("Origem", "source"),
                           ("Referência", "ref"), ("Commit", "commit")):
            print(f"{label}: {info[key] or 'não registrado'}")
        if info["dirty"]:
            print("Checkout com alterações locais; o commit não inclui essas alterações.")
        return EXIT_OK
    print(f"codar {__version__} (Python {sys.version.split()[0]}, {sys.platform})")
    return EXIT_OK


# =============================================================================== parser

def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(prog="codar", description="Tradução offline de intenção para código (≤3GB RAM).")
    ap.add_argument("-V", "--version", action="store_true", help="mostra a versão")
    sub = ap.add_subparsers(dest="cmd", metavar="comando")

    def common_engine(p):
        p.add_argument("-l", "--lang", help="linguagem alvo (py, js, ts, go, rs, java, cs, c, cpp, sh, ps1, lua, rb, php)")
        p.add_argument("--local", action="store_true", help="roda o motor no próprio processo, sem daemon")
        p.add_argument("--no-autostart", action="store_true", help="não sobe o daemon automaticamente")
        p.add_argument("--json", action="store_true", help="saída JSON completa")

    p = sub.add_parser("run", help="traduz uma intenção (argumento ou stdin) em código")
    p.add_argument("intent", nargs="*")
    common_engine(p)
    p.add_argument("--file", help="arquivo de destino (contexto e detecção de linguagem)")
    p.add_argument("--context", metavar="ARQUIVO", help="código que vem antes da intenção (editores mandam o buffer)")
    p.add_argument("--indent", help="indentação da linha atual, aplicada ao código gerado")
    p.add_argument("--stages", help="estágios permitidos, ex.: 0,1")
    p.add_argument("--each", action="store_true", help="cada linha do stdin é uma intenção")
    p.add_argument("--mode", default="auto", choices=["auto", "line", "block"])
    p.add_argument("--hints", action="store_true", help="injeta dicas da auditoria como comentários")
    p.add_argument("--no-audit", action="store_true")
    p.add_argument("--stream", action="store_true", help="mostra tokens do SLM enquanto gera (stderr)")
    p.add_argument("--indent-unit", help="unidade de indentação (ex.: '  ' ou '\\t')")
    p.add_argument("-q", "--quiet", action="store_true")
    p.add_argument("-v", "--verbose", action="store_true")
    p.set_defaults(fn=cmd_run)

    p = sub.add_parser("compile", help="compila pseudocódigo indentado (arquivo ou stdin) para a linguagem alvo")
    p.add_argument("file", nargs="?")
    common_engine(p)
    for flag in ("--hints", "--no-audit", "--stream", "--quiet", "--verbose"):
        p.add_argument(flag, action="store_true")
    p.add_argument("--stages")
    p.add_argument("--indent-unit")
    p.set_defaults(fn=cmd_compile)

    p = sub.add_parser("audit", help="auditoria estática de um arquivo (ou stdin)")
    p.add_argument("file", nargs="?")
    common_engine(p)
    p.add_argument("--hints", action="store_true", help="imprime o código com as dicas injetadas")
    p.set_defaults(fn=cmd_audit)

    p = sub.add_parser("servir", aliases=["serve"], help="ver no celular: serve uma pasta na rede local (com QR code) "
                       "ou repassa um servidor de desenvolvimento (--proxy 5173)")
    p.add_argument("pasta", nargs="?", default=".", help="pasta a mostrar (padrão: a atual)")
    p.add_argument("--porta", type=int, default=None, help="porta (padrão: a mesma de sempre, sorteada na primeira vez)")
    p.add_argument("--proxy", type=int, metavar="PORTA", help="repassa este servidor de localhost para a rede")
    p.add_argument("--local", action="store_true", help="só neste computador (não abre na rede)")
    p.set_defaults(fn=cmd_servir)
    p = sub.add_parser("explicar", aliases=["explain"], help="explica o erro de um programa: "
                       "python app.py 2>&1 | codar explicar  (ou: codar explicar -- python app.py)")
    p.add_argument("comando", nargs=argparse.REMAINDER, help="comando a rodar (depois de --)")
    p.set_defaults(fn=cmd_explicar)
    p = sub.add_parser("start", help="sobe o daemon")
    p.add_argument("--foreground", action="store_true")
    p.set_defaults(fn=cmd_start)
    sub.add_parser("stop", help="para o daemon").set_defaults(fn=cmd_stop)
    p = sub.add_parser("restart", help="reinicia o daemon")
    p.set_defaults(fn=cmd_restart)
    p = sub.add_parser("status", help="telemetria do daemon (RAM, modelo, estágios)")
    p.add_argument("--json", action="store_true")
    p.set_defaults(fn=cmd_status)

    p = sub.add_parser("init", help="cria configuração, banco de padrões e baixa o modelo")
    p.add_argument("--model", help="chave do modelo (veja `codar model list`)")
    p.add_argument("--no-model", action="store_true")
    p.add_argument("--force", action="store_true", help="sobrescreve o config.toml")
    p.set_defaults(fn=cmd_init)

    p = sub.add_parser("patterns", aliases=["p"], help="banco de padrões: list | search | show | add | remove")
    p.add_argument("action", choices=["list", "search", "show", "add", "remove"])
    p.add_argument("terms", nargs="*")
    common_engine(p)
    p.add_argument("--title")
    p.add_argument("--keywords")
    p.add_argument("--code-file")
    p.set_defaults(fn=cmd_patterns)

    from codar.cli import modelcmd

    modelcmd.register(sub)

    p = sub.add_parser("advise", help="consultor de projeto: sugestões com opções executáveis")
    p.add_argument("path", nargs="?", default=".")
    p.add_argument("--apply", metavar="ID", help="aplica a sugestão ID")
    p.add_argument("--option", help="opção escolhida (ex.: pnpm, bun)")
    p.add_argument("--yes", action="store_true", help="não pede confirmação")
    p.add_argument("--dry-run", action="store_true", help="só mostra o que seria feito")
    p.add_argument("--json", action="store_true")
    p.add_argument("--local", action="store_true")
    p.set_defaults(fn=lambda a: __import__("codar.cli.advisecmd", fromlist=["x"]).cmd_advise(a))

    p = sub.add_parser("studio", aliases=["tui", "ide"], help="IDE imersiva no terminal")
    p.add_argument("path", nargs="?", default=".")
    p.add_argument("-l", "--lang")
    p.set_defaults(fn=cmd_studio)

    p = sub.add_parser("repl", help="REPL simples (sem dependências)")
    p.add_argument("-l", "--lang", default="python")
    p.add_argument("--local", action="store_true")
    p.set_defaults(fn=cmd_repl)

    p = sub.add_parser("shell-init", help="integração com bash/zsh/fish/pwsh (atalho Ctrl+G)")
    p.add_argument("shell", choices=["bash", "zsh", "fish", "pwsh", "powershell"])
    p.set_defaults(fn=lambda a: __import__("codar.cli.shellinit", fromlist=["x"]).cmd_shell_init(a))

    p = sub.add_parser("completion", help="completar com Tab: bash | zsh | fish")
    p.add_argument("shell", choices=["bash", "zsh", "fish"])
    p.set_defaults(fn=lambda a: __import__("codar.cli.completion", fromlist=["x"]).cmd_completion(a))

    p = sub.add_parser("hook", help="hook global do SO: trigger | install")
    p.add_argument("action", choices=["trigger", "install"])
    p.add_argument("-l", "--lang")
    p.set_defaults(fn=lambda a: __import__("codar.cli.hook", fromlist=["x"]).cmd_hook(a))

    p = sub.add_parser("bench", help="teste de carga: latência por estágio e RAM do daemon")
    p.add_argument("-n", type=int, default=200, help="requisições por estágio determinístico")
    p.add_argument("--stage2", type=int, default=3, help="requisições ao SLM (0 = pula)")
    p.add_argument("--concurrency", type=int, default=4)
    p.add_argument("--soak", type=int, default=0, help="requisições extras para detectar vazamento")
    p.add_argument("--json", action="store_true")
    p.set_defaults(fn=lambda a: __import__("codar.cli.bench", fromlist=["x"]).cmd_bench(a))

    sub.add_parser("doctor", help="diagnóstico do ambiente").set_defaults(
        fn=lambda a: __import__("codar.cli.doctor", fromlist=["x"]).cmd_doctor(a))

    p = sub.add_parser("config", help="config: path | get [chave] | set chave valor | edit")
    p.add_argument("action", choices=["path", "get", "set", "edit"])
    p.add_argument("key", nargs="?")
    p.add_argument("value", nargs="?")
    p.set_defaults(fn=cmd_config)

    p = sub.add_parser("extras", help="extras opcionais (Studio, IA local): status | install | remove")
    p.add_argument("action", nargs="?", choices=["status", "install", "remove"], default="status")
    p.add_argument("names", nargs="*", metavar="studio|llm|all", help="padrão: todos")
    p.set_defaults(fn=cmd_extras)

    p = sub.add_parser("plugins", help="plugins: list | new NOME")
    p.add_argument("action", choices=["list", "new"])
    p.add_argument("name", nargs="?")
    p.set_defaults(fn=lambda a: __import__("codar.cli.plugincmd", fromlist=["x"]).cmd_plugins(a))

    p = sub.add_parser("vscode", help="alterna para o VS Code (abre arquivo/linha)")
    p.add_argument("path", nargs="?")
    p.add_argument("--line", type=int)
    p.set_defaults(fn=cmd_vscode)

    p = sub.add_parser("version", help="versão e procedência da instalação")
    p.add_argument("--verbose", "-v", action="store_true", help="mostra caminhos, origem e commit instalado")
    p.add_argument("--json", action="store_true", help="diagnóstico da instalação em JSON")
    p.set_defaults(fn=cmd_version)
    return ap


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    parser = build_parser()
    if not argv:
        if sys.stdin.isatty() and sys.stdout.isatty():
            return cmd_studio(argparse.Namespace(path=".", lang=None, local=False))
        argv = ["run"]
    if argv[0] not in parser._subparsers._group_actions[0].choices and not argv[0].startswith("-"):  # type: ignore[union-attr]
        argv = ["run", *argv]  # `codar "imprimir oi" -l go` == `codar run ...`
    args = parser.parse_args(argv)
    if args.version:
        return cmd_version(args)
    if not getattr(args, "fn", None):
        parser.print_help()
        return EXIT_OK
    try:
        return int(args.fn(args) or 0)
    except KeyboardInterrupt:
        return 130
    except BrokenPipeError:
        return EXIT_OK


if __name__ == "__main__":
    raise SystemExit(main())
