import argparse
import hashlib
import io
import json
import zipfile

import pytest

from codar import toolchains
from codar.cli.toolchaincmd import cmd_toolchains


def test_gerenciadores_e_aliases(monkeypatch):
    monkeypatch.setattr(toolchains.os, "geteuid", lambda: 0)
    assert toolchains.canonical("flutter") == "flutter"  # não confunde framework com Dart
    assert toolchains.canonical("ps1") == "powershell"
    assert toolchains.package_commands("go", "apt-get") == [["apt-get", "update"], ["apt-get", "install", "-y", "golang-go"]]
    assert toolchains.package_commands("ts", "zypper") == [["zypper", "--non-interactive", "install", "nodejs", "npm"]]
    assert "Microsoft.PowerShell" in toolchains.package_commands("pwsh", "winget")[0]
    with pytest.raises(toolchains.InstallError):
        toolchains.canonical("dart; rm -rf app")


def test_dry_run_nao_baixa_sdk(monkeypatch, capsys, tmp_path):
    monkeypatch.setenv("CODAR_HOME", str(tmp_path))
    monkeypatch.setattr(toolchains, "executable", lambda name: None)
    monkeypatch.setattr(toolchains, "install_sdk", lambda name: pytest.fail("download no dry-run"))
    toolchains.install("flutter", dry_run=True)
    assert "SDK oficial" in capsys.readouterr().out
    assert not (tmp_path / "data/toolchains").exists()


def test_cli_valida_todos_os_nomes_antes_de_instalar(monkeypatch):
    calls = []
    monkeypatch.setattr(toolchains, "install", lambda *a, **kw: calls.append(a))
    args = argparse.Namespace(action="install", names=["dart", "linguagem_inexistente"], dry_run=False)
    assert cmd_toolchains(args) == 1 and calls == []


def test_download_confere_checksum_e_recusa_arquivo_invalido(monkeypatch, tmp_path):
    data = b"sdk de teste"
    monkeypatch.setattr(toolchains, "_get", lambda url: io.BytesIO(data))
    target = tmp_path / "sdk.zip"
    toolchains.download("https://sdk.invalid/a.zip", target, hashlib.sha256(data).hexdigest())
    assert target.read_bytes() == data
    with pytest.raises(toolchains.InstallError, match="não confere"):
        toolchains.download("https://sdk.invalid/a.zip", target, "0" * 64)
    assert not target.exists()


def test_hashes_powershell_em_utf16(monkeypatch):
    data = ("A" * 64 + "  powershell-linux-x64.tar.gz\r\n").encode("utf-16")
    monkeypatch.setattr(toolchains, "_get", lambda url: io.BytesIO(data))
    assert toolchains._text("https://sdk.invalid/hashes.sha256").startswith("A" * 64)


def test_extracao_recusa_caminhos_fora_da_pasta(tmp_path):
    archive = tmp_path / "sdk.zip"
    with zipfile.ZipFile(archive, "w") as z:
        z.writestr("../../fora.txt", "não deve ser extraído")
    with pytest.raises(toolchains.InstallError, match="fora da pasta"):
        toolchains.extract(archive, tmp_path / "sdk")
    assert not (tmp_path.parent / "fora.txt").exists()


def test_instalacao_dart_atomica_e_executavel_no_studio(monkeypatch, tmp_path):
    monkeypatch.setenv("CODAR_HOME", str(tmp_path / "codar"))
    monkeypatch.setattr(toolchains, "_platform", lambda: ("linux", "x64"))
    monkeypatch.setattr(toolchains, "_text", lambda url: json.dumps({"version": "3.13.5"}) if url.endswith("VERSION") else "a" * 64)

    def download(url, destination, checksum):
        with zipfile.ZipFile(destination, "w") as z:
            info = zipfile.ZipInfo("dart-sdk/bin/dart")
            info.external_attr = 0o100755 << 16
            z.writestr(info, "#!/bin/sh\nexit 0\n")

    monkeypatch.setattr(toolchains, "download", download)
    toolchains.install_sdk("dart")
    found = toolchains.executable("dart", path="/nada")
    assert found and found.endswith("dart-sdk/bin/dart")
    assert str(toolchains.root() / "dart/dart-sdk/bin") in toolchains.environment({"PATH": "/nada"})["PATH"]
    with pytest.raises(toolchains.InstallError, match="já existe"):
        toolchains.install_sdk("dart")


def test_falha_de_download_nao_publica_instalacao_parcial(monkeypatch, tmp_path):
    monkeypatch.setenv("CODAR_HOME", str(tmp_path))
    monkeypatch.setattr(toolchains, "_platform", lambda: ("linux", "x64"))
    monkeypatch.setattr(toolchains, "_text", lambda url: json.dumps({"version": "3.13.5"}) if url.endswith("VERSION") else "a" * 64)
    monkeypatch.setattr(toolchains, "download", lambda *args: (_ for _ in ()).throw(toolchains.InstallError("falhou")))
    with pytest.raises(toolchains.InstallError):
        toolchains.install_sdk("dart")
    assert not (toolchains.root() / "dart").exists()
    assert list(toolchains.root().iterdir()) == []
