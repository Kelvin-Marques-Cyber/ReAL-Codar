import sys
import json
import subprocess

import pytest


@pytest.mark.skipif(not sys.platform.startswith('linux'), reason='mede a memória via procfs Linux')
def test_rss_reflete_alocacao_real_e_detecta_pressao():
    # Processo novo evita que arenas reservadas por outros testes escondam o crescimento.
    source = '''
import json
from codar.daemon.memguard import MemGuard, rss_bytes
before = rss_bytes()
guard = MemGuard({'budget_mb': before // 1048576 + 10})
data = bytearray(b'x' * (16 * 1048576))
measured = guard.sample([])
print(json.dumps([before, rss_bytes(), measured.level, len(data)]))
'''
    result = subprocess.run([sys.executable, '-c', source], capture_output=True, text=True, check=True)
    before, after, level, size = json.loads(result.stdout)
    assert after >= before + 8 * 1048576 and size == 16 * 1048576
    assert level == 'hard'


def test_pico_local_nao_reinicia_entre_consultas(tmp_path, monkeypatch):
    monkeypatch.setenv('CODAR_HOME', str(tmp_path))
    from codar.engine.local import LocalClient
    import codar.daemon.memguard as memory

    with LocalClient(with_model=False) as client:
        monkeypatch.setattr(memory, 'rss_bytes', lambda *args: 80 * 1048576)
        assert client.stats()['memory']['peak_mb'] == 80
        monkeypatch.setattr(memory, 'rss_bytes', lambda *args: 50 * 1048576)
        stats = client.stats()['memory']
        assert stats['total_mb'] == 50 and stats['peak_mb'] == 80
