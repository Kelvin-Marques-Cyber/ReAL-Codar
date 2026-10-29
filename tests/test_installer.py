"""Exercita o script real com comandos externos falsos, sem instalar pacotes no sistema."""

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "packaging/install.sh"
pytestmark = pytest.mark.skipif(shutil.which("sh") is None, reason="instalador POSIX")


@pytest.fixture
def sandbox(tmp_path):
    bindir = tmp_path / "bin with spaces"
    bindir.mkdir()
    log = tmp_path / "calls.jsonl"
    env = {**os.environ, "PATH": f"{bindir}{os.pathsep}{os.environ['PATH']}",
           "MOCK_BIN": str(bindir), "MOCK_LOG": str(log)}
    env.pop("CODAR_VERSION", None)
    env.pop("CODAR_PKG", None)

    def command(name, body):
        path = bindir / name
        path.write_text(f"#!{sys.executable}\nimport os, sys, json\n" + body, encoding="utf-8")
        path.chmod(0o755)

    record = "with open(os.environ['MOCK_LOG'], 'a') as f: f.write(json.dumps(sys.argv) + '\\n')\n"
    command("id", "print(os.environ.get('MOCK_UID', '1000'))\n")
    command("apt-get", record + "sys.exit(99)\n")
    command("pipx", record + "if sys.argv[1] == 'environment': print(os.environ['MOCK_BIN'])\n"
            "elif os.environ.get('MOCK_PIPX_FAIL'): sys.exit(7)\n")
    command("codar", record + "print('codar 0.1.1')\n")
    command("curl", record + "sys.exit(22)\n")

    def run(*args):
        result = subprocess.run(["sh", str(SCRIPT), *args], env=env, capture_output=True, text=True)
        calls = [json.loads(line) for line in log.read_text().splitlines()] if log.exists() else []
        return result, calls

    return env, run


def test_pipx_updates_main_and_verifies_explicit_executable(sandbox):
    env, run = sandbox
    result, calls = run("--pipx")
    assert result.returncode == 0, result.stderr
    install = calls[0]
    assert install[1:4] == ["install", "--force", "--pip-args=--no-cache-dir"]
    assert install[-1] == "codar[studio] @ git+https://github.com/Kelvin-Marques-Cyber/ReAL-Codar.git@main"
    assert calls[-1] == [str(Path(env["MOCK_BIN"]) / "codar"), "version", "--verbose"]
    assert not any(Path(call[0]).name in ("apt-get", "curl") for call in calls)


@pytest.mark.parametrize("variable,value", [("MOCK_UID", "0"), ("CODAR_VERSION", "0.1.1"),
                                           ("CODAR_PKG", "local.rpm")])
def test_pipx_rejects_root_or_conflicting_release_options(sandbox, variable, value):
    env, run = sandbox
    env[variable] = value
    result, calls = run("--pipx")
    assert result.returncode != 0 and not calls


def test_pipx_failure_does_not_claim_success(sandbox):
    env, run = sandbox
    env["MOCK_PIPX_FAIL"] = "1"
    result, calls = run("--pipx")
    assert result.returncode == 7
    assert len(calls) == 1


@pytest.mark.parametrize("version", ["0.1.1", "v0.1.1"])
def test_unavailable_release_explains_main_without_installing(sandbox, version):
    env, run = sandbox
    env["CODAR_VERSION"] = version
    result, calls = run()
    assert result.returncode != 0
    assert "--pipx" in result.stderr and "Release" in result.stderr
    assert calls[0][-1].endswith("/releases/tags/v0.1.1")
    assert not any(Path(call[0]).name == "apt-get" for call in calls)


def test_unknown_option_does_not_install(sandbox):
    _, run = sandbox
    result, calls = run("--typo")
    assert result.returncode != 0 and not calls


def _release(sandbox, tmp_path, conteudo_soma):
    """curl falso: a Release tem o .deb e (se conteudo_soma) um SHA256SUMS; sudo só registra a chamada."""
    import hashlib

    env, run = sandbox
    pacote = b"pacote deb falso"
    soma = conteudo_soma(hashlib.sha256(pacote).hexdigest()) if conteudo_soma else None
    base = "https://github.com/Kelvin-Marques-Cyber/ReAL-Codar/releases/download/v0.5.0/"
    ativos = [{"browser_download_url": base + "codar_0.5.0-1_all.deb"}]
    if soma is not None:
        ativos.append({"browser_download_url": base + "SHA256SUMS"})
    dados = {"release": json.dumps({"assets": ativos}, indent=1), "deb": pacote.decode(), "sums": soma or ""}
    (tmp_path / "dados.json").write_text(json.dumps(dados), encoding="utf-8")
    env["MOCK_DADOS"] = str(tmp_path / "dados.json")
    bindir = Path(env["MOCK_BIN"])
    corpo = ("import json, os, sys\n"
             "with open(os.environ['MOCK_LOG'], 'a') as f: f.write(json.dumps(sys.argv) + '\\n')\n"
             "d = json.load(open(os.environ['MOCK_DADOS']))\n"
             "url = sys.argv[-1]; destino = sys.argv[sys.argv.index('-o') + 1]\n"
             "chave = 'release' if 'api.github.com' in url else 'sums' if url.endswith('SHA256SUMS') else 'deb'\n"
             "open(destino, 'w').write(d[chave])\n")
    for nome, texto in (("curl", corpo), ("sudo", "import json, os, sys\n"
                        "with open(os.environ['MOCK_LOG'], 'a') as f: f.write(json.dumps(sys.argv) + '\\n')\n")):
        caminho = bindir / nome
        caminho.write_text(f"#!{sys.executable}\n" + texto, encoding="utf-8")
        caminho.chmod(0o755)
    return run


def _instalou(calls):
    return any(Path(call[0]).name == "sudo" and "apt-get" in call for call in calls)


def test_pacote_so_e_instalado_com_sha256_conferido(sandbox, tmp_path):
    run = _release(sandbox, tmp_path, lambda h: f"{h}  codar_0.5.0-1_all.deb\n")
    result, calls = run()
    assert "SHA-256 conferido" in result.stdout and _instalou(calls), result.stderr


@pytest.mark.parametrize("soma", [lambda h: "0" * 64 + "  codar_0.5.0-1_all.deb\n",
                                  lambda h: f"{h}  outro-arquivo.deb\n", None],
                         ids=["sha-diferente", "pacote-nao-listado", "sem-sha256sums"])
def test_pacote_sem_verificacao_nao_e_instalado(sandbox, tmp_path, soma):
    run = _release(sandbox, tmp_path, soma)
    result, calls = run()
    assert result.returncode != 0 and "cancelada" in result.stderr and not _instalou(calls)
