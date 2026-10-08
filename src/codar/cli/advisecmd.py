"""`codar advise`: sugestões de projeto com opções; aceitar executa o plano escolhido."""

from __future__ import annotations

import json
import sys
from pathlib import Path

from codar import config
from codar.advisor import scan_project
from codar.advisor.apply import ApplyError, apply_steps, find_option
from codar.plugin_loader import discover

IMPACT_COLOR = {"high": "red", "medium": "orange", "low": "cyan"}


def cmd_advise(args) -> int:
    from codar.cli.hud import Hud

    hud = Hud(sys.stdout)
    root = Path(args.path).expanduser().resolve()
    bundle = discover(config.load())
    if args.apply:
        return _apply(root, bundle, args.apply, args.option, hud, args.yes, args.dry_run)
    report = scan_project(root, bundle.advice)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0
    sugs = report["suggestions"]
    facts = report["facts"]
    print(hud.rule("consultor de projeto"))
    print(hud.kv("projeto", facts["root"]) + "   " + hud.kv("arquivos", str(facts["files"])) + "   " +
          hud.kv("linguagens", ", ".join(f"{k}:{v}" for k, v in facts["langs"].items()) or "-"))
    if not sugs:
        print(hud.bullet("nenhuma sugestão — projeto em ordem", "mint"))
        return 0
    for n, s in enumerate(sugs, 1):
        rows = hud.wrap(s["title"], IMPACT_COLOR.get(s["impact"], "text"), bold=True) + hud.wrap(s["reason"], "text")
        for k, o in enumerate(s["options"], 1):
            rows.append(hud.c(f"[{k}] ", "mint", bold=True) + hud.c(o["label"], "green", bold=True))
            if o.get("reason"):
                rows += hud.wrap(o["reason"], "dim", indent="    ")
            for st in o["steps"][:6]:
                rows += hud.wrap(st, "cyan", indent="      ")
        print(hud.panel(f"{n}. {s['id']} · {s['impact']}", rows))
    if not sys.stdin.isatty() or args.yes:
        print(hud.c("aplique com: codar advise --apply <id> --option <opção>", "dim"))
        return 0
    while True:
        try:
            choice = input(hud.c("aplicar qual sugestão? (número, Enter para sair) ", "red", bold=True)).strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return 0
        if not choice:
            return 0
        if not choice.isdigit() or not 1 <= int(choice) <= len(sugs):
            continue
        s = sugs[int(choice) - 1]
        opts = s["options"]
        oc = "1"
        if len(opts) > 1:
            oc = input(hud.c(f"opção [1-{len(opts)}] (n cancela): ", "red", bold=True)).strip() or "1"
        if oc.lower() == "n" or not oc.isdigit() or not 1 <= int(oc) <= len(opts):
            continue
        _apply(root, bundle, s["id"], opts[int(oc) - 1]["id"], hud, yes=False, dry_run=False)


def _apply(root: Path, bundle, sid: str, oid: str | None, hud, yes: bool, dry_run: bool) -> int:
    try:
        title, opt, steps = find_option(root, bundle, sid, oid)
    except ApplyError as exc:
        print(hud.pill("ERRO", "red") + " " + str(exc), file=sys.stderr)
        return 1
    print(hud.pill("PLANO", "red") + " " + hud.c(f"{title} → {opt['label']}", "green", bold=True))
    apply_steps(root, steps, bundle, lambda s: print("  " + hud.c(s, "dim")), dry_run=True)
    if dry_run:
        return 0
    if not yes:
        try:
            ok = input(hud.c("executar estes passos? [s/N] ", "red", bold=True)).strip().lower() in ("s", "sim", "y", "yes")
        except (EOFError, KeyboardInterrupt):
            ok = False
        if not ok:
            print(hud.c("cancelado", "dim"))
            return 1
    try:
        apply_steps(root, steps, bundle, lambda s: print("  " + hud.c(s, "text")))
    except ApplyError as exc:
        print(hud.pill("FALHOU", "red") + " " + str(exc), file=sys.stderr)
        return 1
    print(hud.pill("APLICADO", "mint") + " " + hud.c(opt["label"], "green"))
    return 0
