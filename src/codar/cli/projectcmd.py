"""Configuração, propostas e verificações de projeto."""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

from codar import toolchains
from codar.project import CONFIG_NAME, Project
from codar.validation import check_project, default_command, run_command
from codar.workspace import EditStore

TEMPLATE = '''# Comandos são listas de argumentos, sem shell.
[project]
skills = []
guidance = ["Preserve project conventions and unrelated code."]
exclude = []
context_chars = 4000
repair_attempts = 1

[commands]
# run = ["python", "{file}"]
# test = ["python", "-m", "pytest"]
# analyze = ["flutter", "analyze"]
# format = ["dart", "format", "."]

[toolchains]
# python = "3.12"
# dart = ">=3.0.0,<4.0.0"
'''


def register(sub):
    p = sub.add_parser("project", help="projeto: init | info | context | doctor | run")
    p.add_argument("action", choices=["init", "info", "context", "doctor", "run"])
    p.add_argument("terms", nargs="*")
    p.add_argument("--root", default=".")
    p.add_argument("--file")
    p.add_argument("--json", action="store_true")
    p.set_defaults(fn=cmd_project)
    p = sub.add_parser("edit", help="propõe uma edição em vários arquivos e mostra o diff")
    p.add_argument("intent", nargs="+")
    p.add_argument("--file", action="append", dest="files", required=True)
    p.add_argument("--root", default=".")
    p.add_argument("--local", action="store_true")
    p.add_argument("--no-autostart", action="store_true")
    p.add_argument("--apply", action="store_true", help="aplica se a validação passar")
    p.add_argument("--json", action="store_true")
    p.set_defaults(fn=cmd_edit)
    p = sub.add_parser("edits", help="histórico: list | show | apply | restore | recover")
    p.add_argument("action", choices=["list", "show", "apply", "restore", "recover"])
    p.add_argument("id", nargs="?")
    p.add_argument("--root", default=".")
    p.add_argument("--file")
    p.add_argument("--hunk", action="append", help="aplica só esse trecho (repetível)")
    p.add_argument("--json", action="store_true")
    p.set_defaults(fn=cmd_edits)
    p = sub.add_parser("check", help="verifica sintaxe; testes e analisadores são opções explícitas")
    p.add_argument("files", nargs="*")
    p.add_argument("--root", default=".")
    for flag in ("tests", "analyze", "format", "no-native", "json"):
        p.add_argument("--" + flag, action="store_true")
    p.add_argument("--timeout", type=int, default=60)
    p.set_defaults(fn=cmd_check)


def display(value, as_json=False):
    if as_json or not isinstance(value, dict) or "diff" not in value:
        print(json.dumps(value, ensure_ascii=False, indent=2))
        return
    print(f"Edição {value['id']} · {value['status']}")
    print(value["diff"])
    for check in value.get("validation", []):
        print(f"{check['path']}: {check['status']} {check.get('message', '')}")
    for note in value.get("notes", []):
        print(note)
    if value["status"] == "draft":
        print(f"Aplicar: codar edits apply {value['id']} --root {json.dumps(value['root'], ensure_ascii=False)}")


def project_versions(project: Project) -> list[dict]:
    from codar.plugin_loader import version_matches

    results = []
    for name, expected in project.toolchains.items():
        executable = toolchains.executable(name)
        result = {"language": name, "expected": expected, "executable": executable, "status": "missing", "actual": ""}
        if executable:
            checked = run_command([executable, "--version"], project.root, 15)
            match = re.search(r"\b\d+\.\d+(?:\.\d+)?\b", checked["message"])
            actual = match[0] if match else ""
            compatible = version_matches(actual, expected) if actual and re.search(r"[<>=!]", expected) else \
                         bool(actual and (actual == expected or actual.startswith(expected + ".")))
            result.update(actual=actual, status="ok" if compatible else "mismatch")
        results.append(result)
    return results


def cmd_project(args) -> int:
    try:
        project = Project.load(args.root)
        if args.action == "init":
            file = project.root / CONFIG_NAME
            with file.open("x", encoding="utf-8") as handle:
                handle.write(TEMPLATE)
            print(file)
            return 0
        if args.action == "context":
            value = project.context(" ".join(args.terms), args.file or "")
        elif args.action == "doctor":
            value = {"root": str(project.root), "toolchains": project_versions(project)}
        elif args.action == "run":
            command = default_command(project, "run", args.file)
            if not command:
                raise ValueError("configure commands.run em codar.toml ou informe --file")
            return subprocess.call(command, cwd=project.root, env=toolchains.environment())
        else:
            value = {**project.as_dict(), "files": project.files()}
        display(value, args.json)
        return int(args.action == "doctor" and any(t["status"] != "ok" for t in value["toolchains"]))
    except (OSError, ValueError, toolchains.InstallError) as exc:
        print(f"codar: {exc}", file=sys.stderr)
        return 1


def cmd_edit(args) -> int:
    from codar.cli.main import _client
    from codar.client import RpcError

    try:
        root = str(Path(args.root).expanduser().resolve())
        with _client(args) as client:
            proposal = client.call("project.edit", {"root": root, "files": args.files, "intent": " ".join(args.intent)})
        if args.apply:
            proposal = EditStore(root).apply(proposal["id"])
        display(proposal, args.json)
        return 2 if any(c["status"] == "error" for c in proposal.get("validation", [])) else 0
    except (OSError, ValueError, RpcError, RuntimeError) as exc:
        print(f"codar: {exc}", file=sys.stderr)
        return 1


def cmd_edits(args) -> int:
    try:
        store = EditStore(args.root)
        if args.action == "list":
            value = store.list(file=args.file)
        elif args.action == "recover":
            value = store.recover()
        else:
            if not args.id:
                raise ValueError("informe o id da edição (codar edits list)")
            if args.action == "apply":
                value = store.apply(args.id, args.hunk)
            elif args.action == "restore":
                value = store.restore(args.id)
            else:
                value = store.describe(store.get(args.id))
        display(value, args.json)
        return 0
    except (OSError, ValueError, KeyError) as exc:
        print(f"codar: {exc}", file=sys.stderr)
        return 1


def cmd_check(args) -> int:
    try:
        actions = [name for name, selected in (("test", args.tests), ("analyze", args.analyze), ("format", args.format)) if selected]
        result = check_project(args.root, args.files, actions=actions, native=not args.no_native, timeout=args.timeout)
        if args.json:
            display(result, True)
        else:
            for item in result["files"]:
                print(f"{item['path']}: {item['status']} {item.get('message', '').strip()}")
            for item in result["commands"]:
                print(f"{' '.join(item['command'])}: {item['status']}\n{item['message']}")
            print(f"Verificação {'sem erros detectados' if result['ok'] else 'falhou'}; {result['skipped']} não verificadas")
        return 0 if result["ok"] else 2
    except (OSError, ValueError, KeyError, toolchains.InstallError) as exc:
        print(f"codar: {exc}", file=sys.stderr)
        return 1
