"""Instalação transacional de plugins locais ou Git HTTPS, com origem e cópia de recuperação."""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import tempfile
import time
import uuid
from pathlib import Path
from urllib.parse import urlsplit

from codar import config, paths
from codar.locking import file_lock
from codar.plugin_loader import PLUGIN_IGNORE, builtin_root, discover, load_plugin, plugin_files, version_matches
from codar.project import safe_path

METADATA = ".codar-install.json"
IGNORE = PLUGIN_IGNORE


def valid_name(name: str) -> str:
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]*", name):
        raise ValueError("nome de plugin inválido")
    return name


def fingerprint(root: Path) -> str:
    digest = hashlib.sha256()
    for file in plugin_files(root):
        digest.update(file.relative_to(root).as_posix().encode() + b"\0" + file.read_bytes() + b"\0")
    return digest.hexdigest()


def validate_plugin(root: Path, expected: str | None = None):
    fingerprint(root)
    plugin = load_plugin(root, builtin=False)
    if plugin.errors:
        raise ValueError("plugin inválido: " + "; ".join(plugin.errors))
    valid_name(plugin.name)
    if expected and plugin.name != expected:
        raise ValueError(f"a origem contém {plugin.name}; esperado {expected}")
    for builtin in builtin_root().iterdir():
        if builtin.is_dir() and (builtin / "plugin.toml").is_file():
            if load_plugin(builtin, True).name == plugin.name:
                raise ValueError("nome reservado por plugin embutido; use outro nome e ids específicos para sobrescrever padrões")
    bundle = discover(config.load())
    available = {p.name: p for p in bundle.plugins if not p.errors}
    for name, spec in plugin.requires_plugins.items():
        dependency = available.get(name)
        if not dependency or not version_matches(dependency.version, spec):
            raise ValueError(f"instale a dependência {name} {spec} primeiro")
    for existing in available.values():
        spec = existing.requires_plugins.get(plugin.name)
        if spec and not version_matches(plugin.version, spec):
            raise ValueError(f"{existing.name} requer {plugin.name} {spec}; atualização preservada")
    return plugin


def _git(command: list[str], directory: Path) -> str:
    try:
        proc = subprocess.run(["git", "-c", "core.hooksPath=" + str(directory / ".no-hooks"),
                               "-c", "core.autocrlf=false", *command], capture_output=True, text=True, timeout=90,
                              stdin=subprocess.DEVNULL, env={**os.environ, "GIT_TERMINAL_PROMPT": "0"})
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise ValueError(f"não foi possível obter o plugin com Git: {exc}") from exc
    if proc.returncode:
        raise ValueError("Git não concluiu a operação: " + proc.stderr[-1500:].strip())
    return proc.stdout.strip()


def _obtain(source: str, ref: str | None, subdir: str | None, temporary: Path) -> tuple[Path, dict]:
    if source.startswith("https://"):
        url = urlsplit(source)
        if not url.hostname or url.username or url.password or url.query or url.fragment:
            raise ValueError("use URL HTTPS do repositório, sem credenciais nem parâmetros")
        if ref and (ref.startswith("-") or not re.fullmatch(r"[A-Za-z0-9_./-]+", ref) or ".." in ref):
            raise ValueError("referência Git inválida")
        repo = temporary / "repository"
        _git(["clone", "--quiet", "--depth", "1", "--no-checkout", "--", source, str(repo)], temporary)
        if ref:
            _git(["-C", str(repo), "fetch", "--quiet", "--depth", "1", "origin", ref], temporary)
        _git(["-C", str(repo), "checkout", "--quiet", "--detach", "FETCH_HEAD" if ref else "HEAD"], temporary)
        revision = _git(["-C", str(repo), "rev-parse", "HEAD"], temporary)
        root = safe_path(repo, subdir) if subdir else repo
        origin = {"kind": "git", "source": source, "ref": ref or "", "subdir": subdir or "", "revision": revision}
    else:
        if "://" in source or ref:
            raise ValueError("use uma pasta local ou um repositório Git HTTPS")
        root = Path(source).expanduser().resolve()
        root = safe_path(root, subdir) if subdir else root
        origin = {"kind": "local", "source": str(Path(source).expanduser().resolve()), "subdir": subdir or "", "ref": ""}
    if not (root / "plugin.toml").is_file():
        raise ValueError("origem sem plugin.toml; informe --subdir quando o plugin estiver numa subpasta")
    return root, origin


def _private_data() -> Path:
    return paths.ensure_private_dir(paths.data_dir() / "plugin-backups")


def _journal(record: dict | None):
    file = _private_data() / "transaction.json"
    if record is None:
        file.unlink(missing_ok=True)
    else:
        temporary = file.with_suffix(".tmp")
        with temporary.open("w", encoding="utf-8") as handle:
            json.dump(record, handle)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, file)


def _recover_plugins() -> dict:
    file = _private_data() / "transaction.json"
    if not file.exists():
        return {"recovered": False}
    record = json.loads(file.read_text(encoding="utf-8"))
    name = valid_name(record["name"])
    destination = paths.user_plugins_dir() / name
    backup = safe_path(_private_data(), record["backup"])
    if not destination.exists() and backup.is_dir() and record.get("action") != "remove":
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(backup, destination)
    _journal(None)
    return {"recovered": True, "name": name}


def recover_plugins() -> dict:
    with file_lock(_private_data() / ".lock"):
        return _recover_plugins()


def _backup(source: Path, destination: Path):
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".copy-", dir=destination.parent) as directory:
        staged = Path(directory) / "package"
        expected = fingerprint(source)
        shutil.copytree(source, staged)
        if fingerprint(staged) != expected or fingerprint(source) != expected:
            raise ValueError("plugin mudou durante a cópia de recuperação; arquivos preservados")
        os.replace(staged, destination)


def install_plugin(source: str, *, ref: str | None = None, subdir: str | None = None, update: str | None = None,
                   origin_override: dict | None = None) -> dict:
    if not source.startswith("https://"):
        source_root = Path(source).expanduser().resolve()
        if subdir:
            source_root = safe_path(source_root, subdir)
        validate_plugin(source_root, update)  # inválidos não criam uma instalação vazia
    parent = paths.ensure_private_dir(paths.user_plugins_dir())
    with file_lock(_private_data() / ".lock"):
        _recover_plugins()
        with tempfile.TemporaryDirectory(prefix=".install-", dir=parent) as directory:
            temporary = Path(directory)
            source_root, origin = _obtain(source, ref, subdir, temporary)
            if origin_override is not None:
                origin = {k: v for k, v in origin_override.items() if k in ("kind", "source", "ref", "subdir", "revision")}
            if source_root == parent or source_root in parent.parents:
                raise ValueError("a pasta de origem não pode conter a pasta de instalação")
            candidate = validate_plugin(source_root, update)
            destination = parent / candidate.name
            if destination.is_symlink():
                raise ValueError("destino é um link simbólico")
            if destination.exists() and not update:
                raise ValueError(f"já existe: {destination}; use codar plugins update {candidate.name}")
            if update and not destination.is_dir():
                raise ValueError("plugin não está instalado")
            if update:
                info = _metadata(destination)
                if info.get("fingerprint") and info["fingerprint"] != fingerprint(destination):
                    raise ValueError("plugin modificado localmente; arquivos preservados. Instale as mudanças por outra origem")
                current = load_plugin(destination, False)
                if origin_override is None and not current.errors and not version_matches(candidate.version, ">=" + current.version):
                    raise ValueError("a origem é mais antiga que o plugin instalado; use restore para recuperar uma versão anterior")
            staged = temporary / "package"
            source_hash = fingerprint(source_root)
            shutil.copytree(source_root, staged, ignore=shutil.ignore_patterns(*IGNORE))
            if fingerprint(staged) != source_hash:
                raise ValueError("a origem mudou durante a cópia; instalação cancelada")
            validate_plugin(staged, candidate.name)
            backup = None
            if destination.exists():
                backup = _private_data() / candidate.name / (str(time.time_ns()) + "-" + uuid.uuid4().hex[:8])
                backup.parent.mkdir(parents=True, exist_ok=True)
            origin.update(name=candidate.name, version=candidate.version, installed=time.time(), fingerprint=source_hash,
                          backup=backup.relative_to(_private_data()).as_posix() if backup else "")
            (staged / METADATA).write_text(json.dumps(origin, ensure_ascii=False, indent=2), encoding="utf-8")
            if backup:
                _backup(destination, backup)
                _journal({"name": candidate.name, "backup": origin["backup"]})
                os.replace(destination, temporary / "previous")
            try:
                os.replace(staged, destination)
            except BaseException:
                if backup and backup.exists() and not destination.exists():
                    os.replace(temporary / "previous", destination)
                raise
            finally:
                if destination.exists():
                    _journal(None)
            return origin


def _metadata(root: Path) -> dict:
    try:
        return json.loads((root / METADATA).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def update_plugin(name: str, source: str | None = None, *, ref: str | None = None, subdir: str | None = None) -> dict:
    name = valid_name(name)
    info = _metadata(paths.user_plugins_dir() / name)
    source = source or info.get("source")
    if not source:
        raise ValueError("origem não registrada; informe a pasta ou URL do plugin")
    return install_plugin(source, ref=ref if ref is not None else info.get("ref") or None,
                          subdir=subdir if subdir is not None else info.get("subdir") or None, update=name)


def remove_plugin(name: str) -> dict:
    name = valid_name(name)
    with file_lock(_private_data() / ".lock"):
        _recover_plugins()
        destination = paths.user_plugins_dir() / name
        if destination.is_symlink() or not destination.is_dir():
            raise ValueError("plugin do usuário não encontrado")
        dependents = [p.name for p in discover(config.load()).plugins if not p.errors and name in p.requires_plugins]
        if dependents:
            raise ValueError("outros plugins dependem dele: " + ", ".join(dependents))
        backup = _private_data() / name / str(time.time_ns())
        backup.parent.mkdir(parents=True, exist_ok=True)
        _backup(destination, backup)
        with tempfile.TemporaryDirectory(prefix=".remove-", dir=destination.parent) as directory:
            _journal({"name": name, "backup": backup.relative_to(_private_data()).as_posix(), "action": "remove"})
            os.replace(destination, Path(directory) / "previous")
            _journal(None)
        return {"name": name, "removed": True, "backup": str(backup)}


def restore_plugin(name: str) -> dict:
    name = valid_name(name)
    backups = _private_data() / name
    choices = sorted((p for p in backups.iterdir() if p.is_dir() and not p.name.startswith(".")),
                     key=lambda p: p.name, reverse=True) if backups.is_dir() else []
    if not choices:
        raise ValueError("não há versão anterior para recuperar")
    source = choices[0]
    installed = paths.user_plugins_dir() / name
    previous = _metadata(source) or _metadata(installed)
    # A origem continua sendo a original; o backup não vira um canal de atualização.
    return install_plugin(str(source), update=name if installed.exists() else None, origin_override=previous)
