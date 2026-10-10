"""Mede RSS do motor e do Studio sem IA em processos novos (Linux, sem downloads).

Execute na raiz do checkout com Python/Textual instalados:
    python docs/benchmarks/measure_memory.py --out docs/benchmarks/memory-0.3.1.json
"""
from __future__ import annotations

import argparse
import asyncio
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import platform
import statistics
import subprocess
import sys
import tempfile


def memory():
    fields = {}
    for line in Path('/proc/self/status').read_text().splitlines():
        if line.startswith(('VmRSS:', 'VmHWM:')):
            fields[line.split(':')[0]] = round(int(line.split()[1]) / 1024, 2)
    return dict(rss_mib=fields['VmRSS'], peak_mib=fields['VmHWM'])


def requests(client):
    for n in range(20):
        result = client.translate(f'x é igual a {n}', 'python', stages=(0, 1))
        assert result['body'].strip() == f'x = {n}'
    result = client.translate('criar uma calculadora', 'python', stages=(0, 1))
    assert result['body'].strip()


async def studio(root):
    from codar.engine.local import LocalClient
    from codar.studio.app import Studio

    app = Studio(root, local=True)
    app.backend._local = LocalClient(with_model=False)
    async with app.run_test(size=(150, 42)) as pilot:
        for n in range(3):
            file = root / f'arquivo{n}.py'
            file.write_text(''.join(f'valor_{i} = {i}\n' for i in range(200)))
            await app.open_file(file)
        await pilot.pause(.4)
        initial = memory()
        await asyncio.to_thread(requests, app.backend._local)
        await app.submit_intent('x é igual a 10')
        for _ in range(100):
            await pilot.pause(.05)
            if 'x = 10' in app.current_editor().text:
                break
        assert 'x = 10' in app.current_editor().text
        return dict(initial=initial, after_workload=memory(), model_loaded=False,
                    workload='Studio headless 150x42, 3 abas de 200 linhas, 20 traduções por regras, '
                             '1 calculadora por padrão e 1 intenção aplicada no editor; motor no mesmo processo')


def worker(kind, root):
    if kind == 'studio':
        return asyncio.run(studio(root))
    from codar.engine.local import LocalClient

    with LocalClient(with_model=False) as client:
        initial = memory()
        requests(client)
        return dict(initial=initial, after_workload=memory(), model_loaded=False,
                    workload='20 traduções por regras e 1 calculadora por padrão; motor local sem daemon separado')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--runs', type=int, default=3)
    parser.add_argument('--out', type=Path)
    parser.add_argument('--worker', choices=['engine', 'studio'], help=argparse.SUPPRESS)
    args = parser.parse_args()
    if not sys.platform.startswith('linux'):
        parser.error('Esta medição usa /proc do Linux; não extrapole para outros sistemas.')
    if args.worker:
        print(json.dumps(worker(args.worker, Path.cwd())))
        return
    if not 1 <= args.runs <= 20:
        parser.error('--runs deve estar entre 1 e 20')
    results = {}
    for kind in ('engine', 'studio'):
        runs = []
        for _ in range(args.runs):
            with tempfile.TemporaryDirectory(prefix='codar-memory-') as directory:
                root = Path(directory)
                env = {**os.environ, 'CODAR_HOME': str(root / 'home'), 'CODAR_NO_AUTOSTART': '1',
                       'CODAR_SHELL_ENV': '0', 'PYTHONPATH': str(Path(__file__).resolve().parents[2] / 'src')}
                run = subprocess.run([sys.executable, str(Path(__file__).resolve()), '--worker', kind],
                                     env=env, cwd=root, text=True, capture_output=True, timeout=90, check=True)
                runs.append(json.loads(run.stdout))
        results[kind] = dict(runs=runs, median_rss_mib=statistics.median(r['after_workload']['rss_mib'] for r in runs),
                             min_rss_mib=min(r['after_workload']['rss_mib'] for r in runs),
                             max_rss_mib=max(r['after_workload']['rss_mib'] for r in runs),
                             max_peak_mib=max(r['after_workload']['peak_mib'] for r in runs))
    from codar import __version__
    import textual
    report = dict(version=__version__, measured_at_utc=datetime.now(timezone.utc).isoformat(),
                  environment=dict(os=platform.system(), architecture=platform.machine(),
                                   python=platform.python_version(), textual=textual.__version__),
                  metric='RSS e VmHWM de /proc/self/status em MiB (1 MiB = 1048576 bytes)',
                  exclusions='Sem modelo, daemon separado, emulador de terminal, servidor de linguagem, '
                             'builds ou programas filhos ativos. Studio usa o driver headless de teste do Textual.',
                  comparison='Não foi feito benchmark comparativo com outras IDEs.', results=results)
    content = json.dumps(report, ensure_ascii=False, indent=2) + '\n'
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(content, encoding='utf-8')
    print(content)


if __name__ == '__main__':
    main()
