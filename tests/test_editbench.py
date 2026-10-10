import pytest

from codar.evals.editbench import evaluate, tasks


@pytest.mark.parametrize("task", tasks(), ids=lambda task: task["id"])
def test_gabarito_passa_e_bug_original_falha(task):
    assert evaluate(task, task["reference"])["ok"]
    assert not evaluate(task, task["selected"])["ok"]


def test_benchmark_recusa_corte_e_codigo_duplicado():
    task = tasks()[0]
    assert evaluate(task, task["reference"], complete=False)["reason"] == "incomplete"
    assert evaluate(task, task["reference"] * 2)["reason"] == "validation"


def test_verificacao_funciona_sem_resource_do_unix(monkeypatch):
    from codar.evals import runner

    block = '''import builtins
original_import = builtins.__import__
def without_resource(name, *args, **kwargs):
    if name == 'resource':
        raise ImportError('indisponível no Windows')
    return original_import(name, *args, **kwargs)
builtins.__import__ = without_resource
'''
    monkeypatch.setattr(runner, "_SANDBOX", block + runner._SANDBOX)
    assert runner.check("x = 42", "assert x == 42")[0]
