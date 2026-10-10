"""SDKs opcionais: usa ferramentas existentes, instala SDKs oficiais por usuário e pacotes pelo gerenciador do SO."""

from __future__ import annotations

import hashlib
import json
import os
import platform
import re
import shlex
import shutil
import subprocess
import tarfile
import tempfile
import urllib.request
import zipfile
from pathlib import Path

from codar import langs, paths

TOOLS = {"python": ("python3", "python"), "javascript": ("node",), "typescript": ("node",),
         "go": ("go",), "rust": ("rustc",), "java": ("java",), "c": ("cc", "gcc"), "cpp": ("c++", "g++"),
         "php": ("php",), "ruby": ("ruby",), "lua": ("lua",), "dart": ("dart",), "flutter": ("flutter",),
         "powershell": ("pwsh",)}
DOCS = {"dart": "https://dart.dev/get-dart", "flutter": "https://docs.flutter.dev/install/manual",
        "powershell": "https://learn.microsoft.com/powershell/scripting/install/installing-powershell"}
_PACKAGES = {
    "apt-get": {"python": "python3", "javascript": "nodejs npm", "go": "golang-go", "rust": "rustc cargo",
                "java": "default-jdk", "c": "build-essential", "cpp": "build-essential", "php": "php-cli",
                "ruby": "ruby", "lua": "lua5.4"},
    "dnf": {"python": "python3", "javascript": "nodejs npm", "go": "golang", "rust": "rust cargo",
            "java": "java-latest-openjdk-devel", "c": "gcc", "cpp": "gcc-c++", "php": "php-cli",
            "ruby": "ruby", "lua": "lua"},
    "zypper": {"python": "python3", "javascript": "nodejs npm", "go": "go", "rust": "rust cargo",
               "java": "java-devel", "c": "gcc", "cpp": "gcc-c++", "php": "php-cli", "ruby": "ruby", "lua": "lua"},
    "pacman": {"python": "python", "javascript": "nodejs npm", "go": "go", "rust": "rust",
               "java": "jdk-openjdk", "c": "base-devel", "cpp": "base-devel", "php": "php", "ruby": "ruby", "lua": "lua"},
    "apk": {"python": "python3", "javascript": "nodejs npm", "go": "go", "rust": "rust cargo",
            "java": "openjdk21", "c": "build-base", "cpp": "build-base", "php": "php", "ruby": "ruby", "lua": "lua5.4"},
    "brew": {"python": "python", "javascript": "node", "go": "go", "rust": "rust", "java": "openjdk",
             "c": "gcc", "cpp": "gcc", "php": "php", "ruby": "ruby", "lua": "lua"},
    "winget": {"python": "Python.Python.3.13", "javascript": "OpenJS.NodeJS.LTS", "go": "GoLang.Go",
               "rust": "Rustlang.Rustup", "java": "EclipseAdoptium.Temurin.21.JDK", "php": "PHP.PHP.8.4",
               "powershell": "Microsoft.PowerShell"},
}


class InstallError(RuntimeError):
    pass


def canonical(name: str) -> str:
    if name.lower() == "flutter":
        return "flutter"
    lang = langs.try_resolve(name)
    key = lang.id if lang else name.lower()
    if key not in TOOLS:
        raise InstallError(f"instalação automática não disponível para {name}; use `codar toolchains list`")
    return key


def root() -> Path:
    return paths.data_dir() / "toolchains"


def bin_dirs() -> list[Path]:
    base = root()
    return [p for p in (base / "flutter/bin", base / "dart/dart-sdk/bin", base / "powershell") if p.is_dir()]


def environment(env: dict[str, str] | None = None, project: str | Path | None = None) -> dict[str, str]:
    env = dict(os.environ if env is None else env)
    extra = os.pathsep.join(str(p) for p in bin_dirs())
    if extra:
        env["PATH"] = env.get("PATH", "") + os.pathsep + extra
    from codar.runtimes import environment as selected_environment

    return selected_environment(env, project)


def executable(name: str, path: str | None = None, project: str | Path | None = None) -> str | None:
    key = canonical(name)
    from codar.runtimes import selected

    if chosen := selected(key, project):
        return chosen['executable']
    search = environment({"PATH": path if path is not None else os.environ.get("PATH", "")}, project=project)["PATH"]
    for command in TOOLS[key]:
        found = shutil.which(command, path=search)
        if found:
            return found
    return None


def manager() -> str | None:
    choices = ("winget",) if os.name == "nt" else (("brew",) if platform.system() == "Darwin" else
                                                   ("zypper", "apt-get", "dnf", "pacman", "apk"))
    return next((pm for pm in choices if shutil.which(pm)), None)


def package_commands(name: str, pm: str | None = None) -> list[list[str]]:
    key, pm = canonical(name), pm or manager()
    package = _PACKAGES.get(pm or "", {}).get("javascript" if key == "typescript" else key)
    if not package:
        raise InstallError(f"nenhum instalador de {key} disponível neste sistema")
    prefix = []
    if pm not in ("brew", "winget") and os.geteuid() != 0:
        if not shutil.which("sudo"):
            raise InstallError("o gerenciador do sistema precisa de privilégios de administrador (sudo ausente)")
        prefix = ["sudo"]
    if pm == "winget":
        return [[pm, "install", "--id", package, "--exact", "--accept-package-agreements", "--accept-source-agreements"]]
    if pm == "apt-get":
        return [prefix + [pm, "update"], prefix + [pm, "install", "-y", *package.split()]]
    args = {"dnf": ["install", "-y"], "zypper": ["--non-interactive", "install"],
            "pacman": ["-S", "--needed", "--noconfirm"], "apk": ["add"], "brew": ["install"]}[pm]
    return [prefix + [pm, *args, *package.split()]]


def _get(url: str):
    return urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "codar-toolchains"}), timeout=30)


def _text(url: str) -> str:
    with _get(url) as response:
        data = response.read(2_000_000)
        # hashes.sha256 do PowerShell pode vir em UTF-16 com BOM.
        return data.decode("utf-16" if data.startswith((b"\xff\xfe", b"\xfe\xff")) else "utf-8-sig")


def download(url: str, destination: Path, sha256: str) -> None:
    if not re.fullmatch(r"[0-9a-fA-F]{64}", sha256):
        raise InstallError("o servidor não forneceu um SHA-256 válido")
    digest = hashlib.sha256()
    with _get(url) as response, destination.open("wb") as out:
        while chunk := response.read(1024 * 1024):
            digest.update(chunk)
            out.write(chunk)
    if digest.hexdigest().lower() != sha256.lower():
        destination.unlink()
        raise InstallError("SHA-256 do SDK não confere; instalação cancelada")


def extract(archive: Path, directory: Path) -> None:
    """Recusa arquivos que escapem da pasta e links de arquivos de download."""
    directory = directory.resolve()

    def inside(name):
        if not (directory / name).resolve().is_relative_to(directory):
            raise InstallError("o arquivo do SDK contém um caminho fora da pasta de instalação")

    if zipfile.is_zipfile(archive):
        with zipfile.ZipFile(archive) as z:
            for member in z.infolist():
                inside(member.filename)
                mode = member.external_attr >> 16
                if mode & 0o170000 == 0o120000:
                    raise InstallError("link simbólico inesperado no SDK")
                z.extract(member, directory)
                if mode & 0o111 and not member.is_dir():
                    (directory / member.filename).chmod(0o755)
    else:
        with tarfile.open(archive) as t:
            for member in t.getmembers():
                inside(member.name)
                if not (member.isfile() or member.isdir()):
                    raise InstallError("tipo de arquivo inesperado no SDK")
            t.extractall(directory, **({"filter": "data"} if hasattr(tarfile, "data_filter") else {}))


def _platform() -> tuple[str, str]:
    system = {"Linux": "linux", "Darwin": "macos", "Windows": "windows"}.get(platform.system())
    arch = {"x86_64": "x64", "amd64": "x64", "aarch64": "arm64", "arm64": "arm64"}.get(platform.machine().lower())
    if not system or not arch:
        raise InstallError("SDK automático disponível para Linux, macOS e Windows em x64/arm64")
    return system, arch


def install_sdk(name: str) -> None:
    key = canonical(name)
    system, arch = _platform()
    base = root()
    base.mkdir(parents=True, exist_ok=True)
    destination = base / key
    if destination.exists():
        raise InstallError(f"já existe uma instalação em {destination}; confira `codar toolchains list`")
    with tempfile.TemporaryDirectory(prefix=f"{key}-", dir=base) as temporary:
        stage = Path(temporary)
        payload = stage / "sdk"
        if key == "flutter":
            git = shutil.which("git")
            if not git:
                raise InstallError("instale Git antes de instalar o Flutter")
            subprocess.run([git, "clone", "--depth", "1", "--branch", "stable",
                            "https://github.com/flutter/flutter.git", str(payload)], check=True)
            binary = payload / "bin" / ("flutter.bat" if system == "windows" else "flutter")
        elif key == "dart":
            archive_root = "https://storage.googleapis.com/dart-archive/channels/stable/release"
            version = json.loads(_text(f"{archive_root}/latest/VERSION"))["version"]
            if not re.fullmatch(r"\d+\.\d+\.\d+", version):
                raise InstallError("versão estável do Dart inválida")
            sdk_os = "macos" if system == "macos" else system
            url = f"{archive_root}/{version}/sdk/dartsdk-{sdk_os}-{arch}-release.zip"
            checksum = _text(url + ".sha256sum").split()[0]
            archive = stage / "sdk.zip"
            download(url, archive, checksum)
            extract(archive, payload)
            binary = payload / "dart-sdk/bin" / ("dart.exe" if system == "windows" else "dart")
        elif key == "powershell" and system != "windows":
            release = json.loads(_text("https://api.github.com/repos/PowerShell/PowerShell/releases/latest"))
            assets = release["assets"]
            sdk_os = "osx" if system == "macos" else "linux"
            if system == "linux" and ("musl" in platform.libc_ver()[0].lower() or list(Path("/lib").glob("ld-musl-*"))):
                sdk_os = "linux-musl"
            suffix = f"-{sdk_os}-{arch}.tar.gz"
            asset = next((a for a in assets if a["name"].endswith(suffix)), None)
            if not asset:
                raise InstallError(f"esta release do PowerShell não fornece um SDK para {sdk_os}/{arch}")
            checksum_asset = next((a for a in assets if a["name"].lower() == "hashes.sha256"), None)
            if not checksum_asset:
                raise InstallError("a release do PowerShell não fornece hashes.sha256")
            hashes = _text(checksum_asset["browser_download_url"])
            checksum = next((line.split()[0] for line in hashes.splitlines()
                             if line.split() and line.split()[-1].lstrip("*") == asset["name"]), "")
            archive = stage / "sdk.tar.gz"
            download(asset["browser_download_url"], archive, checksum)
            extract(archive, payload)
            binary = payload / "pwsh"
            if binary.is_file():
                binary.chmod(0o755)
        else:
            raise InstallError(f"SDK {key} indisponível para este sistema")
        if not binary.is_file():
            raise InstallError("o SDK baixado não contém o executável esperado")
        payload.rename(destination)  # só publica depois de baixar, conferir e extrair tudo


def install(name: str, dry_run: bool = False) -> None:
    key = canonical(name)
    found = executable(key)
    if found:
        print(f"{key}: já disponível em {found}")
        return
    sdk = key in ("dart", "flutter") or (key == "powershell" and os.name != "nt")
    if sdk:
        print(f"{key}: SDK oficial em {root() / key} · {DOCS[key]}", flush=True)
        if not dry_run:
            install_sdk(key)
    else:
        for command in package_commands(key):
            print(subprocess.list2cmdline(command) if os.name == "nt" else shlex.join(command), flush=True)
            if not dry_run:
                subprocess.run(command, check=True)
    if not dry_run:
        print(f"{key}: instalação concluída. Reabra seu terminal se o gerenciador modificou o PATH.")
