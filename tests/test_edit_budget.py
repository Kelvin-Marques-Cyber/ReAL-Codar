"""O orçamento considera a saída inteira antes de chamar o modelo."""

import pytest

from codar import config
from codar.engine.stage2 import Backend, GenResult, ModelUnavailable, Stage2


class TokenBackend(Backend):
    loaded = True

    def __init__(self):
        self.calls = []

    def tokens(self, text):
        return len(text)

    def complete(self, prompt, **kwargs):
        self.calls.append((prompt, kwargs["max_tokens"]))
        return GenResult("ok", 2, len(prompt), 1, "stop")


@pytest.fixture
def stage():
    cfg = config.load()
    cfg["model"].update(backend="none", n_ctx=300, max_tokens=180)
    stage = Stage2(cfg)
    stage.backend = TokenBackend()
    yield stage
    stage.shutdown()


def test_corta_contexto_opcional_para_reservar_substituicao_completa(stage):
    levels = []
    def prompt(level):
        levels.append(level)
        return "p" * (260 if level == 0 else 100)
    stage.generate(prompt, required_output="s" * 90)
    assert levels == [0, 1]
    assert stage.backend.calls == [("p" * 100, 180)]


def test_selecao_grande_nao_inicia_geracao(stage):
    with pytest.raises(ModelUnavailable, match="max_tokens"):
        stage.generate(lambda _: "p", required_output="s" * 170)
    assert stage.backend.calls == []


def test_prompt_sem_espaco_nao_corta_codigo_original(stage):
    selected = "s" * 100
    with pytest.raises(ModelUnavailable, match="original foi preservado"):
        stage.generate(lambda _: "p" * 220, required_output=selected)
    assert stage.backend.calls == [] and selected == "s" * 100


def test_geracao_de_linha_curta_continua_funcionando(stage):
    stage.generate(lambda _: "p" * 220)
    assert stage.backend.calls[0][1] == 72
