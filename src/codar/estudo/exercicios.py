"""Exercícios corrigidos por entradas/saídas, mediante execução explícita do aluno."""

from dataclasses import asdict, dataclass
from decimal import Decimal, InvalidOperation
import hashlib
import os
from pathlib import Path
import shutil
import signal
import subprocess
import tempfile
import time

from codar import langs, toolchains
from codar.advisor.pacotes import python_do_projeto
from codar.project import read_source, safe_path


@dataclass(frozen=True)
class Exercise:
    id: str
    title: str
    task: str
    cases: tuple[tuple[str, str], ...]
    hints: tuple[str, ...]
    languages: tuple[str, ...] = ()  # vazio: linguagens com executor de programas
    difficulty: str = 'iniciante'
    assessment: str = 'behavior'
    comparison: str = 'numbers'


EXERCISES = {
    'dobro': Exercise('dobro', 'Entrada, cálculo e saída',
        'Leia um inteiro da entrada padrão e escreva somente seu dobro na saída padrão, sem mensagens adicionais.',
        (('3\n', '6'), ('0\n', '0'), ('-7\n', '-14'), ('12345\n', '24690')),
        ('Leia a entrada e converta para inteiro.', 'Multiplique por 2, incluindo valores negativos.',
         'Mostre o resultado, sem pedir texto adicional ao usuário.')),
    'soma': Exercise('soma', 'Somar dois inteiros',
        'Leia dois inteiros separados por espaço na mesma linha. Escreva somente a soma.',
        (('2 5\n', '7'), ('0 0\n', '0'), ('-8 3\n', '-5'), ('12345 -12345\n', '0')),
        ('Separe a linha nos espaços.', 'Converta os dois valores antes de somar.', 'Confira zero e sinais diferentes.')),
    'ordenar': Exercise('ordenar', 'Ordenar uma sequência',
        'Leia inteiros separados por espaços. Escreva os valores em ordem crescente, separados por um espaço; preserve repetições.',
        (('3 1 2\n', '1 2 3'), ('-4 0 -1\n', '-4 -1 0'), ('2 2 1\n', '1 2 2'), ('8\n', '8')),
        ('Converta os valores antes de ordenar.', 'Ordenação numérica difere da ordenação de texto.',
         'Não remova elementos repetidos.')),
    'maximo': Exercise('maximo', 'Maior valor sem sentinela incorreta',
        'Leia pelo menos um inteiro por linha de entrada, separado por espaços. Escreva somente o maior valor.',
        (('-8 -3 -12\n', '-3'), ('0\n', '0'), ('4 9 9 2\n', '9'), ('-1 0 1\n', '1')),
        ('Não inicialize o maior com zero: a sequência pode ter só negativos.', 'Use o primeiro valor como referência.')),
    'contar_pares': Exercise('contar_pares', 'Contar pares incluindo zero e negativos',
        'Leia inteiros separados por espaços. Escreva quantos deles são pares. Uma linha vazia representa zero elementos.',
        (('1 2 3 4\n', '2'), ('-4 -3 0 8\n', '3'), ('\n', '0'), ('1 3 5\n', '0')),
        ('O resto da divisão por 2 identifica pares.', 'Zero também é par.', 'Trate a entrada vazia.'),
        difficulty='intermediario'),
    'fibonacci': Exercise('fibonacci', 'Sequência e casos de base',
        'Leia um inteiro n entre 0 e 30. Escreva F(n), com F(0)=0, F(1)=1 e F(n)=F(n-1)+F(n-2).',
        (('0\n', '0'), ('1\n', '1'), ('10\n', '55'), ('30\n', '832040')),
        ('Defina os dois casos iniciais.', 'Uma solução iterativa usa duas variáveis.',
         'Evite recursão exponencial que repete os mesmos cálculos.'), difficulty='intermediario'),
    'palavras': Exercise('palavras', 'Contagem ordenada de palavras',
        'Leia palavras minúsculas ASCII separadas por espaços. Escreva uma linha por palavra em ordem alfabética, '
        'no formato palavra quantidade. Uma linha vazia deve gerar saída vazia.',
        (('ana bia ana\n', 'ana 2\nbia 1'), ('z a z a z\n', 'a 2\nz 3'), ('\n', ''), ('codar\n', 'codar 1')),
        ('Use um mapa de frequências.', 'Ordene as chaves antes de imprimir.', 'Não imprima rótulos adicionais.'),
        difficulty='avancado', comparison='tokens'),
    'html_documento': Exercise('html_documento', 'Documento com navegação semântica',
        'Crie um documento HTML com doctype html, html lang="pt-BR", head com charset UTF-8 e title não vazio, '
        'body com um main, um h1 não vazio e nav com link para uma seção existente por id. '
        'A correção confere esses critérios estruturais; revise a experiência manualmente no navegador.',
        (), ('Use elementos semânticos.', 'O fragmento de href deve apontar para um id único.'),
        languages=('html',), assessment='structure'),
    'html_formulario': Exercise('html_formulario', 'Formulário de email com rótulo e envio',
        'Crie um form contendo input type="email" obrigatório, com name e id únicos, um label for apontando para esse id '
        'e texto de rótulo não vazio. Inclua button type="submit" com texto. Não use disabled nesses controles. '
        'A correção é estrutural; teclado, apresentação e anúncio por leitor de tela exigem revisão no navegador.',
        (), ('Placeholder não substitui label.', 'for e id devem coincidir.', 'O controle e o botão devem estar no mesmo form.'),
        languages=('html',), assessment='structure'),
    'css_grade': Exercise('css_grade', 'Grade adaptável com espaçamento',
        'Defina uma regra simples de topo .galeria, sem @ ou !important, que declare display:grid, gap com um único valor '
        'positivo em px, rem, em ou % e grid-template-columns usando '
        'repeat(auto-fit, minmax(..., 1fr)). Use min(100%, ...) no tamanho mínimo para evitar estouro em contêiner estreito. '
        'A correção confere declarações; abra um HTML com cartões para revisar o layout real.',
        (), ('Use unidades como rem para o mínimo.', 'Comentários e strings não contam como declarações.',
             'Exemplo de mínimo: min(100%, 14rem).'),
        languages=('css',), difficulty='intermediario', assessment='structure'),
    'sql_totais': Exercise('sql_totais', 'Agregações em SQLite sem servidor',
        'Escreva uma única consulta SELECT (ou WITH ... SELECT) para a tabela vendas(categoria TEXT, valor INTEGER). '
        'Retorne duas colunas: categoria e SUM(valor), uma linha por categoria, em ordem crescente de categoria. '
        'Os testes preparam diferentes conjuntos em SQLite em memória; não crie nem altere tabelas.',
        (), ('Agrupe por categoria.', 'Ordene explicitamente.', 'Use somente recursos aceitos pelo SQLite local.'),
        languages=('sql',), difficulty='intermediario', assessment='query'),
}


def _stop(process):
    if os.name != 'nt':
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
    else:
        try:
            subprocess.run(['taskkill', '/PID', str(process.pid), '/T', '/F'], capture_output=True, timeout=5)
        except (OSError, subprocess.TimeoutExpired):
            pass
        process.kill()
    process.wait()


def _run(argv, root, env, stdin='', timeout=3):
    # Arquivos temporários limitam o uso de RAM. A saída é monitorada e o grupo
    # de processos é encerrado quando excede tempo ou volume.
    with tempfile.TemporaryFile() as output, tempfile.TemporaryFile() as errors, tempfile.TemporaryFile() as input_file:
        input_file.write(stdin.encode())
        input_file.seek(0)
        process = subprocess.Popen(argv, cwd=root, env=env, stdin=input_file, stdout=output, stderr=errors,
                                   start_new_session=os.name != 'nt')
        start = time.monotonic()
        failure = ''
        while process.poll() is None:
            if time.monotonic() - start > timeout:
                failure = 'tempo limite excedido'
                break
            if os.fstat(output.fileno()).st_size + os.fstat(errors.fileno()).st_size > 256_000:
                failure = 'limite de saída excedido'
                break
            time.sleep(.02)
        if failure:
            _stop(process)
        output.seek(0)
        errors.seek(0)
        stdout = output.read(16_000).decode('utf-8', errors='replace')
        stderr = errors.read(4000).decode('utf-8', errors='replace')
        if os.fstat(output.fileno()).st_size + os.fstat(errors.fileno()).st_size > 256_000:
            failure = failure or 'limite de saída excedido'
        return process.returncode, stdout, failure or stderr


def execution_plan(file, lang, folder, root, env):
    target = str(folder / ('program.exe' if os.name == 'nt' else 'program'))
    compile_cmd = None
    if lang == 'python':
        run = [python_do_projeto(root), '-u', str(file)]
    elif lang in ('javascript', 'typescript'):
        runtime = 'bun' if lang == 'typescript' and shutil.which('bun', path=env.get('PATH')) else 'node'
        run = [runtime, str(file)]
    elif lang in ('c', 'cpp', 'rust'):
        compiler = {'c': 'gcc', 'cpp': 'g++', 'rust': 'rustc'}[lang]
        compile_cmd = [compiler, str(file), '-o', target]
        run = [target]
    elif lang == 'go':
        compile_cmd = ['go', 'build', '-o', target, str(file)]
        run = [target]
    elif lang == 'kotlin':
        jar = str(folder / 'program.jar')
        compile_cmd = ['kotlinc', str(file), '-include-runtime', '-d', jar]
        run = ['java', '-jar', jar]
    else:
        meta = langs.LANGS[lang]
        if not meta.runner:
            raise ValueError('Sem executor para exercícios nesta linguagem. Escolha uma linguagem de programação com runtime disponível.')
        run = [part.replace('{file}', str(file)) for part in meta.runner]
    for command in (compile_cmd, run):
        if not command or (command is run and compile_cmd and command[0] == target):
            continue
        executable = command[0]
        if not Path(executable).is_file() and not shutil.which(executable, path=env.get('PATH')):
            raise FileNotFoundError('Runtime/compilador ausente: ' + executable)
    return compile_cmd, run


def check(root: Path, relative: str, identity: str, *, timeout=3) -> dict:
    if identity not in EXERCISES:
        raise ValueError('Exercício desconhecido. Use codar study exercises.')
    root = Path(root).resolve()
    source = safe_path(root, relative)
    meta = langs.from_path(source)
    if not meta:
        raise ValueError('Não foi possível detectar a linguagem do arquivo.')
    original = read_source(source)
    fingerprint = hashlib.sha256(original.encode()).hexdigest()
    result = {'exercise': identity, 'language': meta.id, 'file': relative, 'fingerprint': fingerprint,
              'status': 'skipped', 'cases': [], 'message': '', 'assessment': EXERCISES[identity].assessment}
    exercise = EXERCISES[identity]
    if exercise.languages and meta.id not in exercise.languages:
        raise ValueError('Este exercício aceita: ' + ', '.join(exercise.languages))
    if exercise.assessment in ('structure', 'query'):
        from codar.estudo.validadores import evaluate

        result['cases'] = evaluate(identity, original, timeout=timeout)
        return _finish(root, source, original, result)
    env = toolchains.environment(project=root)
    env.update({'PYTHONUNBUFFERED': '1', 'PYTHONPATH': str(root), 'GOTOOLCHAIN': 'local', 'GOPROXY': 'off', 'GOSUMDB': 'off'})
    with tempfile.TemporaryDirectory(prefix='codar-exercise-') as directory:
        folder = Path(directory)
        snapshot = folder / source.name
        snapshot.write_text(original, encoding='utf-8')
        try:
            compile_cmd, run = execution_plan(snapshot, meta.id, folder, root, env)
            if compile_cmd:
                code, output, error = _run(compile_cmd, root, env, timeout=30)
                if code != 0:
                    return {**result, 'status': 'error', 'message': 'Compilação falhou: ' + (error or output)}
            for stdin, expected in exercise.cases:
                code, output, error = _run(run, root, env, stdin, timeout=max(.1, min(timeout, 30)))
                try:
                    if exercise.comparison == 'numbers':
                        actual = [Decimal(item) for item in output.split()]
                        wanted = [Decimal(item) for item in expected.split()]
                    else:
                        actual, wanted = output.split(), expected.split()
                    passed = code == 0 and error not in ('tempo limite excedido', 'limite de saída excedido') and actual == wanted
                except InvalidOperation:
                    passed = False
                result['cases'].append({'input': stdin.strip(), 'expected': expected, 'actual': output.strip(),
                                        'ok': passed, 'exit_code': code, 'error': error})
                if error in ('tempo limite excedido', 'limite de saída excedido'):
                    break
        except FileNotFoundError as exc:
            return {**result, 'message': str(exc)}
    return _finish(root, source, original, result)


def _finish(root, source, original, result):
    if read_source(source) != original:
        return {**result, 'status': 'stale', 'message': 'O arquivo mudou durante o teste; o resultado refere-se ao snapshot anterior.'}
    passed = bool(result['cases']) and all(case['ok'] for case in result['cases'])
    if result['assessment'] == 'behavior':
        passed = passed and len(result['cases']) == len(EXERCISES[result['exercise']].cases)
    if passed:
        from codar.estudo.progresso import marcar

        try:
            marcar(root, result['language'], 'exercise.' + result['exercise'])
            result['progress_saved'] = True
        except (OSError, ValueError) as exc:
            result['progress_saved'] = False
            result['progress_error'] = str(exc)
    return {**result, 'status': 'ok' if passed else 'error',
            'message': 'Todos os casos passaram.' if passed else 'Há casos que precisam de correção.'}


def _programa(lang):
    meta = langs.LANGS.get(lang)
    return meta is None or meta.programa


def catalog(lang=None):
    return [asdict(exercise) for exercise in EXERCISES.values()
            if lang is None or lang in exercise.languages or (not exercise.languages and _programa(lang))]
