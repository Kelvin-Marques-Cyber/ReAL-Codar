"""O patternlint confere o código de saída real dos programas, inclusive em Go."""

import shutil

import pytest

from codar.evals.patternlint import run_session

GO = 'package main\n\nimport (\n\t"fmt"\n\t"os"\n)\n\nfunc main() {\n\tfmt.Println("uso: app COMANDO")\n\tos.Exit(2)\n}\n'


@pytest.mark.skipif(not shutil.which("go"), reason="Go ausente")
def test_go_preserva_codigo_de_saida_do_programa():
    # go run sairia com 1; o binário compilado sai com o 2 que o programa pediu.
    assert run_session("go", GO, "", ["uso:"], status=2) == ""
    assert "esperava 0" in run_session("go", GO, "", ["uso:"], status=0)


@pytest.mark.skipif(not shutil.which("go"), reason="Go ausente")
def test_go_que_nao_compila_e_falha_clara():
    assert run_session("go", "package main\nfunc main() { x }\n", "", []).startswith("não compilou")
