"""Verifica conteúdo, integridade e instalação da distribuição sem alterar o sistema."""

import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile
import zipfile

import pytest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("codar_release_builder", ROOT / "packaging/build_portable.py")
builder = importlib.util.module_from_spec(spec)
spec.loader.exec_module(builder)


@pytest.fixture
def source(tmp_path):
    root = tmp_path / "source with spaces"
    (root / "dist").mkdir(parents=True)
    shutil.copytree(ROOT / "packaging/portable", root / "packaging/portable", ignore=shutil.ignore_patterns("__pycache__"))
    (root / "LICENSE").write_text("test license", encoding="utf-8")
    (root / "src/codar").mkdir(parents=True)
    (root / "src/codar/__init__.py").write_text('__version__ = "0.3.0"\n', encoding="utf-8")
    (root / "clients/powershell/Codar").mkdir(parents=True)
    (root / "clients/powershell/Codar/Codar.psd1").write_text("@{ ModuleVersion = '0.3.0' }", encoding="utf-8")
    with zipfile.ZipFile(root / "dist/codar-0.3.0-py3-none-any.whl", "w") as wheel:
        wheel.writestr("codar-0.3.0.dist-info/METADATA", "Metadata-Version: 2.4\nName: codar\nVersion: 0.3.0\n")
    (root / "clients/vscode").mkdir(parents=True)
    with zipfile.ZipFile(root / "clients/vscode/codar.vsix", "w") as vsix:
        vsix.writestr("extension/package.json", json.dumps({"version":"0.3.0"}))
    return root


@pytest.mark.parametrize("target", ["windows", "macos"])
def test_archive_has_matching_wheel_wrapper_and_checksums(source, target):
    path = builder.write_bundle(source, "0.3.0", target)
    if target == "windows":
        with zipfile.ZipFile(path) as archive:
            entries = {name.split("/",1)[1]:archive.read(name) for name in archive.namelist()}
        assert "install.ps1" in entries and "powershell/Codar/Codar.psd1" in entries
    else:
        with tarfile.open(path) as archive:
            entries = {m.name.split("/",1)[1]:archive.extractfile(m).read() for m in archive.getmembers()}
            assert archive.getmember("codar-0.3.0-macos/install.sh").mode == 0o755
    manifest = json.loads(entries["manifest.json"])
    assert manifest["version"] == "0.3.0" and manifest["platform"] == target
    for name, expected in manifest["sha256"].items():
        assert hashlib.sha256(entries[name]).hexdigest() == expected
    assert "@VERSION@" not in entries["README.md"].decode("utf-8")


def test_inventory_excludes_old_versions_and_covers_every_asset(source):
    (source / "dist/codar-0.2.0.tar.gz").touch()
    (source / "dist/codar_0.3.0-1_all.deb").write_bytes(b"package fixture")
    assets = builder.build(source)
    inventory = json.loads((source / "dist/RELEASE.json").read_text(encoding="utf-8"))
    assert inventory["source_revision"] is None
    assert not any("0.2.0" in p.name for p in assets)
    assert {p.name for p in assets} == {a["name"] for a in inventory["assets"]} | {"RELEASE.json", "SHA256SUMS"}
    for line in (source / "dist/SHA256SUMS").read_text(encoding="utf-8").splitlines():
        expected, name = line.split("  ")
        assert hashlib.sha256((source / "dist" / name).read_bytes()).hexdigest() == expected


def test_stale_vsix_cannot_be_distributed(source):
    with zipfile.ZipFile(source / "clients/vscode/codar.vsix", "w") as vsix:
        vsix.writestr("extension/package.json", json.dumps({"version":"0.2.0"}))
    with pytest.raises(ValueError, match="VSIX"):
        builder.write_bundle(source, "0.3.0", "windows")


@pytest.fixture
def installer(source, tmp_path):
    root = tmp_path / "installed bundle with spaces"
    root.mkdir()
    for name, value in builder.bundle_files(source, "0.3.0", "macos").items():
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(value)
    return root


def test_verify_only_runs_without_pipx_or_network(installer):
    result = subprocess.run([sys.executable, str(installer / "install.py"), "--verify-only"], text=True, capture_output=True)
    assert result.returncode == 0 and "0.3.0 conferidos" in result.stdout


def test_corruption_is_rejected_before_installing(installer):
    (installer / "codar-0.3.0-py3-none-any.whl").write_bytes(b"broken")
    result = subprocess.run([sys.executable, str(installer / "install.py")], text=True, capture_output=True)
    assert result.returncode == 1 and "SHA-256" in result.stderr
    assert "instalado em" not in result.stdout


@pytest.mark.skipif(os.name == "nt", reason="comandos simulados com shebang POSIX")
@pytest.mark.parametrize("failure,version", [(False,"0.3.0"),(True,"0.3.0"),(False,"0.2.0")])
def test_installer_uses_exact_wheel_and_does_not_claim_failed_install(installer, tmp_path, failure, version):
    bindir = tmp_path / "commands with spaces"
    bindir.mkdir()
    log = tmp_path / "calls.jsonl"
    pipx = bindir / "pipx"
    pipx.write_text(f"#!{sys.executable}\nimport json,sys\n"
                    f"with open({str(log)!r},'a') as f: f.write(json.dumps(sys.argv[1:])+'\\n')\n"
                    f"if sys.argv[1]=='install' and {failure!r}: sys.exit(17)\n"
                    f"if sys.argv[1]=='environment': print({str(bindir)!r})\n", encoding="utf-8")
    pipx.chmod(0o755)
    codar = bindir / "codar"
    codar.write_text(f"#!{sys.executable}\nprint({json.dumps({'version':version})!r})\n", encoding="utf-8")
    codar.chmod(0o755)
    env = {**os.environ, "PATH":str(bindir)+os.pathsep+os.environ["PATH"]}
    result = subprocess.run([sys.executable, str(installer / "install.py"), "--core"], env=env, text=True, capture_output=True)
    calls = [json.loads(line) for line in log.read_text(encoding="utf-8").splitlines()]
    assert calls[0][-1] == str(installer / "codar-0.3.0-py3-none-any.whl")
    success = not failure and version == "0.3.0"
    assert (result.returncode == 0) == success
    assert ("instalado em" in result.stdout) == success
    assert (["ensurepath","--prepend"] in calls) == success
