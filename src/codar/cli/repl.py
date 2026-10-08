"""REPL sem dependências (funciona em qualquer servidor/PowerShell): uma intenção por linha."""

from __future__ import annotations

import os
import re
import sys

from codar import paths

HELP = """comandos (Tab completa comandos, linguagens e palavras; ↑ volta ao histórico):
  :lang <ling>   troca a linguagem (py, go, rs, ts, ps1, sh...)     :stages 0,1   restringe estágios
  :hints         liga/desliga dicas inline                          :stats        telemetria do daemon
  :block         alterna modo pseudocódigo (linha vazia executa)    :save <id>    salva o último resultado como padrão
  :history       últimas traduções                                  :q            sai"""
META = (":lang", ":stages", ":hints", ":block", ":stats", ":history", ":save", ":help", ":q")


def completer(readline):
    """Tab: comandos (:lang…), linguagens depois de :lang, e palavras do pseudocódigo e do histórico."""
    from codar import langs
    from codar.vocab import EXAMPLES, PSEUDO_WORDS

    word = re.compile(r"[^\W\d]\w{2,}")  # palavras e identificadores; nada de 'caro' entre aspas ou números
    words = set(PSEUDO_WORDS) | {w for phrase, _ in EXAMPLES for w in phrase.split() if word.fullmatch(w)}
    lang_names = sorted(set(langs.LANGS) | {"py", "js", "ts", "rs", "cs", "sh", "ps1", "rb"})

    def complete(text: str, state: int) -> str | None:
        line = readline.get_line_buffer()
        if line.startswith(":lang "):
            pool = lang_names
        elif line.startswith(":") and " " not in line:
            pool = list(META)
        else:
            seen = {w for i in range(1, readline.get_current_history_length() + 1)
                    for w in (readline.get_history_item(i) or "").split() if word.fullmatch(w)}
            pool = sorted(words | seen)
        matches = [w + " " for w in pool if w.startswith(text)]
        return matches[state] if state < len(matches) else None

    return complete


def repl(args) -> int:
    from codar.cli.hud import STAGE_COLOR, STAGE_LABEL, Hud
    from codar.client import Client, DaemonNotRunning, RpcError

    hud = Hud(sys.stdout)
    try:
        import readline  # noqa: F401  (histórico e edição de linha onde disponível)

        hist = paths.data_dir() / "repl_history"
        hist.parent.mkdir(parents=True, exist_ok=True)
        try:
            readline.read_history_file(str(hist))
        except OSError:
            pass
        readline.set_completer(completer(readline))
        readline.set_completer_delims(" \t\n")
        # libedit (macOS) usa outra sintaxe para ligar o Tab
        readline.parse_and_bind("bind ^I rl_complete" if "libedit" in (readline.__doc__ or "") else "tab: complete")
    except ImportError:
        readline, hist = None, None
    try:
        if getattr(args, "local", False):
            from codar.engine.local import LocalClient

            client = LocalClient()
        else:
            client = Client.connect()
    except (DaemonNotRunning, OSError, RuntimeError, TimeoutError) as exc:
        print(f"codar: daemon indisponível: {exc}", file=sys.stderr)
        return 4
    lang = getattr(args, "lang", None) or "python"
    stages, hints, block, buf, last = (0, 1, 2), False, False, [], None
    print(hud.banner())
    print(hud.c(HELP, "dim"))
    while True:
        prompt = hud.c(f"{'…' if block and buf else '❯'} ", "red", bold=True) + hud.c(f"{lang} ", "dim")
        try:
            line = input(prompt)
        except (EOFError, KeyboardInterrupt):
            print()
            break
        text = line.strip()
        if text.startswith(":"):
            cmd, _, rest = text[1:].partition(" ")
            if cmd in ("q", "quit", "sair"):
                break
            if cmd == "lang" and rest:
                lang = rest.strip()
            elif cmd == "stages":
                stages = tuple(int(x) for x in rest.split(",") if x.strip())
            elif cmd == "hints":
                hints = not hints
                print(hud.c(f"dicas inline: {'on' if hints else 'off'}", "dim"))
            elif cmd == "block":
                block, buf = not block, []
                print(hud.c(f"modo pseudocódigo: {'on (linha vazia executa)' if block else 'off'}", "dim"))
            elif cmd == "stats":
                s = client.stats()
                print(hud.c(str({k: s.get(k) for k in ("memory", "stages")}), "green"))
            elif cmd == "history":
                for h in client.call("history", {"limit": 10}):
                    print(hud.c(f"[{h['stage']}] {h['intent'][:60]}", "green"))
            elif cmd == "save" and rest and last:
                client.call("patterns.add", {"id": rest.strip(), "title": last[0][:80], "lang": last[1]["lang"],
                                             "code": last[1]["code"], "keywords": last[0]})
                print(hud.pill("SALVO", "mint") + " " + hud.c(rest.strip(), "green"))
            else:
                print(hud.c(HELP, "dim"))
            continue
        if block:
            if text:
                buf.append(line)
                continue
            if not buf:
                continue
            text, buf = "\n".join(buf), []
        if not text:
            continue
        try:
            res = client.translate(text, lang, stages=stages, hints=hints, mode="block" if block else "auto")
        except RpcError as exc:
            print(hud.pill("UNRESOLVED", "red") + " " + hud.c(exc.message, "text"))
            continue
        last = (text, res)
        code = res.get("annotated") if hints and res.get("annotated") else res["code"]
        print(hud.pill(STAGE_LABEL.get(res["stage"], res["stage"]), STAGE_COLOR.get(res["stage"], "red")) + " " +
              hud.c(res["source"], "green") + " " + hud.c(f"{res['timings'].get('total_ms', 0):.2f}MS", "mint"))
        print(hud.c(code, "moon"))
        for f in res.get("findings", []):
            print(hud.c(f"  ⚠ {f['id']} L{f['line']} {f['message']}", "orange"))
    if readline and hist:
        try:
            readline.write_history_file(str(hist))
        except OSError:
            pass
    client.close()
    os.environ.pop("CODAR_REPL", None)
    return 0
