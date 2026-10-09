"""Lista e explica as diretrizes locais usadas pela IA do CODAR."""

import sys

from codar import config, langs
from codar.plugin_loader import discover


def cmd_skills(args) -> int:
    lang = langs.try_resolve(args.lang) if args.lang else None
    if args.lang and lang is None:
        print(f"linguagem desconhecida: {args.lang}", file=sys.stderr)
        return 1
    skills = [s for s in discover(config.load()).skills if not lang or not s.langs or lang.id in s.langs]
    if args.action == "show":
        skills = [s for s in skills if s.id == args.name]
        if not skills:
            print("skill não encontrada; use `codar skills list`", file=sys.stderr)
            return 1
    for skill in skills:
        print(f"{skill.id} · {', '.join(skill.langs) or 'todas'} · plugin {skill.source}")
        if args.action == "show":
            print(f"  gatilhos: {skill.triggers or 'sempre nesta linguagem'}")
            for rule in skill.guidance:
                print(f"  - {rule}")
    return 0
