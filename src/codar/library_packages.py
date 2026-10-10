"""Planos explícitos de instalação no projeto; importar nunca instala nada."""

from __future__ import annotations

import os
from pathlib import Path
import re
import shutil
import subprocess
import sys

from codar.runtimes import environment, selected
from codar.library_names import python_distribution


def installation_plan(root: Path, name: str, lang: str, version: str | None = None) -> list[list[str]]:
    if version and not re.fullmatch(r'[0-9][\w.+-]{0,100}', version):
        raise ValueError('Informe uma versão exata, como 2.1.0, sem comandos ou URLs.')
    patterns = {
        'python': r'[A-Za-z0-9][A-Za-z0-9_.-]{0,120}',
        'javascript': r'(?:@[a-z0-9_.-]+/)?[a-z0-9][a-z0-9_.-]{0,120}',
        'typescript': r'(?:@[a-z0-9_.-]+/)?[a-z0-9][a-z0-9_.-]{0,120}',
        'dart': r'[a-z][a-z0-9_]{0,100}', 'rust': r'[A-Za-z][A-Za-z0-9_-]{0,100}',
        'csharp': r'[A-Za-z][A-Za-z0-9_.-]{0,120}',
        'php': r'[a-z0-9][a-z0-9_.-]+/[a-z0-9][a-z0-9_.-]+',
        'ruby': r'[a-zA-Z][a-zA-Z0-9_.-]{0,120}',
        'go': r'[a-zA-Z0-9][a-zA-Z0-9_.-]+(?:/[a-zA-Z0-9_.-]+)+',
    }
    if lang not in patterns:
        raise ValueError('Instalação ainda sem adaptador para essa linguagem. Use seu gerenciador e '
                         'libraries learn --source para fornecer fontes/documentação.')
    if not re.fullmatch(patterns[lang], name) or '..' in name:
        raise ValueError('Nome de pacote inválido. Use o identificador do registro, sem comandos, opções ou URLs.')
    if lang == 'python':
        if name.lower() in ('tkinter', '_tkinter'):
            raise ValueError('Tkinter é componente Tcl/Tk da distribuição Python; não é instalado pelo pip. '
                             'Use as instruções do consultor do CODAR para esse runtime.')
        name = python_distribution(name)
        chosen = selected('python', root)
        executable = Path(chosen['executable']) if chosen else None
        if executable and (executable.parent.parent / 'pyvenv.cfg').is_file():
            commands = []
        else:
            executable = next((root / p / ('Scripts/python.exe' if os.name == 'nt' else 'bin/python')
                               for p in ('.venv', 'venv', 'env') if (root / p / 'pyvenv.cfg').is_file()), None)
            commands = []
            if executable is None:
                folder = root / '.venv'
                if folder.exists():
                    raise ValueError('A pasta .venv já existe e não é um ambiente válido; não será sobrescrita.')
                base = chosen['executable'] if chosen else getattr(sys, '_base_executable', sys.executable)
                commands.append([str(base), '-m', 'venv', str(folder)])
                executable = folder / ('Scripts/python.exe' if os.name == 'nt' else 'bin/python')
        commands.append([str(executable), '-m', 'pip', 'install', name + ('==' + version if version else '')])
        return commands
    if lang in ('javascript', 'typescript'):
        from codar.advisor.pacotes import gerenciador

        manager = gerenciador(root)
        if not (root / 'package.json').is_file():
            raise ValueError('Crie o package.json do projeto antes de instalar dependências.')
        return [[manager, 'install' if manager == 'npm' else 'add', name + ('@' + version if version else '')]]
    if lang == 'dart':
        manifest = root / 'pubspec.yaml'
        if not manifest.is_file():
            raise ValueError('pubspec.yaml não encontrado no projeto.')
        flutter = re.search(r'^\s+sdk:\s*flutter\b', manifest.read_text(encoding='utf-8'), re.M)
        return [['flutter' if flutter else 'dart', 'pub', 'add', name + (':' + version if version else '')]]
    if lang == 'rust':
        if not (root / 'Cargo.toml').is_file():
            raise ValueError('Cargo.toml não encontrado no projeto.')
        return [['cargo', 'add', name + ('@' + version if version else '')], ['cargo', 'fetch']]
    if lang == 'csharp':
        projects = sorted(root.glob('*.csproj'))
        if len(projects) != 1:
            raise ValueError('Informe uma pasta com exatamente um arquivo .csproj.')
        return [['dotnet', 'add', str(projects[0]), 'package', name] + (['--version', version] if version else [])]
    if lang == 'php':
        if not (root / 'composer.json').is_file():
            raise ValueError('composer.json não encontrado no projeto.')
        return [['composer', 'require', name + (':' + version if version else '')]]
    if lang == 'ruby':
        if not (root / 'Gemfile').is_file():
            raise ValueError('Gemfile não encontrado no projeto.')
        return [['bundle', 'add', name] + (['--version', version] if version else [])]
    if not (root / 'go.mod').is_file():
        raise ValueError('go.mod não encontrado no projeto.')
    return [['go', 'get', name + ('@v' + version if version else '')]]


def install(root: Path, commands: list[list[str]]) -> None:
    env = environment(dict(os.environ), root)
    for argv in commands:
        if not Path(argv[0]).is_file() and not shutil.which(argv[0], path=env.get('PATH')):
            raise ValueError('Gerenciador/runtime não encontrado: ' + argv[0] + '. Use codar toolchains.')
        subprocess.run(argv, cwd=root, env=env, check=True, timeout=600)
