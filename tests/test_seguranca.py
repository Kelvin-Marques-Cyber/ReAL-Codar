"""Conteúdo de terceiros (plugins, sugestões) não escreve fora do projeto nem vira código executado."""

import types

import pytest

from codar.advisor.apply import ApplyError, apply_steps
from codar.plugin_loader import _patterns_from

SEM_PADROES = types.SimpleNamespace(patterns=[])


@pytest.mark.parametrize("campo", ["write", "append", "json_set", "backup"])
@pytest.mark.parametrize("destino", ["../fora.txt", "/tmp/codar-fora-do-projeto.txt", "sub/../../fora.txt", "a\\..\\..\\fora.txt"])
def test_sugestao_nao_escreve_fora_do_projeto(tmp_path, campo, destino):
    projeto = tmp_path / "projeto"
    projeto.mkdir()
    passo = {campo: destino, "content": "x", "lines": ["x"], "key": "a", "value": 1}
    with pytest.raises(ApplyError, match="passo recusado"):
        apply_steps(projeto, [passo], SEM_PADROES, lambda _texto: None)
    assert not (tmp_path / "fora.txt").exists()


def test_sugestao_nao_segue_link_simbolico_para_fora(tmp_path):
    projeto, fora = tmp_path / "projeto", tmp_path / "fora"
    projeto.mkdir()
    fora.mkdir()
    (projeto / "config").symlink_to(fora, target_is_directory=True)
    with pytest.raises(ApplyError):
        apply_steps(projeto, [{"write": "config/settings.json", "content": "{}"}], SEM_PADROES, lambda _texto: None)
    assert not (fora / "settings.json").exists()


def test_sugestao_dentro_do_projeto_continua_funcionando(tmp_path):
    apply_steps(tmp_path, [{"write": ".vscode/settings.json", "content": "{}\n"}], SEM_PADROES, lambda _texto: None)
    assert (tmp_path / ".vscode" / "settings.json").read_text() == "{}\n"


def test_nome_de_slot_com_codigo_recusa_o_padrao():
    erros = []
    padroes = _patterns_from({"pattern": [{"id": "x.y", "title": "t", "code": {"python": "print(1)"},
                                           "slots": {"a=__import__('os').system('id')": "1", "valido": "2"}}]},
                             "plugin-teste", erros)
    assert padroes == [] and "slot(s) com nome inválido" in erros[0]


def test_planejador_needle_nao_executa_nome_de_parametro(tmp_path):
    from codar.engine.needle_adapter import NeedleRouter

    alvo = tmp_path / "executado"
    router = NeedleRouter.__new__(NeedleRouter)
    router.min_confidence = 0.6
    router._needle = types.SimpleNamespace(tool=lambda f: f, Needle=lambda tools: types.SimpleNamespace(
        run=lambda intent: {"confidence": 0}))
    malicioso = f"x=open({str(alvo)!r}, 'w')"
    assert router.plan("teste", [{"id": "p.1", "title": "Título", "params": [malicioso, "nome"]}]) == []
    assert not alvo.exists()
