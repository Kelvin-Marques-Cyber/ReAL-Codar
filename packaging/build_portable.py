"""Gera distribuições Python por sistema e um inventário dos arquivos da Release."""

from __future__ import annotations

import hashlib
import io
import json
from pathlib import Path
import platform
import re
import shutil
import subprocess
import tarfile
import zipfile


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def bundle_files(root: Path, version: str, target: str) -> dict[str, bytes]:
    wheel_name = f"codar-{version}-py3-none-any.whl"
    wheel = root / "dist" / wheel_name
    with zipfile.ZipFile(wheel) as archive:
        metadata = archive.read(f"codar-{version}.dist-info/METADATA").decode("utf-8")
        if f"\nVersion: {version}\n" not in metadata:
            raise ValueError("A versão da wheel não corresponde à distribuição")
    portable = root / "packaging" / "portable"
    data = {wheel_name: wheel.read_bytes(), "LICENSE": (root / "LICENSE").read_bytes(),
            "install.py": (portable / "install.py").read_bytes()}
    wrapper = "install.ps1" if target == "windows" else "install.sh"
    data[wrapper] = (portable / wrapper).read_bytes()
    label = "Windows (Python)" if target == "windows" else "macOS (Python)"
    data["README.md"] = (portable / "README.md").read_text(encoding="utf-8").replace(
        "@VERSION@", version).replace("@PLATFORM@", label).encode("utf-8")
    vsix = root / "clients" / "vscode" / "codar.vsix"
    if vsix.is_file():
        with zipfile.ZipFile(vsix) as archive:
            if json.loads(archive.read("extension/package.json")).get("version") != version:
                raise ValueError("A versão do VSIX não corresponde à distribuição")
        data["codar.vsix"] = vsix.read_bytes()
    if target == "windows":
        for file in sorted((root / "clients" / "powershell" / "Codar").iterdir()):
            if file.is_file():
                data[f"powershell/Codar/{file.name}"] = file.read_bytes()
    manifest = {"version": version, "platform": target, "wheel": wheel_name,
                "requires_python": ">=3.10", "sha256": {name: digest(value) for name, value in sorted(data.items())}}
    data["manifest.json"] = (json.dumps(manifest, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    return data


def write_bundle(root: Path, version: str, target: str) -> Path:
    data = bundle_files(root, version, target)
    folder = f"codar-{version}-{target}"
    suffix = "zip" if target == "windows" else "tar.gz"
    output = root / "dist" / f"{folder}-python.{suffix}"
    if target == "windows":
        with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for name, value in sorted(data.items()):
                archive.writestr(f"{folder}/{name}", value)
    else:
        with tarfile.open(output, "w:gz") as archive:
            for name, value in sorted(data.items()):
                entry = tarfile.TarInfo(f"{folder}/{name}")
                entry.size = len(value)
                entry.mode = 0o755 if name == "install.sh" else 0o644
                archive.addfile(entry, io.BytesIO(value))
    return output


def build(root: Path) -> list[Path]:
    source = (root / "src" / "codar" / "__init__.py").read_text(encoding="utf-8")
    version = re.search(r'^__version__ = "([^"]+)"', source, re.MULTILINE).group(1)
    dist = root / "dist"
    for target in ("windows", "macos"):
        write_bundle(root, version, target)
    vsix = root / "clients" / "vscode" / "codar.vsix"
    if vsix.is_file():
        shutil.copyfile(vsix, dist / "codar.vsix")
    candidates = list(dist.glob(f"codar-{version}.*")) + list(dist.glob(f"codar-{version}-*"))
    candidates += list(dist.glob(f"codar_{version}-*"))
    if (dist / "codar.vsix").is_file():
        candidates.append(dist / "codar.vsix")
    assets = sorted({p for p in candidates if p.is_file()})
    try:
        revision = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True, stderr=subprocess.DEVNULL).strip()
        dirty = bool(subprocess.check_output(["git", "status", "--porcelain"], cwd=root, text=True, stderr=subprocess.DEVNULL).strip())
    except (OSError, subprocess.CalledProcessError):
        revision, dirty = None, None
    release = {"version": version, "source_revision": revision if not dirty else None,
               "source_dirty": dirty, "build_platform": platform.system().lower(),
               "assets": [{"name":p.name,"bytes":p.stat().st_size,"sha256":digest(p.read_bytes())} for p in assets]}
    inventory = dist / "RELEASE.json"
    inventory.write_text(json.dumps(release, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    assets.append(inventory)
    checksums = dist / "SHA256SUMS"
    checksums.write_text("".join(f"{digest(p.read_bytes())}  {p.name}\n" for p in assets), encoding="utf-8")
    return [*assets, checksums]


if __name__ == "__main__":
    for path in build(Path(__file__).resolve().parents[1]):
        print(path.name)
