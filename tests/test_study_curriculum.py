"""Percursos, retomada e correções adversariais pelo mesmo CLI usado pelo aluno."""

import json
import shutil
import subprocess
import sys
import sqlite3

import pytest

from codar import estudo, langs
from codar.cli.main import main
from codar.estudo.curriculo import AULAS, buscar, percurso
from codar.estudo.exercicios import EXERCISES, catalog, check
from codar.estudo import progresso


@pytest.fixture(autouse=True)
def home(tmp_path, monkeypatch):
    monkeypatch.setenv('CODAR_HOME', str(tmp_path / 'home'))


@pytest.mark.parametrize('lang', sorted(langs.LANGS))
def test_percurso_tem_conteudo_nativo_niveis_e_projeto_reais(lang, tmp_path):
    path = percurso(lang, tmp_path)
    ids = [lesson['id'] for lesson in path['lessons']]
    assert len(ids) == len(set(ids)) == len(estudo.catalogo(lang))
    assert path['project'] in ids and ids[-1] == path['project']
    assert path['next'] == 'guia_' + lang and path['environment']
    levels = [lesson['level'] for lesson in path['lessons']]
    assert set(levels) == {'iniciante', 'intermediario', 'avancado'}
    assert levels == sorted(levels, key=['iniciante', 'intermediario', 'avancado'].index)
    for index, lesson in enumerate(path['lessons']):
        assert lesson['previous'] == (ids[index - 1] if index else None)
        assert lesson['next'] == (ids[index + 1] if index + 1 < len(ids) else None)
        assert set(lesson['related']).issubset(ids)
    for aula in AULAS[lang]:
        concept = estudo.POR_ID[f'{lang}_{aula.chave}']
        assert estudo.exemplo(concept, lang) == (aula.codigo, lang)
        assert all((aula.texto, aula.pratique, aula.erro, aula.confira, aula.codigo))
        assert len(aula.texto) > 90 and len(aula.pratique) > 50
        assert 'TODO' not in aula.codigo


def test_busca_sem_acentos_retorna_assunto_e_nao_outra_linguagem():
    assert 'html_semantica' in [c.id for c in buscar('html', 'formularios')]
    assert 'css_movimento' in [c.id for c in buscar('css', 'movimento reduzido')]
    assert not buscar('python', 'flexbox')
    with pytest.raises(ValueError):
        buscar('html', ' ')


def test_cli_navega_busca_retorna_e_retomada_preserva_escopo(tmp_path, capsys):
    root = tmp_path / 'a'
    common = ['--lang', 'html', '--root', str(root), '--json']
    assert main(['study', 'resume', *common]) == 0
    first = json.loads(capsys.readouterr().out)
    assert first['id'] == 'guia_html' and first['next'] and first['module']
    assert main(['study', 'mark', first['id'], '--lang', 'html', '--root', str(root)]) == 0
    capsys.readouterr()
    assert main(['study', 'resume', *common]) == 0
    assert json.loads(capsys.readouterr().out)['id'] == first['next']
    assert main(['study', 'search', 'metadados', *common]) == 0
    assert 'html_metadados' in [x['id'] for x in json.loads(capsys.readouterr().out)]
    assert percurso('html', tmp_path / 'b')['practiced'] == 0
    assert percurso('python', root)['practiced'] == 0


@pytest.mark.parametrize('aula', AULAS['python'], ids=lambda a: a.chave)
def test_novos_exemplos_python_executam_de_verdade_sem_rede(aula, tmp_path):
    result = subprocess.run([sys.executable, '-c', aula.codigo], cwd=tmp_path, capture_output=True, text=True, timeout=5)
    assert result.returncode == 0, result.stderr


@pytest.mark.parametrize('identity', ['promessas', 'api', 'modulos', 'testes', 'projeto'])
def test_exemplos_javascript_terminal_executam(identity, tmp_path):
    if not shutil.which('node'):
        pytest.skip('Node opcional indisponível')
    aula = next(a for a in AULAS['javascript'] if a.chave == identity)
    file = tmp_path / ('exemplo.mjs' if identity == 'modulos' else 'exemplo.cjs')
    file.write_text(aula.codigo, encoding='utf-8')
    result = subprocess.run(['node', str(file)], cwd=tmp_path, capture_output=True, text=True, timeout=10)
    assert result.returncode == 0, result.stderr


@pytest.mark.parametrize('aula', AULAS['c'], ids=lambda a: a.chave)
def test_exemplos_c_compilam_e_executam(aula, tmp_path):
    if not shutil.which('gcc'):
        pytest.skip('GCC opcional indisponível')
    file = tmp_path / 'exemplo.c'
    target = tmp_path / 'exemplo'
    file.write_text(aula.codigo, encoding='utf-8')
    compiled = subprocess.run(['gcc', '-std=c11', '-Wall', '-Wextra', str(file), '-o', str(target)],
                              capture_output=True, text=True, timeout=15)
    assert compiled.returncode == 0, compiled.stderr
    result = subprocess.run([str(target)], capture_output=True, text=True, timeout=3)
    assert result.returncode == 0, result.stderr


@pytest.mark.parametrize('aula', AULAS['java'], ids=lambda a: a.chave)
def test_exemplos_java_executam_quando_jdk_local_disponivel(aula, tmp_path):
    if not shutil.which('java'):
        pytest.skip('JDK opcional indisponível')
    file = tmp_path / 'Exemplo.java'
    file.write_text(aula.codigo, encoding='utf-8')
    result = subprocess.run(['java', str(file)], cwd=tmp_path, capture_output=True, text=True, timeout=20)
    assert result.returncode == 0, result.stderr


@pytest.mark.parametrize('aula', AULAS['sql'], ids=lambda a: a.chave)
def test_exemplos_sql_rodam_no_dialeto_documentado_sqlite(aula):
    with sqlite3.connect(':memory:') as connection:
        connection.executescript(aula.codigo)
        if aula.chave == 'integridade':
            assert connection.execute('SELECT quantidade FROM estoque').fetchone() == (5,)


def test_catalogo_de_desafios_filtra_linguagem_e_nao_promete_yaml_executavel():
    assert {c['id'] for c in catalog('html')} == {'html_formulario', 'html_documento'}
    assert {c['id'] for c in catalog('css')} == {'css_grade'}
    assert {c['id'] for c in catalog('sql')} == {'sql_totais'}
    assert not catalog('yaml') and not catalog('dockerfile')
    assert {c['difficulty'] for c in catalog('python')} == {'iniciante', 'intermediario', 'avancado'}


FORM = '<form><label for="email">Seu email</label><input type="email" id="email" name="email" required>' \
       '<button type="submit">Enviar</button></form>'
GRID = '.galeria { display: grid; gap: 1rem; grid-template-columns: repeat(auto-fit, minmax(min(100%, 14rem), 1fr)); }'


def solve(tmp_path, identity, source):
    lang = EXERCISES[identity].languages[0]
    file = tmp_path / ('solucao' + langs.LANGS[lang].exts[0])
    file.write_text(source, encoding='utf-8')
    result = check(tmp_path, file.name, identity)
    assert file.read_text(encoding='utf-8') == source
    return result


def test_html_e_css_passam_so_criterios_declarados_e_persistem(tmp_path):
    for identity, code in [('html_formulario', FORM), ('css_grade', GRID)]:
        result = solve(tmp_path, identity, code)
        assert result['status'] == 'ok', result
        assert result['assessment'] == 'structure' and result['progress_saved']
    assert 'exercise.html_formulario' in progresso.ler(tmp_path, 'html')
    assert percurso('html', tmp_path)['practiced'] == 0
    assert percurso('html', tmp_path)['validated_exercises'][0]['id'] == 'html_formulario'


@pytest.mark.parametrize('broken', [
    FORM.replace('for="email"', 'for="outro"'),
    FORM.replace('required', ''),
    FORM.replace('<input ', '<input disabled '),
    FORM.replace('<input ', '<fieldset disabled><input ').replace('<button', '</fieldset><button'),
    FORM.replace('Seu email', '   '),
    FORM.replace('</form>', '<input id="email" name="outro"></form>'),
    FORM.replace('<button', '</form><form><button'),
    '<!--' + FORM + '-->',
    '<script>' + FORM + '</script>',
    FORM.replace('</label>', ''),
])
def test_html_rejeita_rotulos_falsos_controles_desabilitados_e_tags_em_comentarios(tmp_path, broken):
    result = solve(tmp_path, 'html_formulario', broken)
    assert result['status'] == 'error'
    assert not progresso.ler(tmp_path, 'html')


def test_documento_html_exige_metadados_landmark_e_destino_do_link(tmp_path):
    code = estudo.exemplo(estudo.POR_ID['html_estrutura'], 'html')[0]
    assert solve(tmp_path, 'html_documento', code)['status'] == 'ok'
    assert solve(tmp_path, 'html_documento', code.replace('id="aulas"', 'id="outro"'))['status'] == 'error'
    assert solve(tmp_path, 'html_documento', code.replace('<title>Estudos</title>', '<title></title>'))['status'] == 'error'


@pytest.mark.parametrize('broken', [
    '/* ' + GRID + ' */',
    '.outro { content: "' + GRID + '"; }',
    GRID.replace('gap: 1rem', 'gap: 0rem'),
    GRID.replace('display: grid', 'display: flex'),
    GRID + '\n.galeria { display: block; }',
    GRID.replace('auto-fit', '2'),
    GRID.replace('min(100%, 14rem)', '14rem'),
    GRID[:-1],
    GRID + ' /* comentário aberto',
])
def test_css_rejeita_falsos_positivos_e_regras_sobrescritas(tmp_path, broken):
    assert solve(tmp_path, 'css_grade', broken)['status'] == 'error'


def test_css_ignora_comentarios_e_strings_sem_confundir_delimitadores(tmp_path):
    code = GRID.replace('display: grid', 'display: /* escolha */ grid') + '\n.x { content: "/* } */"; }'
    assert solve(tmp_path, 'css_grade', code)['status'] == 'ok'


def test_sql_valida_varios_datasets_incluindo_vazio_e_duplica(tmp_path):
    query = 'SELECT categoria, SUM(valor) FROM vendas GROUP BY categoria ORDER BY categoria;'
    result = solve(tmp_path, 'sql_totais', query)
    assert result['status'] == 'ok' and len(result['cases']) == 4, result
    assert solve(tmp_path, 'sql_totais', query.replace('SUM(valor)', 'SUM(DISTINCT valor)'))['status'] == 'error'


@pytest.mark.parametrize('query', [
    'DROP TABLE vendas;',
    "ATTACH DATABASE '/tmp/estudo-invasivo.db' AS externo;",
    "SELECT load_extension('inexistente');",
    'SELECT randomblob(1000000000);',
    "SELECT 'A', 30 UNION ALL SELECT 'B', 5;",
    'SELECT categoria, SUM(valor) FROM vendas;',
    'SELECT 1; SELECT 2;',
    'WITH RECURSIVE x(n) AS (VALUES(1) UNION ALL SELECT n+1 FROM x) SELECT sum(n) FROM x;',
])
def test_sql_nega_mutacao_extensoes_alocacao_e_consultas_sem_fim(tmp_path, query):
    result = solve(tmp_path, 'sql_totais', query)
    assert result['status'] == 'error'
    assert not progresso.ler(tmp_path, 'sql')


def test_exercicio_cli_nao_exige_runtime_para_html_e_registra_aprovacao(tmp_path, capsys):
    file = tmp_path / 'cadastro.html'
    file.write_text(FORM)
    assert main(['study', 'check', 'html_formulario', '--root', str(tmp_path), '--file', str(file), '--json']) == 0
    result = json.loads(capsys.readouterr().out)
    assert result['status'] == 'ok' and result['assessment'] == 'structure'
    assert main(['study', 'path', '--root', str(tmp_path), '--lang', 'html', '--json']) == 0
    path = json.loads(capsys.readouterr().out)
    assert path['validated_exercises'][0]['id'] == 'html_formulario'
    assert not path['lessons'][0]['practiced']


@pytest.mark.parametrize('identity,code', [
    ('maximo', 'print(max(map(int, input().split())))'),
    ('contar_pares', 'print(sum(int(x)%2==0 for x in input().split()))'),
    ('fibonacci', 'n=int(input())\na,b=0,1\nfor _ in range(n): a,b=b,a+b\nprint(a)'),
    ('palavras', 'from collections import Counter\nc=Counter(input().split())\nfor p in sorted(c): print(p,c[p])'),
])
def test_novos_desafios_aceitam_comportamento_equivalente(tmp_path, identity, code):
    file = tmp_path / 'solucao.py'
    file.write_text(code)
    assert check(tmp_path, file.name, identity)['status'] == 'ok'
    file.write_text('print(0)')
    assert check(tmp_path, file.name, identity)['status'] == 'error'


def test_falha_ao_salvar_progresso_nao_fabrica_reprovacao_ou_sucesso_de_gravacao(tmp_path, monkeypatch):
    def fail(*args):
        raise OSError('armazenamento indisponível')

    monkeypatch.setattr(progresso, 'marcar', fail)
    result = solve(tmp_path, 'html_formulario', FORM)
    assert result['status'] == 'ok' and result['progress_saved'] is False
    assert 'indisponível' in result['progress_error']
