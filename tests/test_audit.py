"""Auditoria estática: regras que já pegaram bugs reais."""

import pytest

from codar import config
from codar.audit import Auditor
from codar.plugin_loader import discover


@pytest.fixture(scope="module")
def auditor():
    cfg = config.load()
    return Auditor(cfg["audit"], discover(cfg).rules)


def ids(auditor, code, lang):
    return {f.id for f in auditor.audit(code, lang)}


@pytest.mark.parametrize("code", [
    "sort -u nomes.txt > nomes.txt",          # gerado pela IA ao pedir "remover linhas duplicadas do arquivo"
    'grep -v foo "$arq" > "$arq"',
    "cat dados.csv | sort | uniq > dados.csv",
])
def test_bash_ler_e_gravar_o_mesmo_arquivo(auditor, code):
    assert "SH012" in ids(auditor, code + "\n", "bash")


@pytest.mark.parametrize("code", [
    "sort -u -o nomes.txt nomes.txt",
    'awk 1 "$arq" > "$arq.tmp" && mv "$arq.tmp" "$arq"',
    "# sort f.txt > f.txt",
])
def test_bash_formas_seguras_nao_disparam(auditor, code):
    assert "SH012" not in ids(auditor, code + "\n", "bash")


def test_python_segredo_e_sql_concatenado(auditor):
    code = 'senha = "admin123"\ncur.execute("SELECT * FROM users WHERE id = " + user_id)\n'
    assert {"PY017", "PY003"} <= ids(auditor, code, "python")
