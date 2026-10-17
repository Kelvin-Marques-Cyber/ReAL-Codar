import json
import shutil

import pytest

from codar.cli.main import main
from codar.estudo.exercicios import check


def test_comportamento_correto_e_incorreto_sem_comparar_codigo(tmp_path):
    file = tmp_path / 'solucao.py'
    correct = 'n = int(input())\nprint(n+n)\n'
    file.write_text(correct)
    result = check(tmp_path, 'solucao.py', 'dobro')
    assert result['status'] == 'ok' and len(result['cases']) == 4
    assert file.read_text() == correct
    file.write_text('n = int(input())\nprint(n+2)\n')
    broken = check(tmp_path, 'solucao.py', 'dobro')
    assert broken['status'] == 'error' and not all(c['ok'] for c in broken['cases'])
    assert broken['fingerprint'] != result['fingerprint']


def test_laco_infinito_e_saida_excessiva_sao_interrompidos(tmp_path):
    file = tmp_path / 'solucao.py'
    file.write_text('while True: pass\n')
    result = check(tmp_path, file.name, 'dobro', timeout=.15)
    assert result['status'] == 'error' and 'tempo limite' in result['cases'][0]['error']
    file.write_text('while True: print("a"*10000)\n')
    result = check(tmp_path, file.name, 'dobro')
    assert result['status'] == 'error' and 'limite de saída' in result['cases'][0]['error']


@pytest.mark.parametrize('extension,code', [
    ('.js', "const fs=require('fs');console.log(Number(fs.readFileSync(0,'utf8'))*2);"),
    ('.sh', 'read n\nprintf "%s\\n" "$((n*2))"\n'),
    ('.c', '#include <stdio.h>\nint main(){int n; scanf("%d", &n); printf("%d\\n",n*2); return 0;}'),
])
def test_exercicios_em_outros_runtimes(tmp_path, extension, code):
    runtime = {'.js':'node','.sh':'bash','.c':'gcc'}[extension]
    if not shutil.which(runtime):
        pytest.skip('runtime opcional ausente: ' + runtime)
    file = tmp_path / ('solucao' + extension)
    file.write_text(code)
    assert check(tmp_path, file.name, 'dobro')['status'] == 'ok'


def test_runtime_ausente_nao_passa_como_validado(tmp_path, monkeypatch):
    (tmp_path / 'solucao.rb').write_text('puts gets.to_i*2\n')
    monkeypatch.setattr('codar.estudo.exercicios.shutil.which', lambda *a, **k: None)
    assert check(tmp_path, 'solucao.rb', 'dobro')['status'] == 'skipped'


def test_cli_executa_solucao_explicita_e_emite_json(tmp_path, capsys):
    file = tmp_path / 'solucao.py'
    file.write_text('print(sum(map(int, input().split())))\n')
    assert main(['study', 'check', 'soma', '--root', str(tmp_path), '--file', str(file), '--json']) == 0
    result = json.loads(capsys.readouterr().out)
    assert result['status'] == 'ok' and len(result['cases']) == 4


def test_recusa_arquivo_fora_do_projeto(tmp_path):
    with pytest.raises(ValueError):
        check(tmp_path, '../externo.py', 'dobro')
