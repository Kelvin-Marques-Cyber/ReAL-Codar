import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest
from codar import runtimes, toolchains
from codar.advisor.pacotes import python_do_projeto
from codar.cli.toolchaincmd import cmd_toolchains


def test_escolha_por_projeto_e_subpastas_nao_muda_codar(tmp_path, monkeypatch):
    monkeypatch.setenv('CODAR_HOME', str(tmp_path / 'config'))
    a, b = tmp_path / 'a', tmp_path / 'b'
    a.mkdir()
    b.mkdir()
    original = sys.executable
    entry = runtimes.choose('python', '', project=a, executable=original)
    assert python_do_projeto(a) == original
    assert runtimes.selected('python', a / 'src') == entry
    assert runtimes.selected('python', b) is None
    assert sys.executable == original
    if os.name != 'nt':
        env = toolchains.environment(project=a / 'src')
        result = subprocess.run(['python', '-I', '-c', 'import sys;print(sys.prefix)'], env=env,
                                capture_output=True, text=True, check=True)
        assert result.stdout.strip() == sys.prefix


def test_catalogo_escolhe_versao_instalada_e_venv_nunca_sobrescreve(tmp_path, monkeypatch):
    monkeypatch.setenv('CODAR_HOME', str(tmp_path / 'home'))
    entries = runtimes.versions('python')
    assert entries and all(Path(entry['executable']).is_file() for entry in entries)
    base = str(Path(getattr(sys, '_base_executable', sys.executable)).absolute())
    entry = next(e for e in entries if e['executable'] == base)
    project = tmp_path / 'project'
    project.mkdir()
    chosen = runtimes.create_venv(project, entry['key'], '.venv-test')
    if os.name != 'nt':
        env = toolchains.environment(project=project)
        result = subprocess.run(['python', '-c', 'import sys;print(sys.prefix)'], env=env,
                                capture_output=True, text=True, check=True)
        assert result.stdout.strip() == str(project / '.venv-test')
        assert env['VIRTUAL_ENV'] == str(project / '.venv-test')
    assert python_do_projeto(project) == chosen['executable']
    marker = project / '.venv-test' / 'preservar.txt'
    marker.write_text('meus dados')
    with pytest.raises(FileExistsError):
        runtimes.create_venv(project, entry['key'], '.venv-test')
    assert marker.read_text() == 'meus dados'


def test_instalar_multiplas_versoes_dryrun_e_config_invalida(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv('CODAR_HOME', str(tmp_path))
    args = argparse.Namespace(action='install', names=['python'], sdk_versions=['3.12', '3.13'], dry_run=True)
    assert cmd_toolchains(args) == 0
    assert 'python install 3.12 3.13' in capsys.readouterr().out
    assert not toolchains.root().exists()
    args.sdk_versions = ['3.13; echo erro']
    assert cmd_toolchains(args) == 1
    file = runtimes._state_path()
    file.parent.mkdir(parents=True, exist_ok=True)
    file.write_text(json.dumps(['formato errado']))
    with pytest.raises(ValueError, match='inválida'):
        runtimes.environment({})
