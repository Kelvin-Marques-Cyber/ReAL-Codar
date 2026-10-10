"""Várias versões instaladas e escolha explícita por projeto, sem trocar o Python do CODAR."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import shlex
import shutil
import subprocess
import sys
import tempfile

from codar import paths


def _state_path():
    return paths.data_dir() / 'runtime-selections.json'


def selections():
    file = _state_path()
    if not file.exists():
        return {}
    try:
        state = json.loads(file.read_text(encoding='utf-8'))
        if not isinstance(state, dict) or any(not isinstance(entries, dict) or any(
                not isinstance(entry, dict) or not isinstance(entry.get('executable'), str)
                or not isinstance(entry.get('version'), str) for entry in entries.values()) for entries in state.values()):
            raise ValueError('formato inválido')
        return state
    except (ValueError, OSError) as exc:
        raise ValueError('Configuração de runtimes inválida; confira ' + str(file)) from exc


def _entries(values, project=None):
    entries = dict(values.get('*', {}))
    if project:
        root = Path(project).resolve()
        for folder in reversed((root, *root.parents)):
            entries.update(values.get(str(folder), {}))
    return entries


def selected(name, project=None):
    entry = _entries(selections(), project).get(name)
    if entry and not Path(entry['executable']).is_file():
        raise ValueError('O runtime selecionado não existe mais: ' + entry['executable'])
    return entry


def _version(executable, name):
    if name == 'python':
        argv = [str(executable), '-I', '-c', 'import sys; print(".".join(map(str,sys.version_info[:3])))']
    else:
        argv = [str(executable), {'go': 'version', 'lua': '-v', 'java': '-version'}.get(name, '--version')]
    try:
        result = subprocess.run(argv, capture_output=True, text=True, timeout=4)
        match = re.search(r'\b\d+\.\d+\.\d+\b', result.stdout + result.stderr)
        return match[0] if result.returncode == 0 and match else ''
    except (OSError, subprocess.TimeoutExpired):
        return ''


def versions(name='python'):
    from codar import toolchains

    name = toolchains.canonical(name)
    candidates = []
    if name == 'python':
        candidates.append(Path(getattr(sys, '_base_executable', sys.executable)))
        uv = shutil.which('uv')
        if uv:
            for env in (dict(os.environ), {**os.environ, 'UV_PYTHON_INSTALL_DIR': str(toolchains.root() / 'python')}):
                try:
                    result = subprocess.run([uv, 'python', 'list', '--only-installed', '--output-format', 'json'],
                                            env=env, capture_output=True, text=True, timeout=10)
                    if result.returncode == 0:
                        candidates.extend(Path(item['path']) for item in json.loads(result.stdout)
                                          if isinstance(item, dict) and item.get('path'))
                except (OSError, ValueError, TypeError, subprocess.TimeoutExpired):
                    pass
        for directory in os.environ.get('PATH', '').split(os.pathsep)[:64]:
            folder = Path(directory)
            if folder.is_dir():
                try:
                    candidates.extend(p for p in list(folder.iterdir())[:10000]
                                      if re.fullmatch(r'python(?:3(?:\.\d+)?)?(?:\.exe)?', p.name))
                except OSError:
                    pass
    else:
        if executable := toolchains.executable(name):
            candidates.append(Path(executable))
        for folder in (toolchains.root() / 'versions' / name).glob('*'):
            suffix = ('.bat' if name == 'flutter' else '.exe') if os.name == 'nt' else ''
            candidates.append(folder / (('dart-sdk/bin/dart' if name == 'dart' else 'bin/flutter' if name == 'flutter' else 'pwsh') + suffix))
    entries, seen = [], set()
    for executable in candidates:
        if not executable.is_file():
            continue
        resolved = str(executable.resolve())
        if resolved in seen:
            continue
        seen.add(resolved)
        version = _version(executable, name)
        if version:
            entries.append(dict(language=name, version=version, executable=str(executable.absolute()),
                                key=version + ':' + hashlib.sha256(str(executable.absolute()).encode()).hexdigest()[:8]))
    return sorted(entries, key=lambda entry: (tuple(map(int, entry['version'].split('.'))), entry['executable']), reverse=True)


def choose(name, version, project=None, executable=None):
    from codar import toolchains

    name = toolchains.canonical(name)
    if executable:
        path = Path(executable).expanduser().absolute()
        actual = _version(path, name)
        if not actual:
            raise ValueError('Executável inválido ou versão não identificada.')
        entry = dict(language=name, version=actual, executable=str(path))
    else:
        if not re.fullmatch(r'\d+\.\d+(?:\.\d+)?(?::[a-f0-9]{8})?', version):
            raise ValueError('Escolha uma versão numérica instalada, como 3.13.')
        entries = versions(name)
        entry = next((item for item in entries if item['key'] == version or item['version'] == version
                      or item['version'].startswith(version + '.')), None)
        if entry is None:
            raise ValueError('Versão não instalada. Use codar toolchains versions ou install --version.')
    scope = str(Path(project).resolve()) if project else '*'
    state = selections()
    state.setdefault(scope, {})[name] = entry
    file = _state_path()
    file.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=file.parent, delete=False) as output:
        json.dump(state, output, ensure_ascii=False, indent=2)
        temporary = Path(output.name)
    temporary.replace(file)
    return entry


def environment(env, project=None):
    result = dict(env)
    entries = _entries(selections(), project)
    directories = []
    for name, entry in entries.items():
        executable = Path(entry['executable'])
        if not executable.is_file():
            raise ValueError('O runtime selecionado foi removido: ' + str(executable))
        if name == 'python' and os.name != 'nt':
            key = hashlib.sha256(str(executable).encode()).hexdigest()[:16]
            shim = paths.data_dir() / 'runtime-shims' / key
            shim.mkdir(parents=True, exist_ok=True)
            for alias in ('python', 'python3'):
                target = shim / alias
                if not target.exists():
                    target.write_text('#!/bin/sh\nexec ' + shlex.quote(str(executable)) + ' "$@"\n')
                    target.chmod(0o700)
            for alias in ('pip', 'pip3'):
                target = shim / alias
                if not target.exists():
                    target.write_text('#!/bin/sh\nexec ' + shlex.quote(str(executable)) + ' -m pip "$@"\n')
                    target.chmod(0o700)
            directories.append(str(shim))
        directories.append(str(executable.parent))
        if name == 'python':
            result.pop('VIRTUAL_ENV', None)
            if (executable.parent.parent / 'pyvenv.cfg').is_file():
                result['VIRTUAL_ENV'] = str(executable.parent.parent)
    if directories:
        result['PATH'] = os.pathsep.join(directories) + os.pathsep + result.get('PATH', '')
    return result


def install_python(versions_to_install, dry_run=False):
    from codar import toolchains

    if not versions_to_install or any(not re.fullmatch(r'3\.\d{1,2}(?:\.\d{1,2})?', version) for version in versions_to_install):
        raise ValueError('Use versões Python como 3.12 ou 3.13.6.')
    uv = shutil.which('uv')
    if not uv:
        print('pipx install uv')
        if not dry_run:
            pipx = shutil.which('pipx')
            if not pipx:
                raise ValueError('Instale pipx ou uv antes de baixar versões Python.')
            subprocess.run([pipx, 'install', 'uv'], check=True)
            location = subprocess.run([pipx, 'environment', '--value', 'PIPX_BIN_DIR'],
                                      capture_output=True, text=True, check=True).stdout.strip()
            uv = shutil.which('uv') or str(Path(location) / ('uv.exe' if os.name == 'nt' else 'uv'))
    command = [uv or 'uv', 'python', 'install', *versions_to_install]
    print(shlex.join(command))
    print('Origem: distribuições python-build-standalone da Astral, gerenciadas pelo uv. '
          'https://docs.astral.sh/uv/guides/install-python/')
    if not dry_run:
        subprocess.run(command, env={**os.environ, 'UV_PYTHON_INSTALL_DIR': str(toolchains.root() / 'python')}, check=True)


def create_venv(project, version, folder='.venv'):
    from codar.project import safe_path

    root = Path(project).resolve()
    target = safe_path(root, folder)
    entries = versions('python')
    entry = next((item for item in entries if item['key'] == version or item['version'] == version
                  or item['version'].startswith(version + '.')), None)
    if not entry:
        raise ValueError('Instale a versão Python antes de criar seu venv.')
    target.mkdir(exist_ok=False)
    subprocess.run([entry['executable'], '-m', 'venv', str(target)], check=True)
    executable = target / ('Scripts/python.exe' if os.name == 'nt' else 'bin/python')
    return choose('python', version, project=root, executable=str(executable))
