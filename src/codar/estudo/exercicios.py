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
              'status': 'skipped', 'cases': [], 'message': ''}
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
            exercise = EXERCISES[identity]
            for stdin, expected in exercise.cases:
                code, output, error = _run(run, root, env, stdin, timeout=max(.1, min(timeout, 30)))
                try:
                    actual_numbers = [Decimal(item) for item in output.split()]
                    wanted_numbers = [Decimal(item) for item in expected.split()]
                    passed = code == 0 and error not in ('tempo limite excedido', 'limite de saída excedido') and actual_numbers == wanted_numbers
                except InvalidOperation:
                    passed = False
                result['cases'].append({'input': stdin.strip(), 'expected': expected, 'actual': output.strip(),
                                        'ok': passed, 'exit_code': code, 'error': error})
                if error in ('tempo limite excedido', 'limite de saída excedido'):
                    break
        except FileNotFoundError as exc:
            return {**result, 'message': str(exc)}
    if read_source(source) != original:
        return {**result, 'status': 'stale', 'message': 'O arquivo mudou durante o teste; o resultado refere-se ao snapshot anterior.'}
    passed = len(result['cases']) == len(EXERCISES[identity].cases) and all(case['ok'] for case in result['cases'])
    return {**result, 'status': 'ok' if passed else 'error',
            'message': 'Todos os casos passaram.' if passed else 'Há casos que precisam de correção.'}


def catalog():
    return [asdict(exercise) for exercise in EXERCISES.values()]
