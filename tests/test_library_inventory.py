import json
from pathlib import Path
import subprocess

import pytest

from codar.cli.main import main
from codar.libraries import LibraryCatalog
from codar.library_inventory import inventory


def write(root, name, text):
    file = root / name
    file.parent.mkdir(parents=True, exist_ok=True)
    file.write_text(text, encoding='utf-8')
    return file


@pytest.fixture(autouse=True)
def home(tmp_path, monkeypatch):
    monkeypatch.setenv('CODAR_HOME', str(tmp_path / 'home'))


def test_inventario_python_une_estados_sem_importar_biblioteca(tmp_path, monkeypatch):
    write(tmp_path, 'pyproject.toml', '[project]\ndependencies=["requests>=2", "naoinstalada==1"]\n')
    write(tmp_path, 'app.py', 'import requests\n')
    write(tmp_path, '.venv/pyvenv.cfg', '')
    base = '.venv/lib/python3.12/site-packages/'
    write(tmp_path, base + 'requests-2.dist-info/METADATA', 'Name: requests\nVersion: 2.0\n')
    write(tmp_path, base + 'requests/__init__.py', 'raise RuntimeError("nao execute")\ndef get(url): pass\n')
    LibraryCatalog(tmp_path).learn('requests', 'python')
    real_run = subprocess.run
    def run(argv, **kw):
        assert Path(argv[0]).name in ('git', 'git.exe'), 'Inventário executou runtime/gerenciador'
        return real_run(argv, **kw)
    monkeypatch.setattr(subprocess, 'run', run)
    rows = {row.name: row for row in inventory(tmp_path, 'python')}
    request = rows['requests']
    assert request.declared and request.installed and request.imported and request.documented
    assert request.version == '2.0' and not request.unresolved
    assert rows['naoinstalada'].unresolved


def test_pacote_instalado_sem_referencia_e_modulo_renomeado(tmp_path):
    write(tmp_path, 'requirements.txt', 'scikit-learn>=1.0\n')
    write(tmp_path, 'app.py', 'import sklearn\n')
    write(tmp_path, '.venv/lib/python3.12/site-packages/scikit_learn-1.dist-info/METADATA', 'Name: scikit-learn\nVersion: 1.5\n')
    write(tmp_path, '.venv/lib/python3.12/site-packages/scikit_learn-1.dist-info/top_level.txt', 'sklearn\n')
    rows = inventory(tmp_path, 'python')
    assert len(rows) == 1 and rows[0].installed and rows[0].imported and rows[0].declared
    assert rows[0].module == 'sklearn' and not rows[0].documented


def test_npm_scopes_e_dependencias_sem_tipos(tmp_path):
    write(tmp_path, 'package.json', json.dumps({'dependencies': {'react': '^19', '@acme/api': '^2', 'ausente': '^1'}}))
    write(tmp_path, 'app.ts', "import React from 'react';\nimport { f } from '@acme/api/client';\n")
    for name in ('react', '@acme/api'):
        write(tmp_path, f'node_modules/{name}/package.json', json.dumps({'name': name, 'version': '2.0'}))
    rows = {row.name: row for row in inventory(tmp_path, 'typescript')}
    assert rows['react'].installed and rows['react'].imported
    assert rows['@acme/api'].installed and rows['@acme/api'].imported
    assert rows['ausente'].unresolved
    assert len(inventory(tmp_path, 'typescript', 'instalada')) == 2


@pytest.mark.parametrize('lang,manifest,text,name', [
    ('dart', 'pubspec.yaml', 'name: app\ndependencies:\n  dio: ^5.0\n', 'dio'),
    ('rust', 'Cargo.toml', '[dependencies]\nserde={version="1", features=["derive"]}\n', 'serde'),
    ('go', 'go.mod', 'module app\nrequire (\n example.com/api v1.0.0\n)\n', 'example.com/api'),
    ('csharp', 'app.csproj', '<Project><ItemGroup><PackageReference Include="Dapper" Version="2.0" /></ItemGroup></Project>', 'Dapper'),
])
def test_manifestos_de_outros_ecossistemas(tmp_path, lang, manifest, text, name):
    write(tmp_path, manifest, text)
    rows = inventory(tmp_path, lang)
    assert rows[0].name == name and rows[0].declared


def test_import_local_e_codigo_ignorado_nao_viram_dependencia_externa(tmp_path):
    write(tmp_path, 'app.py', 'from util import somar\n')
    write(tmp_path, 'util.py', 'def somar(a, b): return a+b\n')
    write(tmp_path, '.venv/lib/site-packages/escondido.py', 'import pacote_inexistente\n')
    rows = inventory(tmp_path, 'python')
    assert len(rows) == 1 and rows[0].origin == 'projeto' and not rows[0].unresolved


def test_cli_json_inventario(tmp_path, capsys):
    write(tmp_path, 'requirements.txt', 'pytest==8.0\n')
    assert main(['libraries', 'inventory', '--root', str(tmp_path), '--json']) == 0
    rows = json.loads(capsys.readouterr().out)
    assert rows[0]['declared'] and rows[0]['unresolved']


def test_manifesto_linkado_fora_do_projeto_nao_e_lido(tmp_path):
    project = tmp_path / 'project'
    project.mkdir()
    external = write(tmp_path, 'external.json', '{"dependencies":{"segredo":"1"}}')
    try:
        (project / 'package.json').symlink_to(external)
    except OSError:
        pytest.skip('symlinks indisponíveis')
    assert inventory(project, 'javascript') == []
