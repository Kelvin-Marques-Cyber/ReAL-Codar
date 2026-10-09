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
