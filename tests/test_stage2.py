"""Estágio 2 sem modelo de verdade: agendamento do pré-aquecimento."""

import threading
from collections import deque

from codar import config
from codar.engine.stage2 import Stage2


class FakeBackend:
    loaded = True
    child_pid = None

    def __init__(self, log):
        self.log = log

    def warm(self, prompt):
        lang = next(n for n in ("PowerShell", "JavaScript", "Python") if n in prompt)
        self.log.append("aquece " + lang)


def test_aquecimento_cede_a_vez_para_pedidos_do_usuario():
    cfg = config.load()
    cfg["model"]["backend"] = "none"
    s2 = Stage2(cfg)
    log = []
    s2.backend, s2.fmt = FakeBackend(log), "chatml"
    s2._warm_queue = deque(["powershell", "javascript"])

    gate = threading.Event()
    s2.submit(gate.wait)                          # a thread do modelo está ocupada...
    s2.submit(s2._warm_next)                      # ...o aquecimento entra na fila...
    pedido = s2.submit(lambda: log.append("pedido do usuário"))  # ...e um pedido real chega logo depois
    gate.set()
    pedido.result(timeout=5)
    s2.pool.shutdown(wait=True)

    assert log == ["pedido do usuário", "aquece PowerShell", "aquece JavaScript"]
