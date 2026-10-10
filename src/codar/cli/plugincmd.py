"""`codar plugins`: list | new <nome> (cria o esqueleto de um plugin do usuário)."""

from __future__ import annotations

import sys
import json
from pathlib import Path

from codar import config, paths
from codar.plugin_loader import discover

TEMPLATE_PATTERN = '''# Padrões = ferramentas verificadas que a IA reutiliza em vez de escrever código do zero.
[[pattern]]
id = "{name}.exemplo"
title = "Exemplo do plugin {name}"
keywords = "exemplo demo {name}"
slots = {{ nome = "mundo" }}

[pattern.code]
python = \'\'\'
def saudar(nome: str = "{{{{nome}}}}") -> str:
    return f"Olá, {{nome}}!"
\'\'\'
'''

TEMPLATE_SKILLS = '''[[skill]]
id = "{name}.convencoes"
triggers = "{name}"
guidance = ["Follow the {name} team conventions: small functions, explicit errors."]
'''

TEMPLATE_RULES = '''[[rule]]
id = "{upper}001"
langs = ["python"]
pattern = 'print\\('
severity = "info"
category = "style"
message = "Prefira logging a print em código de produção"
suggestion = "use logging.getLogger(__name__)"
'''

TEMPLATE_ADVICE = '''[[advice]]
id = "{name}.readme"
title = "Projeto sem README"
reason = "Um README curto explica como instalar, rodar e testar."
impact = "low"
category = "docs"
when = {{ missing = ["README.md", "README.rst", "README"] }}

[[advice.option]]
id = "criar"
label = "Criar README.md"
steps = [{{ write = "README.md", content = "# Projeto\\n\\n## Como rodar\\n\\n## Como testar\\n" }}]
'''


def cmd_plugins(args) -> int:
    from codar.cli.hud import Hud

    hud = Hud(sys.stdout)
    if args.action == "list":
        for p in discover(config.load()).plugins:
            tag = hud.c("embutido", "dim") if p.builtin else hud.c("usuário", "cyan")
            print(hud.c(f"{p.name:20}", "green") + f" {tag}  " + hud.c(
                f"{len(p.patterns):3} padrões · {len(p.skills):2} skills · {len(p.rules):3} regras · "
                f"{len(p.advice):2} conselhos", "text") + ("  " + hud.c(f"{len(p.errors)} erro(s)", "red") if p.errors else ""))
        return 0
    if args.action not in ("new", "list"):
        return manage_plugin(args)
    if not args.name or not args.name.replace("-", "").replace("_", "").isalnum():
        print("uso: codar plugins new <nome>", file=sys.stderr)
        return 1
    root = paths.user_plugins_dir() / args.name
    if root.exists():
        print(f"já existe: {root}", file=sys.stderr)
        return 1
    (root / "patterns").mkdir(parents=True)
    fmt = {"name": args.name, "upper": args.name.upper().replace("-", "")[:4]}
    (root / "plugin.toml").write_text(f'[plugin]\nname = "{args.name}"\nversion = "0.1.0"\n'
                                      f'description = "Plugin {args.name}"\n', encoding="utf-8")
    (root / "patterns" / "exemplo.toml").write_text(TEMPLATE_PATTERN.format(**fmt), encoding="utf-8")
    (root / "skills.toml").write_text(TEMPLATE_SKILLS.format(**fmt), encoding="utf-8")
    (root / "rules.toml").write_text(TEMPLATE_RULES.format(**fmt), encoding="utf-8")
    (root / "advice.toml").write_text(TEMPLATE_ADVICE.format(**fmt), encoding="utf-8")
    print(hud.pill("PLUGIN CRIADO", "mint") + " " + hud.c(str(root), "green"))
    print(hud.c("edite os .toml e rode `codar restart` (ou o método reload) para recarregar", "dim"))
    return 0


def install_plugin(directory: str | None) -> int:
    """Interface preservada para scripts que instalam uma pasta local."""
    from codar.plugin_manager import install_plugin as install

    try:
        if not directory:
            raise ValueError("uso: codar plugins install <pasta-com-plugin.toml>")
        result = install(directory)
        print(f"plugin {result['name']} instalado: {paths.user_plugins_dir() / result['name']}")
        print("rode `codar restart` para carregar padrões, skills e regras")
        return 0
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print(f"codar: {exc}", file=sys.stderr)
        return 1


def manage_plugin(args) -> int:
    from codar import plugin_manager as manager

    try:
        if not args.name:
            raise ValueError("informe o nome, pasta ou URL do plugin")
        if args.action == "install":
            result = manager.install_plugin(args.name, ref=args.ref, subdir=args.subdir)
        elif args.action == "update":
            result = manager.update_plugin(args.name, args.source, ref=args.ref, subdir=args.subdir)
        elif args.action == "remove":
            result = manager.remove_plugin(args.name)
        elif args.action == "restore":
            result = manager.restore_plugin(args.name)
        elif args.action == "validate":
            plugin = manager.validate_plugin(Path(args.name).expanduser().resolve())
            result = {"name": plugin.name, "version": plugin.version, "valid": True}
        elif args.action in ("enable", "disable"):
            name = manager.valid_name(args.name)
            available = {p.name for p in discover({}).plugins}
            if name not in available:
                raise ValueError("plugin não encontrado")
            disabled = set(config.load()["plugins"].get("disabled", []))
            disabled.discard(name) if args.action == "enable" else disabled.add(name)
            config.set_value("plugins.disabled", json.dumps(sorted(disabled)))
            result = {"name": name, "enabled": args.action == "enable"}
        else:
            plugin = next((p for p in discover({}).plugins if p.name == args.name), None)
            if not plugin:
                raise ValueError("plugin não encontrado")
            result = {"name": plugin.name, "version": plugin.version, "builtin": plugin.builtin,
                      "errors": plugin.errors, "requires_codar": plugin.requires_codar,
                      "requires_plugins": plugin.requires_plugins, "origin": manager._metadata(plugin.root)}
        print(json.dumps(result, ensure_ascii=False, indent=2))
        if args.action in ("install", "update", "remove", "restore", "enable", "disable"):
            try:
                from codar.client import Client

                with Client.connect(autostart=False, timeout=3) as client:
                    client.call("reload")
                print("plugins recarregados no daemon")
            except Exception:
                print("rode codar restart para carregar a mudança")
        return 0
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print(f"codar: {exc}", file=sys.stderr)
        return 1
