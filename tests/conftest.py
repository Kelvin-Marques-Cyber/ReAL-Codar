import asyncio
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from codar import config  # noqa: E402
from codar.engine.router import Request, Router  # noqa: E402
from codar.engine.stage1 import PatternStore  # noqa: E402
from codar.engine.stage2 import GenResult  # noqa: E402
from codar.plugin_loader import discover  # noqa: E402


@pytest.fixture(autouse=True)
def _sem_shell_do_usuario(monkeypatch):
    """O Studio lê o ambiente do seu shell (bash -i) ao abrir; nos testes, não roda o .bashrc de quem testa."""
    monkeypatch.setenv("CODAR_SHELL_ENV", "0")


class FakeStage2:
    """Stage2 falso: registra os prompts e devolve respostas programadas (sem carregar modelo)."""

    fmt = "chatml"
    name = "fake"

    def __init__(self) -> None:
        self.prompts: list[str] = []
        self.answer = "resultado = 42\n"
        self.load_error = None

    def configured(self) -> bool:
        return True

    def submit(self, fn, *args, **kwargs):
        from concurrent.futures import Future

        fut: Future = Future()
        try:
            fut.set_result(fn(*args, **kwargs))
        except Exception as exc:  # pragma: no cover
            fut.set_exception(exc)
        return fut

    def generate(self, builder, on_token=None, cancel=None, max_tokens=None, stop=None):
        prompt = builder(0)
        self.prompts.append(prompt)
        return GenResult(self.answer, 5, len(prompt) // 3, 1.0, "stop")

    def plan(self, prompt, schema, cancel=None):
        self.prompts.append(prompt)
        return {"steps": []}, GenResult("{}", 1, 1, 1.0, "stop")


@pytest.fixture(scope="session")
def bundle():
    return discover(config.load())


@pytest.fixture()
def router(bundle, tmp_path):
    cfg = config.load()
    store = PatternStore(":memory:")
    store.sync(bundle.patterns, bundle.fingerprint)
    r = Router(cfg, store, bundle, FakeStage2())
    yield r
    store.close()


@pytest.fixture()
def translate(router):
    def _t(intent, lang="python", **kw):
        return asyncio.run(router.translate(Request(intent=intent, lang=lang, lang_explicit=True, **kw)))
    return _t
