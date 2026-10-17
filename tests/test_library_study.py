import json

import pytest

from codar.cli.main import main
from codar.estudo.bibliotecas import track


def write(root, name, text):
    file = root / name
    file.parent.mkdir(parents=True, exist_ok=True)
    file.write_text(text, encoding='utf-8')
    return file


@pytest.fixture(autouse=True)
def home(tmp_path, monkeypatch):
    monkeypatch.setenv('CODAR_HOME', str(tmp_path / 'home'))


def test_trilha_usa_api_real_e_nao_executa_modulo(tmp_path):
    file = write(tmp_path, 'minhalib.py', 'raise RuntimeError("nao executar")\ndef somar(a: int, b: int) -> int:\n    """Soma dois inteiros."""\n    return a + b\n')
    value = track(tmp_path, 'minhalib', 'python')
    assert value.documented and len(value.lessons) == 6
    assert value.version == 'local'
    assert value.lessons[2].example == 'import minhalib'
    assert 'def somar(a: int, b: int)' in value.lessons[3].example
    assert str(file) in value.lessons[3].sources
    file.write_text('def multiplicar(a, b): return a*b\n')
    updated = track(tmp_path, 'minhalib', 'python')
    assert updated.fingerprint != value.fingerprint
    assert 'multiplicar' in updated.lessons[3].example and 'somar' not in updated.lessons[3].example


@pytest.mark.parametrize('lang,name,ext,text', [
    ('typescript', 'util', '.ts', 'export function somar(a: number, b: number): number { return a+b; }'),
    ('rust', 'minha_lib', '.rs', 'pub fn somar(a: i32, b: i32) -> i32 { a+b }'),
    ('dart', 'minha_lib', '.dart', 'int somar(int a, int b) => a+b;'),
])
def test_referencias_manuais_geram_trilha_nativa(tmp_path, lang, name, ext, text):
    file = write(tmp_path, 'api' + ext, text)
    value = track(tmp_path, name, lang, source=file)
    assert value.lang == lang and value.documented
    assert 'somar' in value.lessons[3].example


def test_biblioteca_sem_fontes_nao_inventa_api(tmp_path):
    value = track(tmp_path, 'biblioteca_inexistente', 'python')
    assert not value.documented and value.version == 'não resolvida'
    assert value.lessons[3].example == ''
    assert 'Nenhuma assinatura' in value.lessons[3].text


def test_cli_tutorial_json(tmp_path, capsys):
    write(tmp_path, 'util.py', 'def somar(a, b): return a+b\n')
    assert main(['libraries', 'tutorial', 'util', '--root', str(tmp_path), '--json']) == 0
    value = json.loads(capsys.readouterr().out)
    assert value['documented'] and len(value['lessons']) == 6
