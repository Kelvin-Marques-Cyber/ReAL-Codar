"""codar toolchains: ferramentas de programação, independentes dos extras Python do CODAR."""

import json
import os
import shlex
import subprocess
import sys
import urllib.error
import tarfile
import zipfile

from codar import toolchains
from codar import runtimes


def cmd_toolchains(args) -> int:
    try:
        root = None if getattr(args, 'global_runtime', False) else getattr(args, 'root', '.')
        if args.action == "env":
            path = toolchains.environment({'PATH': ''}, project=root)['PATH'].rstrip(os.pathsep)
            if args.shell == "powershell":
                print("$env:PATH = '" + (path + os.pathsep).replace("'", "''") + "' + $env:PATH")
            elif args.shell == "fish":
                for folder in reversed(path.split(os.pathsep)):
                    if folder:
                        print("fish_add_path --prepend " + shlex.quote(str(folder)))
            else:
                print("export PATH=" + (shlex.quote(path) + ':' if path else '') + '"$PATH"')
            return 0
        if args.action in ('versions', 'use', 'venv'):
            if not args.names or len(args.names) > (2 if args.action == 'use' else 1):
                raise ValueError('Informe uma linguagem; use aceita também a versão após o nome.')
            name = toolchains.canonical(args.names[0])
            if args.action == 'versions':
                entries = runtimes.versions(name)
                current = runtimes.selected(name, root)
                if args.json:
                    print(json.dumps({'installed': entries, 'selected': current}, ensure_ascii=False, indent=2))
                else:
                    for item in entries:
                        mark = '*' if current and current['executable'] == item['executable'] else ' '
                        print(f"{mark} {item['version']:12} {item['executable']}  [{item['key']}]")
                    if not entries:
                        print('Nenhuma versão encontrada. Use codar toolchains install ' + name)
                return 0
            versions = getattr(args, 'sdk_versions', None) or []
            version = args.names[1] if len(args.names) == 2 else versions[0] if len(versions) == 1 else ''
            if args.action == 'venv':
                if name != 'python' or not version or root is None:
                    raise ValueError('Use toolchains venv python --version 3.13 --root . --venv .venv313')
                entry = runtimes.create_venv(root, version, getattr(args, 'venv', '.venv'))
            else:
                entry = runtimes.choose(name, version, project=root, executable=getattr(args, 'path', None))
            print(f"{name} {entry['version']} selecionado para {root or 'projetos sem escolha própria'}: {entry['executable']}")
            return 0
        if args.action == "list":
            entries = [{"language": key, "executable": toolchains.executable(key)} for key in toolchains.TOOLS]
            if args.json:
                print(json.dumps(entries, ensure_ascii=False, indent=2))
            else:
                for item in entries:
                    print(f"{item['language']:12} {item['executable'] or 'ausente · codar toolchains install ' + item['language']}")
            return 0
        if not args.names:
            raise toolchains.InstallError("uso: codar toolchains install <linguagem> [outra ...]")
        # Valida todos os nomes antes de começar a instalação de qualquer um.
        names = list(dict.fromkeys(toolchains.canonical(name) for name in args.names))
        versions = getattr(args, 'sdk_versions', None)
        if versions:
            if names != ['python']:
                raise ValueError('--version na instalação é exclusivo de Python; outros SDKs aceitam executáveis instalados com use --path.')
            runtimes.install_python(versions, dry_run=args.dry_run)
            return 0
        for name in names:
            toolchains.install(name, dry_run=args.dry_run)
        return 0
    except (toolchains.InstallError, OSError, ValueError, KeyError, TypeError, subprocess.CalledProcessError,
            urllib.error.URLError, EOFError, tarfile.TarError, zipfile.BadZipFile) as exc:
        print(f"codar: instalação não concluída: {exc}", file=sys.stderr)
        return 1
