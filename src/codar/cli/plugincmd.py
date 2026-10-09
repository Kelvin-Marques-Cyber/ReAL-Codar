"""`codar plugins`: list | new <nome> (cria o esqueleto de um plugin do usuário)."""

from __future__ import annotations

import sys
import re
import shutil
import tempfile
from pathlib import Path

from codar import config, paths
from codar.plugin_loader import discover, load_plugin

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
    if args.action == "install":
        return install_plugin(args.name)
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
    """Instala um plugin local validado, sem sobrescrever outro nem executar plugin.py."""
    try:
        source = Path(directory or "").expanduser().resolve()
        if not directory or not (source / "plugin.toml").is_file():
            raise ValueError("uso: codar plugins install <pasta-com-plugin.toml>")
        plugin = load_plugin(source, builtin=False)
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]*", plugin.name):
            raise ValueError("nome do plugin inválido")
        if plugin.errors:
            raise ValueError("plugin inválido: " + "; ".join(plugin.errors))
        if any(file.is_symlink() for file in source.rglob("*")):
            raise ValueError("plugins locais devem conter arquivos próprios, sem links simbólicos")
        parent = paths.user_plugins_dir()
        parent.mkdir(parents=True, exist_ok=True)
        destination = parent / plugin.name
        if destination.exists():
            raise ValueError(f"já existe: {destination}; seus arquivos foram preservados")
        with tempfile.TemporaryDirectory(prefix=".install-", dir=parent) as temporary:
            stage = Path(temporary) / plugin.name
            shutil.copytree(source, stage, ignore=shutil.ignore_patterns(".git", "__pycache__", ".venv", "node_modules"))
            stage.rename(destination)
        print(f"plugin {plugin.name} instalado: {destination}")
        print("rode `codar restart` para carregar padrões, skills e regras")
        return 0
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print(f"codar: {exc}", file=sys.stderr)
        return 1
