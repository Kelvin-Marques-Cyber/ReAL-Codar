"""Cenários mínimos de regressão do roteiro (docs/QUALIDADE.md): a tabela aponta para testes que existem."""

import ast
import re
from pathlib import Path

import pytest

from codar.client import RpcError
from codar.engine.local import LocalClient

RAIZ = Path(__file__).resolve().parents[1]


def _referencias():
    texto = (RAIZ / "docs" / "QUALIDADE.md").read_text(encoding="utf-8")
    return sorted(set(re.findall(r"`(tests/[\w/]+\.py)::(\w+)`", texto)))


def test_tabela_de_cenarios_cobre_os_oito_cenarios_do_roteiro():
    texto = (RAIZ / "docs" / "QUALIDADE.md").read_text(encoding="utf-8")
    linhas = [linha for linha in texto.split("\n") if linha.startswith("| ") and "tests/" in linha]
    assert len(linhas) == 8 and len(_referencias()) >= 8


@pytest.mark.parametrize("arquivo,nome", _referencias())
def test_cenario_documentado_aponta_para_teste_existente(arquivo, nome):
    modulo = ast.parse((RAIZ / arquivo).read_text(encoding="utf-8"))
    assert nome in {n.name for n in modulo.body if isinstance(n, ast.FunctionDef)}, f"{arquivo}::{nome}"


def test_recursos_deterministicos_funcionam_com_a_ia_desativada(tmp_path, monkeypatch):
    """Compilador, banco, imports, consultas e auditoria não dependem do modelo; geração livre falha com clareza."""
    monkeypatch.setenv("CODAR_HOME", str(tmp_path / "home"))
    with LocalClient(with_model=False, db=str(tmp_path / "padroes.db")) as client:
        assert client.translate("x é igual a 10", "python")["code"] == "x = 10"
        assert client.translate("validar cpf", "python")["stage"] == "1"
        imports = client.translate("importe numpy", "python")
        assert imports["imports"] == ["import numpy as np"] and not imports["body"].strip()  # alias convencional
        assert client.translate("o que é uma lista", "python")["action"] == "query"
        assert client.audit("import os\nos.system('rm -rf ' + pasta)\n", "python")["findings"]
        with pytest.raises(RpcError) as erro:
            client.translate("crie um jogo de xadrez com interface gráfica", "python")
        assert "Estágio 2" in erro.value.message
