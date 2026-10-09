"""Regressões: editar substitui o alvo, respostas atrasadas não alteram outro trecho nem apagam código."""

import asyncio

import pytest

from codar.engine.postprocess import strip_context_echo
from codar.engine.router import Request, TranslateError
from codar.engine.stage2 import GenResult
from codar.studio.edits import EditTarget, hoist_imports, wants_edit


def test_edicao_recebe_selecao_e_contexto_sem_usar_snippet_do_banco(translate, router):
    router.stage2.answer = "def calcular(a, b):\n    return a + b\n"
    res = translate("criar uma calculadora", mode="edit", selected="def calcular(a, b):\n    pass",
                    before="# antes\n", after="\nprint(calcular(2, 3))")
    assert res.stage == "2:edit" and res.body.count("def calcular") == 1
    prompt = router.stage2.prompts[-1]
    assert "Selected code to replace" in prompt and "return the complete replacement" in prompt.lower()
    assert "# antes" in prompt and "print(calcular(2, 3))" in prompt


def test_edicao_incompleta_nao_e_cacheada_nem_reparada_cortando_linhas(translate, router, monkeypatch):
    answer = "x = 1\ndef f():\n    return ("
    monkeypatch.setattr(router.stage2, "generate", lambda *a, **kw: GenResult(answer, 10, 10, 1, "length"))
    res = translate("complete meu código", mode="edit", selected="x = 1\n")
    assert res.complete is False and "return (" in res.body
    assert res.notes and not router._cache


def test_edicao_nao_corta_selecao_grande(translate, router):
    with pytest.raises(TranslateError, match="trecho menor"):
        translate("corrija", mode="edit", selected="x" * 12001)
    assert not router.stage2.prompts
    with pytest.raises(TranslateError, match="IA local"):
        translate("corrija", mode="edit", selected="x = 1", stages=(0, 1))


def test_edicao_flutter_ativa_skill_pelo_codigo_existente(translate, router):
    router.stage2.answer = "Widget build(BuildContext context) => const Text('Olá');"
    translate("corrija o botão", "dart", mode="edit", selected="Widget build(BuildContext context) {}",
              before="import 'package:flutter/material.dart';")
    assert "check mounted before setState" in router.stage2.prompts[-1]


def test_protocolo_mantem_contexto_de_edicao():
    req = Request.from_params({"intent": "corrija", "context": {"before": "a" * 7000, "after": "b" * 4000,
                                                               "selected": "x" * 9000}, "options": {"mode": "edit"}})
    assert len(req.before) == 6000 and len(req.after) == 3000 and len(req.selected) == 9000


def test_cache_nao_confunde_caixa_ou_contextos_deterministicos(translate):
    assert '"Ana"' in translate("imprimir 'Ana'", stages=(0, 1)).code
    assert '"ana"' in translate("imprimir 'ana'", stages=(0, 1)).code
    assert not translate("x igual a 1", "go", before="x := 2", stages=(0,)).cached
    assert not translate("x igual a 1", "go", before="y := 2", stages=(0,)).cached


def test_eco_remove_bloco_contiguo_mas_preserva_repeticao_isolada():
    assert strip_context_echo("x = 1\ny = 2\nprint(x + y)", "x = 1\ny = 2\n") == "print(x + y)"
    assert strip_context_echo("print(x)\nx = 2", "print(x)\ny = 1") == "print(x)\nx = 2"
    assert strip_context_echo("print(x)", "print(x)") == "print(x)"
    assert strip_context_echo("novo()\nfim()\nsair()", after="\nfim()\nsair()") == "novo()"


def test_selecao_parcial_e_imports_sem_duplicacao():
    text = "def f():\n    valor = 1\n    return valor\n"
    target = EditTarget.capture(text, "edit", (1, 12), ((1, 12), (1, 13)))
    result, _, _ = target.apply("    2", ["import os", "import os"], "python", "    ")
    assert result == "import os\n\ndef f():\n    valor = 2\n    return valor\n"
    assert hoist_imports("library app;\n\nvoid main() {}", ["import 'dart:io';"], "dart")[0].startswith(
        "library app;\nimport 'dart:io';")
    assert hoist_imports('"""Descrição do módulo."""\nfrom __future__ import annotations\nx = 1',
                        ["import os"], "python")[0].startswith(
        '"""Descrição do módulo."""\nfrom __future__ import annotations\nimport os')


def test_imports_powershell_respeitam_param_e_cmdletbinding():
    text = "[CmdletBinding()]\nparam([string] $Name = '(João)')\nWrite-Output $Name"
    result, _ = hoist_imports(text, ["Import-Module Microsoft.PowerShell.Utility"], "powershell")
    assert result.startswith("[CmdletBinding()]\nparam([string] $Name = '(João)')\nImport-Module")


@pytest.mark.parametrize("intent,edit", [("corrija meu código", True), ("por favor, refatore", True),
                                        ("complete a função", True), ("crie uma classe", False),
                                        ("imprimir total", False)])
def test_pedidos_explicitos_de_edicao(intent, edit):
    assert wants_edit(intent) is edit


def test_studio_substitui_selecao_e_desfaz_corpo_e_imports_juntos(tmp_path, monkeypatch):
    pytest.importorskip("textual")
    from textual.widgets import Input
    from textual.widgets.text_area import Selection
    from test_studio_navegacao import _abrir, _studio

    text = "def f():\n    valor = 1\n    return valor\n"
    app = _studio(tmp_path, monkeypatch, {"a.py": text})
    calls = []
    app.translate_worker = lambda *args: calls.append(args)

    async def scenario():
        async with app.run_test(size=(150, 42)) as pilot:
            ed = await _abrir(app, pilot, tmp_path / "a.py")
            ed.selection = Selection((1, 0), (2, 0))
            field = app.query_one("#intent", Input)
            field.value = "corrija o valor"
            await app._intent(Input.Submitted(field, field.value))
            intent, lang, mode, path, before, indent, unit, target, editor_id = calls[-1]
            assert mode == "edit" and target.selected == "    valor = 1\n"
            ed.move_cursor((0, 0))  # mover o cursor não redireciona a resposta
            res = {"body": "    valor = 2", "code": "import os\n\n    valor = 2", "imports": ["import os"],
                   "stage": "2:edit", "source": "teste", "lang": "python", "timings": {}, "findings": []}
            app._apply(res, target, editor_id, indent)
            assert ed.text == "import os\n\ndef f():\n    valor = 2\n    return valor\n"
            ed.undo()
            assert ed.text == text
            ed.selection = Selection((0, 0), (0, 0))
            field.value = "complete meu código"
            await app._intent(Input.Submitted(field, field.value))
            assert calls[-1][-2].selected == text

    asyncio.run(scenario())


def test_studio_preserva_edicao_nova_e_resposta_incompleta(tmp_path, monkeypatch):
    pytest.importorskip("textual")
    from test_studio_navegacao import _abrir, _studio

    app = _studio(tmp_path, monkeypatch, {"a.ps1": "$x = 1\n", "b.dart": "void main() {}\n"})
    calls = []
    app.translate_worker = lambda *args: calls.append(args)

    async def scenario():
        async with app.run_test(size=(150, 42)) as pilot:
            ed = await _abrir(app, pilot, tmp_path / "a.ps1")
            app.request("corrija", "edit", ed)
            target, editor_id = calls[-1][-2:]
            other = await _abrir(app, pilot, tmp_path / "b.dart")
            res = {"body": "$x = 2", "code": "$x = 2", "imports": [], "stage": "2:edit", "source": "teste",
                   "lang": "powershell", "timings": {}, "findings": [], "complete": False}
            app._apply(res, target, editor_id, "")
            assert ed.text == "$x = 1\n" and other.text == "void main() {}\n"
            res["complete"] = True
            ed.insert("# modificado\n", (0, 0))
            app._apply(res, target, editor_id, "")
            assert ed.text == "# modificado\n$x = 1\n" and other.text == "void main() {}\n"
            tabs = app.query_one("#editors")
            await tabs.remove_pane("ed-1")
            app._apply(res, target, editor_id, "")  # aba fechada não muda a atual
            assert other.text == "void main() {}\n"

    asyncio.run(scenario())
