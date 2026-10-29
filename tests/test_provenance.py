"""Procedência visível: estágio, modelo, sintaxe e teste; código da IA nunca aparece como testado."""

import argparse
import re

from codar.engine.provenance import verification


def test_compilador_e_deterministico_mas_nao_executado(translate):
    res = translate("x é igual a 10")
    check = res.verification
    assert res.stage == "0" and check["origin"] == "compiler" and check["model"] is None
    assert check["syntax"] == "ok" and check["validator"] == "python_ast" and check["tested"] is False
    assert "sem execução" in check["summary"]


def test_variante_do_banco_so_conta_como_testada_com_teste_executavel(translate):
    python = translate("validar cpf", stages=(0, 1))
    assert python.stage == "1" and python.verification["tested"] is True
    assert python.verification["sources"] == ["pattern:br.cpf"]
    assert "testada no patternlint" in python.verification["summary"]
    go = translate("validar cpf", "go", stages=(0, 1))  # br.cpf não tem teste em Go
    assert go.stage == "1" and go.verification["tested"] is False


def test_padrao_salvo_pelo_usuario_nao_herda_o_teste(router, translate):
    from codar.plugin_loader import Pattern

    original = router.store.get("br.cpf")
    router.store.add(Pattern(id="br.cpf", title=original.title, keywords=original.keywords,
                             require=original.require, code={"python": "def validar_cpf(cpf):\n    return True\n"}))
    router.clear_cache()
    res = translate("validar cpf", stages=(0, 1))
    assert res.source == "pattern:br.cpf" and res.verification["tested"] is False


def test_ia_nunca_e_testada_e_informa_o_modelo(router, translate):
    router.stage2.answer = "def media(xs):\n    return sum(xs) / len(xs)\n"
    res = translate("crie uma função que calcula a média de uma lista")
    check = res.verification
    assert res.stage.startswith("2") and check["origin"] == "ai" and check["model"] == "fake"
    assert check["tested"] is False and check["syntax"] == "ok"
    assert "não testado" in check["summary"]


def test_sintaxe_invalida_e_dependencias_aparecem_na_verificacao():
    context = "numpy [python; versão 2.1.0; site-packages; revisão abcdef123456]\nnumpy.mean(a)"
    check = verification("2:gen", "slm:qwen", "def f(:\n", "python", library_context=context)
    assert check["syntax"] == "error" and check["reason"] and check["tested"] is False
    assert check["sources"] == ["numpy 2.1.0 (site-packages)"] and check["model"] == "qwen"


def test_consulta_informativa_declara_que_nada_foi_gerado(translate):
    res = translate("o que é uma lista")
    assert res.action == "query" and res.verification["origin"] == "information"


def test_cli_mostra_verificacao_somente_quando_pedida(capsys):
    from codar.cli.hud import Hud
    from codar.cli.main import print_result

    res = dict(code="x = 1", stage="2:gen", source="slm:qwen", timings={"total_ms": 1}, findings=[], notes=[],
               verification=verification("2:gen", "slm:qwen", "x = 1", "python"))
    hud = Hud()
    hud.mode = "truecolor"  # o HUD de um terminal interativo

    def err():
        return re.sub(r"\x1b\[[0-9;]*m", "", capsys.readouterr().err)
    print_result(res, argparse.Namespace(verbose=False), hud)
    quiet = err()
    assert "NÃO TESTADO" in quiet and "não testado" not in quiet
    print_result(res, argparse.Namespace(verbose=True), hud)
    assert "IA local (qwen); sintaxe verificada (python_ast); não testado" in err()
