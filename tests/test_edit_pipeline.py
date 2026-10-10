import asyncio
import re
import threading

import pytest

from codar.editing import edit_units, propose_project, validate_change
from codar.engine.router import TranslateError
from codar.engine.stage2 import Cancelled, GenResult
from codar.workspace import EditStore


def test_edicao_de_dois_arquivos_usa_proposta_anterior_como_contexto(tmp_path, monkeypatch, router):
    monkeypatch.setenv("CODAR_HOME", str(tmp_path / "home"))
    (tmp_path / "codar.toml").write_text('[project]\nguidance=["Do not add unrelated behavior"]\n', encoding="utf-8", newline="")
    (tmp_path / "login.py").write_text('def login():\n    return False\n', encoding="utf-8", newline="")
    (tmp_path / "test_login.py").write_text('from login import login\ndef test_login():\n    assert login() is False\n', encoding="utf-8", newline="")
    answers = iter(['def login():\n    return True\n', 'from login import login\ndef test_login():\n    assert login() is True\n'])
    def generate(builder, **kwargs):
        router.stage2.prompts.append(builder(0))
        return GenResult(next(answers), 20, 100, 1, "stop")
    monkeypatch.setattr(router.stage2, "generate", generate)
    result = asyncio.run(propose_project(router, str(tmp_path), ["login.py", "test_login.py"], "corrija login e teste"))
    assert "return True" in router.stage2.prompts[-1]
    assert (tmp_path / "login.py").read_text().endswith("return False\n")
    store = EditStore(tmp_path)
    store.apply(result["id"])
    assert (tmp_path / "login.py").read_text().endswith("return True\n")
    assert (tmp_path / "test_login.py").read_text().endswith("is True\n")


def test_reparo_tem_limite_e_proposta_invalida_nao_aplica(tmp_path, monkeypatch, router):
    monkeypatch.setenv("CODAR_HOME", str(tmp_path / "home"))
    (tmp_path / "app.py").write_text("x=1\n", encoding="utf-8", newline="")
    router.stage2.answer = "def f(:\n"
    result = asyncio.run(propose_project(router, str(tmp_path), ["app.py"], "corrija"))
    assert len(router.stage2.prompts) == 2
    assert result["validation"][0]["status"] == "error"
    with pytest.raises(ValueError):
        EditStore(tmp_path).apply(result["id"])
    assert (tmp_path / "app.py").read_text() == "x=1\n"


def test_resposta_incompleta_e_cancelamento_nao_criam_mudancas(tmp_path, monkeypatch, router):
    monkeypatch.setenv("CODAR_HOME", str(tmp_path / "home"))
    (tmp_path / "a.py").write_text("x=1\n", encoding="utf-8", newline="")
    monkeypatch.setattr(router.stage2, "generate", lambda *a, **k: GenResult("x=", 10, 10, 1, "length"))
    with pytest.raises(TranslateError, match="incompleta"):
        asyncio.run(propose_project(router, str(tmp_path), ["a.py"], "corrija"))
    cancel = threading.Event(); cancel.set()
    with pytest.raises(Cancelled):
        asyncio.run(propose_project(router, str(tmp_path), ["a.py"], "corrija", cancel))
    assert (tmp_path / "a.py").read_text() == "x=1\n"


def test_divisao_preserva_funcoes_inteiras_decoradores_e_classes():
    text = '# cabeçalho\nimport os\n\n' + '\n'.join(f'@decorator\ndef f{i}():\n    return {i}\n' for i in range(5))
    units = edit_units(text, "a.py", 80)
    assert len(units) == 5 and all(text[a:b].startswith("@decorator") for a, b in units)
    text = 'class A:\n' + '\n'.join(f'    def f{i}(self):\n        return {i}\n' for i in range(5))
    assert len(edit_units(text, "a.py", 80)) == 5
    with pytest.raises(TranslateError):
        edit_units("def f():\n" + "    x=1\n" * 100, "a.py", 100)


def test_dart_nao_separa_assinatura_do_corpo():
    pytest.importorskip("tree_sitter_dart")
    text = 'class A {\n' + '\n'.join(f'  int f{i}() {{ return {i}; }}' for i in range(8)) + '\n}\n'
    units = edit_units(text, "a.dart", 60)
    assert len(units) == 8
    assert all(re.search(r"int f\d\(\) \{ return \d; \}", text[a:b]) for a, b in units)


def test_powershell_divide_funcao_sem_contar_chaves_em_strings():
    text = '\n'.join(f'function Get-F{i} {{\n    Write-Output "}} {{{i}"\n}}\n' for i in range(8))
    units = edit_units(text, "a.ps1", 70)
    assert len(units) == 8 and all(text[a:b].rstrip().endswith("}") for a, b in units)


def test_definicoes_iguais_em_classes_diferentes_nao_sao_duplicacao():
    text = "class A:\n    def f(self): pass\nclass B:\n    def f(self): pass\n"
    assert validate_change("", text, "a.py")["status"] == "ok"
    assert validate_change("", text + "def g(): pass\ndef g(): pass\n", "a.py")["status"] == "error"
