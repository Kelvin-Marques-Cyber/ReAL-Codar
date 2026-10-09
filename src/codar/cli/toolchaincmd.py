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


def cmd_toolchains(args) -> int:
    try:
        if args.action == "env":
            path = os.pathsep.join(str(p) for p in toolchains.bin_dirs())
            if args.shell == "powershell":
                print("$env:PATH += '" + (os.pathsep + path).replace("'", "''") + "'")
            elif args.shell == "fish":
                for folder in toolchains.bin_dirs():
                    print("fish_add_path --append " + shlex.quote(str(folder)))
            else:
                print("export PATH=\"$PATH\"" + (":" + shlex.quote(path) if path else ""))
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
        for name in names:
            toolchains.install(name, dry_run=args.dry_run)
        return 0
    except (toolchains.InstallError, OSError, ValueError, KeyError, TypeError, subprocess.CalledProcessError,
            urllib.error.URLError, EOFError, tarfile.TarError, zipfile.BadZipFile) as exc:
        print(f"codar: instalação não concluída: {exc}", file=sys.stderr)
        return 1
