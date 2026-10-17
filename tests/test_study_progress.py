import json
from concurrent.futures import ThreadPoolExecutor

import pytest

from codar.cli.main import main
from codar.estudo import progresso


@pytest.fixture(autouse=True)
def home(tmp_path, monkeypatch):
    monkeypatch.setenv('CODAR_HOME', str(tmp_path / 'home'))


def test_export_import_mescla_sem_importar_caminhos(tmp_path):
    a, b = tmp_path / 'a', tmp_path / 'b'
    progresso.marcar(a, 'rust', 'guia_rust')
    progresso.marcar(b, 'python', 'funcao')
    payload = progresso.exportar(a)
    assert str(a) not in json.dumps(payload)
    assert progresso.importar(b, payload) == 1
    assert 'guia_rust' in progresso.ler(b, 'rust')
    assert 'funcao' in progresso.ler(b, 'python')
    older = {'schema': 1, 'progress': {'rust': {'guia_rust': '2000-01-01T00:00:00+00:00'}}}
    progresso.importar(b, older)
    assert progresso.ler(b, 'rust') == progresso.ler(a, 'rust')


def test_gravacoes_concorrentes_preservam_todos_registros(tmp_path):
    with ThreadPoolExecutor(max_workers=8) as pool:
        list(pool.map(lambda i: progresso.marcar(tmp_path, 'python', f'licao_{i}'), range(32)))
    assert len(progresso.ler(tmp_path, 'python')) == 32


@pytest.mark.parametrize('payload', [[], {}, {'schema': True, 'progress': {}},
    {'schema': 1, 'progress': {'bash': {'../arquivo': '2000-01-01T00:00:00Z'}}},
    {'schema': 1, 'progress': {'nao_existe': {}}},
    {'schema': 1, 'progress': {'python': {'funcao': 'amanhã'}}},
    {'schema': 1, 'progress': {'python': {'funcao': '2000-01-01'}}}])
def test_importacao_invalida_nao_modifica_progresso(tmp_path, payload):
    progresso.marcar(tmp_path, 'python', 'funcao')
    before = progresso._file().read_bytes()
    with pytest.raises(ValueError):
        progresso.importar(tmp_path, payload)
    assert progresso._file().read_bytes() == before


def test_arquivo_corrompido_nao_e_substituido(tmp_path):
    file = progresso._file()
    file.parent.mkdir(parents=True)
    file.write_text('{quebrou')
    with pytest.raises(ValueError):
        progresso.marcar(tmp_path, 'python', 'funcao')
    assert file.read_text() == '{quebrou'


def test_cli_registra_exporta_importa_e_consulta(tmp_path, capsys):
    assert main(['study', 'mark', 'funcao', '--root', str(tmp_path)]) == 0
    file = tmp_path / 'progresso.json'
    assert main(['study', 'export', '--root', str(tmp_path), '--file', str(file)]) == 0
    assert main(['study', 'import', '--root', str(tmp_path / 'outro'), '--file', str(file)]) == 0
    capsys.readouterr()
    assert main(['study', 'progress', '--root', str(tmp_path / 'outro'), '--json']) == 0
    assert 'funcao' in json.loads(capsys.readouterr().out)
