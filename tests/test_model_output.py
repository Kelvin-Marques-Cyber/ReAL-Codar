"""Regressões do handshake ChatML: o fence não pode encerrar a geração antes do código."""

from codar.engine.models import STOP, build_import_prompt, build_literal_prompt, build_prompt
from codar.engine.postprocess import clean_generation


def test_markdown_fence_nao_interrompe_a_geracao():
    assert "```" not in STOP
    for prompt in (
        build_prompt("chatml", "Python", "python", "leia uma playlist"),
        build_import_prompt("chatml", "Python", "python", "importar youtube"),
        build_literal_prompt("chatml", "Python", "python", "x vale 5", [("x é igual a 5", "x = 5")]),
    ):
        assert prompt.endswith("<|im_start|>assistant\n")
        assert not prompt.endswith("```python\n")


def test_extrai_codigo_marcado_sem_inserir_prosa():
    text = "Aqui está o código:\n```python\nfrom yt_dlp import YoutubeDL\n\nplaylist_url = input()\n```"
    assert clean_generation(text, "python") == "from yt_dlp import YoutubeDL\n\nplaylist_url = input()"


def test_codigo_sem_markdown_continua_sendo_preservado():
    assert clean_generation("from yt_dlp import YoutubeDL\n", "python") == "from yt_dlp import YoutubeDL"


def test_sequencia_de_raciocinio_fechada_nao_vira_codigo():
    raw = "<think>considerar possibilidades</think>\n```python\nprint(42)\n```"
    assert clean_generation(raw, "python") == "print(42)"
